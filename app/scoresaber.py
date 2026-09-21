import asyncio
import logging

import httpx

log = logging.getLogger("bsplay.scoresaber")

RETRY_STATUS = {429, 500, 502, 503, 504}


class ScoreSaberClient:
    def __init__(self, settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.scoresaber_api_base,
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict) -> dict:
        last_error = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in RETRY_STATUS:
                    last_error = f"HTTP {resp.status_code}"
                else:
                    resp.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = str(exc)
            wait = min(2 ** attempt, 30)
            log.warning("retry %s %s (attempt %s) in %ss: %s", path, params, attempt + 1, wait, last_error)
            await asyncio.sleep(wait)
        raise RuntimeError(f"ScoreSaber 요청 실패 ({path}): {last_error}")

    async def fetch_leaderboards(
        self,
        *,
        ranked: bool = False,
        qualified: bool = False,
        min_star: float = None,
        max_star: float = None,
        category: int = None,
        sort: int = None,
        progress=None,
    ) -> list:
        params = {}
        if ranked:
            params["ranked"] = "true"
        if qualified:
            params["qualified"] = "true"
        if min_star is not None and min_star >= 0:
            params["minStar"] = str(min_star)
        if max_star is not None and max_star >= 0:
            params["maxStar"] = str(max_star)
        if category is not None:
            params["category"] = str(category)
        if sort is not None:
            params["sort"] = str(sort)

        items = []
        page = 1
        expected_pages = None
        while True:
            params["page"] = str(page)
            data = await self._get("/leaderboards", params)
            batch = data.get("leaderboards") or []
            if not batch:
                break
            items.extend(batch)
            meta = data.get("metadata") or {}
            total = meta.get("total")
            per_page = meta.get("itemsPerPage") or len(batch)
            if expected_pages is None and total:
                expected_pages = max(1, -(-int(total) // int(per_page)))
            if progress:
                progress(expected_pages, page, len(items))
            if expected_pages is not None and page >= expected_pages:
                break
            page += 1
            await asyncio.sleep(self.settings.request_delay)
        return items

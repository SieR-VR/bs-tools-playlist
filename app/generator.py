import asyncio
import json
import logging
import os

from . import cover

log = logging.getLogger("bsplay.generator")

DIFF_NAMES = {1: "Easy", 3: "Normal", 5: "Hard", 7: "Expert", 9: "ExpertPlus"}
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def _song_entry(lb: dict) -> dict:
    diff = lb.get("difficulty") or {}
    raw = diff.get("difficultyRaw") or ""
    if raw.count("_") >= 2:
        name = raw.split("_")[1]
    else:
        name = DIFF_NAMES.get(diff.get("difficulty"), "Expert")
    song_hash = (lb.get("songHash") or "").upper()
    return {
        "songName": lb.get("songName") or "",
        "levelAuthorName": lb.get("levelAuthorName") or "",
        "hash": song_hash,
        "levelid": f"custom_level_{song_hash}",
        "difficulties": [{"characteristic": "Standard", "name": name}],
    }


def _stars(lb: dict) -> float:
    try:
        return float(lb.get("stars") or 0)
    except (TypeError, ValueError):
        return 0.0


def _dedup_by_id(leaderboards: list) -> list:
    seen = {}
    for lb in leaderboards:
        lid = lb.get("id")
        if lid is not None and lid not in seen:
            seen[lid] = lb
    return list(seen.values())


def _sort_key(lb: dict) -> tuple:
    return (_stars(lb), (lb.get("songName") or "").lower(), lb.get("id") or 0)


async def _publish_playlist(
    *,
    uploader,
    filename: str,
    title: str,
    entries: list,
    template_path: str,
    cover_text: str,
    font_path: str,
) -> dict:
    image_uri = await asyncio.to_thread(cover.cover_data_uri, template_path, cover_text, font_path)
    payload = {
        "customData": {"syncURL": uploader.url(filename)},
        "playlistTitle": title,
        "playlistAuthor": "",
        "songs": entries,
        "image": image_uri,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await uploader.upload(filename, data)
    return {"title": title, "songs": len(entries), "bytes": len(data), "url": uploader.url(filename)}


async def run_generation(settings, uploader, progress=None) -> dict:
    font_path = await asyncio.to_thread(cover.ensure_font, ASSETS_DIR)
    templates = os.path.join(ASSETS_DIR, "templates")
    result = {"playlists": [], "skipped": []}

    from .scoresaber import ScoreSaberClient

    client = ScoreSaberClient(settings)
    try:
        for star in range(0, settings.max_star + 1):
            label = f"ranked ★{star}"

            def on_page(expected, page, collected, label=label):
                if progress:
                    progress(f"{label}: 페이지 {page}/{expected or '?'} (수집 {collected})")

            leaderboards = await client.fetch_leaderboards(
                ranked=True,
                min_star=star - 1,
                max_star=star + 1,
                category=1,
                sort=0,
                progress=on_page,
            )
            buckets = [lb for lb in _dedup_by_id(leaderboards) if int(_stars(lb)) == star]
            if not buckets:
                result["skipped"].append({"title": f"ranked_star_{star:02d}", "reason": "해당 별 구간에 랭크맵 없음"})
                log.info("skip star %s (no maps)", star)
                continue
            buckets.sort(key=_sort_key, reverse=settings.sort_desc)
            entries = [_song_entry(lb) for lb in buckets]
            if progress:
                progress(f"{label}: 정렬·커버·업로드 중 ({len(entries)}맵)")
            template = os.path.join(templates, f"s{min(star, 14):02d}.png")
            item = await _publish_playlist(
                uploader=uploader,
                filename=f"ranked_star_{star:02d}.bplist",
                title=f"ranked_star_{star:02d}",
                entries=entries,
                template_path=template,
                cover_text=str(star),
                font_path=font_path,
            )
            result["playlists"].append(item)
            log.info("uploaded %s (%s songs)", item["title"], item["songs"])

        label = "qualified"

        def on_page_q(expected, page, collected, label=label):
            if progress:
                progress(f"{label}: 페이지 {page}/{expected or '?'} (수집 {collected})")

        qualified = _dedup_by_id(
            await client.fetch_leaderboards(
                qualified=True,
                category=4,
                sort=1,
                progress=on_page_q,
            )
        )
        if not qualified:
            result["skipped"].append({"title": "ranked_star_qualified", "reason": "현재 qualified 맵 없음 (ScoreSaber 상태)"})
            log.info("skip qualified (no maps)")
        else:
            qualified.sort(key=_sort_key, reverse=settings.sort_desc)
            entries = [_song_entry(lb) for lb in qualified]
            if progress:
                progress(f"qualified: 정렬·커버·업로드 중 ({len(entries)}맵)")
            item = await _publish_playlist(
                uploader=uploader,
                filename="ranked_star_qualified.bplist",
                title="ranked_star_qualified",
                entries=entries,
                template_path=os.path.join(templates, "qualified.png"),
                cover_text="Q",
                font_path=font_path,
            )
            result["playlists"].append(item)
            log.info("uploaded qualified (%s songs)", item["songs"])
    finally:
        await client.aclose()
    return result

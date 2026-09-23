import argparse
import asyncio
import json
import logging
import os

import httpx

from .config import Settings
from .generator import _song_entry, _sort_key
from .run import R2Uploader
from .scoresaber import ScoreSaberClient

log = logging.getLogger("bsplay.expand")

STANDARD_MODE = "SoloStandard"


async def load_input(source: str) -> dict:
    if source.lower().startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(source)
            resp.raise_for_status()
            return resp.json()
    with open(source, encoding="utf-8") as f:
        return json.load(f)


def collect_hashes(playlist: dict) -> list:
    hashes = []
    seen = set()
    for song in playlist.get("songs") or []:
        h = (song.get("hash") or "").upper()
        if not h:
            levelid = song.get("levelid") or ""
            if levelid.startswith("custom_level_"):
                h = levelid[len("custom_level_"):].upper()
        if h and h not in seen:
            seen.add(h)
            hashes.append(h)
    return hashes


async def fetch_ranked_difficulties(client: ScoreSaberClient, hashes: list, delay: float, progress=None):
    boards = {}
    missing = []
    unranked_diffs = 0
    for idx, song_hash in enumerate(hashes, 1):
        entries = []
        try:
            await asyncio.sleep(delay)
            diffs = await client.get_difficulties(song_hash) or []
            for diff in diffs:
                if diff.get("gameMode") != STANDARD_MODE:
                    continue
                await asyncio.sleep(delay)
                try:
                    info = await client.get_leaderboard_info_by_id(diff.get("leaderboardId"))
                except Exception as exc:
                    log.warning("리더보드 조회 실패 %s/%s: %s", song_hash, diff.get("difficultyRaw"), exc)
                    continue
                if info.get("ranked") and (info.get("stars") or 0) > 0:
                    entries.append(info)
                else:
                    unranked_diffs += 1
        except Exception as exc:
            log.warning("난이도 목록 조회 실패 %s: %s", song_hash, exc)
        boards[song_hash] = entries
        if not entries:
            missing.append(song_hash)
        if progress:
            progress(idx, len(hashes), song_hash, len(entries))
    return boards, missing, unranked_diffs


async def expand(settings: Settings, source: str, out_path: str, title: str = None, upload: bool = False) -> dict:
    playlist = await load_input(source)
    in_title = playlist.get("playlistTitle") or "playlist"
    hashes = collect_hashes(playlist)
    if not hashes:
        raise SystemExit("입력 플레이리스트에 곡(hash)이 없습니다.")

    client = ScoreSaberClient(settings)
    try:
        boards, missing, unranked_diffs = await fetch_ranked_difficulties(
            client,
            hashes,
            settings.request_delay,
            progress=lambda i, n, h, c: print(f"[{i}/{n}] {h[:8]}… 랭크 난이도 {c}개", flush=True),
        )
    finally:
        await client.aclose()

    leaderboards = [lb for h in hashes for lb in boards.get(h) or []]
    leaderboards.sort(key=_sort_key, reverse=settings.sort_desc)
    songs = [_song_entry(lb) for lb in leaderboards]
    if not songs:
        raise SystemExit("확장 가능한 랭크 난이도가 없습니다 (모든 곡이 랭크 상태가 아님).")

    out_title = title or f"{in_title}_alldiff"
    custom_data = {k: v for k, v in (playlist.get("customData") or {}).items() if k != "syncURL"}
    if upload:
        if not settings.r2_ready:
            raise SystemExit("R2 설정이 불충분합니다. 누락: " + ", ".join(settings.missing_r2_keys))
        uploader = R2Uploader(settings)
        filename = os.path.basename(out_path)
        custom_data["syncURL"] = uploader.url(filename)
    new_playlist = {
        "customData": custom_data,
        "playlistTitle": out_title,
        "playlistAuthor": playlist.get("playlistAuthor") or "",
        "songs": songs,
        "image": playlist.get("image") or "",
    }
    data = json.dumps(new_playlist, ensure_ascii=False).encode("utf-8")
    await asyncio.to_thread(lambda: open(out_path, "wb").write(data))
    if upload:
        await uploader.upload(filename, data)
    return {
        "input_title": in_title,
        "output_title": out_title,
        "songs_in": len(playlist.get("songs") or []),
        "unique_hashes": len(hashes),
        "expanded_songs": len(songs),
        "hashes_without_ranked": len(missing),
        "unranked_difficulties_skipped": unranked_diffs,
        "output_path": out_path,
        "uploaded_url": (uploader.url(filename) if upload else None),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="플레이리스트의 곡을 모든 랭크 난이도로 확장해 별 순으로 정렬")
    parser.add_argument("source", help="입력 .bplist 파일 경로 또는 URL")
    parser.add_argument("-o", "--out", default=None, help="출력 파일 경로 (기본: <입력>_alldiff.bplist)")
    parser.add_argument("--title", default=None, help="출력 플레이리스트 제목 (기본: <입력 제목>_alldiff)")
    parser.add_argument("--upload", action="store_true", help="결과를 R2에도 업로드")
    parser.add_argument("--delay", type=float, default=None, help="API 요청 간격(초) 오버라이드")
    parser.add_argument("--desc", action="store_true", help="별 내림차순으로 정렬")
    args = parser.parse_args()

    settings = Settings()
    if args.delay is not None:
        settings.request_delay = args.delay
    if args.desc:
        settings.sort_desc = True

    source = args.source
    stem = os.path.splitext(os.path.basename(source.rstrip("/").split("?")[0]))[0] or "playlist"
    out_path = args.out or os.path.join(os.getcwd(), f"{stem}_alldiff.bplist")

    result = asyncio.run(expand(settings, source, out_path, title=args.title, upload=args.upload))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

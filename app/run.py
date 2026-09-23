import asyncio
import json
import logging
import os

from . import r2
from .config import Settings
from .generator import run_generation


class R2Uploader:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.client = r2.make_client(settings)

    def url(self, filename: str) -> str:
        return r2.public_url(self.settings, filename)

    async def upload(self, filename: str, data: bytes) -> None:
        await asyncio.to_thread(
            r2.upload_bytes,
            self.client,
            self.settings.r2_bucket,
            r2.object_key(self.settings, filename),
            data,
        )


class LocalUploader:
    def __init__(self, out_dir: str) -> None:
        self.out_dir = os.path.abspath(out_dir)
        os.makedirs(self.out_dir, exist_ok=True)

    def url(self, filename: str) -> str:
        return f"file://{os.path.join(self.out_dir, filename).replace(os.sep, '/')}"

    async def upload(self, filename: str, data: bytes) -> None:
        path = os.path.join(self.out_dir, filename)
        await asyncio.to_thread(lambda: open(path, "wb").write(data))


def build_uploader(settings: Settings, out_dir: str = None):
    if out_dir:
        return LocalUploader(out_dir)
    if not settings.r2_ready:
        raise SystemExit(
            "R2 설정이 불충분합니다. 누락된 환경변수: " + ", ".join(settings.missing_r2_keys)
        )
    return R2Uploader(settings)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    import argparse

    parser = argparse.ArgumentParser(description="랭크 플레이리스트 생성 (기본: R2 업로드)")
    parser.add_argument("--out", default=None, help="지정하면 R2 대신 로컬 폴더에 저장")
    parser.add_argument("--max-star", type=int, default=None, help="최대 별 구간 오버라이드")
    parser.add_argument("--delay", type=float, default=None, help="요청 간격(초) 오버라이드")
    args = parser.parse_args()

    settings = Settings()
    if args.max_star is not None:
        settings.max_star = args.max_star
    if args.delay is not None:
        settings.request_delay = args.delay

    uploader = build_uploader(settings, args.out)

    async def run():
        def progress(step):
            print(step, flush=True)

        result = await run_generation(settings, uploader, progress=progress)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    asyncio.run(run())


if __name__ == "__main__":
    main()

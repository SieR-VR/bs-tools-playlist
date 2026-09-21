import argparse
import asyncio
import json
import logging
import os

from .config import Settings
from .generator import run_generation


class LocalUploader:
    def __init__(self, out_dir: str) -> None:
        self.out_dir = os.path.abspath(out_dir)
        os.makedirs(self.out_dir, exist_ok=True)

    def url(self, filename: str) -> str:
        return f"file://{os.path.join(self.out_dir, filename).replace(os.sep, '/')}"

    async def upload(self, filename: str, data: bytes) -> None:
        path = os.path.join(self.out_dir, filename)
        await asyncio.to_thread(lambda: open(path, "wb").write(data))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="로컬 파일 출력으로 플레이리스트 생성 (R2 불필요)")
    parser.add_argument("--out", default="out", help="출력 폴더 (기본: out)")
    parser.add_argument("--max-star", type=int, default=None, help="최대 별 구간 오버라이드")
    parser.add_argument("--delay", type=float, default=None, help="요청 간격(초) 오버라이드")
    args = parser.parse_args()

    settings = Settings()
    if args.max_star is not None:
        settings.max_star = args.max_star
    if args.delay is not None:
        settings.request_delay = args.delay

    async def run():
        def progress(step):
            print(step, flush=True)
        result = await run_generation(settings, LocalUploader(args.out), progress=progress)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    asyncio.run(run())


if __name__ == "__main__":
    main()

import os

from . import __version__

_TRUTHY = ("1", "true", "yes", "on")


def _bool(name: str, default: bool) -> bool:
    return str(os.getenv(name, default)).strip().lower() in _TRUTHY


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        self.generate_token = os.getenv("GENERATE_TOKEN", "")
        self.run_on_startup = _bool("RUN_ON_STARTUP", True)

        self.r2_account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
        self.r2_access_key_id = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        self.r2_secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        self.r2_bucket = os.getenv("R2_BUCKET", "").strip()
        self.r2_public_base_url = os.getenv("R2_PUBLIC_BASE_URL", "").strip().rstrip("/")
        prefix = os.getenv("R2_KEY_PREFIX", "playlists/").strip().strip("/")
        self.r2_key_prefix = f"{prefix}/" if prefix else ""

        self.scoresaber_api_base = os.getenv("SCORESABER_API_BASE", "https://scoresaber.com/api").strip().rstrip("/")
        self.user_agent = os.getenv("USER_AGENT", f"bs-playlist-generator/{__version__}")
        self.max_star = _int("MAX_STAR", 16)
        self.sort_desc = _bool("SORT_DESC", False)
        self.request_delay = _float("REQUEST_DELAY", 0.15)
        self.max_retries = _int("MAX_RETRIES", 6)
        self.request_timeout = _float("REQUEST_TIMEOUT", 30.0)

    @property
    def r2_ready(self) -> bool:
        return all(
            (
                self.r2_account_id,
                self.r2_access_key_id,
                self.r2_secret_access_key,
                self.r2_bucket,
                self.r2_public_base_url,
            )
        )

    @property
    def missing_r2_keys(self) -> list:
        names = {
            "R2_ACCOUNT_ID": self.r2_account_id,
            "R2_ACCESS_KEY_ID": self.r2_access_key_id,
            "R2_SECRET_ACCESS_KEY": self.r2_secret_access_key,
            "R2_BUCKET": self.r2_bucket,
            "R2_PUBLIC_BASE_URL": self.r2_public_base_url,
        }
        return [k for k, v in names.items() if not v]

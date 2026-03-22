"""Application configuration scaffolding.

Usage:
    from app.core.config import get_settings

    settings = get_settings()
"""

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILES = (REPO_ROOT / ".env", BACKEND_ROOT / ".env")
_ENV_LOADED = False


def _load_environment() -> None:
    """Load environment variables from supported .env files once."""
    global _ENV_LOADED

    if _ENV_LOADED:
        return

    for env_file in _ENV_FILES:
        if env_file.exists():
            load_dotenv(env_file, override=False)

    _ENV_LOADED = True


def _read_bool_env(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int_env(name: str, default: int) -> int:
    """Read an integer environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _read_optional_env(name: str) -> Optional[str]:
    """Read an optional environment variable."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value


def _read_path_env(name: str, default_relative_path: str) -> Path:
    """Read a filesystem path and resolve relative paths from the repo root."""
    value = os.getenv(name, default_relative_path)
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


@dataclass(frozen=True)
class Settings:
    """Static application settings."""

    app_name: str
    app_version: str
    app_env: str
    debug: bool
    api_prefix: str
    host: str
    port: int
    sqlite_url: str
    duckdb_path: Path
    cache_dir: Path
    data_dir: Path
    openai_api_key: Optional[str]
    openai_model: str
    enable_akshare: bool
    enable_baostock: bool
    enable_cninfo: bool
    enable_eastmoney: bool


@lru_cache
def get_settings() -> Settings:
    """Load application settings from environment variables."""
    _load_environment()

    return Settings(
        app_name=os.getenv("APP_NAME", "A-Share Research Assistant API"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        app_env=os.getenv("APP_ENV", "development"),
        debug=_read_bool_env("APP_DEBUG", default=False),
        api_prefix=os.getenv("API_PREFIX", ""),
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=_read_int_env("APP_PORT", default=8000),
        sqlite_url=os.getenv("SQLITE_URL", "sqlite:///./app.db"),
        duckdb_path=_read_path_env("DUCKDB_PATH", "data/market.duckdb"),
        cache_dir=_read_path_env("CACHE_DIR", "cache"),
        data_dir=_read_path_env("DATA_DIR", "data"),
        openai_api_key=_read_optional_env("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        enable_akshare=_read_bool_env("ENABLE_AKSHARE", default=True),
        enable_baostock=_read_bool_env("ENABLE_BAOSTOCK", default=True),
        enable_cninfo=_read_bool_env("ENABLE_CNINFO", default=True),
        enable_eastmoney=_read_bool_env("ENABLE_EASTMONEY", default=True),
    )

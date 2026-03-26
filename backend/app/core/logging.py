"""应用日志初始化。"""

from __future__ import annotations

from logging.handlers import RotatingFileHandler
import logging
from pathlib import Path

from app.core.config import Settings

_LOGGING_CONFIGURED = False


def configure_logging(settings: Settings) -> Path:
    """初始化控制台与文件日志。"""
    global _LOGGING_CONFIGURED

    log_dir = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / settings.log_file_name

    if _LOGGING_CONFIGURED:
        return log_file_path

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(_resolve_log_level(settings.log_level))
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "日志系统已初始化。console_level=%s file=%s",
        settings.log_level.upper(),
        log_file_path,
    )
    _LOGGING_CONFIGURED = True
    return log_file_path


def _resolve_log_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)

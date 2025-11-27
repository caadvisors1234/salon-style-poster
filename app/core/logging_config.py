"""
アプリケーション共通のロギング設定
"""
import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings

# ログ出力ディレクトリ
LOG_DIR = Path(settings.LOG_DIR)


def setup_logging(service_name: str = "app", level: str | int | None = None) -> None:
    """
    ロギング設定を初期化する

    Args:
        service_name: ログファイル名のプレフィックス（例: "web", "worker"）
        level: 任意のログレベル。未指定の場合は設定値から決定。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_level_value: str | int = level or settings.LOG_LEVEL or ("DEBUG" if settings.DEBUG else "INFO")
    if isinstance(log_level_value, str):
        log_level_value = logging._nameToLevel.get(log_level_value.upper(), logging.INFO)
    log_file = LOG_DIR / f"{service_name}.log"

    log_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": log_level_value,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "level": log_level_value,
                "filename": str(log_file),
                "maxBytes": settings.LOG_MAX_BYTES,
                "backupCount": settings.LOG_BACKUP_COUNT,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            # ルートロガー
            "": {
                "handlers": ["console", "file"],
                "level": log_level_value,
            },
            # Uvicorn系ロガー
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": log_level_value,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console", "file"],
                "level": log_level_value,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": log_level_value,
                "propagate": False,
            },
            # Celeryロガー
            "celery": {
                "handlers": ["console", "file"],
                "level": log_level_value,
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(log_config)

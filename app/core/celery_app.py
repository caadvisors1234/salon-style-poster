"""
Celeryアプリケーション設定
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Celeryアプリケーション初期化
celery_app = Celery(
    "salon_board_poster",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1時間タイムアウト
    task_soft_time_limit=3300,  # 55分ソフトタイムアウト
    worker_prefetch_multiplier=1,  # 一度に1タスクのみ取得
    worker_max_tasks_per_child=10,  # ワーカープロセス再起動（メモリリーク対策）
    worker_hijack_root_logger=False,  # 既存ロガー設定を維持
)

# タスク自動検出
celery_app.autodiscover_tasks(["app.services"])

# 定期実行タスクのスケジュール
celery_app.conf.beat_schedule = {
    "cleanup-screenshots-daily": {
        "task": "cleanup_screenshots",
        "schedule": crontab(hour=3, minute=30),
    }
}

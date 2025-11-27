"""
Celeryワーカーのエントリーポイント
"""
from app.core.celery_app import celery_app
from app.core.logging_config import setup_logging

# タスクをインポート（自動検出を確実にするため）
from app.services import tasks

# ワーカー起動前にロギング設定を適用
setup_logging("worker")

if __name__ == "__main__":
    celery_app.start()

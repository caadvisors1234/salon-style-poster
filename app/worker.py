"""
Celeryワーカーのエントリーポイント
"""
from app.core.celery_app import celery_app

# タスクをインポート（自動検出を確実にするため）
from app.services import tasks

if __name__ == "__main__":
    celery_app.start()

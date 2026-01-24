"""
アプリケーション設定
環境変数からの設定読み込み
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """アプリケーション設定クラス"""

    # アプリケーション基本情報
    APP_NAME: str = "SALON BOARD Style Poster"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    USE_HEADFUL_MODE: bool = True  # ヘッドフルモード（画面あり）を使用するか

    # データベース設定
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        """データベース接続URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis設定
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def CELERY_BROKER_URL(self) -> str:
        """Celeryブローカー URL"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Celery結果バックエンド URL"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # JWT設定
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # 暗号化設定
    ENCRYPTION_KEY: str

    # CORS設定
    BACKEND_CORS_ORIGINS: List[str] = []

    # ログ設定
    LOG_DIR: str = "logs"
    LOG_LEVEL: str | None = None  # 明示指定がない場合は DEBUG フラグに従う
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5

    # スクリーンショット保全ポリシー
    SCREENSHOT_DIR: str = "app/static/screenshots"
    SCREENSHOT_RETENTION_DAYS: int = 30
    SCREENSHOT_DIR_MAX_BYTES: int = 524_288_000

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# グローバル設定インスタンス
settings = Settings()

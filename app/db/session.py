"""
データベースセッション管理
SQLAlchemy Engineとセッションの作成
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# SQLAlchemy Engineの作成
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 接続の有効性を事前確認
    pool_size=5,         # 接続プールサイズ
    max_overflow=10,     # 最大オーバーフロー接続数
    echo=settings.DEBUG  # SQLログ出力（デバッグモード時のみ）
)

# セッションローカルの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ベースクラス
Base = declarative_base()


def get_db():
    """
    データベースセッション取得（依存関数）
    FastAPIの依存性注入で使用

    Yields:
        Session: データベースセッション
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

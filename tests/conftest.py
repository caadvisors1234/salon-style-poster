import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.core.config import settings

# --- テスト用データベース設定 ---
# テストではSQLiteのインメモリデータベースを使用
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}, # SQLiteで必要
    poolclass=StaticPool, # 各テストで同じ接続を使い回す
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- テスト用フィクスチャ ---

@pytest.fixture(scope="function")
def db_session():
    """
    テストごとにクリーンなデータベースセッションとテーブルを提供するフィクスチャ
    """
    # テスト前にテーブルを全て作成
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # テスト後にテーブルを全て削除
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClientを提供するフィクスチャ
    依存性をテスト用DBセッションにオーバーライド
    """

    def override_get_db():
        """テスト用のDBセッションを返す依存関数"""
        try:
            yield db_session
        finally:
            pass # セッションクローズはdb_sessionフィクスチャで行う

    # アプリケーションのget_db依存性をオーバーライド
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    # テスト終了後にオーバーライドを元に戻す
    app.dependency_overrides.clear()

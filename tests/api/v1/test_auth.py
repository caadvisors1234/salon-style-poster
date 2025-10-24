from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.crud.user import create_user
from app.schemas.user import UserCreate

def test_login_success(client: TestClient, db_session: Session):
    """正常なログインのテスト"""
    # テスト用ユーザー作成
    email = "test@example.com"
    password = "password123"
    user_in = UserCreate(email=email, password=password, role="user")
    hashed_password = get_password_hash(password)
    create_user(db_session, user_in, hashed_password)

    # ログインリクエスト
    response = client.post(
        f"/api/v1/auth/token",
        data={"username": email, "password": password}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_failure_wrong_password(client: TestClient, db_session: Session):
    """パスワード間違いによるログイン失敗のテスト"""
    email = "test2@example.com"
    password = "password123"
    user_in = UserCreate(email=email, password=password, role="user")
    hashed_password = get_password_hash(password)
    create_user(db_session, user_in, hashed_password)

    response = client.post(
        f"/api/v1/auth/token",
        data={"username": email, "password": "wrongpassword"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_login_failure_wrong_username(client: TestClient):
    """ユーザー名間違いによるログイン失敗のテスト"""
    response = client.post(
        f"/api/v1/auth/token",
        data={"username": "nonexistent@example.com", "password": "password123"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_read_current_user(client: TestClient, db_session: Session):
    """現在のユーザー情報取得のテスト"""
    email = "test3@example.com"
    password = "password123"
    user_in = UserCreate(email=email, password=password, role="admin")
    hashed_password = get_password_hash(password)
    create_user(db_session, user_in, hashed_password)

    # ログインしてトークン取得
    login_response = client.post(
        f"/api/v1/auth/token",
        data={"username": email, "password": password}
    )
    token = login_response.json()["access_token"]

    # /me エンドポイントにリクエスト
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    current_user = response.json()
    assert current_user["email"] == email
    assert current_user["role"] == "admin"
    assert "id" in current_user

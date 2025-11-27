from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.crud.user import create_user, update_user
from app.schemas.user import UserCreate, UserUpdate
from app.models.user import User

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


def test_login_inactive_user(client: TestClient, db_session: Session):
    """非アクティブユーザーはログインできない"""
    email = "inactive@example.com"
    password = "password123"
    user_in = UserCreate(email=email, password=password, role="user", is_active=False)
    hashed_password = get_password_hash(password)
    create_user(db_session, user_in, hashed_password)

    response = client.post(
        f"/api/v1/auth/token",
        data={"username": email, "password": password}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_me_rejects_inactive_user(client: TestClient, db_session: Session):
    """トークン発行後に非アクティブ化された場合も利用を拒否する"""
    email = "to_inactivate@example.com"
    password = "password123"
    user_in = UserCreate(email=email, password=password, role="user")
    hashed_password = get_password_hash(password)
    user = create_user(db_session, user_in, hashed_password)

    login_response = client.post(
        f"/api/v1/auth/token",
        data={"username": email, "password": password}
    )
    token = login_response.json()["access_token"]

    # 非アクティブ化
    update_user(db_session, user.id, UserUpdate(is_active=False))

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"/api/v1/auth/me", headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_login_case_insensitive_lookup_for_legacy_mixed_case(client: TestClient, db_session: Session):
    """既存データに大文字が含まれてもログインできる（ケースインセンシティブ取得）"""
    legacy_email = "LegacyCase@Example.com"
    password = "password123"
    legacy_user = User(
        email=legacy_email,  # 大文字を含んだまま保存（過去データ想定）
        hashed_password=get_password_hash(password),
        role="user",
        is_active=True,
    )
    db_session.add(legacy_user)
    db_session.commit()

    response = client.post(
        f"/api/v1/auth/token",
        data={"username": legacy_email, "password": password}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

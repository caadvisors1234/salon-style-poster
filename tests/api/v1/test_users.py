import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud.user import create_user, get_user_by_email
from app.schemas.user import UserCreate
from app.core.security import get_password_hash

# --- テスト用のフィクスチャ ---

@pytest.fixture(scope="function")
def admin_user_and_headers(client: TestClient, db_session: Session):
    """管理者ユーザーを作成し、認証ヘッダーを返すフィクスチャ"""
    email = "admin@test.com"
    password = "adminpassword"
    user_in = UserCreate(email=email, password=password, role="admin")
    hashed_password = get_password_hash(password)
    create_user(db_session, user_in, hashed_password)

    login_response = client.post(
        f"/api/v1/auth/token",
        data={"username": email, "password": password}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers

@pytest.fixture(scope="function")
def normal_user_and_headers(client: TestClient, db_session: Session):
    """一般ユーザーを作成し、認証ヘッダーを返すフィクスチャ"""
    email = "user@test.com"
    password = "userpassword"
    user_in = UserCreate(email=email, password=password, role="user")
    hashed_password = get_password_hash(password)
    create_user(db_session, user_in, hashed_password)

    login_response = client.post(
        f"/api/v1/auth/token",
        data={"username": email, "password": password}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers

# --- テストケース ---

def test_get_users_as_admin(client: TestClient, admin_user_and_headers: dict):
    """管理者としてユーザー一覧を取得するテスト"""
    response = client.get("/api/v1/users", headers=admin_user_and_headers)
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data

def test_get_users_as_normal_user(client: TestClient, normal_user_and_headers: dict):
    """一般ユーザーとしてユーザー一覧を取得しようとすると403エラーになるテスト"""
    response = client.get("/api/v1/users", headers=normal_user_and_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"

def test_create_user_as_admin(client: TestClient, admin_user_and_headers: dict):
    """管理者として新規ユーザーを作成するテスト"""
    new_user_email = "newuser@test.com"
    new_user_password = "newpassword"
    response = client.post(
        "/api/v1/users",
        headers=admin_user_and_headers,
        json={"email": new_user_email, "password": new_user_password, "role": "user"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == new_user_email
    assert data["role"] == "user"

def test_create_existing_user_as_admin(client: TestClient, admin_user_and_headers: dict):
    """既存のユーザーを作成しようとすると409エラーになるテスト"""
    response = client.post(
        "/api/v1/users",
        headers=admin_user_and_headers,
        json={"email": "admin@test.com", "password": "password", "role": "user"}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "User with this email already exists"

def test_delete_user_as_admin(client: TestClient, admin_user_and_headers: dict, db_session: Session):
    """管理者としてユーザーを削除するテスト"""
    # 削除対象のユーザーを作成
    email_to_delete = "delete_me@test.com"
    password = "password"
    user_in = UserCreate(email=email_to_delete, password=password, role="user")
    hashed_password = get_password_hash(password)
    user_to_delete = create_user(db_session, user_in, hashed_password)

    # 削除リクエスト
    response = client.delete(
        f"/api/v1/users/{user_to_delete.id}",
        headers=admin_user_and_headers
    )
    assert response.status_code == 204


def test_admin_cannot_deactivate_self(client: TestClient, admin_user_and_headers: dict, db_session: Session):
    """管理者は自分自身を非アクティブ化できない"""
    admin = get_user_by_email(db_session, "admin@test.com")
    response = client.put(
        f"/api/v1/users/{admin.id}",
        headers=admin_user_and_headers,
        json={"is_active": False}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot deactivate your own account"


def test_admin_cannot_change_own_role(client: TestClient, admin_user_and_headers: dict, db_session: Session):
    """管理者は自分自身のロールを変更できない"""
    admin = get_user_by_email(db_session, "admin@test.com")
    response = client.put(
        f"/api/v1/users/{admin.id}",
        headers=admin_user_and_headers,
        json={"role": "user"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot change your own role"


def test_email_normalization_and_duplicate_prevention(client: TestClient, admin_user_and_headers: dict):
    """メールアドレスを正規化し、大小文字違いの重複を防ぐ"""
    response = client.post(
        "/api/v1/users",
        headers=admin_user_and_headers,
        json={"email": "MixedCase@Example.com", "password": "password123", "role": "user"}
    )
    assert response.status_code == 201
    first_user = response.json()
    assert first_user["email"] == "mixedcase@example.com"

    # 同じメールを小文字で再作成すると409
    dup_response = client.post(
        "/api/v1/users",
        headers=admin_user_and_headers,
        json={"email": "mixedcase@example.com", "password": "password123", "role": "user"}
    )
    assert dup_response.status_code == 409
    assert dup_response.json()["detail"] == "User with this email already exists"

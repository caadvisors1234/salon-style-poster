import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud.user import create_user
from app.schemas.user import UserCreate
from app.core.security import get_password_hash

# --- フィクスチャ ---

@pytest.fixture(scope="function")
def normal_user_auth_headers(client: TestClient, db_session: Session):
    """テスト用の一般ユーザーを作成し、認証ヘッダーを返す"""
    email = f"user_settings@test.com"
    password = "password"
    user_in = UserCreate(email=email, password=password, role="user")
    hashed_password = get_password_hash(password)
    create_user(db_session, user_in, hashed_password)

    login_response = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# --- テストケース ---

def test_create_and_get_setting(client: TestClient, normal_user_auth_headers: dict):
    """設定の作成と一覧取得のテスト"""
    # 1. 新しい設定を作成
    setting_data = {
        "setting_name": "My Main Salon",
        "sb_user_id": "salon_user@example.com",
        "sb_password": "salon_password_123",
        "salon_name": "Main Street Salon"
    }
    create_response = client.post(
        "/api/v1/sb-settings",
        headers=normal_user_auth_headers,
        json=setting_data
    )
    assert create_response.status_code == 201
    created_data = create_response.json()
    assert created_data["setting_name"] == setting_data["setting_name"]
    assert "id" in created_data

    # 2. 設定一覧を取得して、作成したものが含まれているか確認
    get_response = client.get("/api/v1/sb-settings", headers=normal_user_auth_headers)
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert len(get_data["settings"]) == 1
    assert get_data["settings"][0]["setting_name"] == setting_data["setting_name"]

def test_update_setting(client: TestClient, normal_user_auth_headers: dict):
    """設定の更新テスト"""
    # 1. テスト用の設定を作成
    setting_data = {"setting_name": "Before Update", "sb_user_id": "user@update", "sb_password": "pass"}
    create_response = client.post("/api/v1/sb-settings", headers=normal_user_auth_headers, json=setting_data)
    setting_id = create_response.json()["id"]

    # 2. 設定を更新
    update_data = {"setting_name": "After Update", "salon_name": "Updated Salon Name"}
    update_response = client.put(
        f"/api/v1/sb-settings/{setting_id}",
        headers=normal_user_auth_headers,
        json=update_data
    )
    assert update_response.status_code == 200
    updated_json = update_response.json()
    assert updated_json["setting_name"] == "After Update"
    assert updated_json["salon_name"] == "Updated Salon Name"

def test_delete_setting(client: TestClient, normal_user_auth_headers: dict):
    """設定の削除テスト"""
    # 1. テスト用の設定を作成
    setting_data = {"setting_name": "To Be Deleted", "sb_user_id": "user@delete", "sb_password": "pass"}
    create_response = client.post("/api/v1/sb-settings", headers=normal_user_auth_headers, json=setting_data)
    setting_id = create_response.json()["id"]

    # 2. 設定を削除
    delete_response = client.delete(f"/api/v1/sb-settings/{setting_id}", headers=normal_user_auth_headers)
    assert delete_response.status_code == 204

    # 3. 削除されたことを確認
    get_response = client.get("/api/v1/sb-settings", headers=normal_user_auth_headers)
    assert len(get_response.json()["settings"]) == 0

def test_cannot_access_other_user_settings(client: TestClient, db_session: Session, normal_user_auth_headers: dict):
    """他のユーザーの設定を操作できないことのテスト"""
    # 1. 別のユーザーを作成
    other_email = "other@test.com"
    other_password = "otherpass"
    other_user_in = UserCreate(email=other_email, password=other_password, role="user")
    hashed_password = get_password_hash(other_password)
    other_user = create_user(db_session, other_user_in, hashed_password)

    # 2. 別のユーザーとして設定を作成
    other_login_res = client.post("/api/v1/auth/token", data={"username": other_email, "password": other_password})
    other_token = other_login_res.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    setting_data = {"setting_name": "Other User Setting", "sb_user_id": "other@user", "sb_password": "pass"}
    create_response = client.post("/api/v1/sb-settings", headers=other_headers, json=setting_data)
    other_setting_id = create_response.json()["id"]

    # 3. 元のユーザーで他のユーザーの設定を操作しようとして失敗することを確認
    # GET
    get_res = client.get(f"/api/v1/sb-settings/{other_setting_id}", headers=normal_user_auth_headers)
    # Note: GET by id is not implemented, so this would be 405 Method Not Allowed.
    assert get_res.status_code == 405

    # PUT
    update_res = client.put(f"/api/v1/sb-settings/{other_setting_id}", headers=normal_user_auth_headers, json={"setting_name": "hacked"})
    assert update_res.status_code == 403

    # DELETE
    delete_res = client.delete(f"/api/v1/sb-settings/{other_setting_id}", headers=normal_user_auth_headers)
    assert delete_res.status_code == 403

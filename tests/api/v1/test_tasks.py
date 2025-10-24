import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch
import pandas as pd
from pathlib import Path

from app.crud.user import create_user
from app.crud.salon_board_setting import create_setting
from app.crud import current_task as crud_task
from app.schemas.user import UserCreate
from app.schemas.salon_board_setting import SalonBoardSettingCreate
from app.core.security import get_password_hash

# --- フィクスチャ ---

@pytest.fixture(scope="function")
def user_with_setting(client: TestClient, db_session: Session):
    """テスト用のユーザーと設定を作成し、認証ヘッダーと設定IDを返す"""
    email = f"taskuser@test.com"
    password = "password"
    user_in = UserCreate(email=email, password=password, role="user")
    hashed_password = get_password_hash(password)
    user = create_user(db_session, user_in, hashed_password)

    login_response = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    setting_in = SalonBoardSettingCreate(
        setting_name="Test Salon for Tasks", sb_user_id="salon_id", sb_password="salon_pass"
    )
    setting = create_setting(db_session, setting_in, user.id)

    return {"headers": headers, "setting_id": setting.id, "user_id": user.id}

# --- テストケース ---

@patch("app.api.v1.endpoints.tasks.process_style_post_task.delay")
def test_create_task_success(mock_celery_task, client: TestClient, user_with_setting: dict, tmp_path: Path):
    """正常なタスク作成のテスト"""
    style_data = {"画像名": ["image1.jpg"], "スタイリスト名": ["Test Stylist"], "クーポン名": ["Test Coupon"], "コメント":["c"], "スタイル名":["s"], "カテゴリ":["レディース"], "長さ":["ロング"], "メニュー内容":["m"], "ハッシュタグ":["h"]}
    df = pd.DataFrame(style_data)
    csv_path = tmp_path / "styles.csv"
    df.to_csv(csv_path, index=False)
    image1_path = tmp_path / "image1.jpg"
    image1_path.write_text("fake image data")

    with open(csv_path, "rb") as csv_file, open(image1_path, "rb") as img_file:
        files = {
            "style_data_file": ("styles.csv", csv_file, "text/csv"),
            "image_files": ("image1.jpg", img_file, "image/jpeg")
        }
        data = {"setting_id": user_with_setting["setting_id"]}
        response = client.post("/api/v1/tasks/style-post", files=files, data=data, headers=user_with_setting["headers"])

    assert response.status_code == 202
    assert "task_id" in response.json()
    mock_celery_task.assert_called_once()

def test_create_task_already_running(client: TestClient, user_with_setting: dict, tmp_path: Path):
    """タスク実行中に再度タスクを作成しようとすると409エラーになるテスト"""
    style_data = {"画像名": ["image1.jpg"], "スタイリスト名": ["Test Stylist"], "クーポン名": ["Test Coupon"], "コメント":["c"], "スタイル名":["s"], "カテゴリ":["レディース"], "長さ":["ロング"], "メニュー内容":["m"], "ハッシュタグ":["h"]}
    df = pd.DataFrame(style_data)
    csv_path = tmp_path / "styles.csv"
    df.to_csv(csv_path, index=False)
    image1_path = tmp_path / "image1.jpg"
    image1_path.write_text("fake image data")

    with open(csv_path, "rb") as csv_file, open(image1_path, "rb") as img_file:
        files = [("style_data_file", ("styles.csv", csv_file, "text/csv")), ("image_files", ("image1.jpg", img_file, "image/jpeg"))]
        data = {"setting_id": user_with_setting["setting_id"]}
        with patch("app.api.v1.endpoints.tasks.process_style_post_task.delay") as mock_celery_task:
            response1 = client.post("/api/v1/tasks/style-post", files=files, data=data, headers=user_with_setting["headers"])
            assert response1.status_code == 202

    with open(csv_path, "rb") as csv_file, open(image1_path, "rb") as img_file:
        files = [("style_data_file", ("styles.csv", csv_file, "text/csv")), ("image_files", ("image1.jpg", img_file, "image/jpeg"))]
        response2 = client.post("/api/v1/tasks/style-post", files=files, data=data, headers=user_with_setting["headers"])
    
    assert response2.status_code == 409
    assert response2.json()["detail"] == "You already have a task in progress"

def test_create_task_invalid_file_format(client: TestClient, user_with_setting: dict, tmp_path: Path):
    """不正なファイル形式でのタスク作成失敗をテスト"""
    invalid_file = tmp_path / "style.txt"
    invalid_file.write_text("invalid content")
    image1_path = tmp_path / "image1.jpg"
    image1_path.write_text("fake image data")

    with open(invalid_file, "rb") as txt_file, open(image1_path, "rb") as img_file:
        files = [("style_data_file", ("style.txt", txt_file, "text/plain")), ("image_files", ("image1.jpg", img_file, "image/jpeg"))]
        data = {"setting_id": user_with_setting["setting_id"]}
        response = client.post("/api/v1/tasks/style-post", files=files, data=data, headers=user_with_setting["headers"])

    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]

def test_create_task_missing_image(client: TestClient, user_with_setting: dict, tmp_path: Path):
    """画像ファイル不足でのタスク作成失敗をテスト"""
    style_data = {"画像名": ["image1.jpg", "image2.jpg"]}
    df = pd.DataFrame(style_data)
    csv_path = tmp_path / "styles.csv"
    df.to_csv(csv_path, index=False)
    image1_path = tmp_path / "image1.jpg"
    image1_path.write_text("fake image data")

    with open(csv_path, "rb") as csv_file, open(image1_path, "rb") as img_file:
        files = [("style_data_file", ("styles.csv", csv_file, "text/csv")), ("image_files", ("image1.jpg", img_file, "image/jpeg"))]
        data = {"setting_id": user_with_setting["setting_id"]}
        response = client.post("/api/v1/tasks/style-post", files=files, data=data, headers=user_with_setting["headers"])

    assert response.status_code == 422
    assert "Missing image files: image2.jpg" in response.json()["detail"]

@patch("app.api.v1.endpoints.tasks.process_style_post_task.delay")
def test_task_lifecycle(mock_celery_task, client: TestClient, user_with_setting: dict, db_session: Session, tmp_path: Path):
    """タスクのライフサイクル（ステータス確認、キャンセル、削除）をテスト"""
    # 1. タスク作成
    style_data = {"画像名": ["image1.jpg"], "スタイリスト名": ["Test Stylist"], "クーポン名": ["Test Coupon"], "コメント":["c"], "スタイル名":["s"], "カテゴリ":["レディース"], "長さ":["ロング"], "メニュー内容":["m"], "ハッシュタグ":["h"]}
    df = pd.DataFrame(style_data)
    csv_path = tmp_path / "styles.csv"
    df.to_csv(csv_path, index=False)
    image1_path = tmp_path / "image1.jpg"
    image1_path.write_text("fake image data")
    with open(csv_path, "rb") as csv_file, open(image1_path, "rb") as img_file:
        files = [("style_data_file", ("styles.csv", csv_file, "text/csv")), ("image_files", ("image1.jpg", img_file, "image/jpeg"))]
        data = {"setting_id": user_with_setting["setting_id"]}
        response = client.post("/api/v1/tasks/style-post", files=files, data=data, headers=user_with_setting["headers"])
    assert response.status_code == 202
    task_id = response.json()["task_id"]

    # 2. ステータス確認 (PROCESSING)
    status_res = client.get("/api/v1/tasks/status", headers=user_with_setting["headers"])
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "PROCESSING"

    # 3. タスクキャンセル
    cancel_res = client.post("/api/v1/tasks/cancel", headers=user_with_setting["headers"])
    assert cancel_res.status_code == 202

    # 4. ステータス確認 (CANCELLING)
    status_res_cancelling = client.get("/api/v1/tasks/status", headers=user_with_setting["headers"])
    assert status_res_cancelling.status_code == 200
    assert status_res_cancelling.json()["status"] == "CANCELLING"

    # 5. DBを直接更新してタスクを完了状態にする (テストのための擬似的な操作)
    db_task = crud_task.get_task_by_id(db_session, task_id)
    crud_task.update_task_status(db_session, db_task.id, "FAILURE")

    # 6. 完了タスクを削除
    delete_res = client.delete("/api/v1/tasks/finished-task", headers=user_with_setting["headers"])
    assert delete_res.status_code == 204

    # 7. タスクが削除されたことを確認
    status_res_after_delete = client.get("/api/v1/tasks/status", headers=user_with_setting["headers"])
    assert status_res_after_delete.status_code == 404

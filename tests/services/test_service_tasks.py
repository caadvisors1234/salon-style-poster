import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.core.celery_task import MonitoredTask, TaskCancelledError
from app.crud import current_task as crud_task
from app.schemas.task import TaskCreate, TaskStatus

import json

# ダミータスククラスの定義
class MockTask(MonitoredTask):
    name = "mock_task"

@pytest.fixture
def mock_task_instance(db_session):
    """MonitoredTaskのインスタンスを提供するフィクスチャ"""
    task = MockTask()
    # dbプロパティがテスト用セッションを返すようにモックでオーバーライド
    # ただしMonitoredTask.dbはpropertyなので、クラス属性としてモックするか
    # インスタンスの属性として_dbをセットする
    task._db = db_session
    return task

def create_test_task(db, status="PROCESSING"):
    """テスト用タスクレコードを作成"""
    task_id = uuid.uuid4()
    # crud_task.create_task のシグネチャに合わせて呼び出す
    crud_task.create_task(db, task_id, user_id=1, total_items=10)
    crud_task.update_task_status(db, task_id, status)
    return task_id

def test_record_detail(db_session, mock_task_instance):
    """record_detailメソッドのテスト"""
    task_id = create_test_task(db_session)
    
    mock_task_instance.record_detail(
        task_uuid=task_id,
        stage="TEST_STAGE",
        stage_label="Test Label",
        message="Test Message",
        current_index=5,
        total=10
    )
    
    
    # DB確認
    task = crud_task.get_task_by_id(db_session, task_id)
    assert task.progress_detail_json is not None
    progress_detail = json.loads(task.progress_detail_json)
    assert progress_detail["stage"] == "TEST_STAGE"
    assert progress_detail["message"] == "Test Message"
    assert progress_detail["current_index"] == 5

def test_ensure_not_cancelled_ok(db_session, mock_task_instance):
    """キャンセルされていない場合の動作確認"""
    task_id = create_test_task(db_session, status="PROCESSING")
    
    # 例外が発生しないこと
    task_record = mock_task_instance.ensure_not_cancelled(task_id)
    assert task_record.id == task_id

def test_ensure_not_cancelled_cancelling(db_session, mock_task_instance):
    """CANCELLING状態での動作確認"""
    task_id = create_test_task(db_session, status="CANCELLING")
    
    with pytest.raises(TaskCancelledError):
        mock_task_instance.ensure_not_cancelled(task_id)

def test_handle_failure(db_session, mock_task_instance):
    """エラーハンドリングのテスト"""
    task_id = create_test_task(db_session, status="PROCESSING")
    error = ValueError("Something wrong")
    
    mock_task_instance.handle_failure(
        task_uuid=task_id,
        task_id=str(task_id),
        error=error,
        completed_items=3,
        total_items=10
    )
    
    task = crud_task.get_task_by_id(db_session, task_id)
    assert task.status == "FAILURE"
    
    progress_detail = json.loads(task.progress_detail_json)
    assert progress_detail["status"] == "error"
    assert progress_detail["error_reason"] == "Something wrong"

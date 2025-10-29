"""
CurrentTask CRUD操作
"""
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json
from uuid import UUID

from app.models.current_task import CurrentTask


def get_task_by_id(db: Session, task_id: UUID) -> Optional[CurrentTask]:
    """
    タスクIDでタスク取得

    Args:
        db: データベースセッション
        task_id: タスクID（UUID）

    Returns:
        Optional[CurrentTask]: タスク（存在しない場合はNone）
    """
    return db.query(CurrentTask).filter(CurrentTask.id == task_id).first()


def get_task_by_user_id(db: Session, user_id: int) -> Optional[CurrentTask]:
    """
    ユーザーIDでタスク取得

    Args:
        db: データベースセッション
        user_id: ユーザーID

    Returns:
        Optional[CurrentTask]: タスク（存在しない場合はNone）
    """
    return db.query(CurrentTask).filter(CurrentTask.user_id == user_id).first()


def create_task(
    db: Session,
    task_id: UUID,
    user_id: int,
    total_items: int
) -> CurrentTask:
    """
    タスク作成

    Args:
        db: データベースセッション
        task_id: タスクID（CeleryタスクIDと同じ）
        user_id: ユーザーID
        total_items: 処理対象の総スタイル数

    Returns:
        CurrentTask: 作成されたタスク
    """
    db_task = CurrentTask(
        id=task_id,
        user_id=user_id,
        status="PROCESSING",
        total_items=total_items,
        completed_items=0,
        progress_detail_json=None,
        error_info_json=None
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def update_task_progress(db: Session, task_id: UUID, completed_items: int) -> Optional[CurrentTask]:
    """
    タスク進捗更新

    Args:
        db: データベースセッション
        task_id: タスクID
        completed_items: 完了件数

    Returns:
        Optional[CurrentTask]: 更新されたタスク（存在しない場合はNone）
    """
    db_task = get_task_by_id(db, task_id)
    if db_task:
        db_task.completed_items = completed_items
        db.commit()
        db.refresh(db_task)
    return db_task


def update_task_detail(db: Session, task_id: UUID, detail: Dict[str, Any]) -> Optional[CurrentTask]:
    """
    タスク進捗の詳細情報を更新

    Args:
        db: データベースセッション
        task_id: タスクID
        detail: フロントエンド表示用の詳細情報

    Returns:
        Optional[CurrentTask]: 更新されたタスク（存在しない場合はNone）
    """
    db_task = get_task_by_id(db, task_id)
    if db_task:
        db_task.progress_detail_json = json.dumps(detail, ensure_ascii=False)
        db.commit()
        db.refresh(db_task)
    return db_task


def update_task_status(db: Session, task_id: UUID, status: str) -> Optional[CurrentTask]:
    """
    タスクステータス更新

    Args:
        db: データベースセッション
        task_id: タスクID
        status: 新しいステータス（"PROCESSING", "CANCELLING", "SUCCESS", "FAILURE"）

    Returns:
        Optional[CurrentTask]: 更新されたタスク（存在しない場合はNone）
    """
    db_task = get_task_by_id(db, task_id)
    if db_task:
        db_task.status = status
        db.commit()
        db.refresh(db_task)
    return db_task


def add_task_error(db: Session, task_id: UUID, error_info: dict) -> Optional[CurrentTask]:
    """
    タスクエラー情報追加

    Args:
        db: データベースセッション
        task_id: タスクID
        error_info: エラー情報の辞書

    Returns:
        Optional[CurrentTask]: 更新されたタスク（存在しない場合はNone）
    """
    db_task = get_task_by_id(db, task_id)
    if db_task:
        # 既存のエラー情報を取得
        if db_task.error_info_json:
            errors = json.loads(db_task.error_info_json)
        else:
            errors = []

        # 新しいエラーを追加
        errors.append(error_info)

        # JSON文字列として保存
        db_task.error_info_json = json.dumps(errors, ensure_ascii=False)
        db.commit()
        db.refresh(db_task)
    return db_task


def delete_task(db: Session, task_id: UUID) -> bool:
    """
    タスク削除

    Args:
        db: データベースセッション
        task_id: タスクID

    Returns:
        bool: 削除成功（True）/ 失敗（False）
    """
    db_task = get_task_by_id(db, task_id)
    if db_task:
        db.delete(db_task)
        db.commit()
        return True
    return False

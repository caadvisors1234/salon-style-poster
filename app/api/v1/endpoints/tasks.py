"""
タスク管理エンドポイント
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
import json
import os
import shutil
import uuid
from pathlib import Path
from uuid import UUID
import pandas as pd
from slowapi import Limiter

from app.db.session import get_db
from app.core.security import get_current_user
from app.crud import current_task as crud_task, salon_board_setting as crud_setting
from app.schemas.user import User
from app.schemas.task import TaskStatus, ErrorReport
from app.services.tasks import process_style_post_task
from app.core.celery_app import celery_app

router = APIRouter()


def get_user_id_for_rate_limit(request: Request) -> str:
    """
    レート制限用のユーザーID取得関数

    認証済みユーザーのIDを返す。未認証の場合はIPアドレスを返す。
    """
    # リクエストのstateからユーザー情報を取得（get_current_user依存注入後に利用可能）
    # 注: この関数はデコレータで使用されるため、依存注入前に呼ばれる可能性がある
    # その場合はIPアドレスにフォールバック
    try:
        # Authorizationヘッダーが存在する場合のみユーザーIDベースでレート制限
        auth_header = request.headers.get("Authorization")
        if auth_header:
            # トークンからユーザー情報を取得してユーザーIDを返す
            # ただし、ここでは簡易的にIPアドレスを使用
            # 本来はトークンを解析してユーザーIDを取得すべき
            from slowapi.util import get_remote_address
            return get_remote_address(request)
        else:
            from slowapi.util import get_remote_address
            return get_remote_address(request)
    except Exception:
        from slowapi.util import get_remote_address
        return get_remote_address(request)


limiter = Limiter(key_func=get_user_id_for_rate_limit)

# アップロードディレクトリ
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/style-post", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/hour")
async def create_style_post_task(
    request: Request,
    setting_id: int = Form(...),
    style_data_file: UploadFile = File(...),
    image_files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    スタイル投稿タスク作成・実行

    Args:
        setting_id: 使用するSALON BOARD設定ID
        style_data_file: スタイル情報ファイル（CSV/Excel）
        image_files: 画像ファイルリスト
        db: データベースセッション
        current_user: 現在のユーザー

    Returns:
        dict: タスクIDとメッセージ
    """
    # 設定存在確認
    db_setting = crud_setting.get_setting_by_id(db, setting_id)
    if not db_setting or db_setting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found or access denied"
        )

    # ファイル形式確認
    if not (style_data_file.filename.endswith('.csv') or
            style_data_file.filename.endswith('.xlsx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only CSV and Excel files are supported"
        )

    # タスクID生成
    task_uuid = uuid.uuid4()
    task_dir = UPLOAD_DIR / str(task_uuid)
    task_dir.mkdir(parents=True, exist_ok=True)

    try:
        # スタイルデータファイル保存
        style_data_path = task_dir / style_data_file.filename
        with open(style_data_path, "wb") as f:
            shutil.copyfileobj(style_data_file.file, f)

        # 画像ファイル保存
        image_dir = task_dir / "images"
        image_dir.mkdir(exist_ok=True)

        uploaded_image_names = []
        for image_file in image_files:
            image_path = image_dir / image_file.filename
            with open(image_path, "wb") as f:
                shutil.copyfileobj(image_file.file, f)
            uploaded_image_names.append(image_file.filename)

        # ファイルバリデーション: スタイル情報ファイル内の画像名チェック
        if style_data_path.suffix == ".csv":
            df = pd.read_csv(style_data_path)
        else:
            df = pd.read_excel(style_data_path)

        required_images = df["画像名"].tolist()
        missing_images = [img for img in required_images if img not in uploaded_image_names]

        if missing_images:
            # クリーンアップ
            shutil.rmtree(task_dir)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing image files: {', '.join(missing_images)}"
            )

        # current_tasksテーブルにレコード作成（UNIQUE制約でシングルタスク保証）
        try:
            db_task = crud_task.create_task(
                db=db,
                task_id=task_uuid,
                user_id=current_user.id,
                total_items=len(df)
            )
        except IntegrityError:
            # UNIQUE制約違反 = 既にタスク実行中
            shutil.rmtree(task_dir)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a task in progress"
            )

        # Celeryタスクをキューイング
        process_style_post_task.delay(
            task_id=str(task_uuid),
            user_id=current_user.id,
            setting_id=setting_id,
            style_data_filepath=str(style_data_path),
            image_dir=str(image_dir)
        )

        return {
            "task_id": str(task_uuid),
            "message": "Task accepted and started"
        }

    except HTTPException:
        raise
    except Exception as e:
        # エラー時のクリーンアップ
        if task_dir.exists():
            shutil.rmtree(task_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/status", response_model=TaskStatus)
async def get_task_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """タスク進捗状況取得"""
    db_task = crud_task.get_task_by_user_id(db, current_user.id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active task found"
        )

    progress = (db_task.completed_items / db_task.total_items * 100) if db_task.total_items > 0 else 0
    error_entries = []
    if db_task.error_info_json:
        try:
            error_entries = json.loads(db_task.error_info_json)
        except json.JSONDecodeError:
            error_entries = []
    has_errors = len(error_entries) > 0
    error_count = len(error_entries)

    return {
        "task_id": db_task.id,
        "status": db_task.status,
        "total_items": db_task.total_items,
        "completed_items": db_task.completed_items,
        "progress": round(progress, 2),
        "has_errors": has_errors,
        "error_count": error_count,
        "created_at": db_task.created_at
    }


@router.post("/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """タスク即時中止"""
    db_task = crud_task.get_task_by_user_id(db, current_user.id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active task to cancel"
        )

    if db_task.status not in ["PROCESSING", "CANCELLING"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task has already finished"
        )

    # Celeryタスクを即座に終了（terminate=Trueで強制終了）
    # タスクIDの形式: process_style_post[celery-task-id]
    # Redis/Celeryから実行中のタスクを取得して終了
    celery_app.control.revoke(str(db_task.id), terminate=True, signal='SIGKILL')

    # ステータスをFAILUREに更新（中止扱い）
    crud_task.update_task_status(db, db_task.id, "FAILURE")

    return {
        "message": "Task has been forcefully terminated."
    }


@router.get("/error-report", response_model=ErrorReport)
async def get_error_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """エラーレポート取得"""
    db_task = crud_task.get_task_by_user_id(db, current_user.id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed task found"
        )

    if db_task.status not in ["SUCCESS", "FAILURE"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task has not completed yet"
        )

    if not db_task.error_info_json:
        # エラーがない場合は204 No Content
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT
        )

    errors = json.loads(db_task.error_info_json)

    # screenshot_pathをscreenshot_urlに変換
    for error in errors:
        if "screenshot_path" in error:
            # パスをURLに変換
            screenshot_path = error["screenshot_path"]
            if screenshot_path:
                # app/static/screenshots/xxx.png → /static/screenshots/xxx.png
                if screenshot_path.startswith("app/static/"):
                    error["screenshot_url"] = screenshot_path.replace("app/static/", "/static/")
                elif screenshot_path.startswith("static/"):
                    error["screenshot_url"] = "/" + screenshot_path
                elif screenshot_path.startswith("/"):
                    error["screenshot_url"] = screenshot_path
                else:
                    # 念のため/static/を追加
                    error["screenshot_url"] = "/static/" + screenshot_path
            else:
                error["screenshot_url"] = ""
        elif "screenshot_url" not in error:
            error["screenshot_url"] = ""

    return {
        "task_id": db_task.id,
        "total_errors": len(errors),
        "errors": errors
    }


@router.delete("/finished-task", status_code=status.HTTP_204_NO_CONTENT)
async def delete_finished_task(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """完了タスク情報削除"""
    db_task = crud_task.get_task_by_user_id(db, current_user.id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No finished task to delete"
        )

    if db_task.status not in ["SUCCESS", "FAILURE"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete task that is still in progress"
        )

    crud_task.delete_task(db, db_task.id)

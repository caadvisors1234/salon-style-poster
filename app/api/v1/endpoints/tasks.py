"""
タスク管理エンドポイント
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError
from typing import Any, Dict, List, Set
from datetime import datetime, timezone
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
from app.services.tasks import process_style_post_task, unpublish_styles_task
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

            crud_task.update_task_detail(
                db=db,
                task_id=db_task.id,
                detail={
                    "stage": "INITIALIZING",
                    "stage_label": "タスクを準備しています",
                    "message": "Playwrightの起動を準備中です",
                    "status": "pending",
                    "current_index": 0,
                    "total": len(df),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            )
        except IntegrityError:
            # UNIQUE制約違反 = 既にタスク実行中
            shutil.rmtree(task_dir)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a task in progress"
            )

        # Celeryタスクをキューイング
        process_style_post_task.apply_async(
            kwargs={
                "task_id": str(task_uuid),
                "user_id": current_user.id,
                "setting_id": setting_id,
                "style_data_filepath": str(style_data_path),
                "image_dir": str(image_dir)
            },
            task_id=str(task_uuid)
        )

        return {
            "task_id": str(task_uuid),
            "message": "Task accepted and started"
        }

    except HTTPException:
        raise
    except ProgrammingError as e:
        if task_dir.exists():
            shutil.rmtree(task_dir)

        message = str(e)
        if hasattr(e, "orig"):
            message = str(e.orig)
        if "progress_detail_json" in message:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database schema is outdated. Please run 'alembic upgrade head' and try again."
            ) from e

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        ) from e
    except Exception as e:
        # エラー時のクリーンアップ
        if task_dir.exists():
            shutil.rmtree(task_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.post("/style-unpublish", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("6/hour")
async def create_style_unpublish_task(
    request: Request,
    setting_id: int = Form(...),
    range_start: int = Form(...),
    range_end: int = Form(...),
    exclude_numbers: str = Form("", description="カンマ区切りの除外スタイル番号"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    スタイル非掲載タスク作成・実行
    """
    db_setting = crud_setting.get_setting_by_id(db, setting_id)
    if not db_setting or db_setting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found or access denied",
        )

    if range_start <= 0 or range_end <= 0 or range_start > range_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid range. Please set a positive start/end with start <= end.",
        )

    exclude_set: Set[int] = set()
    if exclude_numbers:
        for token in exclude_numbers.replace("\n", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                exclude_set.add(int(token))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="exclude_numbers must be a comma-separated list of integers",
                )

    target_numbers = [n for n in range(range_start, range_end + 1) if n not in exclude_set]
    if not target_numbers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No target styles to unpublish in the specified range.",
        )

    task_uuid = uuid.uuid4()
    total_items = len(target_numbers)

    try:
        try:
            db_task = crud_task.create_task(
                db=db,
                task_id=task_uuid,
                user_id=current_user.id,
                total_items=total_items,
            )

            crud_task.update_task_detail(
                db=db,
                task_id=db_task.id,
                detail={
                    "stage": "INITIALIZING",
                    "stage_label": "タスクを準備しています",
                    "message": f"非掲載対象: {total_items}件、範囲 {range_start}〜{range_end}",
                    "status": "pending",
                    "current_index": 0,
                    "total": total_items,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a task in progress",
            )

        unpublish_styles_task.apply_async(
            kwargs={
                "task_id": str(task_uuid),
                "user_id": current_user.id,
                "setting_id": setting_id,
                "range_start": range_start,
                "range_end": range_end,
                "exclude_numbers": list(exclude_set),
            },
            task_id=str(task_uuid),
        )

        return {
            "task_id": str(task_uuid),
            "message": "Task accepted and started",
        }
    except HTTPException:
        raise
    except Exception as e:
        crud_task.delete_task(db, task_uuid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create unpublish task: {str(e)}",
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
    error_entries_raw: List[Dict[str, Any]] = []
    if db_task.error_info_json:
        try:
            decoded = json.loads(db_task.error_info_json)
            if isinstance(decoded, list):
                error_entries_raw = decoded
        except json.JSONDecodeError:
            error_entries_raw = []

    manual_entries = [
        entry for entry in error_entries_raw
        if entry.get("error_category") == "IMAGE_UPLOAD_ABORTED"
    ]
    error_entries = [
        entry for entry in error_entries_raw
        if entry.get("error_category") != "IMAGE_UPLOAD_ABORTED"
    ]

    has_errors = len(error_entries) > 0
    error_count = len(error_entries)
    manual_upload_count = len(manual_entries)
    detail = None
    if db_task.progress_detail_json:
        try:
            detail = json.loads(db_task.progress_detail_json)
        except json.JSONDecodeError:
            detail = None

    return {
        "task_id": db_task.id,
        "status": db_task.status,
        "total_items": db_task.total_items,
        "completed_items": db_task.completed_items,
        "progress": round(progress, 2),
        "has_errors": has_errors,
        "error_count": error_count,
        "manual_upload_count": manual_upload_count,
        "created_at": db_task.created_at,
        "detail": detail
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

    if db_task.status != "CANCELLING":
        crud_task.update_task_status(db, db_task.id, "CANCELLING")
        crud_task.update_task_detail(
            db=db,
            task_id=db_task.id,
            detail={
                "stage": "CANCELLING",
                "stage_label": "キャンセル要求中",
                "message": "ユーザーがタスクの中止を要求しました",
                "status": "cancelling",
                "current_index": db_task.completed_items,
                "total": db_task.total_items,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        )

    task_identifier = str(db_task.id)
    celery_app.control.revoke(task_identifier, terminate=True, signal="SIGTERM")

    crud_task.update_task_status(db, db_task.id, "FAILURE")
    crud_task.update_task_detail(
        db=db,
        task_id=db_task.id,
        detail={
            "stage": "CANCELLED",
            "stage_label": "タスクは中止されました",
            "message": "ユーザー操作により処理を停止しました",
            "status": "cancelled",
            "current_index": db_task.completed_items,
            "total": db_task.total_items,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    )

    return {
        "message": "Task cancellation requested."
    }


@router.get("/error-report", response_model=ErrorReport)
async def get_error_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """エラーレポート取得（成功スタイル情報を含む）"""
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

    # 成功スタイル情報の取得
    raw_successes = []
    if db_task.success_info_json:
        try:
            raw_successes = json.loads(db_task.success_info_json)
        except json.JSONDecodeError:
            raw_successes = []

    # エラー情報の取得
    raw_errors = []
    if db_task.error_info_json:
        try:
            raw_errors = json.loads(db_task.error_info_json)
        except json.JSONDecodeError:
            raw_errors = []

    manual_uploads = []
    filtered_errors = []

    def convert_screenshot_path(entry: Dict[str, Any]) -> None:
        screenshot_path = entry.get("screenshot_path", "")
        if not screenshot_path:
            entry["screenshot_url"] = ""
            return

        if screenshot_path.startswith("app/static/"):
            entry["screenshot_url"] = screenshot_path.replace("app/static/", "/static/")
        elif screenshot_path.startswith("static/"):
            entry["screenshot_url"] = "/" + screenshot_path
        elif screenshot_path.startswith("/"):
            entry["screenshot_url"] = screenshot_path
        else:
            entry["screenshot_url"] = "/static/" + screenshot_path

    for error in raw_errors:
        entry = dict(error)
        convert_screenshot_path(entry)
        if entry.get("error_category") == "IMAGE_UPLOAD_ABORTED":
            manual_uploads.append(entry)
        else:
            filtered_errors.append(entry)

    return {
        "task_id": db_task.id,
        "total_errors": len(filtered_errors),
        "errors": filtered_errors,
        "manual_uploads": manual_uploads,
        "manual_upload_count": len(manual_uploads),
        "successes": raw_successes,
        "success_count": len(raw_successes)
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

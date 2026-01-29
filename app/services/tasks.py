"""
Celeryタスク定義
スタイル投稿処理の非同期実行
"""
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from celery import Task

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.celery_task import MonitoredTask, TaskCancelledError
from app.crud import current_task as crud_task, salon_board_setting as crud_setting
from app.core.security import decrypt_password
from app.services.salonboard import (
    SalonBoardStylePoster,
    SalonBoardStyleUnpublisher,
    StylePostError,
    StyleUnpublishError,
    load_selectors,
)

logger = logging.getLogger(__name__)
SCREENSHOT_DIR = Path(settings.SCREENSHOT_DIR)


@celery_app.task(bind=True, base=MonitoredTask, name="process_style_post")
def process_style_post_task(
    self,
    task_id: str,
    user_id: int,
    setting_id: int,
    style_data_filepath: str,
    image_dir: str
):
    """
    スタイル投稿処理タスク
    """
    task_uuid = UUID(task_id)
    db = self.db
    # 初期値
    total_items = 0

    try:
        logger.info("=== タスク開始: %s ===", task_id)
        
        # 初期状態の確保 (total_itemsなど)
        db_task_snapshot = crud_task.get_task_by_id(db, task_uuid)
        total_items = db_task_snapshot.total_items if db_task_snapshot else 0

        # SALON BOARD設定取得
        setting = crud_setting.get_setting_by_id(db, setting_id)
        if not setting or setting.user_id != user_id:
            raise Exception("SALON BOARD設定が見つかりません")

        # パスワード復号化
        sb_password = decrypt_password(setting.encrypted_sb_password)

        # サロン情報準備
        salon_info = None
        if setting.salon_id or setting.salon_name:
            salon_info = {
                "id": setting.salon_id,
                "name": setting.salon_name
            }

        # セレクタ読み込み
        selectors = load_selectors()

        # スクリーンショットディレクトリ
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_dir = str(SCREENSHOT_DIR)

        # SalonBoardStylePosterインスタンス化
        poster = SalonBoardStylePoster(
            selectors=selectors,
            screenshot_dir=screenshot_dir,
            headless=not settings.USE_HEADFUL_MODE,
            slow_mo=100
        )

        # 進捗コールバック関数
        def progress_callback(
            completed: int,
            total: int,
            *,
            detail: Optional[Dict[str, Any]] = None,
            error: Optional[Dict[str, Any]] = None
        ) -> None:
            """進捗・詳細・エラー情報を更新"""
            nonlocal total_items

            self.ensure_not_cancelled(task_uuid)

            if total and total > total_items:
                total_items = total

            if detail is not None:
                # MonitoredTask.record_detail を利用
                # detailに含まれるキーを展開して渡す
                stage = detail.pop("stage", "PROGRESS")
                stage_label = detail.pop("stage_label", "")
                message = detail.pop("message", "")
                status_text = detail.pop("status", "running")
                
                # 残りの情報をextraとしてまとめることも可能だが、
                # record_detailの引数に合わせてマッピングする
                current_idx = detail.pop("current_index", completed)
                total_val = detail.pop("total", total_items or total)
                style_name = detail.pop("style_name", None)
                
                self.record_detail(
                    task_uuid=task_uuid,
                    stage=stage,
                    stage_label=stage_label,
                    message=message,
                    status_text=status_text,
                    current_index=current_idx,
                    total=total_val,
                    style_name=style_name,
                    extra=detail # 残りのデータ
                )

            crud_task.update_task_progress(db, task_uuid, completed)
            if error:
                crud_task.add_task_error(db, task_uuid, error)

        # Poster実行
        poster.run(
            user_id=setting.sb_user_id,
            password=sb_password,
            data_filepath=style_data_filepath,
            image_dir=image_dir,
            salon_info=salon_info,
            progress_callback=progress_callback,
            total_items=total_items
        )

        # 完了処理
        crud_task.update_task_status(db, task_uuid, "SUCCESS")
        
        # 最終状態取得
        final_snapshot = crud_task.get_task_by_id(db, task_uuid)
        final_completed = final_snapshot.completed_items if final_snapshot else total_items
        final_total = final_snapshot.total_items if final_snapshot else total_items

        self.record_detail(
            task_uuid=task_uuid,
            stage="COMPLETED",
            stage_label="タスク完了",
            message="すべてのスタイル投稿が完了しました",
            status_text="success",
            current_index=final_completed,
            total=final_total
        )
        logger.info("=== タスク完了: %s ===", task_id)

    except TaskCancelledError as cancel_error:
        self.handle_cancel(task_uuid, task_id, cancel_error, completed_items=0, total_items=total_items)
        raise

    except Exception as e:
        # StylePostError独自の情報を抽出
        error_context = None
        if isinstance(e, StylePostError):
            logger.warning("スクリーンショット: %s", e.screenshot_path)
            error_context = {
                "row_number": 0,
                "style_name": "システムエラー",
                "field": "タスク全体",
                "reason": str(e),
                "screenshot_path": e.screenshot_path
            }
        else:
            # その他の例外
            error_context = {
                "row_number": 0,
                "style_name": "システムエラー",
                "field": "タスク全体",
                "reason": f"予期せぬエラー: {str(e)}",
                "screenshot_path": ""
            }
        
        # 共通ハンドラ呼び出し
        self.handle_failure(
            task_uuid=task_uuid, 
            task_id=task_id, 
            error=e, 
            completed_items=0, 
            total_items=total_items,
            error_context=error_context
        )
        raise

    finally:
        # アップロードファイルのクリーンアップ
        try:
            if os.path.exists(style_data_filepath):
                os.remove(style_data_filepath)
                logger.info("スタイルデータファイル削除: %s", style_data_filepath)

            if os.path.exists(image_dir):
                shutil.rmtree(image_dir)
                logger.info("画像ディレクトリ削除: %s", image_dir)
        except Exception as cleanup_error:
            logger.warning("クリーンアップエラー: %s", cleanup_error)


@celery_app.task(bind=True, base=MonitoredTask, name="unpublish_styles")
def unpublish_styles_task(
    self,
    task_id: str,
    user_id: int,
    setting_id: int,
    salon_url: str,
    range_start: int,
    range_end: int,
    exclude_numbers: List[int],
):
    """
    スタイル非掲載タスク
    """
    task_uuid = UUID(task_id)
    db = self.db
    
    # 初期値
    total_items = 0
    exclude_set: Set[int] = {int(n) for n in exclude_numbers}

    try:
        logger.info("=== 非掲載タスク開始: %s ===", task_id)

        # 初期状態確保
        db_task_snapshot = crud_task.get_task_by_id(db, task_uuid)
        total_items = db_task_snapshot.total_items if db_task_snapshot else 0

        setting = crud_setting.get_setting_by_id(db, setting_id)
        if not setting or setting.user_id != user_id:
            raise Exception("SALON BOARD設定が見つかりません")

        sb_password = decrypt_password(setting.encrypted_sb_password)

        selectors = load_selectors()
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_dir = str(SCREENSHOT_DIR)

        unpublisher = SalonBoardStyleUnpublisher(
            selectors=selectors,
            screenshot_dir=screenshot_dir,
            headless=not settings.USE_HEADFUL_MODE,
            slow_mo=100,
        )

        def progress_callback(
            completed: int,
            total: int,
            *,
            detail: Optional[Dict[str, Any]] = None,
            error: Optional[Dict[str, Any]] = None,
        ) -> None:
            nonlocal total_items
            self.ensure_not_cancelled(task_uuid)

            if total and total > total_items:
                total_items = total

            if detail is not None:
                # MonitoredTask.record_detail を利用
                stage = detail.pop("stage", "PROGRESS")
                stage_label = detail.pop("stage_label", "")
                message = detail.pop("message", "")
                status_text = detail.pop("status", "running")
                
                current_idx = detail.pop("current_index", completed)
                total_val = detail.pop("total", total_items or total)
                style_num = detail.pop("style_number", None)

                self.record_detail(
                    task_uuid=task_uuid,
                    stage=stage,
                    stage_label=stage_label,
                    message=message,
                    status_text=status_text,
                    current_index=current_idx,
                    total=total_val,
                    style_number=style_num,
                    extra=detail
                )

            crud_task.update_task_progress(db, task_uuid, completed)
            if error:
                crud_task.add_task_error(db, task_uuid, error)

        salon_info = None
        if setting.salon_id or setting.salon_name:
            salon_info = {
                "id": setting.salon_id,
                "name": setting.salon_name,
            }

        unpublisher.run_unpublish(
            user_id=setting.sb_user_id,
            password=sb_password,
            salon_top_url=salon_url,
            range_start=range_start,
            range_end=range_end,
            exclude_numbers=exclude_set,
            salon_info=salon_info,
            progress_callback=progress_callback,
        )

        # 完了処理
        crud_task.update_task_status(db, task_uuid, "SUCCESS")
        
        final_snapshot = crud_task.get_task_by_id(db, task_uuid)
        final_completed = final_snapshot.completed_items if final_snapshot else total_items
        final_total = final_snapshot.total_items if final_snapshot else total_items

        self.record_detail(
            task_uuid=task_uuid,
            stage="COMPLETED",
            stage_label="タスク完了",
            message="指定範囲の非掲載処理が完了しました",
            status_text="success",
            current_index=final_completed,
            total=final_total
        )
        logger.info("=== 非掲載タスク完了: %s ===", task_id)

    except TaskCancelledError as cancel_error:
        self.handle_cancel(task_uuid, task_id, cancel_error, completed_items=0, total_items=total_items)
        raise

    except Exception as e:
        # コンテキスト作成
        error_context = None
        screenshot_path = ""
        if isinstance(e, (StylePostError, StyleUnpublishError)):
            screenshot_path = getattr(e, "screenshot_path", "") or ""
            if screenshot_path:
                logger.warning("スクリーンショット: %s", screenshot_path)
        
        error_context = {
            "row_number": 0,
            "style_name": "非掲載エラー",
            "field": "非掲載処理",
            "reason": str(e),
            "screenshot_path": screenshot_path,
        }
        
        # 汎用例外の場合でscreenshot_pathが無い場合の情報補完
        if not isinstance(e, (StylePostError, StyleUnpublishError)):
             error_context["reason"] = f"予期せぬエラー: {str(e)}"

        self.handle_failure(
            task_uuid=task_uuid, 
            task_id=task_id, 
            error=e, 
            completed_items=0, 
            total_items=total_items, 
            error_context=error_context
        )
        raise


def cleanup_screenshots(
    directory: Path,
    retention_days: int,
    max_bytes: int,
    current_time: datetime | None = None
) -> Dict[str, int]:
    """
    スクリーンショットディレクトリをクリーンアップ

    Args:
        directory: 対象ディレクトリ
        retention_days: 保持日数（負数で保持期限なし）
        max_bytes: 最大許容サイズ（0以下で制限なし）
        current_time: テスト用現在時刻

    Returns:
        Dict[str, int]: 削除・残存ファイルに関する統計情報
    """
    metrics: Dict[str, int] = {
        "removed_files": 0,
        "removed_bytes": 0,
        "remaining_files": 0,
        "remaining_bytes": 0,
    }

    directory = Path(directory)
    if not directory.exists():
        return metrics

    now = current_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    cutoff = None
    if retention_days is not None and retention_days >= 0:
        cutoff = now - timedelta(days=retention_days)

    files_with_stats = []
    for file_path in directory.rglob("*"):
        if file_path.is_file():
            try:
                stat = file_path.stat()
            except FileNotFoundError:
                continue
            files_with_stats.append((file_path, stat))

    remaining = []
    for file_path, stat in files_with_stats:
        if cutoff is not None:
            file_mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            if file_mtime < cutoff:
                try:
                    file_path.unlink()
                    metrics["removed_files"] += 1
                    metrics["removed_bytes"] += stat.st_size
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    logger.warning("スクリーンショット削除に失敗しました: %s (%s)", file_path, exc)
                continue
        remaining.append((file_path, stat))

    total_size = sum(stat.st_size for _, stat in remaining)

    if max_bytes is not None and max_bytes > 0 and total_size > max_bytes:
        remaining.sort(key=lambda item: item[1].st_mtime)
        kept = []
        for file_path, stat in remaining:
            if total_size <= max_bytes:
                kept.append((file_path, stat))
                continue
            try:
                file_path.unlink()
                metrics["removed_files"] += 1
                metrics["removed_bytes"] += stat.st_size
                total_size -= stat.st_size
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("スクリーンショット削除に失敗しました: %s (%s)", file_path, exc)
                kept.append((file_path, stat))
        remaining = kept

    # 空ディレクトリを削除
    for subdir in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not subdir.is_dir() or subdir == directory:
            continue
        try:
            if not any(subdir.iterdir()):
                subdir.rmdir()
        except OSError:
            continue

    metrics["remaining_files"] = len(remaining)
    metrics["remaining_bytes"] = total_size
    return metrics


@celery_app.task(name="cleanup_screenshots")
def cleanup_screenshots_task() -> Dict[str, int]:
    """
    スクリーンショットの定期クリーンアップタスク
    """
    result = cleanup_screenshots(
        directory=SCREENSHOT_DIR,
        retention_days=settings.SCREENSHOT_RETENTION_DAYS,
        max_bytes=settings.SCREENSHOT_DIR_MAX_BYTES,
    )
    logger.info(
        "スクリーンショットクリーンアップ完了: removed_files=%s removed_bytes=%s remaining_files=%s remaining_bytes=%s",
        result["removed_files"],
        result["removed_bytes"],
        result["remaining_files"],
        result["remaining_bytes"],
    )
    return result

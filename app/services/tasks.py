"""
Celeryタスク定義
スタイル投稿処理の非同期実行
"""
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict
from uuid import UUID

from celery import Task

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.crud import current_task as crud_task, salon_board_setting as crud_setting
from app.core.security import decrypt_password
from app.services.style_poster import SalonBoardStylePoster, StylePostError, load_selectors

logger = logging.getLogger(__name__)
SCREENSHOT_DIR = Path(settings.SCREENSHOT_DIR)


class DatabaseTask(Task):
    """データベースセッションを管理するベースタスククラス"""
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask, name="process_style_post")
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

    Args:
        self: Celeryタスクインスタンス
        task_id: タスクID（UUID文字列）
        user_id: ユーザーID
        setting_id: SALON BOARD設定ID
        style_data_filepath: アップロードされたスタイル情報ファイルパス
        image_dir: アップロードされた画像ディレクトリパス
    """
    task_uuid = UUID(task_id)
    db = self.db

    try:
        print(f"=== タスク開始: {task_id} ===")

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
            headless=True,
            slow_mo=100
        )

        # 進捗コールバック関数
        def progress_callback(completed: int, total: int, error: dict = None):
            """
            進捗更新とエラー記録

            Args:
                completed: 完了件数
                total: 総件数
                error: エラー情報（任意）
            """
            # 中止リクエスト確認
            task_record = crud_task.get_task_by_id(db, task_uuid)
            if task_record and task_record.status == "CANCELLING":
                print("中止リクエスト検出 - 処理を停止します")
                raise Exception("タスクが中止されました")

            # 進捗更新
            crud_task.update_task_progress(db, task_uuid, completed)

            # エラー記録
            if error:
                crud_task.add_task_error(db, task_uuid, error)

        # Playwrightタスク実行
        poster.run(
            user_id=setting.sb_user_id,
            password=sb_password,
            data_filepath=style_data_filepath,
            image_dir=image_dir,
            salon_info=salon_info,
            progress_callback=progress_callback
        )

        # 成功ステータス更新
        crud_task.update_task_status(db, task_uuid, "SUCCESS")
        print(f"=== タスク完了: {task_id} ===")

    except Exception as e:
        print(f"=== タスクエラー: {task_id} - {e} ===")

        # 中止リクエストによる例外かチェック
        if "タスクが中止されました" in str(e) or "cancelled" in str(e).lower():
            print("タスクが正常に中止されました")
            # 中止ステータスに更新（CANCELLING → FAILURE）
            crud_task.update_task_status(db, task_uuid, "FAILURE")
        else:
            # 通常のエラー処理
            crud_task.update_task_status(db, task_uuid, "FAILURE")

            # スクリーンショットパスを取得（StylePostErrorの場合）
            screenshot_path = ""
            if isinstance(e, StylePostError):
                screenshot_path = e.screenshot_path
                print(f"スクリーンショット: {screenshot_path}")

            # エラー情報記録（致命的エラー）
            crud_task.add_task_error(db, task_uuid, {
                "row_number": 0,
                "style_name": "システムエラー",
                "field": "タスク全体",
                "reason": str(e),
                "screenshot_path": screenshot_path
            })

        raise

    finally:
        # アップロードファイルのクリーンアップ
        try:
            if os.path.exists(style_data_filepath):
                os.remove(style_data_filepath)
                print(f"✓ スタイルデータファイル削除: {style_data_filepath}")

            if os.path.exists(image_dir):
                shutil.rmtree(image_dir)
                print(f"✓ 画像ディレクトリ削除: {image_dir}")
        except Exception as cleanup_error:
            print(f"✗ クリーンアップエラー: {cleanup_error}")


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

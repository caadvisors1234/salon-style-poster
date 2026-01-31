"""
Celeryタスクの共通基底クラス定義
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

from celery import Task
from app.db.session import SessionLocal
from app.crud import current_task as crud_task

logger = logging.getLogger(__name__)


class TaskCancelledError(Exception):
    """ユーザーによってキャンセルされたことを示す例外"""
    pass


class MonitoredTask(Task):
    """
    DBセッション管理とタスクモニタリング機能を提供する基底クラス
    """
    _db = None

    @property
    def db(self):
        """DBセッションプロパティ（遅延初期化）"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """タスク終了時のクリーンアップ"""
        if self._db is not None:
            self._db.close()
            self._db = None

    @staticmethod
    def utc_now_iso() -> str:
        """現在時刻（UTC）のISO8601文字列を返す"""
        return datetime.now(timezone.utc).isoformat()

    def record_detail(
        self,
        task_uuid: UUID,
        stage: str,
        stage_label: str,
        message: str,
        *,
        status_text: str = "running",
        current_index: Optional[int] = None,
        total: Optional[int] = None,
        # style_post用
        style_name: Optional[str] = None,
        # delete用
        style_number: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
        total_items_override: Optional[int] = None
    ) -> None:
        """
        進捗詳細情報をDBに保存する共通メソッド
        """
        detail_payload: Dict[str, Any] = {
            "stage": stage,
            "stage_label": stage_label,
            "message": message,
            "status": status_text,
            "updated_at": self.utc_now_iso()
        }

        if current_index is not None:
            detail_payload["current_index"] = current_index

        # 特定フィールドの設定
        if style_name is not None:
            detail_payload["style_name"] = style_name
        if style_number is not None:
            detail_payload["style_number"] = style_number

        # totalの設定ロジック
        if total is not None:
            detail_payload["total"] = total
        elif total_items_override is not None:
            detail_payload["total"] = total_items_override

        if extra:
            detail_payload.update(extra)

        try:
            crud_task.update_task_detail(self.db, task_uuid, detail_payload)
        except Exception as e:
            # ログ記録のみ行い、タスク自体は止めない
            logger.warning(f"Failed to record task detail: {e}")

    def record_success(
        self,
        task_uuid: UUID,
        row_number: int,
        style_name: str,
        image_name: Optional[str] = None,
        stylist_name: Optional[str] = None,
        category: Optional[str] = None,
        length: Optional[str] = None
    ) -> None:
        """
        成功したスタイル情報をDBに保存する共通メソッド

        Args:
            task_uuid: タスクID
            row_number: CSVファイルの行番号
            style_name: スタイル名
            image_name: 画像ファイル名
            stylist_name: スタイリスト名
            category: カテゴリ
            length: 長さ
        """
        success_payload: Dict[str, Any] = {
            "row_number": row_number,
            "style_name": style_name
        }

        if image_name is not None:
            success_payload["image_name"] = image_name
        if stylist_name is not None:
            success_payload["stylist_name"] = stylist_name
        if category is not None:
            success_payload["category"] = category
        if length is not None:
            success_payload["length"] = length

        try:
            crud_task.add_task_success(self.db, task_uuid, success_payload)
        except Exception as e:
            # ログ記録のみ行い、タスク自体は止めない
            logger.warning(f"Failed to record task success: {e}")

    def ensure_not_cancelled(self, task_uuid: UUID) -> Any:
        """
        ユーザーからのキャンセル要求をチェックする
        
        Returns:
            task_record: 最新のタスクレコード
        
        Raises:
            TaskCancelledError: キャンセル要求があった場合
        """
        task_record = crud_task.get_task_by_id(self.db, task_uuid)
        
        # キャンセル要求中(CANCELLING)または既に失敗(FAILURE)の場合
        if task_record and task_record.status in {"CANCELLING", "FAILURE"}:
            self.record_detail(
                task_uuid=task_uuid,
                stage="CANCELLING",
                stage_label="キャンセル要求中",
                message="キャンセル要求を検出したため処理を停止します",
                status_text="cancelling",
                current_index=task_record.completed_items,
                total=task_record.total_items,
            )
            # 既にキャンセル済み例外を投げる
            raise TaskCancelledError("Task was cancelled by user")
            
        return task_record

    def handle_cancel(
        self, 
        task_uuid: UUID, 
        task_id: str, 
        cancel_error: TaskCancelledError,
        completed_items: int = 0,
        total_items: int = 0
    ):
        """キャンセル発生時の共通処理"""
        logger.info("=== タスクキャンセル: %s - %s ===", task_id, cancel_error)
        crud_task.update_task_status(self.db, task_uuid, "FAILURE") # UI上の扱いはFAILUREまたはCANCELLED
        
        # 直前の状態を取得して記録
        snapshot = crud_task.get_task_by_id(self.db, task_uuid)
        current = snapshot.completed_items if snapshot else completed_items
        total = snapshot.total_items if snapshot else total_items
        
        self.record_detail(
            task_uuid=task_uuid,
            stage="CANCELLED",
            stage_label="タスクは中止されました",
            message="ユーザー操作によりタスクを中止しました",
            status_text="cancelled",
            current_index=current,
            total=total
        )

    def handle_failure(
        self,
        task_uuid: UUID,
        task_id: str,
        error: Exception,
        completed_items: int = 0,
        total_items: int = 0,
        error_context: Optional[Dict[str, Any]] = None
    ):
        """汎用エラー発生時の共通処理"""
        logger.exception("=== タスクエラー: %s ===", task_id)

        # 例外メッセージにキャンセルや中止が含まれる場合のフォールバック
        if "タスクが中止されました" in str(error) or "cancelled" in str(error).lower():
            logger.info("タスクが正常に中止されました（例外メッセージ検知）")
            self.handle_cancel(task_uuid, task_id, TaskCancelledError(str(error)), completed_items, total_items)
            return

        # 通常エラー
        crud_task.update_task_status(self.db, task_uuid, "FAILURE")
        
        # エラー詳細の記録（呼び出し元でscreenshot_pathなどを指定してcrud_task.add_task_errorしてる前提だが、
        # ここで最小限の記録をするか、呼び出し元に任せるか。
        # 今回は add_task_error は呼び出し元で行う設計（コンテキスト依存が強いため））
        
        if error_context:
            crud_task.add_task_error(self.db, task_uuid, error_context)

        snapshot = crud_task.get_task_by_id(self.db, task_uuid)
        current = snapshot.completed_items if snapshot else completed_items
        total = snapshot.total_items if snapshot else total_items

        self.record_detail(
            task_uuid=task_uuid,
            stage="FAILED",
            stage_label="タスク失敗",
            message="エラーが発生したためタスクを終了しました",
            status_text="error",
            current_index=current,
            total=total,
            extra={"error_reason": str(error)}
        )

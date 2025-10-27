"""
Celeryタスク定義
スタイル投稿処理の非同期実行
"""
import os
import shutil
from uuid import UUID
from celery import Task

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.crud import current_task as crud_task, salon_board_setting as crud_setting
from app.core.security import decrypt_password
from app.services.style_poster import SalonBoardStylePoster, StylePostError, load_selectors


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
        screenshot_dir = "app/static/screenshots"

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

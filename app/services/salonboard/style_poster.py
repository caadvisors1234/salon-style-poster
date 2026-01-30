"""
SALON BOARD スタイル自動投稿サービス
Playwrightを使用したブラウザ自動化
"""
import logging
from pathlib import Path
from typing import Callable, Dict, Optional

import pandas as pd
import yaml

from .browser_manager import SalonBoardBrowserManager
from .utils import BrowserUtilsMixin
from .login_handler import LoginHandlerMixin
from .form_handler import StyleFormHandlerMixin
from .exceptions import StylePostError

logger = logging.getLogger(__name__)


class SalonBoardStylePoster(
    StyleFormHandlerMixin,
    LoginHandlerMixin,
    BrowserUtilsMixin,
    SalonBoardBrowserManager
):
    """SALON BOARDスタイル自動投稿クラス"""

    def run(
        self,
        user_id: str,
        password: str,
        data_filepath: str,
        image_dir: str,
        salon_info: Optional[Dict] = None,
        progress_callback: Optional[Callable] = None,
        total_items: Optional[int] = None
    ):
        """
        メイン実行ロジック

        Args:
            user_id: SALON BOARDログインID
            password: SALON BOARDパスワード
            data_filepath: スタイル情報ファイルパス（CSV/Excel）
            image_dir: 画像ディレクトリパス
            salon_info: サロン情報（複数店舗用）
            progress_callback: 進捗コールバック関数
            total_items: 期待される処理件数（事前計算済みの総件数）
        """
        # credentials を保持（セッションリセット用）
        self._user_id = user_id
        self._password = password
        self._salon_info = salon_info

        self.progress_callback = progress_callback
        self.expected_total = total_items or 0

        try:
            # ブラウザ起動
            self._emit_progress(
                0,
                {
                    "stage": "BROWSER_STARTING",
                    "stage_label": "ブラウザ起動準備",
                    "message": "Playwrightを起動しています",
                    "status": "info",
                    "current_index": 0,
                    "total": self.expected_total
                }
            )
            self._start_browser()
            self._emit_progress(
                0,
                {
                    "stage": "BROWSER_READY",
                    "stage_label": "ブラウザ起動完了",
                    "message": "Playwrightの起動が完了しました",
                    "status": "info",
                    "current_index": 0,
                    "total": self.expected_total
                }
            )

            # ログイン
            self.step_login(user_id, password, salon_info)
            self._emit_progress(
                0,
                {
                    "stage": "LOGIN_COMPLETED",
                    "stage_label": "ログイン完了",
                    "message": "SALON BOARDへのログインが完了しました",
                    "status": "info",
                    "current_index": 0,
                    "total": self.expected_total
                }
            )

            # データ読み込み
            logger.info("データファイル読み込み: %s", data_filepath)
            if data_filepath.endswith(".csv"):
                df = pd.read_csv(data_filepath)
            elif data_filepath.endswith(".xlsx"):
                df = pd.read_excel(data_filepath)
            else:
                raise Exception("サポートされていないファイル形式です")

            logger.info("%s件のスタイルデータを読み込みました", len(df))
            logger.debug("データカラム: %s", list(df.columns))
            self.expected_total = len(df)
            self._emit_progress(
                0,
                {
                    "stage": "DATA_READY",
                    "stage_label": "データ読み込み完了",
                    "message": f"{self.expected_total}件のスタイルデータを読み込みました",
                    "status": "info",
                    "current_index": 0,
                    "total": self.expected_total
                }
            )

            # スタイル一覧ページへ移動
            self.step_navigate_to_style_list_page()
            self._emit_progress(
                0,
                {
                    "stage": "NAVIGATED",
                    "stage_label": "投稿準備完了",
                    "message": "スタイル一覧ページを開きました",
                    "status": "info",
                    "current_index": 0,
                    "total": self.expected_total
                }
            )

            # スタイルごとにループ処理
            image_dir_path = Path(image_dir)
            for index, row in df.iterrows():
                style_name = row.get("スタイル名", "不明")
                self._emit_progress(
                    index,
                    {
                        "stage": "STYLE_PROCESSING",
                        "stage_label": "スタイル処理中",
                        "message": f"{index + 1}/{self.expected_total}件目「{style_name}」を処理しています",
                        "status": "working",
                        "current_index": index + 1,
                        "total": self.expected_total,
                        "style_name": style_name
                    }
                )

                try:
                    logger.info("--- スタイル %s/%s 処理中 ---", index + 1, len(df))

                    # 画像パス生成
                    image_filename = row["画像名"]
                    image_path = image_dir_path / image_filename

                    if not image_path.exists():
                        raise Exception(f"画像ファイルが見つかりません: {image_filename}")
                    logger.debug("画像ファイル確認: %s (exists=%s, size=%s bytes)", image_path, image_path.exists(), image_path.stat().st_size if image_path.exists() else "n/a")

                    style_dict = row.to_dict()
                    style_dict["_row_number"] = index + 2  # CSVヘッダー分を考慮

                    # スタイル処理
                    manual_events = self.step_process_single_style(style_dict, str(image_path), index)

                    # 画像アップロード失敗検出とセッションリセット
                    image_upload_failed = any(
                        event.get("error_category") in ("IMAGE_UPLOAD_ABORTED", "ACCESS_CONGESTION")
                        for event in manual_events
                    )

                    if image_upload_failed:
                        logger.warning("画像アップロード失敗を検出、セッションをリセットします")
                        try:
                            self._reset_session_and_relogin(self._user_id, self._password, self._salon_info)
                        except Exception as reset_error:
                            logger.error("セッションリセットに失敗しました: %s", reset_error)
                            # リセット失敗しても処理を継続（次のスタイルで同じ問題が発生する可能性あり）

                    # 成功時の進捗更新
                    self._emit_progress(
                        index + 1,
                        {
                            "stage": "STYLE_COMPLETED",
                            "stage_label": "スタイル投稿完了",
                            "message": f"{index + 1}/{self.expected_total}件目「{style_name}」の投稿が完了しました",
                            "status": "completed",
                            "current_index": index + 1,
                            "total": self.expected_total,
                            "style_name": style_name
                        }
                    )

                    if manual_events:
                        for event in manual_events:
                            event.setdefault("row_number", index + 2)
                            event.setdefault("style_name", style_name)
                            event.setdefault("field", "画像アップロード")
                            event.setdefault("error_category", "IMAGE_UPLOAD_ABORTED")

                            # 画像関連のエラーの場合のみ image_name を設定
                            error_category = event.get("error_category", "")
                            if error_category in ("ACCESS_CONGESTION", "IMAGE_UPLOAD_ABORTED"):
                                event.setdefault("image_name", image_filename)

                            # error_category に基づいてメッセージを分岐
                            field_name = event.get("field", "")

                            if error_category == "ACCESS_CONGESTION":
                                # アクセス集中エラー（混雑）
                                warning_message = f"{style_name} の画像アップロード機能が混雑しているため、SALON BOARDで手動登録してください"
                            elif error_category == "IMAGE_UPLOAD_ABORTED":
                                # 画像アップロードの中断・失敗
                                warning_message = f"{style_name} の画像アップロードに失敗したため、SALON BOARDで手動登録してください"
                            elif error_category == "INPUT_FAILED":
                                # 入力処理のエラー
                                warning_message = f"{style_name} の{field_name}をSALON BOARDで手動入力してください"
                            else:
                                # その他のエラー
                                warning_message = f"{style_name} の{field_name}で問題が発生しました。SALON BOARDで確認してください"

                            self._emit_progress(
                                index + 1,
                                {
                                    "stage": "STYLE_WARNING",
                                    "stage_label": "手動対応が必要",
                                    "message": warning_message,
                                    "status": "warning",
                                    "current_index": index + 1,
                                    "total": self.expected_total,
                                    "style_name": style_name
                                },
                                error=event
                            )

                except Exception as e:
                    logger.error("エラー発生: %s", e)

                    # スクリーンショット取得（StylePostErrorの場合は既に含まれている）
                    if isinstance(e, StylePostError) and e.screenshot_path:
                        screenshot_path = e.screenshot_path
                    else:
                        screenshot_path = self._take_screenshot(f"error-row{index+1}")

                    # エラー発生時はスタイル一覧ページに戻る
                    self._navigate_back_to_style_list_after_error()

                    # エラー情報記録（呼び出し元で処理）
                    error_field = self._get_error_field_from_exception(e)

                    error_payload = {
                        "row_number": index + 2,  # ヘッダー行を考慮
                        "style_name": style_name,
                        "field": error_field,
                        "reason": str(e),
                        "screenshot_path": screenshot_path
                    }
                    self._emit_progress(
                        index + 1,
                        {
                            "stage": "STYLE_ERROR",
                            "stage_label": "スタイル投稿エラー",
                            "message": f"{index + 1}/{self.expected_total}件目「{style_name}」でエラーが発生しました",
                            "status": "error",
                            "current_index": index + 1,
                            "total": self.expected_total,
                            "style_name": style_name
                        },
                        error=error_payload
                    )

            logger.info("全スタイルの処理が完了しました")
            self._emit_progress(
                self.expected_total,
                {
                    "stage": "SUMMARY",
                    "stage_label": "処理完了",
                    "message": "全てのスタイル投稿を完了しました",
                    "status": "success",
                    "current_index": self.expected_total,
                    "total": self.expected_total
                }
            )

        except Exception as e:
            logger.exception("致命的エラー: %s", e)
            self._take_screenshot("fatal-error")
            raise

        finally:
            # ブラウザ終了
            self._close_browser()


    def _reset_session_and_relogin(
        self,
        user_id: str,
        password: str,
        salon_info: Optional[Dict] = None
    ) -> None:
        """
        セッションをリセットして再ログインする

        画像アップロード失敗時などのボット検知回避のため、
        完全に新しいセッションで再ログインを行う

        Args:
            user_id: SALON BOARDログインID
            password: SALON BOARDパスワード
            salon_info: サロン情報（複数店舗用）

        Raises:
            StylePostError: セッションリセットに失敗した場合
        """
        logger.info("セッションリセットと再ログインを開始します...")

        # 進捗通知
        self._emit_progress(
            0,
            {
                "stage": "SESSION_RESETTING",
                "stage_label": "セッションリセット中",
                "message": "ボット検知回避のためセッションをリセットしています...",
                "status": "info",
            }
        )

        try:
            # コンテキストリセット
            self._reset_browser_context()

            # 進捗通知
            self._emit_progress(
                0,
                {
                    "stage": "SESSION_RELOGGING",
                    "stage_label": "再ログイン中",
                    "message": "新しいセッションで再ログインしています...",
                    "status": "info",
                }
            )

            # 再ログイン
            self.step_login(user_id, password, salon_info)

            # スタイル一覧へ移動
            self.step_navigate_to_style_list_page()

            # 待機（サーバー側の制限解除を待つ）
            import time
            wait_seconds = 5
            logger.info("サーバー側の制限解除を待機します（%s秒）...", wait_seconds)
            time.sleep(wait_seconds)

            logger.info("セッションリセットと再ログインが完了しました")

            # 進捗通知
            self._emit_progress(
                0,
                {
                    "stage": "SESSION_RESET_COMPLETED",
                    "stage_label": "セッションリセット完了",
                    "message": "新しいセッションで処理を継続します",
                    "status": "info",
                }
            )

        except Exception as e:
            logger.error("セッションリセットに失敗しました: %s", e)
            raise StylePostError(
                f"セッションリセットに失敗しました: {e}",
                self._take_screenshot("error-session-reset")
            )


def load_selectors(yaml_path: str = "app/selectors.yaml") -> Dict:
    """
    selectors.yamlを読み込む

    Args:
        yaml_path: YAMLファイルパス

    Returns:
        Dict: セレクタ設定の辞書
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

"""
SALON BOARD ユーティリティMixin
共通ユーティリティメソッドを提供
"""
import logging
import time
from datetime import datetime
from typing import Callable, Dict, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .exceptions import StylePostError

logger = logging.getLogger(__name__)


class BrowserUtilsMixin:
    """ブラウザ操作ユーティリティMixin"""

    # 以下はSalonBoardBrowserManagerで定義される属性
    page: object
    selectors: Dict
    screenshot_dir: object
    _random: object
    progress_callback: Optional[Callable]
    expected_total: int

    def _take_screenshot(self, prefix: str = "error") -> str:
        """
        スクリーンショット撮影

        Args:
            prefix: ファイル名のプレフィックス

        Returns:
            str: 保存されたスクリーンショットのパス
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{prefix}-{timestamp}.png"
        filepath = self.screenshot_dir / filename

        if self.page:
            self.page.screenshot(path=str(filepath))
            logger.info("スクリーンショット保存: %s", filepath)
            return str(filepath)
        return ""

    def _human_pause(
        self,
        base_ms: int = 500,
        jitter_ms: int = 100,
        minimum_ms: int = 50
    ) -> None:
        """待機処理"""
        if not self.page:
            return

        # 単純な待機のみ行う
        sleep_ms = max(minimum_ms, base_ms + self._random.randint(-jitter_ms, jitter_ms))
        self.page.wait_for_timeout(sleep_ms)

    def _check_robot_detection(self) -> bool:
        """
        ロボット認証検出

        Returns:
            bool: ロボット認証が検出された場合True
        """
        robot_config = self.selectors.get("robot_detection", {})

        # セレクタチェック（visible状態のものだけ）
        for selector in robot_config.get("selectors", []):
            # 要素が存在し、かつ表示されている場合のみ検出
            locator = self.page.locator(selector)
            if locator.count() > 0:
                # 最初の要素が実際に表示されているかチェック
                try:
                    if locator.first.is_visible(timeout=1000):
                        logger.warning("ロボット認証検出（セレクタ: %s）", selector)
                        self._take_screenshot("robot-detection")
                        return True
                except Exception:
                    # タイムアウトや要素が見つからない場合は無視
                    pass

        # テキストチェック（visible状態のものだけ）
        for text in robot_config.get("texts", []):
            locator = self.page.locator(f"text={text}")
            if locator.count() > 0:
                try:
                    if locator.first.is_visible(timeout=1000):
                        logger.warning("ロボット認証検出（テキスト: %s）", text)
                        self._take_screenshot("robot-detection")
                        return True
                except Exception:
                    pass

        return False

    def _emit_progress(
        self,
        completed: int,
        detail: Optional[Dict[str, object]] = None,
        *,
        error: Optional[Dict[str, object]] = None,
        total_override: Optional[int] = None
    ) -> None:
        """進捗コールバックを通じて詳細情報を通知"""
        if not self.progress_callback:
            return

        total_value = total_override if total_override is not None else self.expected_total

        if not total_value and detail and isinstance(detail.get("total"), int):
            total_value = int(detail["total"])

        if detail is not None:
            payload = dict(detail)
            payload.setdefault("current_index", completed)
            if total_value:
                payload.setdefault("total", total_value)
            self.progress_callback(
                completed,
                total_value,
                detail=payload,
                error=error
            )
        else:
            self.progress_callback(
                completed,
                total_value,
                detail=None,
                error=error
            )

    def _click_and_wait(
        self,
        selector: str,
        click_timeout: Optional[int] = None,
        load_timeout: Optional[int] = None,
        load_state: str = "domcontentloaded",
    ):
        """
        クリック＆待機（ページ遷移対応）

        Args:
            selector: クリックする要素のセレクタ
            click_timeout: クリック操作のタイムアウト（ミリ秒）、Noneの場合はデフォルト値
            load_timeout: ページ読み込みのタイムアウト（ミリ秒）、Noneの場合はデフォルト値
        """
        click_timeout = click_timeout or self.TIMEOUT_CLICK
        load_timeout = load_timeout or self.TIMEOUT_LOAD

        logger.debug(
            "クリック準備: selector=%s, click_timeout=%sms, load_timeout=%sms, load_state=%s",
            selector,
            click_timeout,
            load_timeout,
            load_state,
        )
        self._human_pause()
        self.page.locator(selector).first.click(timeout=click_timeout)
        self._human_pause(base_ms=600, jitter_ms=200)
        self.page.wait_for_load_state(load_state, timeout=load_timeout)
        self._human_pause(base_ms=800, jitter_ms=250)
        logger.debug("クリック完了: selector=%s", selector)

        if self._check_robot_detection():
            raise Exception("ロボット認証が検出されました")

    def _wait_for_dashboard_ready(
        self,
        *,
        timeout_ms: int = 60000,
        header_selector: str = "#headerNavigationBar",
        dashboard_selector: Optional[str] = None,
    ) -> bool:
        """
        ダッシュボード（ヘッダー）表示をポーリングで確認する

        Args:
            timeout_ms: タイムアウト
            header_selector: ヘッダーのセレクタ
            dashboard_selector: セレクタ設定上のダッシュボード識別子

        Returns:
            bool: 表示を確認できた場合 True
        """
        if not self.page:
            return False

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        check_interval_ms = 1000

        while time.monotonic() < deadline:
            try:
                if self.page.locator(header_selector).first.is_visible(timeout=2000):
                    logger.info("ヘッダー検出: %s", header_selector)
                    return True
            except Exception:
                pass

            if dashboard_selector:
                try:
                    if self.page.locator(dashboard_selector).first.is_visible(timeout=2000):
                        logger.info("ダッシュボードナビ検出: %s", dashboard_selector)
                        return True
                except Exception:
                    pass

            # デバッグ情報
            try:
                current_url = self.page.url
                title = self.page.title()
            except Exception:
                current_url = "(unavailable)"
                title = "(unavailable)"
            logger.debug(
                "ダッシュボード待機中: url=%s title=%s",
                current_url,
                title,
            )
            self.page.wait_for_timeout(check_interval_ms)

        return False

    def _wait_for_upload_completion(
        self,
        upload_area_selector: str,
        modal_selector: str,
        timeout_ms: int = 30000
    ) -> None:
        """
        画像アップロード完了をDOMシグナルで確認する
        """
        if not self.page:
            raise Exception("ページが初期化されていません")

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        poll_ms = 600
        last_log = 0.0

        while time.monotonic() < deadline:
            modal_visible = False
            try:
                modal = self.page.locator(modal_selector)
                if modal.count() > 0:
                    modal_visible = modal.first.is_visible(timeout=500)
            except Exception:
                modal_visible = False

            preview_ok = False
            src_text = ""
            bg_image = ""
            try:
                upload_area = self.page.locator(upload_area_selector)
                if upload_area.count() > 0:
                    src_text = upload_area.first.get_attribute("src") or ""
                    try:
                        bg_image = upload_area.first.evaluate(
                            "el => (window.getComputedStyle(el).backgroundImage || '')"
                        ) or ""
                    except Exception:
                        bg_image = ""
                    if src_text and "noimage" not in src_text.lower():
                        preview_ok = True
                    if "url(" in bg_image.lower() and "noimage" not in bg_image.lower():
                        preview_ok = True
            except Exception:
                pass

            if not modal_visible and preview_ok:
                logger.info("画像アップロード後のプレビューを確認しました")
                return

            now = time.monotonic()
            if now - last_log > 2.5:
                logger.debug(
                    "アップロード完了待機中: modal_visible=%s src=%s bg=%s",
                    modal_visible,
                    src_text[:120],
                    bg_image[:120],
                )
                last_log = now

            self.page.wait_for_timeout(poll_ms)

        raise Exception(f"画像アップロード完了を確認できませんでした (timeout={timeout_ms}ms)")

    def _get_error_field_from_exception(self, e: Exception) -> str:
        """
        例外からエラーフィールドを判定

        Args:
            e: 発生した例外

        Returns:
            str: エラーフィールド名
        """
        if not isinstance(e, StylePostError):
            return "処理全体"

        error_msg = str(e)
        if "スタイリスト名の選択" in error_msg:
            return "スタイリスト選択"
        elif "クーポンの選択" in error_msg:
            return "クーポン選択"
        elif "カテゴリ/長さの選択" in error_msg:
            return "カテゴリ/長さ"
        elif "画像アップロード" in error_msg:
            return "画像アップロード"
        elif "テキスト入力" in error_msg:
            return "テキスト入力"
        elif "ハッシュタグの入力" in error_msg:
            return "ハッシュタグ"
        elif "登録の完了" in error_msg:
            return "登録完了"
        elif "新規登録ページへの移動" in error_msg:
            return "新規登録ページ移動"
        elif "スタイル一覧への戻り" in error_msg:
            return "一覧ページへの戻り"
        else:
            return "処理全体"

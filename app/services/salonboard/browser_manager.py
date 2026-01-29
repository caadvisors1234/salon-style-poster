"""
SALON BOARD ブラウザ管理基底クラス
Camoufoxを使用したブラウザ自動化の基盤
"""
import logging
import random
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional

from camoufox.sync_api import Camoufox

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Request

from .constants import (
    TIMEOUT_CLICK,
    TIMEOUT_LOAD,
    TIMEOUT_IMAGE_UPLOAD,
    TIMEOUT_WAIT_ELEMENT,
    TIMEOUT_PAGE_TRANSITION,
    IMAGE_PROCESSING_WAIT,
    WAIT_SHORT_BASE,
    WAIT_MEDIUM_BASE,
    WAIT_LONG_BASE,
    WAIT_JITTER_DEFAULT,
    WAIT_MIN_DEFAULT,
    HUMAN_BASE_WAIT_MS,
    HUMAN_JITTER_MS,
    HUMAN_MIN_WAIT_MS,
)

logger = logging.getLogger(__name__)


class SalonBoardBrowserManager:
    """SALON BOARDブラウザ管理基底クラス"""

    # タイムアウト定数（ミリ秒）- クラス属性として公開
    TIMEOUT_CLICK = TIMEOUT_CLICK
    TIMEOUT_LOAD = TIMEOUT_LOAD
    TIMEOUT_IMAGE_UPLOAD = TIMEOUT_IMAGE_UPLOAD
    TIMEOUT_WAIT_ELEMENT = TIMEOUT_WAIT_ELEMENT
    TIMEOUT_PAGE_TRANSITION = TIMEOUT_PAGE_TRANSITION
    IMAGE_PROCESSING_WAIT = IMAGE_PROCESSING_WAIT

    # 待機時間定数（ミリ秒）
    WAIT_SHORT_BASE = WAIT_SHORT_BASE
    WAIT_MEDIUM_BASE = WAIT_MEDIUM_BASE
    WAIT_LONG_BASE = WAIT_LONG_BASE
    WAIT_JITTER_DEFAULT = WAIT_JITTER_DEFAULT
    WAIT_MIN_DEFAULT = WAIT_MIN_DEFAULT

    HUMAN_BASE_WAIT_MS = HUMAN_BASE_WAIT_MS
    HUMAN_JITTER_MS = HUMAN_JITTER_MS
    HUMAN_MIN_WAIT_MS = HUMAN_MIN_WAIT_MS

    def __init__(
        self,
        selectors: Dict,
        screenshot_dir: str,
        headless: bool = True,
        slow_mo: int = 100
    ):
        """
        初期化

        Args:
            selectors: selectors.yamlから読み込まれたセレクタ設定
            screenshot_dir: エラー時のスクリーンショット保存先ディレクトリ
            headless: ヘッドレスモードで実行するか
            slow_mo: 操作間の遅延時間（ミリ秒）
        """
        self.selectors = selectors
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.slow_mo = slow_mo

        self._random = random.Random()
        self._camoufox: Optional[Camoufox] = None
        self.browser: Optional["Browser"] = None
        self.context: Optional["BrowserContext"] = None
        self.page: Optional["Page"] = None
        self.progress_callback: Optional[Callable] = None
        self._last_failed_upload_reason: Optional[str] = None
        self.expected_total: int = 0

    def _create_page(self) -> "Page":
        """セッションを維持した新規ページ生成"""
        if not self.context:
            raise Exception("ブラウザコンテキストが初期化されていません")
        page = self.context.new_page()
        page.on("requestfailed", self._handle_request_failed)
        page.set_default_timeout(180000)
        return page

    def _recreate_page(self) -> "Page":
        """ページ再生成（セッション維持）"""
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass
            finally:
                self.page = None

        if self.context:
            self.page = self._create_page()
            return self.page

        # コンテキストが失われた場合は再起動
        self._start_browser()
        return self.page

    def _handle_request_failed(self, request: "Request"):
        """HTTPリクエスト失敗のモニタリング"""
        # request.failure がメソッドの場合とプロパティの場合を考慮
        failure_attr = getattr(request, "failure", None)
        failure_text = failure_attr() if callable(failure_attr) else failure_attr

        if not failure_text:
            return
        url = request.url
        if "/CNB/imgreg/imgUpload/" in url:
            message = f"{url} -> {failure_text}"
            self._last_failed_upload_reason = message
            logger.warning("リクエスト失敗検出: %s", message)

    def _start_browser(self):
        """ブラウザ起動（Camoufox版）"""
        self._camoufox = Camoufox(
            headless=self.headless,
            slow_mo=self.slow_mo,
            os="windows",
            locale="ja-JP",
            humanize=True,
            block_webrtc=True,
        )

        # start() メソッドが内部的に __enter__() を呼び出す
        self.browser = self._camoufox.start()
        self.context = self.browser.new_context()
        self.page = self._create_page()

        logger.info("ブラウザ起動完了（Camoufox）")

    def _close_browser(self):
        """ブラウザ終了（Camoufox版）"""
        if self.page:
            try:
                self.page.close()
            except Exception as e:
                logger.warning("ページ終了時に警告: %s", e)
            finally:
                self.page = None

        if self.context:
            try:
                self.context.close()
            except Exception as e:
                logger.warning("ブラウザコンテキスト終了時に警告: %s", e)
            finally:
                self.context = None

        if self._camoufox:
            try:
                self._camoufox.__exit__(None, None, None)
            except Exception as e:
                logger.warning("ブラウザ終了時に警告: %s", e)
            finally:
                self._camoufox = None
                self.browser = None

        logger.info("ブラウザ終了（Camoufox）")

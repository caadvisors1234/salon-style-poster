"""
SALON BOARD ブラウザ管理基底クラス
Playwrightを使用したブラウザ自動化の基盤
"""
import logging
import random
from pathlib import Path
from typing import Callable, Dict, Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Request,
    sync_playwright,
)
from playwright_stealth import stealth_sync

from .constants import (
    TIMEOUT_CLICK,
    TIMEOUT_LOAD,
    TIMEOUT_IMAGE_UPLOAD,
    TIMEOUT_WAIT_ELEMENT,
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
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.progress_callback: Optional[Callable] = None
        self._last_failed_upload_reason: Optional[str] = None
        self.expected_total: int = 0

    def _create_page(self) -> Page:
        """セッションを維持した新規ページ生成"""
        if not self.context:
            raise Exception("ブラウザコンテキストが初期化されていません")
        page = self.context.new_page()
        page.on("requestfailed", self._handle_request_failed)
        stealth_sync(page)
        page.set_default_timeout(180000)
        return page

    def _recreate_page(self) -> Page:
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

    def _handle_request_failed(self, request: Request):
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
        """ブラウザ起動"""
        self.playwright = sync_playwright().start()

        launch_kwargs = {
            "headless": self.headless,
            "slow_mo": self.slow_mo,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--disable-features=WebRtcHideLocalIpsWithMdns",
            ],
            # 自動化制御のフラグを除外
            "ignore_default_args": ["--enable-automation"],
        }

        # Chromeチャンネルを優先使用。失敗時はバンドルChromium。
        try:
            self.browser = self.playwright.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception:
            self.browser = self.playwright.chromium.launch(**launch_kwargs)

        # 固定のWindows User-Agentを使用（指紋の一貫性のため）
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        extra_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
            "accept-encoding": "gzip, deflate, br, zstd",
            "sec-ch-ua": '"Google Chrome";v="120", "Chromium";v="120", "Not=A?Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "upgrade-insecure-requests": "1",
        }
        context_kwargs = {
            "viewport": {"width": 1280, "height": 960},
            "user_agent": user_agent,
            "locale": "ja-JP",
            "timezone_id": "Asia/Tokyo",
            "accept_downloads": True,
            "extra_http_headers": extra_headers,
        }

        self.context = self.browser.new_context(**context_kwargs)
        self.context.add_init_script(
            """
            // 自動化フラグの隠蔽
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

            // PlatformをWindowsに偽装（Linuxコンテナ対策）
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});

            // Hardware Concurrencyの偽装（オプション）
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});

            // WebRTC / IPリーク抑止（必要最低限のスタブ）
            const denyMedia = () => Promise.reject(new Error('NotAllowedError'));
            try {
                if (navigator.mediaDevices) {
                    navigator.mediaDevices.getUserMedia = denyMedia;
                } else {
                    Object.defineProperty(navigator, 'mediaDevices', {get: () => ({ getUserMedia: denyMedia })});
                }
            } catch (_) {}
            const originalRTCPeerConnection = window.RTCPeerConnection || window.webkitRTCPeerConnection;
            if (originalRTCPeerConnection) {
                const Wrapped = function(config) {
                    const pc = new originalRTCPeerConnection(config);
                    try { pc.getTransceivers = () => []; } catch (_) {}
                    return pc;
                };
                Wrapped.prototype = originalRTCPeerConnection.prototype;
                window.RTCPeerConnection = Wrapped;
                window.webkitRTCPeerConnection = Wrapped;
            }
            """
        )

        # 新しいページ作成
        self.page = self._create_page()

        logger.info("ブラウザ起動完了")

    def _close_browser(self):
        """ブラウザ終了"""
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                logger.warning("ブラウザコンテキスト終了時に警告: %s", e)
            finally:
                self.context = None
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("ブラウザ終了")

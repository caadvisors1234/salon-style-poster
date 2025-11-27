"""
SALON BOARD スタイル自動投稿サービス
Playwrightを使用したブラウザ自動化
"""
import logging
import yaml
import pandas as pd
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable
from playwright.sync_api import (
    sync_playwright,
    Page,
    Browser,
    Playwright,
    BrowserContext,
    Response,
    Request,
    TimeoutError as PlaywrightTimeoutError,
)
from playwright_stealth import stealth_sync

logger = logging.getLogger(__name__)


class StylePostError(Exception):
    """スタイル投稿エラー（スクリーンショット情報付き）"""
    def __init__(self, message: str, screenshot_path: str = ""):
        super().__init__(message)
        self.screenshot_path = screenshot_path


class SalonBoardStylePoster:
    """SALON BOARDスタイル自動投稿クラス"""

    # タイムアウト定数（ミリ秒）
    TIMEOUT_CLICK = 10000  # クリック操作
    TIMEOUT_LOAD = 30000   # ページ読み込み
    TIMEOUT_IMAGE_UPLOAD = 60000  # 画像アップロード
    TIMEOUT_WAIT_ELEMENT = 10000  # 要素待機
    IMAGE_PROCESSING_WAIT = 3  # 画像処理待機（秒）
    HUMAN_BASE_WAIT_MS = 700  # 人間らしい基本待機（ミリ秒）
    HUMAN_JITTER_MS = 350  # 人間らしい待機のばらつき（ミリ秒）
    HUMAN_MIN_WAIT_MS = 250  # 最小待機時間（ミリ秒）

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

    def _start_browser(self):
        """ブラウザ起動"""
        logger.info("ブラウザを起動中...")
        self.playwright = sync_playwright().start()

        launch_kwargs = {
            "headless": self.headless,
            "slow_mo": self.slow_mo,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--ignore-certificate-errors",
                "--disable-features=PrivacySandboxSettings3",
                "--disable-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        }

        try:
            self.browser = self.playwright.chromium.launch(channel="chrome", **launch_kwargs)
            logger.info("ChromeチャンネルのChromiumを使用します")
        except Exception as channel_error:
            logger.warning("Chromeチャンネル起動に失敗: %s。Playwright同梱Chromiumで再試行します。", channel_error)
            self.browser = self.playwright.chromium.launch(**launch_kwargs)

        # モバイル実機に近いブラウザコンテキスト作成（自動化検知対策）
        self.context = self.browser.new_context(
            viewport={"width": 1366, "height": 768},  # 一般的なデスクトップ解像度
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            device_scale_factor=1.0,
            is_mobile=False,
            has_touch=False,
            locale="ja-JP",
            timezone_id="Asia/Tokyo"
        )
        self.context.set_extra_http_headers(
            {
                "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
                "Upgrade-Insecure-Requests": "1",
                "DNT": "1",
                "Sec-CH-UA": "\"Google Chrome\";v=\"120\", \"Chromium\";v=\"120\", \"Not:A-Brand\";v=\"99\"",
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": "\"Linux\"",
            }
        )

        # WebDriverフラグやデバイス情報を人間と揃える
        self.context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'platform', {get: () => 'Linux x86_64'});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            """
        )

        # 新しいページ作成
        self.page = self.context.new_page()
        self.page.on("requestfailed", self._handle_request_failed)
        self.page.on("response", self._handle_response)
        self.page.on("request", self._handle_request)
        stealth_sync(self.page)

        # デフォルトタイムアウト設定（3分）
        self.page.set_default_timeout(180000)

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

    def _handle_request_failed(self, request: Request):
        """HTTPリクエスト失敗のモニタリング"""
        failure_text = getattr(request, "failure", None)
        if not failure_text:
            return
        url = request.url
        if "/CNB/imgreg/imgUpload/" in url:
            message = f"{url} -> {failure_text}"
            self._last_failed_upload_reason = message
            logger.warning("リクエスト失敗検出: %s", message)

    def _handle_request(self, request: Request):
        """Akamai関連リクエストの観測"""
        url = request.url
        if any(token in url for token in ("bm-verify", "_abck", "akamai")):
            logger.info("Akamaiリクエスト観測: %s (%s)", url, request.method)

    def _handle_response(self, response: Response):
        """Akamai関連レスポンスの観測"""
        url = response.url
        if any(token in url for token in ("bm-verify", "_abck", "akamai")):
            try:
                body_hint = ""
                if response.status >= 400:
                    body_hint = f", body={response.text()[:120]}"
                logger.info("Akamaiレスポンス観測: %s (status=%s%s)", url, response.status, body_hint)
            except Exception:
                logger.info("Akamaiレスポンス観測: %s (status=%s)", url, response.status)

    def _get_cookie_value(self, name: str) -> Optional[str]:
        """ブラウザコンテキストから特定Cookie値を取得"""
        if not self.context:
            return None
        try:
            cookies = self.context.cookies()
        except Exception as e:
            logger.warning("Cookie取得に失敗しました (%s): %s", name, e)
            return None
        for cookie in cookies:
            if cookie.get("name") == name:
                return cookie.get("value")
        return None

    def _summarize_abck_value(self, value: Optional[str]) -> str:
        """_abckクッキーの状態を簡易表現に整形"""
        if value is None:
            return "not-set"
        if "~0~" in value:
            return "~0~ (cleared)"
        if "~-1~" in value:
            return "~-1~ (pending)"
        if "~1~" in value:
            return "~1~ (grace)"
        suffix = value[-8:] if len(value) > 8 else value
        return f"{suffix} (raw)"

    def _stimulate_akamai_sensor(self):
        """ユーザー操作に近いイベントでAkamaiセンサーを刺激"""
        if not self.page:
            return

        viewport = self.page.viewport_size or {"width": 412, "height": 915}
        width = viewport.get("width", 412)
        height = viewport.get("height", 915)

        # タッチ・スクロール・ジャイロ等のイベントを順番に送る
        for _ in range(2):
            x = self._random.randint(int(width * 0.2), int(width * 0.8))
            y = self._random.randint(int(height * 0.2), int(height * 0.8))
            try:
                self.page.touchscreen.tap(x, y)
            except Exception:
                pass
            try:
                self.page.mouse.move(x, y, steps=5)
                self.page.mouse.wheel(0, self._random.randint(200, 600))
            except Exception:
                pass
            self.page.wait_for_timeout(200)

        try:
            self.page.evaluate(
                """
                () => {
                    window.dispatchEvent(new Event('deviceorientation'));
                    window.dispatchEvent(new Event('devicemotion'));
                    document.body && document.body.dispatchEvent(new Event('touchstart'));
                }
                """
            )
        except Exception:
            pass

        self._human_pause(base_ms=900, jitter_ms=260, minimum_ms=500)

    def _warmup_akamai_endpoints(self):
        """Akamaiクッキー更新を促すためのウォームアップリクエスト"""
        if not self.context:
            return
        target_url = "https://salonboard.com/CNB/imgreg/imgUpload/"
        try:
            response = self.context.request.get(target_url)
            logger.info("Akamaiウォームアップリクエスト: %s (status=%s)", target_url, response.status)
        except Exception as warmup_error:
            logger.warning("Akamaiウォームアップリクエスト失敗: %s", warmup_error)

    def _ensure_akamai_readiness(self, attempts: int = 3, timeout_ms: int = 15000) -> bool:
        """Akamaiセッションが安定するまで刺激と再確認を行う"""
        for attempt in range(1, attempts + 1):
            if self._wait_for_akamai_clearance(timeout_ms=timeout_ms, strict=False):
                return True
            logger.info("Akamaiセンサーが未完了のため刺激 #%s", attempt)
            self._stimulate_akamai_sensor()
            self._warmup_akamai_endpoints()
        ready = self._wait_for_akamai_clearance(timeout_ms=timeout_ms, strict=False)
        if ready:
            return True
        logger.warning("Akamaiセッションが安定しないまま次の処理へ進みます")
        return False

    def _wait_for_akamai_clearance(self, timeout_ms: int = 15000, *, strict: bool = True) -> bool:
        """
        Akamai Bot Managerの検証完了を待機

        _abck Cookieの末尾が ~0~ になるまで待機し、未達なら例外を投げる
        """
        if not self.page:
            return True

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        last_summary: Optional[str] = None
        while time.monotonic() < deadline:
            cookie_value = self._get_cookie_value("_abck")
            summary = self._summarize_abck_value(cookie_value)
            if summary != last_summary:
                logger.info("_abck cookie 状態: %s", summary)
                last_summary = summary
            if cookie_value and ("~0~" in cookie_value or "~1~" in cookie_value):
                logger.info("Akamaiセッション検証完了 (_abck cookie OK)")
                return True
            self.page.wait_for_timeout(250)

        message = (
            f"Akamaiセッション検証が完了せず、_abck cookie が ~0~ になりませんでした "
            f"(status={last_summary or 'unknown'})"
        )
        if strict:
            raise RuntimeError(message)
        logger.warning("%s", message)
        return False

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

    def _perform_dummy_mouse_move(self, margin: int = 32) -> None:
        """ページ内でのマウス移動を小さく挿入し、人間らしい操作を模倣する。"""
        if not self.page:
            return

        viewport = self.page.viewport_size or {"width": 412, "height": 915}
        width = max(1, viewport.get("width", 412))
        height = max(1, viewport.get("height", 915))
        margin = max(0, margin)

        min_x = min(margin, width - 1)
        max_x = max(min_x, width - 1 - margin)
        min_y = min(margin, height - 1)
        max_y = max(min_y, height - 1 - margin)

        try:
            target_x = self._random.randint(min_x, max_x) if max_x >= min_x else self._random.randint(0, width - 1)
            target_y = self._random.randint(min_y, max_y) if max_y >= min_y else self._random.randint(0, height - 1)
            steps = self._random.randint(3, 7)
            self.page.mouse.move(target_x, target_y, steps=steps)
        except Exception:
            # マウス操作がサポートされない環境では黙ってスキップ
            pass

    def _human_pause(
        self,
        base_ms: Optional[int] = None,
        jitter_ms: Optional[int] = None,
        minimum_ms: Optional[int] = None,
        with_mouse_move: bool = False
    ) -> None:
        """
        操作間に人間らしい待機を挿入する

        Args:
            base_ms: 基本待機時間（ミリ秒）
            jitter_ms: 待機時間に加える揺らぎ（ミリ秒）
            minimum_ms: 最小待機時間（ミリ秒）
            with_mouse_move: True の場合は待機前にマウスを小さく動かして人間操作を疑似する
        """
        base = base_ms if base_ms is not None else self.HUMAN_BASE_WAIT_MS
        jitter = jitter_ms if jitter_ms is not None else self.HUMAN_JITTER_MS
        minimum = minimum_ms if minimum_ms is not None else self.HUMAN_MIN_WAIT_MS

        base = max(0, base)
        jitter = max(0, jitter)
        minimum = max(0, minimum)

        delay_ms = base + self._random.randint(-jitter, jitter)
        delay_ms = max(minimum, delay_ms)

        if with_mouse_move:
            self._perform_dummy_mouse_move()

        if self.page:
            self.page.wait_for_timeout(delay_ms)
        else:
            time.sleep(delay_ms / 1000)

    def _select_salon_if_needed(self, salon_info: Optional[Dict]) -> None:
        """
        複数店舗ページが表示された場合、salon_info に基づいてサロンを選択する
        """
        if not self.page:
            return
        salon_config = self.selectors.get("salon_selection", {})
        salon_list_table = salon_config.get("salon_list_table")
        salon_list_row = salon_config.get("salon_list_row")
        salon_id_cell = salon_config.get("salon_id_cell")
        salon_name_cell = salon_config.get("salon_name_cell")

        if not salon_list_table or not salon_list_row:
            return

        table = self.page.locator(salon_list_table)
        try:
            table.wait_for(state="visible", timeout=5000)
            table_count = table.count()
        except Exception:
            table_count = 0
        if table_count == 0:
            logger.debug("サロン選択テーブルが見つかりません: selector=%s", salon_list_table)
            return

        logger.info("複数店舗アカウント検出 - サロン選択中...")
        logger.debug("サロン選択テーブル検出: selector=%s", salon_list_table)

        if not salon_info:
            raise Exception("複数店舗アカウントですが、salon_infoが指定されていません")

        rows = self.page.locator(salon_list_row).all()
        logger.debug("サロン候補行数: %s", len(rows))
        target_id = (salon_info.get("id") or "").strip()
        target_name = (salon_info.get("name") or "").strip()

        for row in rows:
            try:
                salon_id = row.locator(salon_id_cell).text_content().strip() if salon_id_cell else ""
                salon_name = row.locator(salon_name_cell).text_content().strip() if salon_name_cell else ""
            except Exception:
                continue

            logger.debug("サロン候補: id=%s name=%s target_id=%s target_name=%s", salon_id, salon_name, target_id, target_name)
            # ID優先で一致チェック、なければ名前でチェック
            if (target_id and salon_id == target_id) or (not target_id and target_name and salon_name == target_name):
                logger.info("サロン選択: %s (ID: %s)", salon_name or target_name, salon_id or target_id)
                row.locator("a").first.click()
                # 遷移完了を軽く待つ
                self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                return

        raise Exception(f"指定されたサロンが見つかりませんでした: {salon_info}")

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
                "ダッシュボード待機中: url=%s title=%s _abck=%s",
                current_url,
                title,
                self._summarize_abck_value(self._get_cookie_value("_abck")),
            )
            self.page.wait_for_timeout(check_interval_ms)

        return False

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

    def step_login(self, user_id: str, password: str, salon_info: Optional[Dict] = None):
        """
        ログイン処理

        Args:
            user_id: SALON BOARDログインID
            password: SALON BOARDパスワード
            salon_info: サロン情報（複数店舗アカウント用）{"id": "...", "name": "..."}
        """
        logger.info("ログイン処理開始")
        login_config = self.selectors["login"]

        # ログインページへ移動
        logger.debug("ログインページへ遷移: %s", login_config["url"])
        self.page.goto(login_config["url"])
        self._human_pause(base_ms=900, jitter_ms=300)
        if self._check_robot_detection():
            raise Exception("ログインページでロボット認証が検出されました")

        # ID/パスワード入力
        self._human_pause()
        self.page.locator(login_config["user_id_input"]).fill(user_id)
        self._human_pause()
        self.page.locator(login_config["password_input"]).fill(password)
        self._human_pause(base_ms=800, jitter_ms=250)

        # ログインボタンクリック
        self._click_and_wait(login_config["login_button"])

        # 複数店舗選択が必要な場合はここで実施（ヘッダー待機より先に行う）
        self._select_salon_if_needed(salon_info)

        # ログイン完了判定: ヘッダー/ダッシュボード表示をポーリングで確認
        dashboard_selector = login_config["dashboard_global_navi"]
        if not self._wait_for_dashboard_ready(
            timeout_ms=60000,
            header_selector="#headerNavigationBar",
            dashboard_selector=dashboard_selector,
        ):
            screenshot_path = self._take_screenshot("login-wait-timeout")
            logger.error("ログイン後のヘッダー待機に失敗 (timeout=%sms)", 60000)
            raise StylePostError(
                "ログイン後のトップページ読込みが完了しませんでした。",
                screenshot_path=screenshot_path
            )

        # サロン選択ロジック（複数店舗アカウント対応）
        salon_config = self.selectors.get("salon_selection", {})
        salon_list_table = salon_config.get("salon_list_table")

        if salon_list_table and self.page.locator(salon_list_table).count() > 0:
            logger.info("複数店舗アカウント検出 - サロン選択中...")
            logger.debug("サロン一覧テーブル検出: selector=%s", salon_list_table)

            if not salon_info:
                raise Exception("複数店舗アカウントですが、salon_infoが指定されていません")

            rows = self.page.locator(salon_config["salon_list_row"]).all()
            found = False
            logger.debug("サロン候補行数: %s", len(rows))

            for row in rows:
                salon_id = row.locator(salon_config["salon_id_cell"]).text_content().strip()
                salon_name = row.locator(salon_config["salon_name_cell"]).text_content().strip()

                # IDまたは名前で一致確認
                if (salon_info.get("id") and salon_id == salon_info["id"]) or \
                   (salon_info.get("name") and salon_name == salon_info["name"]):
                    logger.info("サロン選択: %s (ID: %s)", salon_name, salon_id)
                    row.locator("a").first.click()
                    # サロン選択後はヘッダーを再確認
                    self.page.wait_for_selector("#headerNavigationBar", timeout=60000, state="visible")
                    found = True
                    break

            if not found:
                raise Exception(f"指定されたサロンが見つかりませんでした: {salon_info}")

        # ログイン成功確認（もう一度ダッシュボードセレクタを軽く確認）
        try:
            self.page.wait_for_selector(dashboard_selector, timeout=10000, state="visible")
            logger.info("ログイン成功 (ダッシュボードナビ二次確認)")
        except PlaywrightTimeoutError:
            # 二次確認はベストエフォート（ここではエラーにしない）
            logger.warning("ログイン後のダッシュボードナビ二次確認をスキップ（非致命）")

    def step_navigate_to_style_list_page(self, use_direct_url: bool = False):
        """
        スタイル一覧ページへ移動

        Args:
            use_direct_url: True の場合、URLで直接遷移（エラー回復時用）
        """
        logger.info("スタイル一覧ページへ移動中...")

        if use_direct_url:
            # 直接URLで遷移（エラー回復時）
            logger.info("直接URLで遷移します...")
            current_url = self.page.url
            # 現在のURLからベースURLを取得
            base_url = current_url.split('/CNB/')[0] if '/CNB/' in current_url else 'https://salonboard.com'
            style_list_url = f"{base_url}/CNB/draft/styleList/"
            logger.info("遷移先: %s", style_list_url)
            self.page.goto(style_list_url, timeout=self.TIMEOUT_LOAD)
            self.page.wait_for_load_state("domcontentloaded", timeout=self.TIMEOUT_LOAD)
            logger.debug("直接URL遷移完了: current_url=%s", self.page.url)
        else:
            # 通常のナビゲーション
            nav_config = self.selectors["navigation"]

            # 掲載管理 → スタイル管理
            try:
                self._click_and_wait(nav_config["keisai_kanri"], load_state="domcontentloaded")
                self._click_and_wait(nav_config["style"], load_state="domcontentloaded")
            except Exception as nav_error:
                logger.warning("通常ナビゲーションに失敗、直接URLで再試行します: %s", nav_error)
                current_url = self.page.url
                base_url = current_url.split('/CNB/')[0] if '/CNB/' in current_url else 'https://salonboard.com'
                style_list_url = f"{base_url}/CNB/draft/styleList/"
                self.page.goto(style_list_url, timeout=self.TIMEOUT_LOAD)
                self.page.wait_for_load_state("domcontentloaded", timeout=self.TIMEOUT_LOAD)
            logger.debug("ナビゲーション完了: current_url=%s", self.page.url)

        logger.info("スタイル一覧ページへ移動完了")

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

    def _navigate_back_to_style_list_after_error(self) -> bool:
        """
        エラー発生後にスタイル一覧ページに戻る

        Returns:
            bool: 戻りに成功した場合True、失敗した場合False
        """
        # まず通常のナビゲーションを試行
        try:
            logger.info("エラー発生により、スタイル一覧ページに戻ります")
            self.step_navigate_to_style_list_page()
            logger.info("スタイル一覧ページに戻りました")
            return True
        except Exception as nav_error:
            logger.warning("通常のナビゲーションに失敗: %s", nav_error)

        # 通常のナビゲーションが失敗した場合、直接URLで遷移
        try:
            logger.info("直接URLで遷移を試みます")
            self.step_navigate_to_style_list_page(use_direct_url=True)
            logger.info("スタイル一覧ページに戻りました（直接URL）")
            return True
        except Exception as direct_error:
            logger.error("直接URL遷移にも失敗: %s", direct_error)
            logger.warning("スタイル一覧ページへの戻りを諦めます。次のスタイル処理時に再試行します。")
            return False

    def step_process_single_style(self, style_data: Dict, image_path: str) -> List[Dict[str, object]]:
        """
        1件のスタイル処理

        Args:
            style_data: スタイル情報の辞書
            image_path: 画像ファイルのパス
        Returns:
            List[Dict[str, object]]: 画像アップロードに関する警告（手動対応が必要な場合のみ）
        """
        manual_upload_events: List[Dict[str, object]] = []
        row_number = style_data.get("_row_number", 0)
        image_filename = Path(image_path).name

        form_config = self.selectors["style_form"]

        # 新規登録ページへ
        try:
            logger.info("新規登録ボタンをクリック中...")
            self._click_and_wait(form_config["new_style_button"])
            logger.info("新規登録ページへ移動完了")
        except Exception as e:
            raise StylePostError(f"新規登録ページへの移動に失敗しました: {e}", self._take_screenshot("error-new-style-page"))

        # 画像アップロード
        try:
            logger.info("画像アップロード開始...")
            self._last_failed_upload_reason = None

            # アップロード開始前の待機（通信の安定化）
            logger.info("Akamaiセッションの検証状態を確認中...")
            clearance_ready = self._ensure_akamai_readiness()
            if not clearance_ready:
                logger.info("センサー刺激後も完了しないため、アップロード処理で完了を誘発します。")
            logger.info("通信安定化のためランダム待機中...")
            self._human_pause(base_ms=1100, jitter_ms=450, minimum_ms=850)

            logger.info("アップロードエリアをクリック中...")
            self.page.locator(form_config["image"]["upload_area"]).click(timeout=self.TIMEOUT_CLICK)
            self._human_pause(base_ms=700, jitter_ms=250, minimum_ms=400)
            logger.info("モーダル表示待機中...")
            self.page.wait_for_selector(form_config["image"]["modal_container"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=750, jitter_ms=260, minimum_ms=450)
            logger.info("画像ファイル選択準備中: %s", image_path)

            self.page.locator(form_config["image"]["file_input"]).set_input_files(image_path)
            try:
                self.page.locator(form_config["image"]["submit_button_active"]).wait_for(
                    state="visible",
                    timeout=self.TIMEOUT_IMAGE_UPLOAD
                )
            except PlaywrightTimeoutError:
                raise Exception("画像選択後に送信ボタンが有効になりませんでした")

            logger.info("画像処理のためランダム待機中...")
            self._human_pause(
                base_ms=int(self.IMAGE_PROCESSING_WAIT * 1000),
                jitter_ms=800,
                minimum_ms=int(self.IMAGE_PROCESSING_WAIT * 800)
            )

            # 送信ボタンの状態を確認
            submit_button = self.page.locator(form_config["image"]["submit_button_active"])
            logger.info("送信ボタン確認中...")

            # ボタンが表示されるまで待機
            submit_button.wait_for(state="visible", timeout=self.TIMEOUT_WAIT_ELEMENT)
            try:
                submit_button.hover(timeout=2000)
            except Exception:
                # hover不可（例: モバイルコンテキスト）の場合はスキップ
                pass
            self._human_pause(base_ms=650, jitter_ms=220, minimum_ms=350, with_mouse_move=True)

            # Akamaiの動的チェックを回避するため、クリック直前にセンサーを再度刺激
            logger.info("Akamaiセンサーを刺激中...")
            self._stimulate_akamai_sensor()
            self._human_pause(base_ms=800, jitter_ms=300, minimum_ms=500, with_mouse_move=True)

            # 強制的にクリック（JavaScriptで実行）
            logger.info("送信ボタンクリック中（JavaScript実行）...")
            upload_predicate = lambda response: (
                "/CNB/imgreg/imgUpload/doUpload" in response.url
                and response.request.method.upper() == "POST"
            )

            upload_response: Optional[Response] = None
            manual_upload_required = False
            manual_upload_reason = ""
            try:
                with self.page.expect_response(upload_predicate, timeout=self.TIMEOUT_IMAGE_UPLOAD) as upload_waiter:
                    submit_button.evaluate("el => el.click()")
                upload_response = upload_waiter.value
                logger.info("画像アップロードレスポンス取得: status=%s, url=%s", upload_response.status, upload_response.url)
            except PlaywrightTimeoutError:
                reason = self._last_failed_upload_reason or "imgUpload/doUpload のレスポンス待機がタイムアウトしました"
                manual_upload_reason = reason
                if "ERR_ABORTED" in reason.upper():
                    manual_upload_required = True
                modal_hidden = False
                try:
                    self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=2000)
                    modal_hidden = True
                except PlaywrightTimeoutError:
                    modal_hidden = False
                if modal_hidden:
                    logger.warning("%s。モーダルは既に閉じているため続行します。", reason)
                else:
                    raise Exception(reason)

            if upload_response and upload_response.status != 200:
                body_preview = ""
                try:
                    body_preview = upload_response.text()[:200]
                except Exception:
                    pass
                extra = ""
                if self._last_failed_upload_reason:
                    extra = f", request_failure={self._last_failed_upload_reason}"
                akamai_status = self._summarize_abck_value(self._get_cookie_value("_abck"))
                raise Exception(
                    f"画像アップロードAPIが失敗しました (status={upload_response.status}, preview={body_preview}, akamai={akamai_status}{extra})"
                )
            elif manual_upload_required:
                warning_message = (
                    f"画像アップロードリクエストがブラウザ側で中断されました (image={image_filename})。"
                    "SALON BOARDで手動アップロードを実施してください。"
                )
                logger.warning("%s", warning_message)
                manual_upload_events.append(
                    {
                        "row_number": row_number,
                        "style_name": style_data.get("スタイル名", "不明"),
                        "field": "画像アップロード",
                        "reason": warning_message,
                        "image_name": image_filename,
                        "error_category": "IMAGE_UPLOAD_ABORTED",
                        "raw_error": manual_upload_reason,
                        "screenshot_path": ""
                    }
                )

            self._human_pause(base_ms=680, jitter_ms=210, minimum_ms=350)

            logger.info("モーダル非表示待機中...")
            try:
                self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=self.TIMEOUT_IMAGE_UPLOAD)
            except PlaywrightTimeoutError as modal_timeout:
                try:
                    self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=1000)
                    logger.warning("モーダル非表示待機がタイムアウトしましたが既に閉じています。")
                except PlaywrightTimeoutError:
                    logger.warning("モーダル非表示待機がタイムアウトしましたが既に閉じています。")
                    akamai_status = self._summarize_abck_value(self._get_cookie_value("_abck"))
                    raise Exception(
                        f"画像アップロードモーダルが閉じません (timeout={self.TIMEOUT_IMAGE_UPLOAD}, akamai={akamai_status})"
                    ) from modal_timeout
            self._human_pause(base_ms=850, jitter_ms=300, minimum_ms=500)

            # 画像アップロード後のページ安定化待機
            logger.info("ページ安定化待機中...")
            try:
                self.page.wait_for_load_state("networkidle", timeout=self.TIMEOUT_LOAD)
            except PlaywrightTimeoutError as load_timeout:
                akamai_status = self._summarize_abck_value(self._get_cookie_value("_abck"))
                raise Exception(
                    f"画像アップロード後のページが安定しません (timeout={self.TIMEOUT_LOAD}, akamai={akamai_status})"
                ) from load_timeout
            self._human_pause(base_ms=900, jitter_ms=320, minimum_ms=500)

            # エラーダイアログの確認と処理
            error_dialog_selector = "div.modpopup01.sch.w400.cf.dialog"
            try:
                error_dialog = self.page.locator(error_dialog_selector)
                if error_dialog.count() > 0 and error_dialog.first.is_visible(timeout=1000):
                    # エラーメッセージを取得
                    error_message = self.page.locator(f"{error_dialog_selector} .message").inner_text()
                    logger.warning("エラーダイアログ検出: %s", error_message)
                    # OKボタンをクリックして閉じる
                    ok_button = self.page.locator(f"{error_dialog_selector} a.accept")
                    ok_button.click(timeout=5000)
                    self._human_pause(base_ms=650, jitter_ms=200, minimum_ms=400)
                    raise Exception(f"画像アップロードエラー: {error_message}")
            except Exception as dialog_error:
                if "画像アップロードエラー" in str(dialog_error):
                    raise
                # ダイアログが存在しない場合は無視
                pass

            logger.info("画像アップロード完了")
        except Exception as e:
            raise StylePostError(f"画像アップロードに失敗しました: {e}", self._take_screenshot("error-image-upload"))

        # スタイリスト名選択
        try:
            logger.info("スタイリスト名選択中...")
            stylist_select = self.page.locator(form_config["stylist_name_select"])
            stylist_select.wait_for(state="visible", timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause()
            stylist_select.select_option(label=style_data["スタイリスト名"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=750, jitter_ms=240, minimum_ms=400)
            logger.info("スタイリスト名選択完了")
        except Exception as e:
            raise StylePostError(f"スタイリスト名の選択に失敗しました（スタイリスト: {style_data.get('スタイリスト名', '不明')}）: {e}", self._take_screenshot("error-stylist-select"))

        # テキスト入力
        try:
            logger.info("テキスト入力中...")
            self._human_pause()
            self.page.locator(form_config["stylist_comment_textarea"]).fill(style_data["コメント"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=650, jitter_ms=220, minimum_ms=400)
            self.page.locator(form_config["style_name_input"]).fill(style_data["スタイル名"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=650, jitter_ms=220, minimum_ms=400)
            self.page.locator(form_config["menu_detail_textarea"]).fill(style_data["メニュー内容"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=750, jitter_ms=230, minimum_ms=400)
            logger.info("テキスト入力完了")
        except Exception as e:
            raise StylePostError(f"テキスト入力に失敗しました: {e}", self._take_screenshot("error-text-input"))

        # カテゴリ/長さ選択
        try:
            logger.info("カテゴリ/長さ選択中...")
            category = style_data["カテゴリ"]
            if category == "レディース":
                self._human_pause()
                self.page.locator(form_config["category_ladies_radio"]).click(timeout=self.TIMEOUT_CLICK)
                self._human_pause(base_ms=620, jitter_ms=200, minimum_ms=350)
                self.page.locator(form_config["length_select_ladies"]).select_option(
                    label=style_data["長さ"], timeout=self.TIMEOUT_WAIT_ELEMENT
                )
            elif category == "メンズ":
                self._human_pause()
                self.page.locator(form_config["category_mens_radio"]).click(timeout=self.TIMEOUT_CLICK)
                self._human_pause(base_ms=620, jitter_ms=200, minimum_ms=350)
                self.page.locator(form_config["length_select_mens"]).select_option(
                    label=style_data["長さ"], timeout=self.TIMEOUT_WAIT_ELEMENT
                )
            self._human_pause(base_ms=750, jitter_ms=220, minimum_ms=400)
            logger.info("カテゴリ/長さ選択完了")
        except Exception as e:
            raise StylePostError(f"カテゴリ/長さの選択に失敗しました（カテゴリ: {category}, 長さ: {style_data.get('長さ', '不明')}）: {e}", self._take_screenshot("error-category-length"))

        # クーポン選択
        try:
            logger.info("クーポン選択中...")
            coupon_config = form_config["coupon"]
            self._human_pause()
            self.page.locator(coupon_config["select_button"]).click(timeout=self.TIMEOUT_CLICK)
            self.page.wait_for_selector(coupon_config["modal_container"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=720, jitter_ms=240, minimum_ms=400)

            coupon_selector = coupon_config["item_label_template"].format(
                name=style_data["クーポン名"]
            )
            self.page.locator(coupon_selector).first.click(timeout=self.TIMEOUT_CLICK)
            self._human_pause(base_ms=640, jitter_ms=220, minimum_ms=350)
            self.page.locator(coupon_config["setting_button"]).click(timeout=self.TIMEOUT_CLICK)
            self.page.wait_for_selector(coupon_config["modal_container"], state="hidden", timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=780, jitter_ms=260, minimum_ms=450)
            logger.info("クーポン選択完了")
        except Exception as e:
            raise StylePostError(f"クーポンの選択に失敗しました（クーポン: {style_data.get('クーポン名', '不明')}）: {e}", self._take_screenshot("error-coupon-select"))

        # ハッシュタグ入力
        try:
            logger.info("ハッシュタグ入力中...")
            hashtag_config = form_config["hashtag"]
            hashtags = style_data["ハッシュタグ"].split(",")

            for tag in hashtags:
                tag = tag.strip()
                if tag:
                    self.page.locator(hashtag_config["input_area"]).fill(tag, timeout=self.TIMEOUT_WAIT_ELEMENT)
                    self.page.locator(hashtag_config["add_button"]).click(timeout=self.TIMEOUT_CLICK)
                    self._human_pause(base_ms=650, jitter_ms=210, minimum_ms=350)  # 反映待機
            logger.info("ハッシュタグ入力完了")
        except Exception as e:
            raise StylePostError(f"ハッシュタグの入力に失敗しました: {e}", self._take_screenshot("error-hashtag"))

        # 登録
        try:
            logger.info("登録ボタンクリック中...")
            self._click_and_wait(form_config["register_button"])
            self.page.wait_for_selector(form_config["complete_text"], timeout=self.TIMEOUT_LOAD)
            logger.info("登録完了")
        except Exception as e:
            raise StylePostError(f"スタイル登録の完了に失敗しました: {e}", self._take_screenshot("error-register"))

        # スタイル一覧へ戻る
        logger.info("スタイル一覧へ戻る...")
        back_to_list_button = form_config["back_to_list_button"]
        list_ready_selector = form_config["new_style_button"]
        back_navigation_timeout = 10000  # 明示的に10秒に制限
        back_navigation_error: Optional[Exception] = None

        try:
            self._click_and_wait(back_to_list_button, load_timeout=back_navigation_timeout)
            self.page.wait_for_selector(list_ready_selector, timeout=self.TIMEOUT_LOAD)
            logger.info("スタイル登録完了: %s", style_data["スタイル名"])
        except Exception as navigation_error:
            back_navigation_error = navigation_error
            logger.warning("通常の戻る操作に失敗（%s）。直接URLで一覧に戻ります。", navigation_error)

        if back_navigation_error:
            try:
                self.step_navigate_to_style_list_page(use_direct_url=True)
                self.page.wait_for_selector(list_ready_selector, timeout=self.TIMEOUT_LOAD)
                logger.info("直接URLでスタイル一覧に戻りました: %s", style_data["スタイル名"])
            except Exception as direct_navigation_error:
                combined_message = (
                    f"スタイル一覧への戻りに失敗しました: {back_navigation_error}; "
                    f"直接URL遷移にも失敗: {direct_navigation_error}"
                )
                raise StylePostError(combined_message, self._take_screenshot("error-back-to-list"))

        return manual_upload_events

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
        self.progress_callback = progress_callback
        expected_total = total_items or 0

        def emit_progress(
            completed: int,
            detail: Optional[Dict[str, object]] = None,
            *,
            error: Optional[Dict[str, object]] = None,
            total_override: Optional[int] = None
        ) -> None:
            """進捗コールバックを通じて詳細情報を通知"""
            if not self.progress_callback:
                return

            total_value = total_override if total_override is not None else expected_total
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

        try:
            # ブラウザ起動
            emit_progress(
                0,
                {
                    "stage": "BROWSER_STARTING",
                    "stage_label": "ブラウザ起動準備",
                    "message": "Playwrightを起動しています",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total
                }
            )
            self._start_browser()
            emit_progress(
                0,
                {
                    "stage": "BROWSER_READY",
                    "stage_label": "ブラウザ起動完了",
                    "message": "Playwrightの起動が完了しました",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total
                }
            )

            # ログイン
            self.step_login(user_id, password, salon_info)
            emit_progress(
                0,
                {
                    "stage": "LOGIN_COMPLETED",
                    "stage_label": "ログイン完了",
                    "message": "SALON BOARDへのログインが完了しました",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total
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
            expected_total = len(df)
            emit_progress(
                0,
                {
                    "stage": "DATA_READY",
                    "stage_label": "データ読み込み完了",
                    "message": f"{expected_total}件のスタイルデータを読み込みました",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total
                }
            )

            # スタイル一覧ページへ移動
            self.step_navigate_to_style_list_page()
            emit_progress(
                0,
                {
                    "stage": "NAVIGATED",
                    "stage_label": "投稿準備完了",
                    "message": "スタイル一覧ページを開きました",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total
                }
            )

            # スタイルごとにループ処理
            image_dir_path = Path(image_dir)
            for index, row in df.iterrows():
                style_name = row.get("スタイル名", "不明")
                emit_progress(
                    index,
                    {
                        "stage": "STYLE_PROCESSING",
                        "stage_label": "スタイル処理中",
                        "message": f"{index + 1}/{expected_total}件目「{style_name}」を処理しています",
                        "status": "working",
                        "current_index": index + 1,
                        "total": expected_total,
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
                    manual_events = self.step_process_single_style(style_dict, str(image_path))

                    # 成功時の進捗更新
                    emit_progress(
                        index + 1,
                        {
                            "stage": "STYLE_COMPLETED",
                            "stage_label": "スタイル投稿完了",
                            "message": f"{index + 1}/{expected_total}件目「{style_name}」の投稿が完了しました",
                            "status": "completed",
                            "current_index": index + 1,
                            "total": expected_total,
                            "style_name": style_name
                        }
                    )

                    if manual_events:
                        for event in manual_events:
                            event.setdefault("row_number", index + 2)
                            event.setdefault("style_name", style_name)
                            event.setdefault("field", "画像アップロード")
                            event.setdefault("error_category", "IMAGE_UPLOAD_ABORTED")
                            event.setdefault("image_name", image_filename)
                            emit_progress(
                                index + 1,
                                {
                                    "stage": "STYLE_WARNING",
                                    "stage_label": "手動対応が必要",
                                    "message": f"{style_name} の画像をSALON BOARDで手動登録してください",
                                    "status": "warning",
                                    "current_index": index + 1,
                                    "total": expected_total,
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
                    emit_progress(
                        index + 1,
                        {
                            "stage": "STYLE_ERROR",
                            "stage_label": "スタイル投稿エラー",
                            "message": f"{index + 1}/{expected_total}件目「{style_name}」でエラーが発生しました",
                            "status": "error",
                            "current_index": index + 1,
                            "total": expected_total,
                            "style_name": style_name
                        },
                        error=error_payload
                    )

            logger.info("全スタイルの処理が完了しました")
            emit_progress(
                expected_total,
                {
                    "stage": "SUMMARY",
                    "stage_label": "処理完了",
                    "message": "全てのスタイル投稿を完了しました",
                    "status": "success",
                    "current_index": expected_total,
                    "total": expected_total
                }
            )

        except Exception as e:
            logger.exception("致命的エラー: %s", e)
            self._take_screenshot("fatal-error")
            raise

        finally:
            # ブラウザ終了
            self._close_browser()


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

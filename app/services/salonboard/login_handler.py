"""
SALON BOARD ログイン処理Mixin
"""
import logging
from typing import Dict, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .exceptions import StylePostError, RobotDetectionError

logger = logging.getLogger(__name__)


class LoginHandlerMixin:
    """ログイン処理Mixin"""

    # 以下はSalonBoardBrowserManagerまたは他のMixinで定義される属性・メソッド
    page: object
    selectors: Dict
    TIMEOUT_LOAD: int
    _human_pause: object
    _check_robot_detection: object
    _click_and_wait: object
    _wait_for_dashboard_ready: object
    _take_screenshot: object

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
        # ロボット認証チェック（検出時は例外がスローされる）
        self._check_robot_detection()

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

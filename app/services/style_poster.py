"""
SALON BOARD スタイル自動投稿サービス
Playwrightを使用したブラウザ自動化
"""
import yaml
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Callable
from playwright.sync_api import sync_playwright, Page, Browser, Playwright


class StylePostError(Exception):
    """スタイル投稿エラー（スクリーンショット情報付き）"""
    def __init__(self, message: str, screenshot_path: str = ""):
        super().__init__(message)
        self.screenshot_path = screenshot_path


class SalonBoardStylePoster:
    """SALON BOARDスタイル自動投稿クラス"""

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

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.progress_callback: Optional[Callable] = None

    def _start_browser(self):
        """ブラウザ起動"""
        print("ブラウザを起動中...")
        self.playwright = sync_playwright().start()

        # Firefoxブラウザ起動
        self.browser = self.playwright.firefox.launch(
            headless=self.headless,
            slow_mo=self.slow_mo
        )

        # ブラウザコンテキスト作成（自動化検知対策）
        context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0"
        )

        # WebDriverフラグ隠蔽
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # 新しいページ作成
        self.page = context.new_page()

        # デフォルトタイムアウト設定（3分）
        self.page.set_default_timeout(180000)

        print("✓ ブラウザ起動完了")

    def _close_browser(self):
        """ブラウザ終了"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("✓ ブラウザ終了")

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
            print(f"✓ スクリーンショット保存: {filepath}")
            return str(filepath)
        return ""

    def _check_robot_detection(self) -> bool:
        """
        ロボット認証検出

        Returns:
            bool: ロボット認証が検出された場合True
        """
        robot_config = self.selectors.get("robot_detection", {})

        # セレクタチェック
        for selector in robot_config.get("selectors", []):
            if self.page.locator(selector).count() > 0:
                print(f"✗ ロボット認証検出（セレクタ: {selector}）")
                return True

        # テキストチェック
        for text in robot_config.get("texts", []):
            if self.page.locator(f"text={text}").count() > 0:
                print(f"✗ ロボット認証検出（テキスト: {text}）")
                return True

        return False

    def _click_and_wait(self, selector: str):
        """
        クリック＆待機（ページ遷移対応）

        Args:
            selector: クリックする要素のセレクタ
        """
        self.page.locator(selector).first.click()
        self.page.wait_for_load_state("networkidle")

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
        print("ログイン処理開始...")
        login_config = self.selectors["login"]

        # ログインページへ移動
        self.page.goto(login_config["url"])

        if self._check_robot_detection():
            raise Exception("ログインページでロボット認証が検出されました")

        # ID/パスワード入力
        self.page.locator(login_config["user_id_input"]).fill(user_id)
        self.page.locator(login_config["password_input"]).fill(password)

        # ログインボタンクリック
        self._click_and_wait(login_config["login_button"])

        # サロン選択ロジック（複数店舗アカウント対応）
        salon_config = self.selectors.get("salon_selection", {})
        salon_list_table = salon_config.get("salon_list_table")

        if salon_list_table and self.page.locator(salon_list_table).count() > 0:
            print("複数店舗アカウント検出 - サロン選択中...")

            if not salon_info:
                raise Exception("複数店舗アカウントですが、salon_infoが指定されていません")

            rows = self.page.locator(salon_config["salon_list_row"]).all()
            found = False

            for row in rows:
                salon_id = row.locator(salon_config["salon_id_cell"]).text_content().strip()
                salon_name = row.locator(salon_config["salon_name_cell"]).text_content().strip()

                # IDまたは名前で一致確認
                if (salon_info.get("id") and salon_id == salon_info["id"]) or \
                   (salon_info.get("name") and salon_name == salon_info["name"]):
                    print(f"✓ サロン選択: {salon_name} (ID: {salon_id})")
                    row.locator("a").first.click()
                    self.page.wait_for_load_state("networkidle")
                    found = True
                    break

            if not found:
                raise Exception(f"指定されたサロンが見つかりませんでした: {salon_info}")

        # ログイン成功確認（30秒タイムアウト）
        try:
            self.page.wait_for_selector(login_config["dashboard_global_navi"], timeout=30000)
            print("✓ ログイン成功")
        except Exception as e:
            # ログイン失敗時のスクリーンショット取得
            screenshot_path = self._take_screenshot("login-failure")
            print(f"✗ ログイン失敗: {e}")
            raise StylePostError(
                "ログインに失敗しました。ユーザーID/パスワードを確認してください。",
                screenshot_path=screenshot_path
            ) from e

    def step_navigate_to_style_list_page(self):
        """スタイル一覧ページへ移動"""
        print("スタイル一覧ページへ移動中...")
        nav_config = self.selectors["navigation"]

        # 掲載管理 → スタイル管理
        self._click_and_wait(nav_config["keisai_kanri"])
        self._click_and_wait(nav_config["style"])

        print("✓ スタイル一覧ページへ移動完了")

    def step_process_single_style(self, style_data: Dict, image_path: str):
        """
        1件のスタイル処理

        Args:
            style_data: スタイル情報の辞書
            image_path: 画像ファイルのパス
        """
        form_config = self.selectors["style_form"]

        # 新規登録ページへ
        print("新規登録ボタンをクリック中...")
        self._click_and_wait(form_config["new_style_button"])
        print("✓ 新規登録ページへ移動完了")

        # 画像アップロード
        print("画像アップロード開始...")
        print(f"  - アップロードエリアをクリック中...")
        self.page.locator(form_config["image"]["upload_area"]).click()
        print(f"  - モーダル表示待機中...")
        self.page.wait_for_selector(form_config["image"]["modal_container"])
        print(f"  - 画像ファイル選択中: {image_path}")
        self.page.locator(form_config["image"]["file_input"]).set_input_files(image_path)
        print(f"  - 画像処理待機中（2秒）...")
        time.sleep(2)  # 画像アップロード処理のための短い待機

        # 送信ボタンの状態を確認
        submit_button = self.page.locator("input.imageUploaderModalSubmitButton")
        print(f"  - 送信ボタン確認中...")

        # ボタンが表示されるまで待機
        submit_button.wait_for(state="visible", timeout=10000)

        # ボタンがクリック可能になるまで待機
        try:
            submit_button.wait_for(state="attached", timeout=5000)
            is_disabled = submit_button.evaluate("el => el.disabled")
            has_active_class = submit_button.evaluate("el => el.classList.contains('isActive')")
            print(f"  - ボタン状態: disabled={is_disabled}, hasActiveClass={has_active_class}")
        except Exception as e:
            print(f"  - ボタン状態確認エラー: {e}")

        # 強制的にクリック（JavaScriptで実行）
        print(f"  - 送信ボタンクリック中（JavaScript実行）...")
        submit_button.evaluate("el => el.click()")

        print(f"  - モーダル非表示待機中...")
        self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=60000)
        print("✓ 画像アップロード完了")

        # スタイリスト名選択
        print("スタイリスト名選択中...")
        self.page.locator(form_config["stylist_name_select"]).select_option(
            label=style_data["スタイリスト名"]
        )
        print("✓ スタイリスト名選択完了")

        # テキスト入力
        print("テキスト入力中...")
        self.page.locator(form_config["stylist_comment_textarea"]).fill(style_data["コメント"])
        self.page.locator(form_config["style_name_input"]).fill(style_data["スタイル名"])
        self.page.locator(form_config["menu_detail_textarea"]).fill(style_data["メニュー内容"])
        print("✓ テキスト入力完了")

        # カテゴリ/長さ選択
        category = style_data["カテゴリ"]
        if category == "レディース":
            self.page.locator(form_config["category_ladies_radio"]).click()
            self.page.locator(form_config["length_select_ladies"]).select_option(
                label=style_data["長さ"]
            )
        elif category == "メンズ":
            self.page.locator(form_config["category_mens_radio"]).click()
            self.page.locator(form_config["length_select_mens"]).select_option(
                label=style_data["長さ"]
            )

        # クーポン選択
        coupon_config = form_config["coupon"]
        self.page.locator(coupon_config["select_button"]).click()
        self.page.wait_for_selector(coupon_config["modal_container"])

        coupon_selector = coupon_config["item_label_template"].format(
            name=style_data["クーポン名"]
        )
        self.page.locator(coupon_selector).first.click()
        self.page.locator(coupon_config["setting_button"]).click()
        self.page.wait_for_selector(coupon_config["modal_container"], state="hidden")

        # ハッシュタグ入力
        hashtag_config = form_config["hashtag"]
        hashtags = style_data["ハッシュタグ"].split(",")

        for tag in hashtags:
            tag = tag.strip()
            if tag:
                self.page.locator(hashtag_config["input_area"]).fill(tag)
                self.page.locator(hashtag_config["add_button"]).click()
                time.sleep(0.5)  # 反映待機

        # 登録
        self._click_and_wait(form_config["register_button"])
        self.page.wait_for_selector(form_config["complete_text"])

        # スタイル一覧へ戻る
        self._click_and_wait(form_config["back_to_list_button"])

        print(f"✓ スタイル登録完了: {style_data['スタイル名']}")

    def run(
        self,
        user_id: str,
        password: str,
        data_filepath: str,
        image_dir: str,
        salon_info: Optional[Dict] = None,
        progress_callback: Optional[Callable] = None
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
        """
        self.progress_callback = progress_callback

        try:
            # ブラウザ起動
            self._start_browser()

            # ログイン
            self.step_login(user_id, password, salon_info)

            # データ読み込み
            print(f"データファイル読み込み: {data_filepath}")
            if data_filepath.endswith(".csv"):
                df = pd.read_csv(data_filepath)
            elif data_filepath.endswith(".xlsx"):
                df = pd.read_excel(data_filepath)
            else:
                raise Exception("サポートされていないファイル形式です")

            print(f"✓ {len(df)}件のスタイルデータを読み込みました")

            # スタイル一覧ページへ移動
            self.step_navigate_to_style_list_page()

            # スタイルごとにループ処理
            image_dir_path = Path(image_dir)
            for index, row in df.iterrows():
                # 進捗コールバック（中止チェック）- try-exceptの外で呼び出し
                if self.progress_callback:
                    self.progress_callback(index, len(df))

                try:
                    print(f"\n--- スタイル {index + 1}/{len(df)} 処理中 ---")

                    # 画像パス生成
                    image_filename = row["画像名"]
                    image_path = image_dir_path / image_filename

                    if not image_path.exists():
                        raise Exception(f"画像ファイルが見つかりません: {image_filename}")

                    # スタイル処理
                    self.step_process_single_style(row.to_dict(), str(image_path))

                    # 成功時の進捗更新
                    if self.progress_callback:
                        self.progress_callback(index + 1, len(df))

                except Exception as e:
                    print(f"✗ エラー発生: {e}")
                    screenshot_path = self._take_screenshot(f"error-row{index+1}")

                    # エラー情報記録（呼び出し元で処理）
                    if self.progress_callback:
                        self.progress_callback(
                            index + 1,
                            len(df),
                            error={
                                "row_number": index + 2,  # ヘッダー行を考慮
                                "style_name": row.get("スタイル名", "不明"),
                                "field": "処理全体",
                                "reason": str(e),
                                "screenshot_path": screenshot_path
                            }
                        )

            print("\n✓ 全スタイルの処理が完了しました")

        except Exception as e:
            print(f"\n✗ 致命的エラー: {e}")
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

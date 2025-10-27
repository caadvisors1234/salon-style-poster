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

    # タイムアウト定数（ミリ秒）
    TIMEOUT_CLICK = 10000  # クリック操作
    TIMEOUT_LOAD = 30000   # ページ読み込み
    TIMEOUT_IMAGE_UPLOAD = 90000  # 画像アップロード
    TIMEOUT_WAIT_ELEMENT = 10000  # 要素待機
    IMAGE_PROCESSING_WAIT = 3  # 画像処理待機（秒）

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

        # セレクタチェック（visible状態のものだけ）
        for selector in robot_config.get("selectors", []):
            # 要素が存在し、かつ表示されている場合のみ検出
            locator = self.page.locator(selector)
            if locator.count() > 0:
                # 最初の要素が実際に表示されているかチェック
                try:
                    if locator.first.is_visible(timeout=1000):
                        print(f"✗ ロボット認証検出（セレクタ: {selector}）")
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
                        print(f"✗ ロボット認証検出（テキスト: {text}）")
                        self._take_screenshot("robot-detection")
                        return True
                except Exception:
                    pass

        return False

    def _click_and_wait(
        self,
        selector: str,
        click_timeout: Optional[int] = None,
        load_timeout: Optional[int] = None
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

        self.page.locator(selector).first.click(timeout=click_timeout)
        self.page.wait_for_load_state("networkidle", timeout=load_timeout)

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

    def step_navigate_to_style_list_page(self, use_direct_url: bool = False):
        """
        スタイル一覧ページへ移動

        Args:
            use_direct_url: True の場合、URLで直接遷移（エラー回復時用）
        """
        print("スタイル一覧ページへ移動中...")

        if use_direct_url:
            # 直接URLで遷移（エラー回復時）
            print("  - 直接URLで遷移します...")
            current_url = self.page.url
            # 現在のURLからベースURLを取得
            base_url = current_url.split('/CNB/')[0] if '/CNB/' in current_url else 'https://salonboard.com'
            style_list_url = f"{base_url}/CNB/draft/styleList/"
            print(f"  - 遷移先: {style_list_url}")
            self.page.goto(style_list_url, timeout=self.TIMEOUT_LOAD)
            self.page.wait_for_load_state("networkidle", timeout=self.TIMEOUT_LOAD)
        else:
            # 通常のナビゲーション
            nav_config = self.selectors["navigation"]

            # 掲載管理 → スタイル管理
            self._click_and_wait(nav_config["keisai_kanri"])
            self._click_and_wait(nav_config["style"])

        print("✓ スタイル一覧ページへ移動完了")

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
            print("エラー発生により、スタイル一覧ページに戻ります...")
            self.step_navigate_to_style_list_page()
            print("✓ スタイル一覧ページに戻りました")
            return True
        except Exception as nav_error:
            print(f"✗ 通常のナビゲーションに失敗: {nav_error}")

        # 通常のナビゲーションが失敗した場合、直接URLで遷移
        try:
            print("直接URLで遷移を試みます...")
            self.step_navigate_to_style_list_page(use_direct_url=True)
            print("✓ スタイル一覧ページに戻りました（直接URL）")
            return True
        except Exception as direct_error:
            print(f"✗ 直接URL遷移にも失敗: {direct_error}")
            print("⚠ スタイル一覧ページへの戻りを諦めます。次のスタイル処理時に再試行します。")
            return False

    def step_process_single_style(self, style_data: Dict, image_path: str):
        """
        1件のスタイル処理

        Args:
            style_data: スタイル情報の辞書
            image_path: 画像ファイルのパス
        """
        form_config = self.selectors["style_form"]

        # 新規登録ページへ
        try:
            print("新規登録ボタンをクリック中...")
            self.page.locator(form_config["new_style_button"]).first.click(timeout=self.TIMEOUT_CLICK)
            self.page.wait_for_load_state("networkidle", timeout=self.TIMEOUT_LOAD)
            print("✓ 新規登録ページへ移動完了")
        except Exception as e:
            raise StylePostError(f"新規登録ページへの移動に失敗しました: {e}", self._take_screenshot("error-new-style-page"))

        # 画像アップロード
        try:
            print("画像アップロード開始...")

            # アップロード開始前の待機（通信の安定化）
            print(f"  - 通信安定化のため待機中（1秒）...")
            time.sleep(1)

            print(f"  - アップロードエリアをクリック中...")
            self.page.locator(form_config["image"]["upload_area"]).click(timeout=self.TIMEOUT_CLICK)
            print(f"  - モーダル表示待機中...")
            self.page.wait_for_selector(form_config["image"]["modal_container"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            print(f"  - 画像ファイル選択中: {image_path}")
            self.page.locator(form_config["image"]["file_input"]).set_input_files(image_path)
            print(f"  - 画像処理待機中（{self.IMAGE_PROCESSING_WAIT}秒）...")
            time.sleep(self.IMAGE_PROCESSING_WAIT)

            # 送信ボタンの状態を確認
            submit_button = self.page.locator("input.imageUploaderModalSubmitButton")
            print(f"  - 送信ボタン確認中...")

            # ボタンが表示されるまで待機
            submit_button.wait_for(state="visible", timeout=self.TIMEOUT_WAIT_ELEMENT)

            # 強制的にクリック（JavaScriptで実行）
            print(f"  - 送信ボタンクリック中（JavaScript実行）...")
            submit_button.evaluate("el => el.click()")

            print(f"  - モーダル非表示待機中...")
            self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=self.TIMEOUT_IMAGE_UPLOAD)

            # 画像アップロード後のページ安定化待機
            print(f"  - ページ安定化待機中...")
            self.page.wait_for_load_state("networkidle", timeout=self.TIMEOUT_LOAD)

            # エラーダイアログの確認と処理
            error_dialog_selector = "div.modpopup01.sch.w400.cf.dialog"
            try:
                error_dialog = self.page.locator(error_dialog_selector)
                if error_dialog.count() > 0 and error_dialog.first.is_visible(timeout=1000):
                    # エラーメッセージを取得
                    error_message = self.page.locator(f"{error_dialog_selector} .message").inner_text()
                    print(f"  - エラーダイアログ検出: {error_message}")
                    # OKボタンをクリックして閉じる
                    ok_button = self.page.locator(f"{error_dialog_selector} a.accept")
                    ok_button.click(timeout=5000)
                    time.sleep(0.5)
                    raise Exception(f"画像アップロードエラー: {error_message}")
            except Exception as dialog_error:
                if "画像アップロードエラー" in str(dialog_error):
                    raise
                # ダイアログが存在しない場合は無視
                pass

            print("✓ 画像アップロード完了")
        except Exception as e:
            raise StylePostError(f"画像アップロードに失敗しました: {e}", self._take_screenshot("error-image-upload"))

        # スタイリスト名選択
        try:
            print("スタイリスト名選択中...")
            stylist_select = self.page.locator(form_config["stylist_name_select"])
            stylist_select.wait_for(state="visible", timeout=self.TIMEOUT_WAIT_ELEMENT)
            stylist_select.select_option(label=style_data["スタイリスト名"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            print("✓ スタイリスト名選択完了")
        except Exception as e:
            raise StylePostError(f"スタイリスト名の選択に失敗しました（スタイリスト: {style_data.get('スタイリスト名', '不明')}）: {e}", self._take_screenshot("error-stylist-select"))

        # テキスト入力
        try:
            print("テキスト入力中...")
            self.page.locator(form_config["stylist_comment_textarea"]).fill(style_data["コメント"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self.page.locator(form_config["style_name_input"]).fill(style_data["スタイル名"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self.page.locator(form_config["menu_detail_textarea"]).fill(style_data["メニュー内容"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            print("✓ テキスト入力完了")
        except Exception as e:
            raise StylePostError(f"テキスト入力に失敗しました: {e}", self._take_screenshot("error-text-input"))

        # カテゴリ/長さ選択
        try:
            print("カテゴリ/長さ選択中...")
            category = style_data["カテゴリ"]
            if category == "レディース":
                self.page.locator(form_config["category_ladies_radio"]).click(timeout=self.TIMEOUT_CLICK)
                self.page.locator(form_config["length_select_ladies"]).select_option(
                    label=style_data["長さ"], timeout=self.TIMEOUT_WAIT_ELEMENT
                )
            elif category == "メンズ":
                self.page.locator(form_config["category_mens_radio"]).click(timeout=self.TIMEOUT_CLICK)
                self.page.locator(form_config["length_select_mens"]).select_option(
                    label=style_data["長さ"], timeout=self.TIMEOUT_WAIT_ELEMENT
                )
            print("✓ カテゴリ/長さ選択完了")
        except Exception as e:
            raise StylePostError(f"カテゴリ/長さの選択に失敗しました（カテゴリ: {category}, 長さ: {style_data.get('長さ', '不明')}）: {e}", self._take_screenshot("error-category-length"))

        # クーポン選択
        try:
            print("クーポン選択中...")
            coupon_config = form_config["coupon"]
            self.page.locator(coupon_config["select_button"]).click(timeout=self.TIMEOUT_CLICK)
            self.page.wait_for_selector(coupon_config["modal_container"], timeout=self.TIMEOUT_WAIT_ELEMENT)

            coupon_selector = coupon_config["item_label_template"].format(
                name=style_data["クーポン名"]
            )
            self.page.locator(coupon_selector).first.click(timeout=self.TIMEOUT_CLICK)
            self.page.locator(coupon_config["setting_button"]).click(timeout=self.TIMEOUT_CLICK)
            self.page.wait_for_selector(coupon_config["modal_container"], state="hidden", timeout=self.TIMEOUT_WAIT_ELEMENT)
            print("✓ クーポン選択完了")
        except Exception as e:
            raise StylePostError(f"クーポンの選択に失敗しました（クーポン: {style_data.get('クーポン名', '不明')}）: {e}", self._take_screenshot("error-coupon-select"))

        # ハッシュタグ入力
        try:
            print("ハッシュタグ入力中...")
            hashtag_config = form_config["hashtag"]
            hashtags = style_data["ハッシュタグ"].split(",")

            for tag in hashtags:
                tag = tag.strip()
                if tag:
                    self.page.locator(hashtag_config["input_area"]).fill(tag, timeout=self.TIMEOUT_WAIT_ELEMENT)
                    self.page.locator(hashtag_config["add_button"]).click(timeout=self.TIMEOUT_CLICK)
                    time.sleep(0.5)  # 反映待機
            print("✓ ハッシュタグ入力完了")
        except Exception as e:
            raise StylePostError(f"ハッシュタグの入力に失敗しました: {e}", self._take_screenshot("error-hashtag"))

        # 登録
        try:
            print("登録ボタンクリック中...")
            self._click_and_wait(form_config["register_button"])
            self.page.wait_for_selector(form_config["complete_text"], timeout=self.TIMEOUT_LOAD)
            print("✓ 登録完了")
        except Exception as e:
            raise StylePostError(f"スタイル登録の完了に失敗しました: {e}", self._take_screenshot("error-register"))

        # スタイル一覧へ戻る
        try:
            print("スタイル一覧へ戻る...")
            self._click_and_wait(form_config["back_to_list_button"])
            print(f"✓ スタイル登録完了: {style_data['スタイル名']}")
        except Exception as e:
            raise StylePostError(f"スタイル一覧への戻りに失敗しました: {e}", self._take_screenshot("error-back-to-list"))

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

                    # スクリーンショット取得（StylePostErrorの場合は既に含まれている）
                    if isinstance(e, StylePostError) and e.screenshot_path:
                        screenshot_path = e.screenshot_path
                    else:
                        screenshot_path = self._take_screenshot(f"error-row{index+1}")

                    # エラー発生時はスタイル一覧ページに戻る
                    self._navigate_back_to_style_list_after_error()

                    # エラー情報記録（呼び出し元で処理）
                    error_field = self._get_error_field_from_exception(e)

                    if self.progress_callback:
                        self.progress_callback(
                            index + 1,
                            len(df),
                            error={
                                "row_number": index + 2,  # ヘッダー行を考慮
                                "style_name": row.get("スタイル名", "不明"),
                                "field": error_field,
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

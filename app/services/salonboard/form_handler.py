"""
SALON BOARD フォーム入力Mixin
スタイルフォームの各種入力処理を提供
"""
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from playwright.sync_api import Response

from .exceptions import StylePostError

logger = logging.getLogger(__name__)


class StyleFormHandlerMixin:
    """スタイルフォーム入力Mixin"""

    # 以下はSalonBoardBrowserManagerまたは他のMixinで定義される属性・メソッド
    page: object
    selectors: Dict
    TIMEOUT_CLICK: int
    TIMEOUT_LOAD: int
    TIMEOUT_IMAGE_UPLOAD: int
    TIMEOUT_WAIT_ELEMENT: int
    IMAGE_PROCESSING_WAIT: int
    WAIT_MEDIUM_BASE: int
    _last_failed_upload_reason: Optional[str]
    _human_pause: object
    _take_screenshot: object
    _click_and_wait: object
    _wait_for_upload_completion: object
    _emit_progress: object
    step_navigate_to_style_list_page: object

    def _upload_image(
        self,
        image_path: str,
        form_config: Dict,
        row_number: int,
        style_name: str
    ) -> List[Dict[str, object]]:
        """画像アップロード処理"""
        manual_upload_events = []
        image_filename = Path(image_path).name

        try:
            logger.info("画像アップロード開始...")
            self._last_failed_upload_reason = None

            logger.info("アップロードエリアをクリック中...")
            self.page.locator(form_config["image"]["upload_area"]).click(timeout=self.TIMEOUT_CLICK)
            self._human_pause(base_ms=self.WAIT_MEDIUM_BASE, jitter_ms=250, minimum_ms=400)

            logger.info("モーダル表示待機中...")
            self.page.wait_for_selector(form_config["image"]["modal_container"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=self.WAIT_MEDIUM_BASE, jitter_ms=250, minimum_ms=450)

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
            submit_button.wait_for(state="visible", timeout=self.TIMEOUT_WAIT_ELEMENT)

            try:
                submit_button.hover(timeout=2000)
            except Exception:
                pass
            self._human_pause(base_ms=650, jitter_ms=220, minimum_ms=350)

            # ネイティブクリック（hover/scrollを伴う）で送信
            logger.info("送信ボタンクリック中（ネイティブクリック）...")
            upload_predicate = lambda response: (
                "/CNB/imgreg/imgUpload/doUpload" in response.url
                and response.request.method.upper() == "POST"
            )

            upload_response: Optional["Response"] = None
            manual_upload_required = False
            manual_upload_reason = ""

            try:
                with self.page.expect_response(upload_predicate, timeout=self.TIMEOUT_IMAGE_UPLOAD) as upload_waiter:
                    try:
                        submit_button.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    try:
                        submit_button.click(timeout=self.TIMEOUT_CLICK)
                    except Exception:
                        try:
                            submit_button.hover(timeout=2000)
                        except Exception:
                            pass
                        self._human_pause(base_ms=500, jitter_ms=200, minimum_ms=250)
                        submit_button.click(timeout=self.TIMEOUT_CLICK, force=True)
                upload_response = upload_waiter.value
                logger.info("画像アップロードレスポンス取得: status=%s, url=%s", upload_response.status, upload_response.url)
            except PlaywrightTimeoutError:
                reason = self._last_failed_upload_reason or "imgUpload/doUpload のレスポンス待機がタイムアウトしました"
                manual_upload_reason = reason
                # NS_BINDING_ABORTED, ERR_ABORTED などをカバー
                if "ABORTED" in reason.upper():
                    manual_upload_required = True

                modal_hidden = False
                try:
                    self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=2000)
                    modal_hidden = True
                except PlaywrightTimeoutError:
                    pass

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
                raise Exception(
                    f"画像アップロードAPIが失敗しました (status={upload_response.status}, preview={body_preview}{extra})"
                )
            elif manual_upload_required:
                warning_message = (
                    f"画像アップロードリクエストがブラウザ側で中断されました (image={image_filename})。"
                    "SALON BOARDで手動アップロードを実施してください。"
                )
                logger.warning("%s", warning_message)
                manual_upload_events.append({
                    "row_number": row_number,
                    "style_name": style_name,
                    "field": "画像アップロード",
                    "reason": warning_message,
                    "image_name": image_filename,
                    "error_category": "IMAGE_UPLOAD_ABORTED",
                    "raw_error": manual_upload_reason,
                    "screenshot_path": ""
                })
                # 失敗検出時点で後続の完了ログやプレビュー待機を行わず、次工程へ進む
                return manual_upload_events

            self._human_pause(base_ms=680, jitter_ms=210, minimum_ms=350)

            logger.info("モーダル非表示待機中...")
            try:
                self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=self.TIMEOUT_IMAGE_UPLOAD)
            except PlaywrightTimeoutError as modal_timeout:
                try:
                    self.page.wait_for_selector(form_config["image"]["modal_container"], state="hidden", timeout=1000)
                    logger.warning("モーダル非表示待機がタイムアウトしましたが既に閉じています。")
                except PlaywrightTimeoutError:
                    raise Exception(
                        f"画像アップロードモーダルが閉じません (timeout={self.TIMEOUT_IMAGE_UPLOAD})"
                    ) from modal_timeout

            self._human_pause(base_ms=850, jitter_ms=300, minimum_ms=500)

            # 画像アップロード後のプレビュー確認
            logger.info("アップロード結果を確認中...")
            self._wait_for_upload_completion(
                upload_area_selector=form_config["image"]["upload_area"],
                modal_selector=form_config["image"]["modal_container"],
                timeout_ms=self.TIMEOUT_LOAD,
            )
            self._human_pause(base_ms=900, jitter_ms=320, minimum_ms=500)

            # エラーダイアログの確認
            error_dialog_selector = "div.modpopup01.sch.w400.cf.dialog"
            try:
                error_dialog = self.page.locator(error_dialog_selector)
                if error_dialog.count() > 0 and error_dialog.first.is_visible(timeout=1000):
                    error_message = self.page.locator(f"{error_dialog_selector} .message").inner_text()
                    logger.warning("エラーダイアログ検出: %s", error_message)
                    ok_button = self.page.locator(f"{error_dialog_selector} a.accept")
                    ok_button.click(timeout=5000)
                    self._human_pause(base_ms=650, jitter_ms=200, minimum_ms=400)
                    raise Exception(f"画像アップロードエラー: {error_message}")
            except Exception as dialog_error:
                if "画像アップロードエラー" in str(dialog_error):
                    raise
                pass

            logger.info("画像アップロード完了")
            return manual_upload_events

        except Exception as e:
            raise StylePostError(f"画像アップロードに失敗しました: {e}", self._take_screenshot("error-image-upload"))

    def _select_stylist(self, stylist_name: str, form_config: Dict):
        """スタイリスト名選択"""
        try:
            logger.info("スタイリスト名選択中...")
            stylist_select = self.page.locator(form_config["stylist_name_select"])
            stylist_select.wait_for(state="visible", timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause()

            stylist_select.select_option(label=stylist_name, timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=750, jitter_ms=240, minimum_ms=400)
            logger.info("スタイリスト名選択完了")
        except Exception as e:
            raise StylePostError(
                f"スタイリスト名の選択に失敗しました（スタイリスト: {stylist_name}）: {e}",
                self._take_screenshot("error-stylist-select")
            )

    def _fill_style_details(self, style_data: Dict, form_config: Dict):
        """テキスト項目入力"""
        try:
            logger.info("テキスト入力中...")
            self._human_pause()
            self.page.locator(form_config["stylist_comment_textarea"]).fill(
                style_data["コメント"], timeout=self.TIMEOUT_WAIT_ELEMENT
            )
            self._human_pause(base_ms=650, jitter_ms=220, minimum_ms=400)

            self.page.locator(form_config["style_name_input"]).fill(
                style_data["スタイル名"], timeout=self.TIMEOUT_WAIT_ELEMENT
            )
            self._human_pause(base_ms=650, jitter_ms=220, minimum_ms=400)

            self.page.locator(form_config["menu_detail_textarea"]).fill(
                style_data["メニュー内容"], timeout=self.TIMEOUT_WAIT_ELEMENT
            )
            self._human_pause(base_ms=750, jitter_ms=230, minimum_ms=400)
            logger.info("テキスト入力完了")
        except Exception as e:
            raise StylePostError(f"テキスト入力に失敗しました: {e}", self._take_screenshot("error-text-input"))

    def _select_category_and_length(self, category: str, length: str, form_config: Dict):
        """カテゴリ/長さ選択"""
        try:
            logger.info("カテゴリ/長さ選択中...")
            if category == "レディース":
                self._human_pause()
                self.page.locator(form_config["category_ladies_radio"]).click(timeout=self.TIMEOUT_CLICK)
                self._human_pause(base_ms=620, jitter_ms=200, minimum_ms=350)
                self.page.locator(form_config["length_select_ladies"]).select_option(
                    label=length, timeout=self.TIMEOUT_WAIT_ELEMENT
                )
            elif category == "メンズ":
                self._human_pause()
                self.page.locator(form_config["category_mens_radio"]).click(timeout=self.TIMEOUT_CLICK)
                self._human_pause(base_ms=620, jitter_ms=200, minimum_ms=350)
                self.page.locator(form_config["length_select_mens"]).select_option(
                    label=length, timeout=self.TIMEOUT_WAIT_ELEMENT
                )
            self._human_pause(base_ms=750, jitter_ms=220, minimum_ms=400)
            logger.info("カテゴリ/長さ選択完了")
        except Exception as e:
            raise StylePostError(
                f"カテゴリ/長さの選択に失敗しました（カテゴリ: {category}, 長さ: {length}）: {e}",
                self._take_screenshot("error-category-length")
            )

    def _select_coupon(self, coupon_name: str, form_config: Dict):
        """クーポン選択"""
        try:
            logger.info("クーポン選択中...")
            coupon_config = form_config["coupon"]
            self._human_pause()

            self.page.locator(coupon_config["select_button"]).click(timeout=self.TIMEOUT_CLICK)
            self.page.wait_for_selector(coupon_config["modal_container"], timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=720, jitter_ms=240, minimum_ms=400)

            coupon_selector = coupon_config["item_label_template"].format(name=coupon_name)
            self.page.locator(coupon_selector).first.click(timeout=self.TIMEOUT_CLICK)
            self._human_pause(base_ms=640, jitter_ms=220, minimum_ms=350)

            self.page.locator(coupon_config["setting_button"]).click(timeout=self.TIMEOUT_CLICK)
            self.page.wait_for_selector(coupon_config["modal_container"], state="hidden", timeout=self.TIMEOUT_WAIT_ELEMENT)
            self._human_pause(base_ms=780, jitter_ms=260, minimum_ms=450)
            logger.info("クーポン選択完了")
        except Exception as e:
            raise StylePostError(
                f"クーポンの選択に失敗しました（クーポン: {coupon_name}）: {e}",
                self._take_screenshot("error-coupon-select")
            )

    def _input_hashtags(self, hashtags_str: str, form_config: Dict):
        """ハッシュタグ入力"""
        try:
            logger.info("ハッシュタグ入力中...")
            hashtag_config = form_config["hashtag"]
            hashtags = hashtags_str.split(",")

            for tag in hashtags:
                tag = tag.strip()
                if tag:
                    self.page.locator(hashtag_config["input_area"]).fill(tag, timeout=self.TIMEOUT_WAIT_ELEMENT)
                    self.page.locator(hashtag_config["add_button"]).click(timeout=self.TIMEOUT_CLICK)
                    self._human_pause(base_ms=650, jitter_ms=210, minimum_ms=350)
            logger.info("ハッシュタグ入力完了")
        except Exception as e:
            raise StylePostError(f"ハッシュタグの入力に失敗しました: {e}", self._take_screenshot("error-hashtag"))

    def _submit_style_registration(self, form_config: Dict):
        """登録実行"""
        try:
            logger.info("登録ボタンクリック中...")
            self._click_and_wait(form_config["register_button"])
            self.page.wait_for_selector(form_config["complete_text"], timeout=self.TIMEOUT_LOAD)
            logger.info("登録完了")
        except Exception as e:
            raise StylePostError(f"スタイル登録の完了に失敗しました: {e}", self._take_screenshot("error-register"))

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

    def step_process_single_style(self, style_data: Dict, image_path: str, current_index: int) -> List[Dict[str, object]]:
        """
        1件のスタイル処理（リファクタリング版）
        """
        row_number = style_data.get("_row_number", 0)
        form_config = self.selectors["style_form"]
        style_name = style_data.get("スタイル名", "不明")

        # 新規登録ページへ
        try:
            logger.info("新規登録ボタンをクリック中...")
            self._click_and_wait(form_config["new_style_button"])
            logger.info("新規登録ページへ移動完了")
        except Exception as e:
            raise StylePostError(f"新規登録ページへの移動に失敗しました: {e}", self._take_screenshot("error-new-style-page"))

        # 1. 画像アップロード
        image_name = style_data.get("画像名", "")
        self._emit_progress(
            current_index,
            {
                "current_index": current_index + 1,
                "stage": "IMAGE_UPLOADING",
                "stage_label": "画像アップロード中",
                "message": f"画像[{image_name}]をアップロードしています...",
                "status": "working",
                "style_name": style_name
            }
        )
        manual_upload_events = self._upload_image(
            image_path, form_config, row_number, style_name
        )

        # 2. スタイリスト選択
        stylist_name = style_data["スタイリスト名"]
        self._emit_progress(
            current_index,
            {
                "current_index": current_index + 1,
                "stage": "STYLIST_SELECTING",
                "stage_label": "スタイリスト選択中",
                "message": f"スタイリスト[{stylist_name}]を選択しています...",
                "status": "working",
                "style_name": style_name
            }
        )
        self._select_stylist(stylist_name, form_config)

        # 3. テキスト入力
        self._emit_progress(
            current_index,
            {
                "current_index": current_index + 1,
                "stage": "TEXT_INPUTTING",
                "stage_label": "詳細入力中",
                "message": "スタイル詳細テキストを入力しています...",
                "status": "working",
                "style_name": style_name
            }
        )
        self._fill_style_details(style_data, form_config)

        # 4. カテゴリ/長さ選択
        self._emit_progress(
            current_index,
            {
                "current_index": current_index + 1,
                "stage": "CATEGORY_SELECTING",
                "stage_label": "カテゴリ設定中",
                "message": "カテゴリと長さを設定しています...",
                "status": "working",
                "style_name": style_name
            }
        )
        self._select_category_and_length(style_data["カテゴリ"], style_data.get("長さ", ""), form_config)

        # 5. クーポン選択
        coupon_name = style_data.get("クーポン名", "")
        if coupon_name:
            self._emit_progress(
                current_index,
                {
                    "current_index": current_index + 1,
                    "stage": "COUPON_SELECTING",
                    "stage_label": "クーポン設定中",
                    "message": f"クーポン[{coupon_name}]を設定しています...",
                    "status": "working",
                    "style_name": style_name
                }
            )
        self._select_coupon(coupon_name, form_config)

        # 6. ハッシュタグ入力
        hashtags = style_data.get("ハッシュタグ", "")
        if hashtags:
            self._emit_progress(
                current_index,
                {
                    "current_index": current_index + 1,
                    "stage": "HASHTAG_INPUTTING",
                    "stage_label": "ハッシュタグ入力中",
                    "message": "ハッシュタグを入力しています...",
                    "status": "working",
                    "style_name": style_name
                }
            )
        self._input_hashtags(hashtags, form_config)

        # 7. 登録
        self._emit_progress(
            current_index,
            {
                "current_index": current_index + 1,
                "stage": "REGISTERING",
                "stage_label": "登録処理中",
                "message": "スタイル情報を登録しています...",
                "status": "working",
                "style_name": style_name
            }
        )
        self._submit_style_registration(form_config)

        # 8. スタイル一覧へ戻る
        logger.info("スタイル一覧へ戻る...")
        back_to_list_button = form_config["back_to_list_button"]
        list_ready_selector = form_config["new_style_button"]
        back_navigation_timeout = 10000

        try:
            self._click_and_wait(back_to_list_button, load_timeout=back_navigation_timeout)
            self.page.wait_for_selector(list_ready_selector, timeout=self.TIMEOUT_LOAD)
            logger.info("スタイル登録完了: %s", style_data["スタイル名"])
        except Exception as navigation_error:
            logger.warning("通常の戻る操作に失敗（%s）。直接URLで一覧に戻ります。", navigation_error)
            try:
                self.step_navigate_to_style_list_page(use_direct_url=True)
                self.page.wait_for_selector(list_ready_selector, timeout=self.TIMEOUT_LOAD)
                logger.info("直接URLでスタイル一覧に戻りました")
            except Exception as direct_error:
                raise StylePostError(
                    f"スタイル一覧への戻りに失敗しました: {navigation_error}; 直接遷移も失敗: {direct_error}",
                    self._take_screenshot("error-back-to-list")
                )

        return manual_upload_events

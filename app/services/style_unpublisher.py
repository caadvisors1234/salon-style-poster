"""
SALON BOARDスタイル非掲載処理
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

from playwright.sync_api import Locator, TimeoutError as PlaywrightTimeoutError

from app.services.style_poster import SalonBoardStylePoster, StylePostError


class StyleUnpublishError(Exception):
    """非掲載処理専用のエラー"""

    def __init__(self, message: str, screenshot_path: str = ""):
        super().__init__(message)
        self.screenshot_path = screenshot_path


@dataclass
class UnpublishCandidate:
    """一覧上の1行を表すデータ"""

    style_number: int
    click_target: Locator


class SalonBoardStyleUnpublisher(SalonBoardStylePoster):
    """
    スタイル非掲載処理を行うクラス

    既存のブラウザ起動・ログイン・人間的待機などのロジックを継承し、
    スタイル一覧から指定範囲のスタイルを順次「非掲載」にする。
    """

    def run_unpublish(
        self,
        user_id: str,
        password: str,
        salon_top_url: str,
        range_start: int,
        range_end: int,
        exclude_numbers: Set[int],
        salon_info: Optional[Dict] = None,
        progress_callback: Optional[Callable[[int, int, Dict, Optional[Dict]], None]] = None,
    ) -> None:
        """
        非掲載処理のメインフロー
        """
        self.progress_callback = progress_callback
        target_numbers = [n for n in range(range_start, range_end + 1) if n not in exclude_numbers]
        expected_total = len(target_numbers)

        def emit_progress(
            completed: int,
            detail: Optional[Dict[str, object]] = None,
            *,
            error: Optional[Dict[str, object]] = None,
            total_override: Optional[int] = None,
        ) -> None:
            if not self.progress_callback:
                return
            total_value = total_override if total_override is not None else expected_total
            if detail is not None:
                payload = dict(detail)
                payload.setdefault("current_index", completed)
                payload.setdefault("total", total_value)
                self.progress_callback(completed, total_value, detail=payload, error=error)
            else:
                self.progress_callback(completed, total_value, detail=None, error=error)

        try:
            emit_progress(
                0,
                {
                    "stage": "BROWSER_STARTING",
                    "stage_label": "ブラウザ起動準備",
                    "message": "Playwrightを起動しています",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total,
                },
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
                    "total": expected_total,
                },
            )

            total_styles = self._fetch_style_count_from_hotpepper(salon_top_url)
            emit_progress(
                0,
                {
                    "stage": "TARGET_READY",
                    "stage_label": "対象件数を確認しました",
                    "message": f"スタイル総数: {total_styles}件 / 非掲載対象: {expected_total}件",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total,
                },
            )

            self.step_login(user_id, password, salon_info=salon_info)
            emit_progress(
                0,
                {
                    "stage": "LOGIN_COMPLETED",
                    "stage_label": "ログイン完了",
                    "message": "SALON BOARDへのログインが完了しました",
                    "status": "info",
                    "current_index": 0,
                    "total": expected_total,
                },
            )

            self.step_navigate_to_style_list_page()
            start_page = max(1, math.ceil(range_end / 150))
            self._go_to_style_list_page(start_page)
            current_page = start_page
            processed = 0

            while processed < expected_total:
                candidates = self._collect_candidates()
                filtered = [
                    c
                    for c in candidates
                    if range_start <= c.style_number <= range_end and c.style_number not in exclude_numbers
                ]

                if not filtered:
                    if current_page > 1:
                        current_page -= 1
                        self._go_to_style_list_page(current_page)
                        continue
                    break

                # 高い番号から処理してズレの影響を軽減
                filtered.sort(key=lambda c: c.style_number, reverse=True)
                target = filtered[0]

                emit_progress(
                    processed,
                    {
                        "stage": "UNPUBLISH_PROCESSING",
                        "stage_label": "非掲載処理中",
                        "message": f"{processed + 1}/{expected_total}件目: スタイル番号 {target.style_number} を非掲載中",
                        "status": "working",
                        "current_index": processed + 1,
                        "total": expected_total,
                        "style_number": target.style_number,
                    },
                )

                try:
                    self._unpublish_single_row(target, current_page)
                    processed += 1
                    emit_progress(
                        processed,
                        {
                            "stage": "UNPUBLISH_COMPLETED",
                            "stage_label": "非掲載完了",
                            "message": f"スタイル番号 {target.style_number} を非掲載にしました",
                            "status": "completed",
                            "current_index": processed,
                            "total": expected_total,
                            "style_number": target.style_number,
                        },
                    )
                except Exception as exc:
                    screenshot_path = ""
                    if isinstance(exc, StyleUnpublishError):
                        screenshot_path = exc.screenshot_path
                    elif isinstance(exc, StylePostError):
                        screenshot_path = exc.screenshot_path
                    else:
                        screenshot_path = self._take_screenshot("unpublish-error")

                    error_payload = {
                        "row_number": 0,
                        "style_name": f"番号 {target.style_number}",
                        "field": "非掲載",
                        "reason": str(exc),
                        "screenshot_path": screenshot_path,
                    }
                    emit_progress(
                        processed,
                        {
                            "stage": "UNPUBLISH_ERROR",
                            "stage_label": "非掲載エラー",
                            "message": f"スタイル番号 {target.style_number} の非掲載に失敗しました",
                            "status": "error",
                            "current_index": processed,
                            "total": expected_total,
                            "style_number": target.style_number,
                        },
                        error=error_payload,
                    )
                    # 一覧に戻ってリトライ可能状態にする
                    self._go_to_style_list_page(current_page)

            emit_progress(
                processed,
                {
                    "stage": "SUMMARY",
                    "stage_label": "処理完了",
                    "message": f"{processed}件の非掲載処理が完了しました",
                    "status": "success",
                    "current_index": processed,
                    "total": expected_total,
                },
            )
        finally:
            self._close_browser()

    def _fetch_style_count_from_hotpepper(self, salon_top_url: str) -> int:
        """
        HotPepperBeautyのスタイルページから件数を取得する
        """
        style_url = salon_top_url.rstrip("/") + "/style/"
        try:
            self.page.goto(style_url, timeout=self.TIMEOUT_LOAD)
            self.page.wait_for_load_state("domcontentloaded", timeout=self.TIMEOUT_LOAD)
            locator = self.page.locator("span.numberOfResult")
            locator.wait_for(state="visible", timeout=self.TIMEOUT_WAIT_ELEMENT)
            text_value = locator.inner_text().strip().replace(",", "")
            return int(text_value)
        except Exception:
            # 取得に失敗した場合は0を返す（呼び出し側でフォールバックメッセージを出す）
            return 0

    def _get_style_list_url(self, page_number: int = 1) -> str:
        """スタイル一覧のURLを生成"""
        current_url = self.page.url if self.page else "https://salonboard.com"
        base_url = current_url.split("/CNB/")[0] if "/CNB/" in current_url else "https://salonboard.com"
        suffix = "/CNB/draft/styleList/"
        if page_number > 1:
            return f"{base_url}{suffix}?pn={page_number}"
        return f"{base_url}{suffix}"

    def _go_to_style_list_page(self, page_number: int) -> None:
        """指定ページのスタイル一覧に移動"""
        target_url = self._get_style_list_url(page_number)
        self.page.goto(target_url, timeout=self.TIMEOUT_LOAD)
        self.page.wait_for_load_state("domcontentloaded", timeout=self.TIMEOUT_LOAD)

    def _collect_candidates(self) -> List[UnpublishCandidate]:
        """一覧テーブルから番号と非掲載ボタンのペアを取得"""
        selectors = self.selectors["style_list"]
        rows = self.page.locator(selectors["rows"])
        row_count = rows.count()
        candidates: List[UnpublishCandidate] = []

        for idx in range(row_count):
            row = rows.nth(idx)
            number_inputs = row.locator(selectors["style_number_input"])
            if number_inputs.count() == 0:
                continue
            style_number_raw = ""
            try:
                style_number_raw = number_inputs.first.input_value().strip()
            except Exception:
                try:
                    attr_value = number_inputs.first.get_attribute("value") or ""
                    style_number_raw = attr_value.strip()
                except Exception:
                    continue
            try:
                style_number = int(style_number_raw)
            except ValueError:
                continue

            unpublish_buttons = row.locator(selectors["unpublish_button"])
            if unpublish_buttons.count() == 0:
                continue

            candidates.append(UnpublishCandidate(style_number=style_number, click_target=unpublish_buttons.first))

        return candidates

    def _unpublish_single_row(self, candidate: UnpublishCandidate, current_page: int) -> None:
        """単一行の非掲載ボタンをクリックし、完了画面から一覧へ戻す"""
        complete_selector = self.selectors["style_list"]["unpublish_complete_text"]
        last_error: Exception | None = None

        for attempt in range(1, 4):
            dialog_handled = False

            def _handle_dialog(dialog):
                nonlocal dialog_handled
                dialog.accept()
                dialog_handled = True

            self.page.once("dialog", _handle_dialog)

            try:
                try:
                    with self.page.expect_navigation(wait_until="domcontentloaded", timeout=self.TIMEOUT_LOAD):
                        candidate.click_target.click(timeout=self.TIMEOUT_CLICK)
                except PlaywrightTimeoutError:
                    # ナビゲーションが発生しない場合もあるため、そのまま進める
                    pass

                try:
                    self.page.wait_for_selector(complete_selector, timeout=self.TIMEOUT_LOAD)
                except PlaywrightTimeoutError:
                    self.page.wait_for_timeout(1500)

                self._human_pause(base_ms=1000, jitter_ms=400, minimum_ms=700)
                return
            except Exception as exc:
                last_error = exc
                self._human_pause(base_ms=3000, jitter_ms=500, minimum_ms=2500)
            finally:
                self._go_to_style_list_page(current_page)
                if not dialog_handled:
                    self._human_pause(base_ms=500, jitter_ms=200, minimum_ms=300)

        raise StyleUnpublishError(
            f"非掲載操作に失敗しました（リトライ上限到達）: {last_error}",
            self._take_screenshot("unpublish-failed"),
        )

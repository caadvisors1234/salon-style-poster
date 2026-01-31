"""
SALON BOARDスタイル削除処理
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set

import logging

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from playwright.sync_api import Locator

from .style_poster import SalonBoardStylePoster
from .exceptions import StylePostError, StyleDeleteError

logger = logging.getLogger(__name__)


@dataclass
class DeleteCandidate:
    """一覧上の1行を表すデータ"""

    style_number: int
    click_target: Locator


class SalonBoardStyleDeleter(SalonBoardStylePoster):
    """
    スタイル削除処理を行うクラス

    既存のブラウザ起動・ログイン・人間的待機などのロジックを継承し、
    スタイル一覧から指定範囲のスタイルを順次「削除」する。
    """

    def run_delete(
        self,
        user_id: str,
        password: str,
        range_start: int,
        range_end: int,
        exclude_numbers: Set[int],
        salon_info: Optional[Dict] = None,
        progress_callback: Optional[Callable[[int, int, Dict, Optional[Dict]], None]] = None,
    ) -> None:
        """
        削除処理のメインフロー
        """
        self.progress_callback = progress_callback
        target_numbers = [n for n in range(range_start, range_end + 1) if n not in exclude_numbers]
        total_targets = len(target_numbers)
        success_count = 0
        error_count = 0

        logger.info(
            "[DELETE] start user=%s range=%s-%s exclude=%s total=%s",
            user_id,
            range_start,
            range_end,
            sorted(exclude_numbers),
            total_targets,
        )

        def emit_progress(
            completed: int,
            detail: Optional[Dict[str, object]] = None,
            *,
            error: Optional[Dict[str, object]] = None,
        ) -> None:
            if not self.progress_callback:
                return
            if detail is not None:
                payload = dict(detail)
                payload.setdefault("current_index", completed)
                payload.setdefault("total", total_targets)
                self.progress_callback(completed, total_targets, detail=payload, error=error)
            else:
                self.progress_callback(completed, total_targets, detail=None, error=error)

        try:
            emit_progress(
                0,
                {
                    "stage": "BROWSER_STARTING",
                    "stage_label": "ブラウザ起動準備",
                    "message": "Playwrightを起動しています",
                    "status": "info",
                    "current_index": 0,
                    "total": total_targets,
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
                    "total": total_targets,
                },
            )

            emit_progress(
                0,
                {
                    "stage": "TARGET_READY",
                    "stage_label": "対象件数を確認しました",
                    "message": f"削除対象: {total_targets}件",
                    "status": "info",
                    "current_index": 0,
                    "total": total_targets,
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
                    "total": total_targets,
                },
            )

            self.step_navigate_to_style_list_page()
            start_page = max(1, math.ceil(range_end / 150))
            self._go_to_style_list_page(start_page)
            current_page = start_page

            # 処理対象番号を降順ソート済みの deque として管理（番号ずれ対策、パフォーマンス改善）
            remaining_targets = deque(
                sorted(
                    [n for n in range(range_start, range_end + 1) if n not in exclude_numbers],
                    reverse=True  # 降順：大きい番号から
                )
            )

            while remaining_targets:
                # 処理対象の最大番号を指定して候補を探す
                target_number = remaining_targets[0]

                candidates = self._collect_candidates()
                logger.info(
                    "[DELETE] page=%s candidates=%s target_number=%s remaining=%s",
                    current_page,
                    len(candidates),
                    target_number,
                    len(remaining_targets),
                )

                # target_number に一致する候補を探す
                target = None
                for c in candidates:
                    if c.style_number == target_number:
                        target = c
                        break

                if target:
                    # 見つかった場合：処理して次の番号へ
                    emit_progress(
                        success_count,
                        {
                            "stage": "DELETE_PROCESSING",
                            "stage_label": "削除処理中",
                            "message": f"{success_count + 1}/{total_targets}件目: スタイル番号 {target_number} を削除中",
                            "status": "working",
                            "current_index": success_count + 1,
                            "total": total_targets,
                            "style_number": target_number,
                        },
                    )

                    try:
                        self._delete_single_row(target, current_page)
                        # 成功時のみカウントアップ
                        success_count += 1
                        remaining_targets.popleft()  # 処理済みを削除

                        logger.info(
                            "[DELETE] success style_number=%s success=%s/%s total=%s remaining=%s",
                            target_number,
                            success_count,
                            total_targets,
                            total_targets,
                            len(remaining_targets),
                        )
                        emit_progress(
                            success_count,
                            {
                                "stage": "DELETE_COMPLETED",
                                "stage_label": "削除完了",
                                "message": f"スタイル番号 {target_number} を削除しました",
                                "status": "completed",
                                "current_index": success_count,
                                "total": total_targets,
                                "style_number": target_number,
                            },
                        )
                        # 成功時は次の反復へ（_delete_single_row内で既に一覧に戻っている）
                        continue

                    except Exception as exc:
                        error_count += 1
                        screenshot_path = ""
                        if isinstance(exc, StyleDeleteError):
                            screenshot_path = exc.screenshot_path
                        elif isinstance(exc, StylePostError):
                            screenshot_path = exc.screenshot_path
                        else:
                            screenshot_path = self._take_screenshot("delete-error")

                        error_payload = {
                            "row_number": 0,
                            "style_name": f"番号 {target_number}",
                            "field": "削除",
                            "reason": str(exc),
                            "screenshot_path": screenshot_path,
                        }
                        # エラー時は success_count をカウントアップせずにエラー報告
                        emit_progress(
                            success_count,
                            {
                                "stage": "DELETE_ERROR",
                                "stage_label": "削除エラー",
                                "message": f"スタイル番号 {target_number} の削除に失敗しました。次のスタイルに進みます。",
                                "status": "error",
                                "current_index": success_count,
                                "total": total_targets,
                                "style_number": target_number,
                            },
                            error=error_payload,
                        )
                        logger.warning(
                            "[DELETE] error style_number=%s, skipping to next target (errors=%s)",
                            target_number,
                            error_count,
                        )
                        # エラーがあったスタイルはスキップして次へ
                        remaining_targets.popleft()
                        # _delete_single_row の finally で既に一覧に戻っている

                else:
                    # target_number が見つからない場合
                    logger.warning(
                        "[DELETE] target_number=%s not found on current page (page=%s)",
                        target_number,
                        current_page,
                    )

                    # 前のページを試す
                    if current_page > 1:
                        current_page -= 1
                        self._go_to_style_list_page(current_page)
                        continue
                    else:
                        # 最初のページまで探しても見つからない → エラー
                        emit_progress(
                            success_count,
                            {
                                "stage": "DELETE_NOT_FOUND",
                                "stage_label": "未処理のスタイルがあります",
                                "message": f"スタイル番号 {target_number} を一覧から見つけられませんでした",
                                "status": "warning",
                                "current_index": success_count,
                                "total": total_targets,
                                "style_number": target_number,
                            },
                            error={
                                "row_number": 0,
                                "style_name": f"番号 {target_number}",
                                "field": "削除",
                                "reason": "スタイル一覧に対象番号が見つかりませんでした",
                                "screenshot_path": self._take_screenshot("delete-not-found"),
                            },
                        )
                        raise StyleDeleteError(
                            f"スタイル番号 {target_number} が一覧で見つかりませんでした"
                        )

            # 最終サマリー：成功件数とエラー件数を明確に表示
            summary_message = (
                f"削除処理が完了しました: "
                f"成功 {success_count}件"
            )
            if error_count > 0:
                summary_message += f"、エラー {error_count}件"

            emit_progress(
                success_count,
                {
                    "stage": "SUMMARY",
                    "stage_label": "処理完了",
                    "message": summary_message,
                    "status": "success" if error_count == 0 else "partial_success",
                    "current_index": success_count,
                    "total": total_targets,
                },
            )
            logger.info(
                "[DELETE] summary: success=%s error=%s total=%s",
                success_count,
                error_count,
                total_targets,
            )
        finally:
            self._close_browser()

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

    def _collect_candidates(self) -> List[DeleteCandidate]:
        """一覧テーブルから番号と削除ボタンのペアを取得"""
        selectors = self.selectors["style_list"]
        rows = self.page.locator(selectors["rows"])
        row_count = rows.count()
        candidates: List[DeleteCandidate] = []

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

            delete_buttons = row.locator(selectors["delete_button"])
            if delete_buttons.count() == 0:
                continue

            candidates.append(DeleteCandidate(style_number=style_number, click_target=delete_buttons.first))

        return candidates

    def _delete_single_row(self, candidate: DeleteCandidate, current_page: int) -> None:
        """単一行の削除ボタンをクリックし、完了画面から一覧へ戻す"""
        complete_selector = self.selectors["style_list"]["delete_complete_text"]
        back_button_selector = self.selectors["style_form"]["back_to_list_button"]
        last_error: Exception | None = None

        for attempt in range(1, 4):
            dialog_handled = False
            navigated_back = False

            def _handle_dialog(dialog):
                nonlocal dialog_handled
                dialog.accept()
                dialog_handled = True

            self.page.once("dialog", _handle_dialog)

            try:
                # 1. 削除ボタンクリック（ダイアログ表示）
                try:
                    with self.page.expect_navigation(wait_until="domcontentloaded", timeout=self.TIMEOUT_LOAD):
                        candidate.click_target.click(timeout=self.TIMEOUT_CLICK)
                except PlaywrightTimeoutError:
                    # ナビゲーションが発生しない場合もあるため、そのまま進める
                    pass

                self._human_pause(base_ms=500, jitter_ms=200, minimum_ms=300)

                # 2. 完了画面の表示を待機
                try:
                    self.page.wait_for_selector(complete_selector, timeout=self.TIMEOUT_LOAD)
                except PlaywrightTimeoutError:
                    # 完了テキストが見つからない場合は少し待って進める
                    self.page.wait_for_timeout(1000)

                # 3. loader_overlay が非表示になるまで待機（クリック対策）
                self._wait_for_loader_overlay_disappeared(timeout_ms=30000)

                self._human_pause(base_ms=800, jitter_ms=300, minimum_ms=500)

                # 4. 「スタイル掲載情報一覧画面へ」ボタンをクリックして一覧に戻る
                try:
                    with self.page.expect_navigation(wait_until="domcontentloaded", timeout=self.TIMEOUT_LOAD):
                        self.page.locator(back_button_selector).first.click(timeout=self.TIMEOUT_CLICK)
                    navigated_back = True
                except PlaywrightTimeoutError:
                    # ナビゲーションが検知されない場合でも、ボタンクリック自体は成功している可能性がある
                    navigated_back = True

                # 5. 一覧画面の読み込み完了を待機
                self.page.wait_for_load_state("domcontentloaded", timeout=self.TIMEOUT_LOAD)

                # 6. loader_overlay が非表示になるまで待機
                self._wait_for_loader_overlay_disappeared(timeout_ms=30000)

                self._human_pause(base_ms=600, jitter_ms=250, minimum_ms=400)

                # 成功時のみリトライループを抜けて終了
                if navigated_back:
                    return

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[DELETE] attempt=%s failed: %s",
                    attempt,
                    exc,
                )
                self._human_pause(base_ms=2000, jitter_ms=500, minimum_ms=1500)

                # エラー時は確実に一覧に戻ることを試みる
                if not navigated_back:
                    try:
                        self._go_to_style_list_page(current_page)
                    except Exception as e:
                        logger.warning("[DELETE] failed to return to list: %s", e)

        # リトライ上限到達
        raise StyleDeleteError(
            f"削除操作に失敗しました（リトライ上限到達）: {last_error}",
            self._take_screenshot("delete-failed"),
        )

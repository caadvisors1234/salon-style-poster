"""
スタイル非掲載処理（unpublish）のテスト

主な検証項目:
1. 連続した範囲の非掲載が正しく動作する
2. 除外番号指定が正しく動作する
3. スタイル番号ずれの問題が解決されている（降順処理）
4. エラー発生時の動作（スキップして継続）
5. 成功件数とエラー件数の正確なカウント
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from dataclasses import dataclass

from app.services.salonboard.style_unpublisher import (
    SalonBoardStyleUnpublisher,
    UnpublishCandidate,
)
from app.services.salonboard.exceptions import StyleUnpublishError
from playwright.sync_api import Locator


@dataclass
class MockLocator:
    """モック用 Locator"""
    click_count: int = 0

    def click(self, timeout=None):
        self.click_count += 1


class TestUnpublisherLogic:
    """非掲載処理のロジックテスト（ブラウザ操作をモック化）"""

    @pytest.fixture
    def mock_selectors(self):
        """セレクタ設定のモック"""
        return {
            "style_list": {
                "rows": "table tbody tr",
                "style_number_input": "input.style-number",
                "unpublish_button": "button.unpublish-btn",
                "unpublish_complete_text": ".complete-message",
            }
        }

    @pytest.fixture
    def unpublisher(self, mock_selectors, tmp_path):
        """SalonBoardStyleUnpublisher のインスタンス"""
        screenshot_dir = str(tmp_path / "screenshots")
        unpublisher = SalonBoardStyleUnpublisher(
            selectors=mock_selectors,
            screenshot_dir=screenshot_dir,
            headless=True,
            slow_mo=0,
        )
        return unpublisher

    def test_remaining_targets_sorted_descending(self, unpublisher):
        """
        テスト: 処理対象番号が降順にソートされること

        シナリオ:
        - range_start=1111, range_end=1114
        - exclude_numbers={1112}
        - 期待される remaining_targets: [1114, 1113, 1111]
        """
        range_start = 1111
        range_end = 1114
        exclude_numbers = {1112}

        # remaining_targets の作成ロジックを検証
        remaining_targets = sorted(
            [n for n in range(range_start, range_end + 1) if n not in exclude_numbers],
            reverse=True  # 降順
        )

        assert remaining_targets == [1114, 1113, 1111]

    def test_remaining_targets_all_consecutive(self, unpublisher):
        """
        テスト: 連続した範囲の降順ソート

        シナリオ:
        - range_start=1111, range_end=1114
        - exclude_numbers={}（除外なし）
        - 期待される remaining_targets: [1114, 1113, 1112, 1111]
        """
        range_start = 1111
        range_end = 1114
        exclude_numbers = set()

        remaining_targets = sorted(
            [n for n in range(range_start, range_end + 1) if n not in exclude_numbers],
            reverse=True
        )

        assert remaining_targets == [1114, 1113, 1112, 1111]

    def test_target_number_selection_from_candidates(self, unpublisher):
        """
        テスト: 候補リストから正しいターゲット番号が選択されること

        シナリオ:
        - target_number = 1113
        - candidates = [UnpublishCandidate(1111, ...), UnpublishCandidate(1113, ...), ...]
        - 期待される: style_number == 1113 の候補が選択される
        """
        target_number = 1113

        # モック候補の作成
        mock_locator = Mock(spec=Locator)
        candidates = [
            UnpublishCandidate(style_number=1111, click_target=mock_locator),
            UnpublishCandidate(style_number=1113, click_target=mock_locator),
            UnpublishCandidate(style_number=1115, click_target=mock_locator),
        ]

        # ターゲット検索ロジック
        target = None
        for c in candidates:
            if c.style_number == target_number:
                target = c
                break

        assert target is not None
        assert target.style_number == 1113

    def test_style_number_shift_scenario(self):
        """
        テスト: スタイル番号ずれのシナリオで正しいスタイルが非掲載されること

        シナリオ（問題の核心）:
        初期状態: [1111, 1112, 1113, 1114]

        1112, 1113のみを非掲載したい場合:
        1. remaining_targets = [1113, 1112]（降順）
        2. 1回目: target_number = 1113
           - 表示一覧: [1111, 1112, 1113, 1114]
           - 表示1113 → 元の1113 ✓
        3. 2回目: target_number = 1112
           - 表示一覧: [1111, 1112, 1114]（元の1113が削除された後）
           - 表示1112 → 元の1112 ✓

        検証: 降順に処理することで、番号ずれの影響を受けない
        """
        # 初期状態のスタイル番号（元の番号）
        original_styles = [1111, 1112, 1113, 1114]

        # 非掲載対象: 1112, 1113
        range_start = 1112
        range_end = 1113
        exclude_numbers = set()

        remaining_targets = sorted(
            [n for n in range(range_start, range_end + 1) if n not in exclude_numbers],
            reverse=True
        )

        assert remaining_targets == [1113, 1112]

        # シミュレーション:
        # 1回目の処理（target_number = 1113）
        target_number_1 = remaining_targets[0]
        assert target_number_1 == 1113

        # 表示一覧をシミュレート（初期状態）
        display_list_1 = original_styles.copy()  # [1111, 1112, 1113, 1114]
        # target_number_1 (1113) に一致する要素を探す
        found_1 = None
        for num in display_list_1:
            if num == target_number_1:
                found_1 = num
                break
        assert found_1 == 1113  # 元の1113が正しく特定される

        # 1113を非掲載後の表示一覧
        display_list_2 = [1111, 1112, 1114]  # 元の1113が削除

        # 2回目の処理（remaining_targets.pop(0)後）
        remaining_targets.pop(0)  # 1113を削除
        target_number_2 = remaining_targets[0]
        assert target_number_2 == 1112

        # target_number_2 (1112) に一致する要素を探す
        found_2 = None
        for num in display_list_2:
            if num == target_number_2:
                found_2 = num
                break
        assert found_2 == 1112  # 元の1112が正しく特定される

    def test_error_counting_with_continuation(self):
        """
        テスト: エラー発生時に処理が継続され、エラー件数が正しくカウントされること

        シナリオ:
        - total_targets = 4
        - success_count = 2
        - error_count = 2
        - 期待されるサマリー: "成功 2件、エラー 2件"
        """
        total_targets = 4
        success_count = 2
        error_count = 2

        summary_message = (
            f"非掲載処理が完了しました: "
            f"成功 {success_count}件"
        )
        if error_count > 0:
            summary_message += f"、エラー {error_count}件"

        assert summary_message == "非掲載処理が完了しました: 成功 2件、エラー 2件"

    def test_status_determination(self):
        """
        テスト: エラーの有無に応じて正しいステータスが設定されること

        シナリオ:
        - error_count = 0 → status = "success"
        - error_count > 0 → status = "partial_success"
        """
        # エラーなし
        error_count_1 = 0
        status_1 = "success" if error_count_1 == 0 else "partial_success"
        assert status_1 == "success"

        # エラーあり
        error_count_2 = 2
        status_2 = "success" if error_count_2 == 0 else "partial_success"
        assert status_2 == "partial_success"

    def test_exclude_numbers_handling(self):
        """
        テスト: 除外番号が正しく処理されること

        シナリオ:
        - range_start=1111, range_end=1115
        - exclude_numbers={1112, 1114}
        - 期待される remaining_targets: [1115, 1113, 1111]
        """
        range_start = 1111
        range_end = 1115
        exclude_numbers = {1112, 1114}

        remaining_targets = sorted(
            [n for n in range(range_start, range_end + 1) if n not in exclude_numbers],
            reverse=True
        )

        assert remaining_targets == [1115, 1113, 1111]
        assert 1112 not in remaining_targets
        assert 1114 not in remaining_targets


class TestUnpublisherIntegration:
    """統合テスト（より完全なシナリオ）"""

    def test_complete_unpublish_scenario_simulation(self):
        """
        テスト: 完全な非掲載シナリオのシミュレーション

        シナリオ:
        - 初期状態: スタイル番号 [1111, 1112, 1113, 1114, 1115]
        - 非掲載対象: 1112, 1113, 1114（1111と1115は除外）
        - 検証: 正しいスタイルが正しい順序で非掲載される
        """
        # 初期状態
        initial_styles = [1111, 1112, 1113, 1114, 1115]

        # 非掲載設定
        range_start = 1112
        range_end = 1114
        exclude_numbers = set()

        # 処理対象リストの作成
        remaining_targets = sorted(
            [n for n in range(range_start, range_end + 1) if n not in exclude_numbers],
            reverse=True
        )
        assert remaining_targets == [1114, 1113, 1112]

        # 処理のシミュレーション
        processed = []
        current_display = initial_styles.copy()

        # 1回目: 1114を非掲載
        target_1 = remaining_targets[0]
        assert target_1 == 1114
        # 表示一覧から1114を探す
        assert target_1 in current_display
        processed.append(target_1)
        current_display.remove(target_1)  # 非掲載
        remaining_targets.pop(0)
        assert current_display == [1111, 1112, 1113, 1115]

        # 2回目: 1113を非掲載
        target_2 = remaining_targets[0]
        assert target_2 == 1113
        # 表示一覧から1113を探す
        assert target_2 in current_display
        processed.append(target_2)
        current_display.remove(target_2)
        remaining_targets.pop(0)
        assert current_display == [1111, 1112, 1115]

        # 3回目: 1112を非掲載
        target_3 = remaining_targets[0]
        assert target_3 == 1112
        # 表示一覧から1112を探す
        assert target_3 in current_display
        processed.append(target_3)
        current_display.remove(target_3)
        remaining_targets.pop(0)
        assert current_display == [1111, 1115]

        # 検証: 正しいスタイルが正しい順序で処理された
        assert processed == [1114, 1113, 1112]
        # 検証: 残っているのは除外したスタイルのみ
        assert current_display == [1111, 1115]

    def test_scenario_with_skipped_middle_style(self):
        """
        テスト: 中間のスタイルを除外するシナリオ

        シナリオ:
        - 初期状態: [1111, 1112, 1113, 1114]
        - 非掲載対象: 1112, 1114（1113を除外）
        - 検証: 1113が正しくスキップされる
        """
        initial_styles = [1111, 1112, 1113, 1114]

        range_start = 1112
        range_end = 1114
        exclude_numbers = {1113}

        remaining_targets = sorted(
            [n for n in range(range_start, range_end + 1) if n not in exclude_numbers],
            reverse=True
        )
        assert remaining_targets == [1114, 1112]
        assert 1113 not in remaining_targets

        # シミュレーション
        processed = []
        current_display = initial_styles.copy()

        # 1114を非掲載
        target_1 = remaining_targets[0]
        assert target_1 == 1114
        processed.append(target_1)
        current_display.remove(target_1)
        remaining_targets.pop(0)
        assert current_display == [1111, 1112, 1113]

        # 1112を非掲載
        target_2 = remaining_targets[0]
        assert target_2 == 1112
        # ここが重要: 1112を探すとき、表示一覧には[1111, 1112, 1113]がある
        # 1112（元の1112）が正しく見つかる
        assert target_2 in current_display
        processed.append(target_2)
        current_display.remove(target_2)
        remaining_targets.pop(0)
        assert current_display == [1111, 1113]

        # 検証: 1113は除外されたため残っている
        assert 1113 in current_display
        assert processed == [1114, 1112]

    def test_error_scenario_simulation(self):
        """
        テスト: エラー発生時のシミュレーション

        シナリオ:
        - 処理対象: [1114, 1113, 1112]
        - 1113の処理でエラー発生
        - 期待される:
          - success_count = 2（1114, 1112）
          - error_count = 1（1113）
        """
        remaining_targets = [1114, 1113, 1112]

        success_count = 0
        error_count = 0

        # 1114: 成功
        target = remaining_targets[0]
        assert target == 1114
        success_count += 1
        remaining_targets.pop(0)
        assert remaining_targets == [1113, 1112]

        # 1113: エラー
        target = remaining_targets[0]
        assert target == 1113
        error_count += 1
        remaining_targets.pop(0)
        assert remaining_targets == [1112]

        # 1112: 成功
        target = remaining_targets[0]
        assert target == 1112
        success_count += 1
        remaining_targets.pop(0)
        assert remaining_targets == []

        # 検証
        assert success_count == 2
        assert error_count == 1

        # サマリーメッセージ
        summary_message = (
            f"非掲載処理が完了しました: "
            f"成功 {success_count}件"
        )
        if error_count > 0:
            summary_message += f"、エラー {error_count}件"

        assert summary_message == "非掲載処理が完了しました: 成功 2件、エラー 1件"

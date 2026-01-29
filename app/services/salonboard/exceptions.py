"""
SALON BOARD 自動化処理の例外クラス定義
"""


class StylePostError(Exception):
    """スタイル投稿エラー（スクリーンショット情報付き）"""

    def __init__(self, message: str, screenshot_path: str = ""):
        super().__init__(message)
        self.screenshot_path = screenshot_path


class StyleUnpublishError(Exception):
    """非掲載処理専用のエラー"""

    def __init__(self, message: str, screenshot_path: str = ""):
        super().__init__(message)
        self.screenshot_path = screenshot_path

"""
SALON BOARD 自動化サービスパッケージ

このパッケージはSALON BOARDへのスタイル投稿・削除処理を提供します。
"""

from .exceptions import StylePostError, StyleDeleteError, RobotDetectionError
from .style_poster import SalonBoardStylePoster, load_selectors
from .style_deleter import SalonBoardStyleDeleter

__all__ = [
    "StylePostError",
    "StyleDeleteError",
    "RobotDetectionError",
    "SalonBoardStylePoster",
    "SalonBoardStyleDeleter",
    "load_selectors",
]

"""
SALON BOARD 自動化サービスパッケージ

このパッケージはSALON BOARDへのスタイル投稿・非掲載処理を提供します。
"""

from .exceptions import StylePostError, StyleUnpublishError, RobotDetectionError
from .style_poster import SalonBoardStylePoster, load_selectors
from .style_unpublisher import SalonBoardStyleUnpublisher

__all__ = [
    "StylePostError",
    "StyleUnpublishError",
    "RobotDetectionError",
    "SalonBoardStylePoster",
    "SalonBoardStyleUnpublisher",
    "load_selectors",
]

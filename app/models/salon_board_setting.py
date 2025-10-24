"""
SalonBoardSettingモデル
SALON BOARD接続設定
"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class SalonBoardSetting(Base):
    """SALON BOARD設定モデル"""

    __tablename__ = "salon_board_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    setting_name = Column(String(100), nullable=False)
    sb_user_id = Column(String(255), nullable=False)
    encrypted_sb_password = Column(String(512), nullable=False)
    salon_id = Column(String(100), nullable=True)
    salon_name = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    # リレーション
    user = relationship("User", back_populates="salon_board_settings")

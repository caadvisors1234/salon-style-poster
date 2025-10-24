"""
Userモデル
システム利用者のアカウント情報
"""
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class User(Base):
    """ユーザーモデル"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        String(50),
        nullable=False,
        default="user"
    )
    is_active = Column(Boolean, nullable=False, server_default='true')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())

    # CHECK制約: roleは'admin'または'user'のみ
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="users_role_check"),
    )

    # リレーション
    salon_board_settings = relationship(
        "SalonBoardSetting",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    current_task = relationship(
        "CurrentTask",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

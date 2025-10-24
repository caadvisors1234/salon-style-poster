"""
CurrentTaskモデル
現在実行中のタスク情報
"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class CurrentTask(Base):
    """現在実行中タスクモデル"""

    __tablename__ = "current_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # ユーザー単位のシングルタスク保証
        index=True
    )
    status = Column(String(50), nullable=False, index=True)
    total_items = Column(Integer, nullable=False)
    completed_items = Column(Integer, nullable=False, default=0)
    error_info_json = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())

    # CHECK制約
    __table_args__ = (
        CheckConstraint(
            "status IN ('PROCESSING', 'CANCELLING', 'SUCCESS', 'FAILURE')",
            name="current_tasks_status_check"
        ),
        CheckConstraint("total_items >= 0", name="current_tasks_total_items_check"),
        CheckConstraint("completed_items >= 0", name="current_tasks_completed_items_check"),
    )

    # リレーション
    user = relationship("User", back_populates="current_task")

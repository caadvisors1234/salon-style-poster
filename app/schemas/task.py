"""
Task関連スキーマ
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Literal
from uuid import UUID


class TaskCreate(BaseModel):
    """タスク作成スキーマ"""
    setting_id: int = Field(..., description="使用するSALON BOARD設定ID")


class TaskStatus(BaseModel):
    """タスクステータススキーマ"""
    task_id: UUID
    status: Literal["PROCESSING", "CANCELLING", "SUCCESS", "FAILURE"]
    total_items: int
    completed_items: int
    progress: float = Field(..., ge=0.0, le=100.0, description="進捗率（0.0〜100.0）")
    has_errors: bool
    error_count: int = Field(default=0, description="エラー件数")
    created_at: datetime

    class Config:
        from_attributes = True


class ErrorDetail(BaseModel):
    """エラー詳細スキーマ"""
    row_number: int = Field(..., description="CSVファイルの行番号")
    style_name: str = Field(..., description="スタイル名")
    field: str = Field(..., description="エラーが発生したフィールド名")
    reason: str = Field(..., description="エラー原因の詳細説明")
    screenshot_url: str = Field(default="", description="エラー発生時のスクリーンショット画像URL")


class ErrorReport(BaseModel):
    """エラーレポートスキーマ"""
    task_id: UUID
    total_errors: int
    errors: List[ErrorDetail]

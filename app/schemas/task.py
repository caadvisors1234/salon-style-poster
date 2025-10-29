"""
Task関連スキーマ
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
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
    manual_upload_count: int = Field(default=0, description="手動画像登録が必要な件数")
    created_at: datetime
    detail: Optional[Dict[str, Any]] = Field(default=None, description="進捗詳細情報")

    class Config:
        from_attributes = True


class ErrorDetail(BaseModel):
    """エラー詳細スキーマ"""
    row_number: int = Field(..., description="CSVファイルの行番号")
    style_name: str = Field(..., description="スタイル名")
    field: str = Field(..., description="エラーが発生したフィールド名")
    reason: str = Field(..., description="エラー原因の詳細説明")
    screenshot_url: str = Field(default="", description="エラー発生時のスクリーンショット画像URL")
    image_name: Optional[str] = Field(default=None, description="関連する画像ファイル名")
    error_category: Optional[str] = Field(default=None, description="エラー種別")
    raw_error: Optional[str] = Field(default=None, description="システムログ上の詳細情報")


class ManualUploadDetail(BaseModel):
    """自動アップロードから漏れた画像の情報"""
    row_number: int = Field(..., description="CSVファイルの行番号")
    style_name: str = Field(..., description="スタイル名")
    image_name: str = Field(..., description="手動登録が必要な画像ファイル名")
    reason: str = Field(..., description="手動登録が必要になった理由")
    raw_error: Optional[str] = Field(default=None, description="内部ログ上の補足情報")


class ErrorReport(BaseModel):
    """エラーレポートスキーマ"""
    task_id: UUID
    total_errors: int
    errors: List[ErrorDetail]
    manual_uploads: List[ManualUploadDetail] = Field(default_factory=list, description="手動登録が必要な画像一覧")
    manual_upload_count: int = Field(default=0, description="手動登録が必要な画像件数")

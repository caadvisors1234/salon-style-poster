"""
SALON BOARD設定関連スキーマ
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


class SalonBoardSettingBase(BaseModel):
    """SALON BOARD設定ベーススキーマ"""
    setting_name: str = Field(..., max_length=100, description="設定名")
    sb_user_id: str = Field(..., max_length=255, description="SALON BOARDログインID")
    salon_id: Optional[str] = Field(None, max_length=100, description="サロンID（複数店舗用）")
    salon_name: Optional[str] = Field(None, max_length=255, description="サロン名（複数店舗用）")


class SalonBoardSettingCreate(SalonBoardSettingBase):
    """SALON BOARD設定作成スキーマ"""
    sb_password: str = Field(..., description="SALON BOARDパスワード（暗号化して保存）")


class SalonBoardSettingUpdate(BaseModel):
    """SALON BOARD設定更新スキーマ"""
    setting_name: Optional[str] = Field(None, max_length=100)
    sb_user_id: Optional[str] = Field(None, max_length=255)
    sb_password: Optional[str] = Field(None, description="新しいパスワード（指定時のみ更新）")
    salon_id: Optional[str] = Field(None, max_length=100)
    salon_name: Optional[str] = Field(None, max_length=255)


class SalonBoardSetting(SalonBoardSettingBase):
    """SALON BOARD設定レスポンススキーマ"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SalonBoardSettingList(BaseModel):
    """SALON BOARD設定一覧レスポンススキーマ"""
    settings: List[SalonBoardSetting]

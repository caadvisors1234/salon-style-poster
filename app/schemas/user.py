"""
User関連スキーマ
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import List, Literal, Optional


class UserBase(BaseModel):
    """ユーザーベーススキーマ"""
    email: EmailStr


class UserCreate(UserBase):
    """ユーザー作成スキーマ"""
    password: str = Field(..., min_length=8, description="パスワード（8文字以上）")
    role: Literal["admin", "user"] = "user"
    is_active: bool = True


class UserUpdate(BaseModel):
    """ユーザー更新スキーマ"""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, description="新しいパスワード（8文字以上）")
    role: Optional[Literal["admin", "user"]] = None
    is_active: Optional[bool] = None


class User(UserBase):
    """ユーザーレスポンススキーマ"""
    id: int
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserInDB(User):
    """DBユーザースキーマ（内部使用）"""
    hashed_password: str


class UserList(BaseModel):
    """ユーザー一覧レスポンススキーマ"""
    total: int
    users: List[User]

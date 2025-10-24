"""
JWT Token関連スキーマ
"""
from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """トークンレスポンス"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """トークンペイロードデータ"""
    email: Optional[str] = None

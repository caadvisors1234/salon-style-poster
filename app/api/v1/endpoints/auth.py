"""
認証エンドポイント
- ログイン（トークン取得）
- 現在のユーザー情報取得
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_current_user
from app.db.session import get_db
from app.crud import user as crud_user
from app.schemas.token import Token
from app.schemas.user import User

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    ログイン（トークン取得）

    Args:
        form_data: OAuth2パスワードフォームデータ
        db: データベースセッション

    Returns:
        Token: アクセストークン

    Raises:
        HTTPException: 認証失敗時
    """
    # ユーザー取得
    user = crud_user.get_user_by_email(db, email=form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # パスワード検証
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # アクセストークン生成
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def read_users_me(
    current_user: User = Depends(get_current_user)
):
    """
    現在のユーザー情報取得

    Args:
        current_user: 現在のユーザー（依存注入）

    Returns:
        User: ユーザー情報
    """
    return current_user

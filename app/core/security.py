"""
セキュリティ関連機能
- パスワードハッシュ化（bcrypt）
- JWT生成/検証
- Fernet暗号化/復号化
- 現在ユーザー取得
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.crud import user as crud_user


# パスワードハッシュ化コンテキスト（bcrypt）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2スキーム（JWT Bearer）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Fernet暗号化インスタンス
fernet = Fernet(settings.ENCRYPTION_KEY.encode())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    パスワード検証

    Args:
        plain_password: 平文パスワード
        hashed_password: ハッシュ化されたパスワード

    Returns:
        bool: 検証結果
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    パスワードハッシュ化

    Args:
        password: 平文パスワード

    Returns:
        str: ハッシュ化されたパスワード
    """
    return pwd_context.hash(password)


def encrypt_password(password: str) -> str:
    """
    パスワード暗号化（Fernet）
    SALON BOARDパスワードの暗号化用

    Args:
        password: 平文パスワード

    Returns:
        str: 暗号化されたパスワード（Base64エンコード）
    """
    encrypted = fernet.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    パスワード復号化（Fernet）

    Args:
        encrypted_password: 暗号化されたパスワード

    Returns:
        str: 平文パスワード
    """
    decrypted = fernet.decrypt(encrypted_password.encode())
    return decrypted.decode()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWTアクセストークン生成

    Args:
        data: トークンに含めるデータ
        expires_delta: 有効期限（指定しない場合はデフォルト値使用）

    Returns:
        str: JWTトークン
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[str]:
    """
    JWTトークンのデコードと検証

    Args:
        token: JWTトークン

    Returns:
        Optional[str]: ユーザーのメールアドレス（トークンが無効な場合はNone）
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    現在ログイン中のユーザーを取得（依存関数）

    Args:
        token: JWTトークン
        db: データベースセッション

    Returns:
        User: ユーザーモデル

    Raises:
        HTTPException: 認証失敗時
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = decode_access_token(token)
    if email is None:
        raise credentials_exception

    user = crud_user.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception

    return user


async def get_current_admin_user(
    current_user = Depends(get_current_user)
):
    """
    現在のユーザーが管理者かチェック（依存関数）

    Args:
        current_user: 現在のユーザー

    Returns:
        User: 管理者ユーザー

    Raises:
        HTTPException: 管理者権限がない場合
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

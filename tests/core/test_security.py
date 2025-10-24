from datetime import timedelta
from jose import jwt

from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings

def test_verify_password():
    """パスワード検証のテスト"""
    password = "plainpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(password, hashed_password) is True
    assert verify_password("wrongpassword", hashed_password) is False

def test_get_password_hash():
    """パスワードハッシュ化のテスト"""
    password = "plainpassword"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)
    assert hash1 != hash2  # ソルトが効いているため、毎回ハッシュは異なる
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)

def test_create_access_token():
    """アクセストークン生成のテスト"""
    data = {"sub": "test@example.com"}
    expires_delta = timedelta(minutes=15)

    token = create_access_token(data, expires_delta)
    
    decoded_payload = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    
    assert decoded_payload["sub"] == "test@example.com"
    assert "exp" in decoded_payload

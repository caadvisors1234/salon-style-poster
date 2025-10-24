"""
User CRUD操作
"""
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    IDでユーザー取得

    Args:
        db: データベースセッション
        user_id: ユーザーID

    Returns:
        Optional[User]: ユーザー（存在しない場合はNone）
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    メールアドレスでユーザー取得

    Args:
        db: データベースセッション
        email: メールアドレス

    Returns:
        Optional[User]: ユーザー（存在しない場合はNone）
    """
    return db.query(User).filter(User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100, role: Optional[str] = None) -> List[User]:
    """
    ユーザー一覧取得

    Args:
        db: データベースセッション
        skip: スキップ件数
        limit: 取得上限件数
        role: 役割フィルタ（"admin" or "user"）

    Returns:
        List[User]: ユーザーリスト
    """
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.offset(skip).limit(limit).all()


def get_users_count(db: Session, role: Optional[str] = None) -> int:
    """
    ユーザー総数取得

    Args:
        db: データベースセッション
        role: 役割フィルタ

    Returns:
        int: ユーザー総数
    """
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.count()


def create_user(db: Session, user: UserCreate) -> User:
    """
    ユーザー作成

    Args:
        db: データベースセッション
        user: ユーザー作成スキーマ

    Returns:
        User: 作成されたユーザー
    """
    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role=user.role,
        is_active=user.is_active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
    """
    ユーザー情報更新

    Args:
        db: データベースセッション
        user_id: ユーザーID
        user_update: ユーザー更新スキーマ

    Returns:
        Optional[User]: 更新されたユーザー（存在しない場合はNone）
    """
    db_user = get_user_by_id(db, user_id)
    if db_user:
        update_data = user_update.model_dump(exclude_unset=True)

        # パスワードが含まれている場合はハッシュ化
        if "password" in update_data and update_data["password"]:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        # フィールドを更新
        for field, value in update_data.items():
            setattr(db_user, field, value)

        db.commit()
        db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    """
    ユーザー削除

    Args:
        db: データベースセッション
        user_id: ユーザーID

    Returns:
        bool: 削除成功（True）/ 失敗（False）
    """
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False

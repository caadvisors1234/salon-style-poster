"""
ユーザー管理エンドポイント（管理者専用）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.core.security import get_current_admin_user, get_password_hash
from app.crud import user as crud_user
from app.schemas.user import User, UserCreate, UserUpdate, UserList

router = APIRouter()


def _normalize_email(email: str) -> str:
    """メールアドレスを正規化（前後空白除去 + 小文字化）"""
    return email.strip().lower()


@router.get("/", response_model=UserList)
async def get_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """ユーザー一覧取得（管理者のみ）"""
    users = crud_user.get_users(db, skip=skip, limit=limit, role=role)
    total = crud_user.get_users_count(db, role=role)
    return {"total": total, "users": users}


@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """ユーザー作成（管理者のみ）"""
    normalized_email = _normalize_email(user.email)

    # メールアドレス重複チェック
    db_user = crud_user.get_user_by_email(db, email=normalized_email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    hashed_password = get_password_hash(user.password)
    normalized_user = UserCreate(
        email=normalized_email,
        password=user.password,
        role=user.role,
        is_active=user.is_active,
    )
    return crud_user.create_user(db, user=normalized_user, hashed_password=hashed_password)


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """ユーザー情報取得（管理者のみ）"""
    db_user = crud_user.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """ユーザー情報更新（管理者のみ、パスワード更新含む）"""
    # 自身の非アクティブ化・ロール降格を防止
    if user_id == current_admin.id:
        if user_update.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )
        if user_update.role and user_update.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role"
            )

    normalized_email: Optional[str] = None

    # メールアドレス重複チェック（変更する場合）
    if user_update.email:
        normalized_email = _normalize_email(user_update.email)
        existing_user = crud_user.get_user_by_email(db, normalized_email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )

    # パスワード更新処理（指定された場合）
    if user_update.password:
        # パスワードをハッシュ化
        hashed_password = get_password_hash(user_update.password)
        # UserUpdateスキーマからpasswordを除外し、hashed_passwordに置き換え
        update_data = user_update.model_dump(exclude_unset=True, exclude={'password'})
        if normalized_email:
            update_data["email"] = normalized_email

        # ユーザー取得
        db_user = crud_user.get_user_by_id(db, user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # フィールド更新
        for field, value in update_data.items():
            setattr(db_user, field, value)

        # ハッシュ化されたパスワードを設定
        db_user.hashed_password = hashed_password

        db.commit()
        db.refresh(db_user)
        return db_user
    else:
        # パスワード更新なしの通常更新
        if normalized_email:
            # model_copyでemailだけ正規化値に差し替え
            user_update = user_update.model_copy(update={"email": normalized_email})
        db_user = crud_user.update_user(db, user_id, user_update)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return db_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """ユーザー削除（管理者のみ）"""
    # 自分自身の削除は禁止
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    success = crud_user.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

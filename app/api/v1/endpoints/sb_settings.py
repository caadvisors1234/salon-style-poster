"""
SALON BOARD設定管理エンドポイント
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.crud import salon_board_setting as crud_setting
from app.schemas.user import User
from app.schemas.salon_board_setting import (
    SalonBoardSetting,
    SalonBoardSettingCreate,
    SalonBoardSettingUpdate,
    SalonBoardSettingList
)

router = APIRouter()


@router.get("/", response_model=SalonBoardSettingList)
async def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """自分のSALON BOARD設定一覧取得"""
    settings = crud_setting.get_settings_by_user_id(db, current_user.id)
    return {"settings": settings}


@router.post("/", response_model=SalonBoardSetting, status_code=status.HTTP_201_CREATED)
async def create_setting(
    setting: SalonBoardSettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SALON BOARD設定作成"""
    return crud_setting.create_setting(db, setting, current_user.id)


@router.put("/{setting_id}", response_model=SalonBoardSetting)
async def update_setting(
    setting_id: int,
    setting_update: SalonBoardSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SALON BOARD設定更新"""
    # 設定存在確認
    db_setting = crud_setting.get_setting_by_id(db, setting_id)
    if not db_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found"
        )

    # 権限確認（自分の設定のみ更新可能）
    if db_setting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own settings"
        )

    return crud_setting.update_setting(db, setting_id, setting_update)


@router.delete("/{setting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SALON BOARD設定削除"""
    # 設定存在確認
    db_setting = crud_setting.get_setting_by_id(db, setting_id)
    if not db_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found"
        )

    # 権限確認（自分の設定のみ削除可能）
    if db_setting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own settings"
        )

    crud_setting.delete_setting(db, setting_id)

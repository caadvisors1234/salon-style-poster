"""
SALON BOARD設定 CRUD操作
"""
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.salon_board_setting import SalonBoardSetting
from app.schemas.salon_board_setting import SalonBoardSettingCreate, SalonBoardSettingUpdate
from app.core.security import encrypt_password


def get_setting_by_id(db: Session, setting_id: int) -> Optional[SalonBoardSetting]:
    """
    IDで設定取得

    Args:
        db: データベースセッション
        setting_id: 設定ID

    Returns:
        Optional[SalonBoardSetting]: 設定（存在しない場合はNone）
    """
    return db.query(SalonBoardSetting).filter(SalonBoardSetting.id == setting_id).first()


def get_settings_by_user_id(db: Session, user_id: int) -> List[SalonBoardSetting]:
    """
    ユーザーIDで設定一覧取得

    Args:
        db: データベースセッション
        user_id: ユーザーID

    Returns:
        List[SalonBoardSetting]: 設定リスト
    """
    return db.query(SalonBoardSetting).filter(SalonBoardSetting.user_id == user_id).all()


def create_setting(db: Session, setting: SalonBoardSettingCreate, user_id: int) -> SalonBoardSetting:
    """
    SALON BOARD設定作成

    Args:
        db: データベースセッション
        setting: 設定作成スキーマ
        user_id: ユーザーID

    Returns:
        SalonBoardSetting: 作成された設定
    """
    # パスワード暗号化
    encrypted_password = encrypt_password(setting.sb_password)

    db_setting = SalonBoardSetting(
        user_id=user_id,
        setting_name=setting.setting_name,
        sb_user_id=setting.sb_user_id,
        encrypted_sb_password=encrypted_password,
        salon_id=setting.salon_id,
        salon_name=setting.salon_name
    )
    db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting


def update_setting(
    db: Session,
    setting_id: int,
    setting_update: SalonBoardSettingUpdate
) -> Optional[SalonBoardSetting]:
    """
    SALON BOARD設定更新

    Args:
        db: データベースセッション
        setting_id: 設定ID
        setting_update: 設定更新スキーマ

    Returns:
        Optional[SalonBoardSetting]: 更新された設定（存在しない場合はNone）
    """
    db_setting = get_setting_by_id(db, setting_id)
    if not db_setting:
        return None

    # 指定されたフィールドのみ更新
    update_data = setting_update.model_dump(exclude_unset=True)

    # パスワードが指定されている場合は暗号化
    if "sb_password" in update_data and update_data["sb_password"]:
        update_data["encrypted_sb_password"] = encrypt_password(update_data.pop("sb_password"))

    for field, value in update_data.items():
        setattr(db_setting, field, value)

    db.commit()
    db.refresh(db_setting)
    return db_setting


def delete_setting(db: Session, setting_id: int) -> bool:
    """
    SALON BOARD設定削除

    Args:
        db: データベースセッション
        setting_id: 設定ID

    Returns:
        bool: 削除成功（True）/ 失敗（False）
    """
    db_setting = get_setting_by_id(db, setting_id)
    if db_setting:
        db.delete(db_setting)
        db.commit()
        return True
    return False

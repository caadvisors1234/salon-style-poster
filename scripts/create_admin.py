#!/usr/bin/env python3
"""
管理者アカウント作成スクリプト

使用方法:
    python scripts/create_admin.py --email admin@example.com --password yourpassword

環境変数:
    データベース接続情報は環境変数(.env)から読み込まれます
"""

import argparse
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User


def create_admin_user(email: str, password: str, db: Session) -> bool:
    """
    管理者アカウントを作成

    Args:
        email: 管理者のメールアドレス
        password: 管理者のパスワード
        db: データベースセッション

    Returns:
        bool: 作成成功時True、既存の場合False
    """
    try:
        # 既存ユーザー確認
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"✗ エラー: メールアドレス '{email}' は既に登録されています")
            return False

        # 管理者アカウント作成
        hashed_password = get_password_hash(password)
        admin_user = User(
            email=email,
            hashed_password=hashed_password,
            role="admin",
            is_active=True
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print(f"✓ 管理者アカウントを作成しました")
        print(f"  - ID: {admin_user.id}")
        print(f"  - メールアドレス: {admin_user.email}")
        print(f"  - ロール: {admin_user.role}")
        print(f"  - 作成日時: {admin_user.created_at}")

        return True

    except IntegrityError as e:
        db.rollback()
        print(f"✗ データベースエラー: {e}")
        return False
    except Exception as e:
        db.rollback()
        print(f"✗ 予期しないエラー: {e}")
        return False


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="SALON BOARD Style Poster 管理者アカウント作成スクリプト"
    )
    parser.add_argument(
        "--email",
        type=str,
        required=True,
        help="管理者のメールアドレス"
    )
    parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="管理者のパスワード"
    )

    args = parser.parse_args()

    # バリデーション
    if "@" not in args.email:
        print("✗ エラー: 有効なメールアドレスを入力してください")
        sys.exit(1)

    if len(args.password) < 8:
        print("✗ エラー: パスワードは8文字以上である必要があります")
        sys.exit(1)

    print("=" * 60)
    print("SALON BOARD Style Poster - 管理者アカウント作成")
    print("=" * 60)
    print(f"メールアドレス: {args.email}")
    print(f"パスワード: {'*' * len(args.password)}")
    print("-" * 60)

    # データベースセッション作成
    db = SessionLocal()

    try:
        # 管理者作成
        success = create_admin_user(args.email, args.password, db)

        if success:
            print("-" * 60)
            print("✓ 管理者アカウントの作成が完了しました")
            print("=" * 60)
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

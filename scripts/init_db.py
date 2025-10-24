#!/usr/bin/env python3
"""
データベース初期化スクリプト

使用方法:
    python scripts/init_db.py

このスクリプトは以下の処理を実行します:
1. Alembicマイグレーションを最新バージョンまで適用
2. データベース接続テスト

環境変数:
    データベース接続情報は環境変数(.env)から読み込まれます
"""

import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from sqlalchemy import text

from app.db.session import engine


def run_migrations():
    """Alembicマイグレーションを実行"""
    print("=" * 60)
    print("データベースマイグレーション実行")
    print("=" * 60)

    try:
        # Alembic設定ファイルのパス
        alembic_cfg = Config("alembic.ini")

        # マイグレーション実行
        print("マイグレーションを実行中...")
        command.upgrade(alembic_cfg, "head")

        print("✓ マイグレーションが完了しました")
        return True

    except Exception as e:
        print(f"✗ マイグレーションエラー: {e}")
        return False


def test_connection():
    """データベース接続テスト"""
    print("-" * 60)
    print("データベース接続テスト")
    print("-" * 60)

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ PostgreSQLバージョン: {version}")

            # テーブル一覧取得
            result = conn.execute(text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """))
            tables = [row[0] for row in result]

            print(f"✓ 作成されたテーブル ({len(tables)} 件):")
            for table in tables:
                print(f"  - {table}")

        return True

    except Exception as e:
        print(f"✗ データベース接続エラー: {e}")
        return False


def main():
    """メイン処理"""
    print()
    print("=" * 60)
    print("SALON BOARD Style Poster - データベース初期化")
    print("=" * 60)
    print()

    # マイグレーション実行
    if not run_migrations():
        print()
        print("=" * 60)
        print("✗ データベース初期化に失敗しました")
        print("=" * 60)
        sys.exit(1)

    print()

    # 接続テスト
    if not test_connection():
        print()
        print("=" * 60)
        print("✗ データベース接続テストに失敗しました")
        print("=" * 60)
        sys.exit(1)

    print()
    print("=" * 60)
    print("✓ データベース初期化が完了しました")
    print()
    print("次のステップ:")
    print("  1. 管理者アカウントを作成してください:")
    print("     python scripts/create_admin.py --email admin@example.com --password yourpassword")
    print()
    print("  2. アプリケーションを起動してください:")
    print("     docker-compose up -d")
    print("=" * 60)


if __name__ == "__main__":
    main()

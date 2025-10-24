"""
Alembic環境設定ファイル

このファイルはAlembicがマイグレーションを実行する際に使用されます。
"""
from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# app.models内のすべてのモデルをインポートしてBaseに登録
from app.db.session import Base
from app.models import user, salon_board_setting, current_task

# app.core.configから設定をインポート
from app.core.config import settings

# Alembic Config オブジェクト
config = context.config

# データベースURLを環境変数から設定
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# ロギング設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# メタデータオブジェクト（autogenerate用）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    オフラインモードでマイグレーションを実行

    データベース接続なしでSQL文を生成します。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    オンラインモードでマイグレーションを実行

    データベースに接続してマイグレーションを実行します。
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

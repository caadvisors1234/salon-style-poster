"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-10-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # usersテーブル作成
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.CheckConstraint("role IN ('admin', 'user')", name='users_role_check')
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])

    # salon_board_settingsテーブル作成
    op.create_table(
        'salon_board_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('setting_name', sa.String(length=100), nullable=False),
        sa.Column('sb_user_id', sa.String(length=255), nullable=False),
        sa.Column('encrypted_sb_password', sa.Text(), nullable=False),
        sa.Column('salon_id', sa.String(length=50), nullable=True),
        sa.Column('salon_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sb_settings_user_id', 'salon_board_settings', ['user_id'])

    # updated_at自動更新トリガー作成
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER update_salon_board_settings_updated_at
        BEFORE UPDATE ON salon_board_settings
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # current_tasksテーブル作成
    op.create_table(
        'current_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PROCESSING'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_info_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.CheckConstraint("status IN ('PROCESSING', 'CANCELLING', 'SUCCESS', 'FAILURE')", name='current_tasks_status_check')
    )
    op.create_index('idx_current_tasks_user_id', 'current_tasks', ['user_id'], unique=True)
    op.create_index('idx_current_tasks_status', 'current_tasks', ['status'])


def downgrade() -> None:
    # current_tasksテーブル削除
    op.drop_index('idx_current_tasks_status', table_name='current_tasks')
    op.drop_index('idx_current_tasks_user_id', table_name='current_tasks')
    op.drop_table('current_tasks')

    # salon_board_settingsテーブル削除
    op.execute("DROP TRIGGER IF EXISTS update_salon_board_settings_updated_at ON salon_board_settings")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_index('idx_sb_settings_user_id', table_name='salon_board_settings')
    op.drop_table('salon_board_settings')

    # usersテーブル削除
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')

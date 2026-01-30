"""add success_info_json column to current_tasks

Revision ID: 20250130_add_success_info
Revises: 4d5d7c9b6d21
Create Date: 2025-01-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250130_add_success_info"
down_revision = "4d5d7c9b6d21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "current_tasks",
        sa.Column("success_info_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("current_tasks", "success_info_json")

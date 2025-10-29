"""add progress detail column to current_tasks"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d5d7c9b6d21"
down_revision = "0efde3d95075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "current_tasks",
        sa.Column("progress_detail_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("current_tasks", "progress_detail_json")


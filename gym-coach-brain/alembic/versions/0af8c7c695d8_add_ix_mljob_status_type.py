"""add_ix_mljob_status_type

Revision ID: 0af8c7c695d8
Revises: 20b31ec66e8e
Create Date: 2026-03-09 14:56:30.992003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0af8c7c695d8'
down_revision: Union[str, Sequence[str], None] = '20b31ec66e8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_mljob_status_type', 'ml_jobs', ['status', 'job_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_mljob_status_type', table_name='ml_jobs')

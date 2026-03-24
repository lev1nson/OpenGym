"""add concrete equipment inventory to user profiles

Revision ID: 6f8f57f3c0aa
Revises: b68ff5fd46f9
Create Date: 2026-03-24 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f8f57f3c0aa"
down_revision: Union[str, Sequence[str], None] = "b68ff5fd46f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_profiles",
        sa.Column("available_equipment_inventory", sa.Text(), nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_profiles", "available_equipment_inventory")

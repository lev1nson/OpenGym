"""add_exercise_family_and_concrete_inventory

Revision ID: xxxx_add_exercise_family_and_concrete_inventory
Revises: b68ff5fd46f9
"""
from alembic import op
import sqlalchemy as sa


revision = 'xxxx_add_exercise_family_and_concrete_inventory'
down_revision = 'b68ff5fd46f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('exercises', sa.Column('exercise_family', sa.String(), nullable=True))
    op.add_column('exercises', sa.Column('requires_concrete_inventory', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('exercises', sa.Column('concrete_item_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('exercises', 'concrete_item_id')
    op.drop_column('exercises', 'requires_concrete_inventory')
    op.drop_column('exercises', 'exercise_family')

"""add onboarding progress fields

Revision ID: 7b6c4a1d9f21
Revises: 6f8f57f3c0aa, d3c1b8a7f5aa, xxxx_add_exercise_family_and_concrete_inventory
"""
from alembic import op
import sqlalchemy as sa


revision = "7b6c4a1d9f21"
down_revision = ("6f8f57f3c0aa", "d3c1b8a7f5aa", "xxxx_add_exercise_family_and_concrete_inventory")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("onboarding_status", sa.String(), nullable=False, server_default="not_started"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("onboarding_current_question_id", sa.String(), nullable=True),
    )
    op.execute(
        """
        UPDATE user_profiles
        SET onboarding_status = CASE
            WHEN onboarding_complete = 1 THEN 'completed'
            ELSE 'not_started'
        END
        """
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "onboarding_current_question_id")
    op.drop_column("user_profiles", "onboarding_status")

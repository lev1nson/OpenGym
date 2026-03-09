"""epic5_schema_contract_checkin_fields_idempotency_rpe_debug

Revision ID: b68ff5fd46f9
Revises: 0af8c7c695d8
Create Date: 2026-03-09 15:10:07.421942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b68ff5fd46f9'
down_revision: Union[str, Sequence[str], None] = '0af8c7c695d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    SQLite does not support ADD CONSTRAINT via ALTER TABLE.
    Unique constraint on ml_jobs is added via batch mode (copy-and-move).
    Non-nullable columns on existing tables need server_default for SQLite compat.
    """
    # ml_jobs: add session_id column + unique constraint via batch mode
    with op.batch_alter_table('ml_jobs') as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            'uq_mljob_session_job_type', ['session_id', 'job_type']
        )

    # rpe_predictions: add debug/anomaly fields
    # anomaly_flag is NOT NULL — provide server_default=0 for existing rows
    op.add_column('rpe_predictions', sa.Column('core_weight_kg', sa.Float(), nullable=True))
    op.add_column('rpe_predictions', sa.Column('ml_weight_kg', sa.Float(), nullable=True))
    op.add_column('rpe_predictions', sa.Column('ml_adjustment_kg', sa.Float(), nullable=True))
    op.add_column(
        'rpe_predictions',
        sa.Column(
            'anomaly_flag',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column('rpe_predictions', sa.Column('source_label', sa.String(), nullable=True))

    # user_profiles: add nullable fields that were in models but missing from initial migration
    op.add_column('user_profiles', sa.Column('age', sa.Integer(), nullable=True))
    op.add_column('user_profiles', sa.Column('goal', sa.String(), nullable=True))
    op.add_column('user_profiles', sa.Column('experience_level', sa.String(), nullable=True))
    op.add_column('user_profiles', sa.Column('sleep_quality_score', sa.Float(), nullable=True))
    op.add_column('user_profiles', sa.Column('stress_score', sa.Float(), nullable=True))

    # workout_sessions: add pre/post check-in and deload fields
    # is_deload is NOT NULL — provide server_default=0 for existing rows
    op.add_column('workout_sessions', sa.Column('sleep_hours', sa.Float(), nullable=True))
    op.add_column('workout_sessions', sa.Column('pre_readiness', sa.Integer(), nullable=True))
    op.add_column('workout_sessions', sa.Column('post_feeling', sa.Integer(), nullable=True))
    op.add_column(
        'workout_sessions',
        sa.Column(
            'is_deload',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('workout_sessions', 'is_deload')
    op.drop_column('workout_sessions', 'post_feeling')
    op.drop_column('workout_sessions', 'pre_readiness')
    op.drop_column('workout_sessions', 'sleep_hours')
    op.drop_column('user_profiles', 'stress_score')
    op.drop_column('user_profiles', 'sleep_quality_score')
    op.drop_column('user_profiles', 'experience_level')
    op.drop_column('user_profiles', 'goal')
    op.drop_column('user_profiles', 'age')
    op.drop_column('rpe_predictions', 'source_label')
    op.drop_column('rpe_predictions', 'anomaly_flag')
    op.drop_column('rpe_predictions', 'ml_adjustment_kg')
    op.drop_column('rpe_predictions', 'ml_weight_kg')
    op.drop_column('rpe_predictions', 'core_weight_kg')
    with op.batch_alter_table('ml_jobs') as batch_op:
        batch_op.drop_constraint('uq_mljob_session_job_type', type_='unique')
        batch_op.drop_column('session_id')

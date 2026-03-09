"""backfill_ml_job_session_ids_add_fk

Revision ID: d3c1b8a7f5aa
Revises: b68ff5fd46f9
Create Date: 2026-03-09 15:55:00.000000

"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3c1b8a7f5aa"
down_revision: Union[str, Sequence[str], None] = "b68ff5fd46f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _extract_session_id(raw_session_ids: str, job_id: int) -> int:
    try:
        payload = json.loads(raw_session_ids)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ml_jobs.id={job_id} has invalid session_ids JSON") from exc

    if not isinstance(payload, list) or len(payload) != 1:
        raise RuntimeError(
            f"ml_jobs.id={job_id} expected one-element session_ids array for PREDICT job, got {payload!r}"
        )

    session_id = payload[0]
    if not isinstance(session_id, int):
        raise RuntimeError(
            f"ml_jobs.id={job_id} expected integer session_id in session_ids, got {session_id!r}"
        )
    return session_id


def upgrade() -> None:
    """Backfill legacy PREDICT rows and enforce the session FK contract."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, session_ids FROM ml_jobs "
            "WHERE job_type = 'PREDICT' AND session_id IS NULL"
        )
    ).fetchall()

    for row in rows:
        session_id = _extract_session_id(row.session_ids, row.id)
        bind.execute(
            sa.text("UPDATE ml_jobs SET session_id = :session_id WHERE id = :job_id"),
            {"session_id": session_id, "job_id": row.id},
        )

    with op.batch_alter_table("ml_jobs") as batch_op:
        batch_op.create_foreign_key(
            "fk_ml_jobs_session_id_workout_sessions",
            "workout_sessions",
            ["session_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("ml_jobs") as batch_op:
        batch_op.drop_constraint(
            "fk_ml_jobs_session_id_workout_sessions",
            type_="foreignkey",
        )

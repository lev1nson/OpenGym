"""
ML job queue CRUD helpers.

Communication contract between main process and ML Worker.
This module is STRICTLY isolated from gym_coach_brain.ml.* — no PyTorch imports.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Integer, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from gym_coach_brain.data.models import MLJob, WorkoutSession
from gym_coach_brain.data.session import get_session, get_default_engine


def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string (timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


def _get_predict_job(session_id: int, db: OrmSession) -> MLJob | None:
    """Return the canonical PREDICT job for a workout session if it already exists."""
    return db.execute(
        select(MLJob).where(
            MLJob.session_id == session_id,
            MLJob.job_type == "PREDICT",
        )
    ).scalars().first()


def _enqueue_predict_in_session(session_id: int, db: OrmSession, commit: bool) -> MLJob:
    """Core idempotent enqueue logic for a PREDICT job within a given session.

    The unique constraint on (session_id, job_type) means only one PREDICT job
    can ever exist per session_id. Idempotency: return existing job regardless of
    its status — once created, a PREDICT job is immutable from the queue's perspective.
    """
    if db.get(WorkoutSession, session_id) is None:
        raise ValueError(f"WorkoutSession {session_id} not found")

    # Fast path: return any existing PREDICT job for this session_id.
    existing = _get_predict_job(session_id, db)
    if existing is not None:
        return existing

    job = MLJob(
        job_type="PREDICT",
        status="pending",
        session_id=session_id,
        session_ids=json.dumps([session_id]),
        created_at=_utcnow_iso(),
    )

    if commit:
        db.add(job)
        try:
            db.commit()
            db.refresh(job)
            return job
        except IntegrityError:
            db.rollback()
            existing = _get_predict_job(session_id, db)
            if existing is not None:
                return existing
            raise

    savepoint = db.begin_nested()
    try:
        db.add(job)
        db.flush()
        savepoint.commit()
        db.refresh(job)
        return job
    except IntegrityError:
        savepoint.rollback()
        existing = _get_predict_job(session_id, db)
        if existing is not None:
            return existing
        raise


def enqueue_predict(
    session_id: int,
    engine=None,
    *,
    db_session: Optional[OrmSession] = None,
) -> MLJob:
    """Enqueue a PREDICT job for a single session. Idempotent.

    If db_session is provided, the operation runs within that session (no commit —
    caller is responsible for committing). This is required when enqueuing within
    an existing transaction (e.g. from api/handlers.py) where the WorkoutSession
    has been flushed but not yet committed.

    If db_session is None, opens its own session using engine (or default engine)
    and commits immediately.
    """
    if db_session is not None:
        return _enqueue_predict_in_session(session_id, db_session, commit=False)
    engine = engine or get_default_engine()
    with get_session(engine) as db:
        return _enqueue_predict_in_session(session_id, db, commit=True)


def enqueue_fine_tune(session_ids: list[int], engine=None) -> MLJob:
    """Enqueue a FINE_TUNE job for eligible sessions.

    Eligibility rules (Epic 5 Contract v3, §13):
    - session must have post_feeling IS NOT NULL (workout completed)
    - session must have is_deload=False (deload sessions skew the model)

    Raises ValueError if no eligible sessions remain after filtering.
    """
    engine = engine or get_default_engine()
    with get_session(engine) as db:
        # Filter to eligible sessions only
        rows = db.execute(
            select(WorkoutSession.id).where(
                WorkoutSession.id.in_(session_ids),
                WorkoutSession.post_feeling.isnot(None),
                WorkoutSession.is_deload.is_(False),
            )
        ).scalars().all()
        eligible_ids = list(rows)

        if not eligible_ids:
            raise ValueError(
                "No eligible sessions for fine-tuning: all provided sessions either "
                "have post_feeling=NULL (incomplete) or is_deload=True."
            )

        job = MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps(eligible_ids),
            created_at=_utcnow_iso(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job


def get_pending_jobs(engine=None) -> list[MLJob]:
    """Return pending jobs: PREDICT jobs first, then FINE_TUNE."""
    engine = engine or get_default_engine()
    with get_session(engine) as db:
        stmt = (
            select(MLJob)
            .where(MLJob.status == "pending")
            .order_by(
                # PREDICT=0 (higher priority), FINE_TUNE=1 (lower priority)
                (MLJob.job_type != "PREDICT").cast(Integer),
                MLJob.created_at,
            )
        )
        return list(db.execute(stmt).scalars().all())


def update_job_status(job_id: int, status: str, engine=None) -> None:
    """Update job status. Sets processed_at for terminal states (done/failed)."""
    engine = engine or get_default_engine()
    with get_session(engine) as db:
        job = db.get(MLJob, job_id)
        if job is None:
            raise ValueError(f"MLJob {job_id} not found")
        job.status = status
        if status in ("done", "failed"):
            job.processed_at = _utcnow_iso()
        db.commit()

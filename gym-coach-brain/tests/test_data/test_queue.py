"""Tests for data/queue.py — CRUD operations, status transitions, idempotency,
fine-tune eligibility filtering, and ml isolation guard.

Uses db_engine fixture (in-memory SQLite, no real files, no PyTorch).
"""
import importlib
import inspect
import json
import os
import tempfile
import threading

import pytest
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import MLJob, WorkoutSession
from gym_coach_brain.data.queue import (
    enqueue_predict,
    enqueue_fine_tune,
    get_pending_jobs,
    update_job_status,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_session(db_engine, *, post_feeling=None, is_deload=False) -> WorkoutSession:
    """Insert a WorkoutSession row and return it (committed)."""
    with Session(db_engine) as s:
        ws = WorkoutSession(
            session_date="2026-03-09",
            status="completed",
            is_deload=is_deload,
            post_feeling=post_feeling,
        )
        s.add(ws)
        s.commit()
        s.refresh(ws)
        return ws


# ─── Original CRUD tests ───────────────────────────────────────────────────────

def test_enqueue_predict_creates_pending_predict_job(db_engine):
    ws = _make_session(db_engine, post_feeling=None, is_deload=False)
    job = enqueue_predict(session_id=ws.id, engine=db_engine)
    assert job.id is not None
    assert job.job_type == "PREDICT"
    assert job.status == "pending"
    assert json.loads(job.session_ids) == [ws.id]
    assert job.session_id == ws.id
    assert job.created_at is not None
    assert job.processed_at is None


def test_enqueue_fine_tune_creates_pending_fine_tune_job(db_engine):
    ws = _make_session(db_engine, post_feeling=5, is_deload=False)
    job = enqueue_fine_tune(session_ids=[ws.id], engine=db_engine)
    assert job.job_type == "FINE_TUNE"
    assert job.status == "pending"
    assert json.loads(job.session_ids) == [ws.id]


def test_get_pending_jobs_returns_predict_before_fine_tune(db_engine):
    ws1 = _make_session(db_engine, post_feeling=5, is_deload=False)
    ws2 = _make_session(db_engine, post_feeling=9, is_deload=False)
    # Insert FINE_TUNE first, PREDICT second — PREDICT should still come first
    enqueue_fine_tune(session_ids=[ws1.id, ws2.id], engine=db_engine)
    ws3 = _make_session(db_engine, post_feeling=None, is_deload=False)
    enqueue_predict(session_id=ws3.id, engine=db_engine)
    jobs = get_pending_jobs(engine=db_engine)
    assert len(jobs) == 2
    assert jobs[0].job_type == "PREDICT"
    assert jobs[1].job_type == "FINE_TUNE"


def test_get_pending_jobs_returns_empty_when_none(db_engine):
    jobs = get_pending_jobs(engine=db_engine)
    assert jobs == []


def test_update_job_status_pending_to_processing(db_engine):
    ws = _make_session(db_engine, post_feeling=None, is_deload=False)
    job = enqueue_predict(session_id=ws.id, engine=db_engine)
    update_job_status(job.id, "processing", engine=db_engine)
    updated_jobs = get_pending_jobs(engine=db_engine)
    assert updated_jobs == []  # no longer pending


def test_update_job_status_to_done_sets_processed_at(db_engine):
    ws = _make_session(db_engine, post_feeling=None, is_deload=False)
    job = enqueue_predict(session_id=ws.id, engine=db_engine)
    update_job_status(job.id, "done", engine=db_engine)
    with Session(db_engine) as s:
        refreshed = s.get(MLJob, job.id)
        assert refreshed.status == "done"
        assert refreshed.processed_at is not None


def test_update_job_status_to_failed_sets_processed_at(db_engine):
    ws = _make_session(db_engine, post_feeling=None, is_deload=False)
    job = enqueue_predict(session_id=ws.id, engine=db_engine)
    update_job_status(job.id, "failed", engine=db_engine)
    with Session(db_engine) as s:
        refreshed = s.get(MLJob, job.id)
        assert refreshed.status == "failed"
        assert refreshed.processed_at is not None


# ─── Idempotency tests ─────────────────────────────────────────────────────────

def test_enqueue_predict_is_idempotent(db_engine):
    """Repeated enqueue_predict for same session_id returns same job, no duplicate."""
    ws = _make_session(db_engine, post_feeling=None, is_deload=False)
    job1 = enqueue_predict(session_id=ws.id, engine=db_engine)
    job2 = enqueue_predict(session_id=ws.id, engine=db_engine)

    assert job1.id == job2.id, "Second call must return same MLJob, not create a new one"

    with Session(db_engine) as s:
        count = s.query(MLJob).filter_by(
            session_id=ws.id, job_type="PREDICT"
        ).count()
    assert count == 1, f"Only one PREDICT job should exist for session_id={ws.id}"


def test_enqueue_predict_returns_same_job_when_already_done(db_engine):
    """After a PREDICT job is done, a new call returns the same job (no re-enqueue).

    One session_id → one PREDICT job forever. If prediction failed or completed,
    the fallback to deterministic core handles the rest — no retry queue.
    """
    ws = _make_session(db_engine, post_feeling=None, is_deload=False)
    job1 = enqueue_predict(session_id=ws.id, engine=db_engine)
    update_job_status(job1.id, "done", engine=db_engine)

    job2 = enqueue_predict(session_id=ws.id, engine=db_engine)
    assert job2.id == job1.id, "Should return existing done job (no re-enqueue for same session)"


def test_enqueue_predict_returns_same_job_when_already_failed(db_engine):
    """After a PREDICT job fails, a new call returns the same failed job."""
    ws = _make_session(db_engine, post_feeling=None, is_deload=False)
    job1 = enqueue_predict(session_id=ws.id, engine=db_engine)
    update_job_status(job1.id, "failed", engine=db_engine)

    job2 = enqueue_predict(session_id=ws.id, engine=db_engine)
    assert job2.id == job1.id, "Should return existing failed job (no re-enqueue)"


def test_enqueue_predict_raises_for_missing_workout_session(db_engine):
    """PREDICT jobs must reference a real WorkoutSession."""
    with pytest.raises(ValueError, match="WorkoutSession 999 not found"):
        enqueue_predict(session_id=999, engine=db_engine)


def test_enqueue_predict_is_concurrency_safe():
    """Concurrent enqueue calls must both resolve to the same persisted job."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        from gym_coach_brain.data.session import get_engine
        from gym_coach_brain.data.models import Base

        engine = get_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        ws = _make_session(engine, post_feeling=None, is_deload=False)

        barrier = threading.Barrier(2)
        results: list[tuple[str, int]] = []
        errors: list[str] = []

        def worker() -> None:
            try:
                barrier.wait()
                job = enqueue_predict(session_id=ws.id, engine=engine)
                results.append((job.job_type, job.id))
            except Exception as exc:  # pragma: no cover - surfaced in assertion below
                errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len(results) == 2
        assert results[0][1] == results[1][1]

        with Session(engine) as s:
            rows = s.query(MLJob).filter_by(session_id=ws.id, job_type="PREDICT").all()
        assert len(rows) == 1
    finally:
        os.remove(path)


# ─── Fine-tune eligibility filtering tests ────────────────────────────────────

def test_enqueue_fine_tune_excludes_sessions_with_null_post_feeling(db_engine):
    """Sessions without post_feeling (incomplete) must be excluded from fine-tuning."""
    ws_complete = _make_session(db_engine, post_feeling=5, is_deload=False)
    ws_incomplete = _make_session(db_engine, post_feeling=None, is_deload=False)

    job = enqueue_fine_tune(
        session_ids=[ws_complete.id, ws_incomplete.id],
        engine=db_engine,
    )
    eligible = json.loads(job.session_ids)
    assert ws_complete.id in eligible
    assert ws_incomplete.id not in eligible


def test_enqueue_fine_tune_excludes_deload_sessions(db_engine):
    """Deload sessions must be excluded from fine-tuning (they skew the model)."""
    ws_normal = _make_session(db_engine, post_feeling=5, is_deload=False)
    ws_deload = _make_session(db_engine, post_feeling=5, is_deload=True)

    job = enqueue_fine_tune(
        session_ids=[ws_normal.id, ws_deload.id],
        engine=db_engine,
    )
    eligible = json.loads(job.session_ids)
    assert ws_normal.id in eligible
    assert ws_deload.id not in eligible


def test_enqueue_fine_tune_raises_when_all_sessions_ineligible(db_engine):
    """ValueError when all provided sessions are filtered out."""
    ws_incomplete = _make_session(db_engine, post_feeling=None, is_deload=False)
    ws_deload = _make_session(db_engine, post_feeling=5, is_deload=True)

    with pytest.raises(ValueError, match="No eligible sessions"):
        enqueue_fine_tune(
            session_ids=[ws_incomplete.id, ws_deload.id],
            engine=db_engine,
        )


# ─── ML isolation guard ────────────────────────────────────────────────────────

def test_queue_module_has_no_ml_imports():
    """Prove data.queue has zero import statements from gym_coach_brain.ml.* (contractual)."""
    import ast
    import gym_coach_brain.data.queue as queue_module

    source = inspect.getsource(queue_module)
    tree = ast.parse(source)

    ml_imports = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            (isinstance(node, ast.ImportFrom) and node.module is not None
             and node.module.startswith("gym_coach_brain.ml"))
            or
            (isinstance(node, ast.Import)
             and any(alias.name.startswith("gym_coach_brain.ml") for alias in node.names))
        )
    ]
    assert ml_imports == [], (
        f"data/queue.py must never import from gym_coach_brain.ml.* — "
        f"PyTorch isolation violated by: {[ast.dump(n) for n in ml_imports]}"
    )

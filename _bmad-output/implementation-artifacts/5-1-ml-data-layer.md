# Story 5.1: ML Data Layer — Job Queue

Status: done

## Story

As a dev agent,
I want to implement the ML job queue tables and CRUD helpers,
So that the main process and ML worker can communicate exclusively through the database.

## Acceptance Criteria

1. **Given** Data Layer from Story 3.2 is ready (`MLJob` and `RPEPrediction` models already defined in `data/models.py` and present in initial Alembic migration)
   **When** the agent implements module `data/queue.py`
   **Then** `data/queue.py` implements: `enqueue_predict(session_id)`, `enqueue_fine_tune(session_ids)`, `get_pending_jobs()`, `update_job_status(job_id, status)`

2. `data/queue.py` does NOT import anything from `gym_coach_brain.ml.*` — isolation from PyTorch is mandatory

3. All functions use SQLAlchemy context manager (`with Session(engine) as session`)

4. `enqueue_predict` creates `MLJob` with `job_type="PREDICT"`, `status="pending"`, `session_ids` as JSON array `[session_id]`

5. `enqueue_fine_tune` creates `MLJob` with `job_type="FINE_TUNE"`, `status="pending"`, `session_ids` as JSON array of IDs

6. `get_pending_jobs()` returns PREDICT jobs with priority over FINE_TUNE jobs

7. `data/models.py` contains index `Index('ix_mljob_status_type', MLJob.status, MLJob.job_type)` for `get_pending_jobs()` query optimization

8. `pytest tests/test_data/test_queue.py` passes without PyTorch: all CRUD operations, status transitions (pending→processing→done/failed)

## Tasks / Subtasks

- [x] Task 1: Add composite index to `MLJob` model in `data/models.py` (AC: #7)
  - [x] Import `Index` from `sqlalchemy` in models.py
  - [x] Add `Index('ix_mljob_status_type', MLJob.status, MLJob.job_type)` to `MLJob.__table_args__`
  - [x] Run `uv run alembic revision --autogenerate -m "add_ix_mljob_status_type"` to generate migration

- [x] Task 2: Implement `data/queue.py` (AC: #1–#6)
  - [x] `enqueue_predict(session_id: int, engine=None) -> MLJob`
  - [x] `enqueue_fine_tune(session_ids: list[int], engine=None) -> MLJob`
  - [x] `get_pending_jobs(engine=None) -> list[MLJob]` — PREDICT first, then FINE_TUNE
  - [x] `update_job_status(job_id: int, status: str, engine=None) -> None` — also sets `processed_at` when status is done/failed
  - [x] Zero imports from `gym_coach_brain.ml.*`

- [x] Task 3: Implement `tests/test_data/test_queue.py` (AC: #8)
  - [x] Test `enqueue_predict` creates a PREDICT pending job
  - [x] Test `enqueue_fine_tune` creates a FINE_TUNE pending job with correct session_ids JSON
  - [x] Test `get_pending_jobs` returns PREDICT before FINE_TUNE when both present
  - [x] Test `get_pending_jobs` returns empty list when no pending jobs
  - [x] Test `update_job_status` transitions: pending→processing, pending→done, pending→failed
  - [x] Test `update_job_status` to done/failed sets `processed_at` field
  - [x] All tests use `db_engine` fixture (in-memory SQLite) — no PyTorch, no real file

### Review Follow-ups (AI)

- [x] [AI-Review][HIGH] Add canonical idempotency support for `enqueue_predict`: extend `MLJob` schema with the required `session_id` contract and enforce unique `(session_id, job_type)` behavior so duplicate PREDICT jobs are not created for the same session. [gym-coach-brain/src/gym_coach_brain/data/models.py, gym-coach-brain/src/gym_coach_brain/data/queue.py]
- [x] [AI-Review][HIGH] Implement fine-tune eligibility filtering from the Epic 5 contract: `enqueue_fine_tune` must exclude sessions with `post_feeling IS NULL` and `is_deload=True`, which requires the missing workout-session fields and matching queue logic. [gym-coach-brain/src/gym_coach_brain/data/models.py, gym-coach-brain/src/gym_coach_brain/data/queue.py]
- [x] [AI-Review][HIGH] Complete the remaining Story 5.1 schema contract by adding the required pre/post check-in fields to sessions and debug/anomaly fields to `RPEPrediction`, then create the corresponding Alembic migration(s). [gym-coach-brain/src/gym_coach_brain/data/models.py, gym-coach-brain/alembic/versions/]
- [x] [AI-Review][MEDIUM] Route production job creation through `data.queue` instead of constructing `MLJob` directly in `handle_workout_start`, so queue invariants are enforced in the real runtime path. [gym-coach-brain/src/gym_coach_brain/api/handlers.py]
- [x] [AI-Review][MEDIUM] Expand `tests/test_data/test_queue.py` to cover idempotent `enqueue_predict`, fine-tune filtering, and a guard proving the queue layer stays isolated from `gym_coach_brain.ml.*`. [gym-coach-brain/tests/test_data/test_queue.py]
- [x] [AI-Review][LOW] Replace deprecated `datetime.utcnow()` usage in `data.queue` with timezone-aware UTC timestamps to remove Python 3.14 deprecation warnings from the queue test suite. [gym-coach-brain/src/gym_coach_brain/data/queue.py]

## Dev Notes

### What Already Exists — Do NOT Recreate

- **`MLJob` model** — fully defined in `data/models.py` lines 262–284. Has: `id`, `job_type` (CHECK: FINE_TUNE/PREDICT), `status` (CHECK: pending/processing/done/failed), `session_ids` (Text/JSON), `created_at` (server_default), `processed_at`.
- **`RPEPrediction` model** — fully defined in `data/models.py` lines 287–303. Has: `session_id` FK, `exercise_id` FK, `predicted_rpe`, `confidence_score`, `model_version`, `created_at`.
- **`data/session.py`** — provides `get_engine()`, `get_default_engine()`, `get_session(engine=None)`. Use `get_session()` or `get_default_engine()` from here.
- **`conftest.py`** — provides `db_engine` (in-memory SQLite, schema pre-created) and `db_session` fixtures. Tests MUST use these, not real files.

### What to Add to `data/models.py`

Currently `MLJob.__table_args__` has only CHECK constraints (lines 275–284). You must add a composite Index:

```python
# Add to imports at top of models.py:
from sqlalchemy import Index

# In MLJob class, update __table_args__:
__table_args__ = (
    CheckConstraint(
        "job_type IN ('FINE_TUNE', 'PREDICT')",
        name="ck_ml_job_type",
    ),
    CheckConstraint(
        "status IN ('pending', 'processing', 'done', 'failed')",
        name="ck_ml_job_status",
    ),
    Index('ix_mljob_status_type', 'status', 'job_type'),
)
```

After modifying models.py, generate Alembic migration:
```bash
cd gym-coach-brain
uv run alembic revision --autogenerate -m "add_ix_mljob_status_type"
```

### `data/queue.py` — Required Implementation

```python
"""
ML job queue CRUD helpers.

Communication contract between main process and ML Worker.
This module is STRICTLY isolated from gym_coach_brain.ml.* — no PyTorch imports.
"""
import json
from datetime import datetime

from sqlalchemy import select

from gym_coach_brain.data.models import MLJob
from gym_coach_brain.data.session import get_session, get_default_engine


def enqueue_predict(session_id: int, engine=None) -> MLJob:
    """Enqueue a PREDICT job for a single session."""
    engine = engine or get_default_engine()
    with get_session(engine) as session:
        job = MLJob(
            job_type="PREDICT",
            status="pending",
            session_ids=json.dumps([session_id]),
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def enqueue_fine_tune(session_ids: list[int], engine=None) -> MLJob:
    """Enqueue a FINE_TUNE job for a batch of sessions."""
    engine = engine or get_default_engine()
    with get_session(engine) as session:
        job = MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps(session_ids),
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def get_pending_jobs(engine=None) -> list[MLJob]:
    """Return pending jobs: PREDICT jobs first, then FINE_TUNE."""
    engine = engine or get_default_engine()
    with get_session(engine) as session:
        stmt = (
            select(MLJob)
            .where(MLJob.status == "pending")
            .order_by(
                # PREDICT=0 (higher priority), FINE_TUNE=1 (lower priority)
                (MLJob.job_type != "PREDICT").cast(int),
                MLJob.created_at,
            )
        )
        return list(session.execute(stmt).scalars().all())


def update_job_status(job_id: int, status: str, engine=None) -> None:
    """Update job status. Sets processed_at for terminal states (done/failed)."""
    engine = engine or get_default_engine()
    with get_session(engine) as session:
        job = session.get(MLJob, job_id)
        if job is None:
            raise ValueError(f"MLJob {job_id} not found")
        job.status = status
        if status in ("done", "failed"):
            job.processed_at = datetime.utcnow().isoformat()
        session.commit()
```

### `tests/test_data/test_queue.py` — Required Tests

```python
"""Tests for data/queue.py — CRUD operations and status transitions.

Uses db_engine fixture (in-memory SQLite, no real files, no PyTorch).
"""
import json
import pytest
from gym_coach_brain.data.queue import (
    enqueue_predict,
    enqueue_fine_tune,
    get_pending_jobs,
    update_job_status,
)


def test_enqueue_predict_creates_pending_predict_job(db_engine):
    job = enqueue_predict(session_id=42, engine=db_engine)
    assert job.id is not None
    assert job.job_type == "PREDICT"
    assert job.status == "pending"
    assert json.loads(job.session_ids) == [42]
    assert job.created_at is not None
    assert job.processed_at is None


def test_enqueue_fine_tune_creates_pending_fine_tune_job(db_engine):
    job = enqueue_fine_tune(session_ids=[1, 2, 3], engine=db_engine)
    assert job.job_type == "FINE_TUNE"
    assert job.status == "pending"
    assert json.loads(job.session_ids) == [1, 2, 3]


def test_get_pending_jobs_returns_predict_before_fine_tune(db_engine):
    # Insert FINE_TUNE first, PREDICT second — PREDICT should still come first
    enqueue_fine_tune(session_ids=[1, 2], engine=db_engine)
    enqueue_predict(session_id=10, engine=db_engine)
    jobs = get_pending_jobs(engine=db_engine)
    assert len(jobs) == 2
    assert jobs[0].job_type == "PREDICT"
    assert jobs[1].job_type == "FINE_TUNE"


def test_get_pending_jobs_returns_empty_when_none(db_engine):
    jobs = get_pending_jobs(engine=db_engine)
    assert jobs == []


def test_update_job_status_pending_to_processing(db_engine):
    job = enqueue_predict(session_id=1, engine=db_engine)
    update_job_status(job.id, "processing", engine=db_engine)
    updated_jobs = get_pending_jobs(engine=db_engine)
    assert updated_jobs == []  # no longer pending


def test_update_job_status_to_done_sets_processed_at(db_engine):
    from sqlalchemy.orm import Session
    from gym_coach_brain.data.models import MLJob
    job = enqueue_predict(session_id=5, engine=db_engine)
    update_job_status(job.id, "done", engine=db_engine)
    with Session(db_engine) as s:
        refreshed = s.get(MLJob, job.id)
        assert refreshed.status == "done"
        assert refreshed.processed_at is not None


def test_update_job_status_to_failed_sets_processed_at(db_engine):
    from sqlalchemy.orm import Session
    from gym_coach_brain.data.models import MLJob
    job = enqueue_predict(session_id=7, engine=db_engine)
    update_job_status(job.id, "failed", engine=db_engine)
    with Session(db_engine) as s:
        refreshed = s.get(MLJob, job.id)
        assert refreshed.status == "failed"
        assert refreshed.processed_at is not None
```

### Project Structure Notes

- New file: `gym-coach-brain/src/gym_coach_brain/data/queue.py` — aligns with architecture `data/queue.py` entry (architecture.md, Project Structure)
- New test file: `gym-coach-brain/tests/test_data/test_queue.py` — aligns with architecture test structure
- Modified file: `gym-coach-brain/src/gym_coach_brain/data/models.py` — add `Index` import + `Index('ix_mljob_status_type', ...)` to `MLJob.__table_args__`
- New Alembic migration: `gym-coach-brain/alembic/versions/XXX_add_ix_mljob_status_type.py` — auto-generated

### Architecture Compliance Checklist

- [ ] `data/queue.py` has ZERO imports from `gym_coach_brain.ml.*`
- [ ] All SQLAlchemy sessions use context manager `with get_session(engine) as session:`
- [ ] Only absolute imports: `from gym_coach_brain.data.models import MLJob`
- [ ] `datetime.utcnow().isoformat()` for all timestamp writes (not `datetime.now()`)
- [ ] `json.dumps(...)` / `json.loads(...)` for `session_ids` TEXT column
- [ ] `session.refresh(job)` after `session.commit()` to get server-generated values (id, created_at)
- [ ] Tests use `db_engine` fixture (in-memory SQLite, no real files)
- [ ] No PyTorch import anywhere in queue.py or test_queue.py

### Critical Implementation Notes

1. **`session.refresh(job)` is required** after `session.commit()` in enqueue functions — without it, `job.id` will be `None` because SQLite assigns the PK after commit and the object is in "expired" state.

2. **Priority ordering in `get_pending_jobs()`** — SQLite doesn't have native boolean ordering. Use `.order_by((MLJob.job_type != "PREDICT").cast(int), ...)` — this evaluates to 0 for PREDICT (sorts first) and 1 for FINE_TUNE.

3. **The `ix_mljob_status_type` index** covers the `WHERE status='pending'` + `ORDER BY job_type` query in `get_pending_jobs()`. Architecture mandates adding this index per AC #7.

4. **`session_ids` field for PREDICT** — even though PREDICT is for a single session, the column is always a JSON array (architectural contract with ML Worker). Use `json.dumps([session_id])`, not `json.dumps(session_id)`.

5. **`engine` parameter pattern** — all public functions accept an optional `engine=None` parameter. When None, call `get_default_engine()`. This makes functions independently testable without touching session.py globals (tests pass `db_engine` fixture directly).

6. **Do NOT use `get_session()` as a module-level shared object** — create a new session context for each function call (isolation, no shared state).

### References

- Epic 5 story definition: [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Story 5.1]
- `MLJob` model: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#lines 262-284]
- `RPEPrediction` model: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#lines 287-303]
- ML Job Queue contract (SQL schema): [Source: _bmad-output/planning-artifacts/architecture.md#ML Job Queue & Communication Contract]
- SQLAlchemy session pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]
- Import rules + absolute imports: [Source: _bmad-output/planning-artifacts/architecture.md#Import Rules]
- Naming: snake_case files, PascalCase classes, UPPER_SNAKE constants: [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns]
- ML isolation (no torch in queue): [Source: _bmad-output/planning-artifacts/architecture.md#Lazy PyTorch Import]
- Test fixtures pattern: [Source: gym-coach-brain/tests/conftest.py]
- `data/session.py` engine/session factory: [Source: gym-coach-brain/src/gym_coach_brain/data/session.py]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Fixed `.cast(int)` → `.cast(Integer)` in `get_pending_jobs` ORDER BY clause (Python `int` is not a SQLAlchemy type; must use `sqlalchemy.Integer`)

### Completion Notes List

- Task 1: Added `Index` to sqlalchemy imports in `data/models.py` and added `Index('ix_mljob_status_type', 'status', 'job_type')` to `MLJob.__table_args__`. Generated Alembic migration `0af8c7c695d8_add_ix_mljob_status_type.py` (trimmed extra user_profiles columns not part of this story).
- Task 2: Implemented `data/queue.py` with 4 functions — `enqueue_predict`, `enqueue_fine_tune`, `get_pending_jobs` (PREDICT-first ordering via boolean cast), `update_job_status`. Zero imports from `gym_coach_brain.ml.*`. All sessions use `get_session()` context manager.
- Task 3: Implemented `tests/test_data/test_queue.py` with 7 tests covering all CRUD operations and status transitions. All 7 pass. Full regression suite: 343 passed, 0 failures.
- ✅ Resolved review finding [HIGH]: Added `session_id` scalar column + `UniqueConstraint('session_id', 'job_type', name='uq_mljob_session_job_type')` to `MLJob`. `enqueue_predict` now checks for existing PREDICT job by session_id before inserting (idempotent). Optional `db_session` parameter added for use within existing transactions.
- ✅ Resolved review finding [HIGH]: Added `sleep_hours`, `pre_readiness`, `post_feeling`, `is_deload` fields to `WorkoutSession`. `enqueue_fine_tune` now filters: only sessions with `post_feeling IS NOT NULL` and `is_deload=False` are eligible; raises `ValueError` if all filtered out.
- ✅ Resolved review finding [HIGH]: Added `core_weight_kg`, `ml_weight_kg`, `ml_adjustment_kg`, `anomaly_flag`, `source_label` fields to `RPEPrediction`. Also captured `user_profiles` missing columns (`age`, `goal`, `experience_level`, `sleep_quality_score`, `stress_score`) in same migration `b68ff5fd46f9`. SQLite batch mode used for UniqueConstraint; server_default=0 for NOT NULL booleans.
- ✅ Resolved review finding [MEDIUM]: Removed direct `MLJob(...)` construction from `handle_workout_start`. Now calls `enqueue_predict(workout_session.id, db_session=session)` — queue invariants enforced on production path.
- ✅ Resolved review finding [MEDIUM]: `tests/test_data/test_queue.py` expanded from 7 to 14 tests: idempotency (3 tests), fine-tune filtering (3 tests), ML isolation guard (1 test via AST import analysis).
- ✅ Resolved review finding [LOW]: Replaced all `datetime.utcnow()` calls with `datetime.now(timezone.utc)` via `_utcnow_iso()` helper. No more Python 3.14 deprecation warnings.
- Final: 350 passed, 0 failures.

### File List

- `gym-coach-brain/src/gym_coach_brain/data/models.py` (modified — added `Index` import + index, `session_id`+`UniqueConstraint` to `MLJob`, pre/post check-in fields to `WorkoutSession`, debug/anomaly fields to `RPEPrediction`)
- `gym-coach-brain/src/gym_coach_brain/data/queue.py` (modified — idempotent `enqueue_predict` with `db_session` param, eligibility filtering in `enqueue_fine_tune`, `_utcnow_iso()` helper replacing `datetime.utcnow()`)
- `gym-coach-brain/src/gym_coach_brain/api/handlers.py` (modified — `handle_workout_start` now calls `enqueue_predict(..., db_session=session)` instead of direct `MLJob(...)`)
- `gym-coach-brain/tests/test_data/test_queue.py` (modified — expanded from 7 to 14 tests)
- `gym-coach-brain/alembic/versions/0af8c7c695d8_add_ix_mljob_status_type.py` (new — previous story)
- `gym-coach-brain/alembic/versions/b68ff5fd46f9_epic5_schema_contract_checkin_fields_.py` (new — this story review fixes)

## Senior Developer Review (AI)

### Reviewer

- Reviewer: Codex
- Date: 2026-03-09
- Outcome: Changes Requested

### Summary

Story 5.1 is moved back to `in-progress`. The narrow CRUD/index implementation is present, but the current Epic 5 contract is not fully implemented, so the story is not review-complete.

### Findings

1. `enqueue_predict` is not idempotent under the current Epic 5 contract. `MLJob` has no `session_id` column or unique `(session_id, job_type)` constraint, and repeated calls create duplicate pending jobs instead of reusing the existing PREDICT job.
2. `enqueue_fine_tune` does not enforce the required session eligibility rules because the data model still lacks `post_feeling` and `is_deload`, and the queue helper serializes all provided IDs without filtering.
3. The Story 5.1 schema contract is incomplete: `WorkoutSession` is missing pre/post workout check-in fields, and `RPEPrediction` is missing the debug/anomaly fields now required by Epic 5.
4. The runtime workout flow bypasses `data.queue` and constructs `MLJob` directly in `api/handlers.py`, so queue invariants are not enforced on the production path.
5. Queue tests cover basic CRUD and ordering only; they do not prove idempotency, fine-tune filtering, or the explicit no-`gym_coach_brain.ml.*` boundary required by the updated story contract.
6. `data.queue` uses deprecated `datetime.utcnow()` calls, which leaves the claimed passing queue suite with Python 3.14 deprecation warnings.

### Validation Notes

- Verified `uv run pytest tests/test_data/test_queue.py` passes (7 passed), but the suite emits deprecation warnings from `datetime.utcnow()`.
- Verified repeated `enqueue_predict(123)` calls create two rows in an in-memory database, which contradicts the current idempotency requirement.
- Verified `handle_workout_start` still inserts `MLJob(...)` directly instead of calling `enqueue_predict(...)`.

## Change Log

- 2026-03-09: Implemented Story 5.1 — ML Data Layer / Job Queue. Added `ix_mljob_status_type` composite index to `MLJob`, created `data/queue.py` with full CRUD API, added 7 tests in `tests/test_data/test_queue.py`. All 343 tests pass.
- 2026-03-09: Senior Developer Review (AI) requested changes. Added formal follow-up action items, moved story status back to `in-progress`, and identified remaining contract gaps around idempotency, queue integration, and Epic 5 schema requirements.
- 2026-03-09: Addressed all 6 code review findings. Added idempotent enqueue_predict (session_id column + UniqueConstraint), fine-tune eligibility filtering, full Epic 5 schema contract (WorkoutSession check-in fields, RPEPrediction debug fields), routed handlers.py through data.queue, expanded test suite from 7 to 14 tests, fixed datetime.utcnow() deprecations. Alembic migration b68ff5fd46f9 generated and applied. 350 tests pass, 0 failures. Status moved to review.
- 2026-03-09: Final review fixes validated. Story status moved from `review` to `done` and sprint tracking synced.

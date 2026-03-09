# Story 5.3: ML Worker daemon - polling loop and systemd

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to implement the ML Worker as an isolated process with systemd supervision,
So that PyTorch failures never crash the main API and memory is bounded.

## Acceptance Criteria

1. **Given** `ml/model.py` and `data/queue.py` are ready
   **When** the agent implements `ml/worker.py`, `ml/__main__.py`, and the systemd unit
   **Then** `class MLWorker` implements a polling loop with a 60s interval by default and a configurable override.

2. `PREDICT` jobs are always dispatched before `FINE_TUNE` jobs.

3. Fine-tuning starts only when at least `N=5` completed sessions exist where `post_feeling IS NOT NULL` and `is_deload=False`, with the threshold configurable and counted across sessions, not per exercise.

4. Any job failure sets `status='failed'`, logs `logger.error(...)` with structured job context, and the polling loop continues.

5. The worker never reprocesses jobs whose status is already `done` or `failed`.

6. A stuck `processing` job is treated as an operational incident and is never silently auto-requeued to `pending`.

7. Structured logging includes at minimum `job_id`, `job_type`, `session_ids`, `status`, and the error or fallback reason.

8. The worker maintains an in-memory `consecutive_anomalies` counter for the current process run: increment on persisted `RPEPrediction.anomaly_flag=True`, reset on `False`.

9. When `consecutive_anomalies >= ScienceConfig.ml.anomaly_rollback_threshold`, the worker attempts to load the previous model version (`model_v{n-1}.pt`), logs an `ERROR` with structured context (`model_version`, `consecutive_anomalies`, `exercise_id`), and resets the counter; if no previous version exists, it logs `CRITICAL` and continues on the current model.

10. An anomalous prediction is written to the database before any rollback decision is executed so anomaly history is preserved.

11. `gym-coach-brain/systemd/gym-coach-brain-ml.service` enforces an 8 GB memory cap and automatic restart-on-failure supervision.

12. `class MLWorker` is testable without PyTorch through a mock model fixture.

13. `pytest tests/test_ml/test_worker.py` passes for polling, job dispatch, priority order, threshold logic, anomaly counter increment, rollback trigger at threshold, and anomaly counter reset after a normal prediction.

## Tasks / Subtasks

- [ ] Task 1: Create the worker runtime skeleton (AC: 1, 11, 12)
  - [ ] Add `gym-coach-brain/src/gym_coach_brain/ml/worker.py` with `MLWorker` constructor, polling entrypoint, and explicit dependency injection for engine, model, science config, and logger.
  - [ ] Add `gym-coach-brain/src/gym_coach_brain/ml/__main__.py` so `python -m gym_coach_brain.ml` starts the daemon.
  - [ ] Create `gym-coach-brain/systemd/gym-coach-brain-ml.service` and the missing `systemd/` directory in the package root.

- [ ] Task 2: Implement queue polling and job lifecycle guards (AC: 1, 2, 4, 5, 6, 7)
  - [ ] Reuse `data.queue.get_pending_jobs()` for priority ordering instead of reimplementing SQL in the worker.
  - [ ] Mark jobs `processing` before execution and mark terminal states with `update_job_status()`.
  - [ ] Treat unexpected `processing` rows as incidents to log, not as jobs to mutate back into `pending`.

- [ ] Task 3: Implement `PREDICT` job execution (AC: 2, 4, 7, 10)
  - [ ] Parse the queued workout session and planned exercises from `WorkoutSession.planned_exercises`.
  - [ ] Build one canonical feature payload per `(session_id, exercise_id)` through `data.features.build_feature_vector(...)` plus `muscle_group_fatigue_estimate`.
  - [ ] Call `RPEModel.predict(...)` and persist `RPEPrediction` rows that match the contract already consumed by `adaptation/engine.py`.

- [ ] Task 4: Implement `FINE_TUNE` job threshold logic and dispatch (AC: 2, 3, 4, 7)
  - [ ] Count eligible sessions from the DB using the same `post_feeling IS NOT NULL` and `is_deload=False` rules already established in `data.queue.enqueue_fine_tune()`.
  - [ ] Skip training when the threshold is not met, leaving a clear log trail instead of failing silently.
  - [ ] Keep `PREDICT` dispatch latency ahead of `FINE_TUNE` work even when both job types are pending.

- [ ] Task 5: Add anomaly tracking and rollback hooks (AC: 8, 9, 10)
  - [ ] Increment or reset the in-memory anomaly counter based on persisted prediction state, not on pre-write assumptions.
  - [ ] Add rollback helper(s) in `worker.py` that target `MODEL_DIR/model_v{n}.pt` naming, while keeping full versioning expansion for Story 5.4.
  - [ ] Log rollback attempts, missing prior versions, and non-blocking continuation paths with structured context.

- [ ] Task 6: Add operational configuration and structured logging (AC: 1, 4, 6, 7, 11)
  - [ ] Read polling interval, fine-tune threshold, and model directory from config/env without hardcoding operational values beyond story defaults.
  - [ ] Use `loguru` structured binds for per-job logs.
  - [ ] Keep the worker resilient: one bad job must not terminate the daemon process.

- [ ] Task 7: Cover the worker with tests (AC: 12, 13)
  - [ ] Add `gym-coach-brain/tests/test_ml/test_worker.py` using in-memory SQLite and a mock RPE model.
  - [ ] Assert queue priority, lifecycle status transitions, threshold behavior, anomaly rollback trigger, and counter reset semantics.
  - [ ] Prove the test module does not require importing real PyTorch to exercise worker orchestration.

- [ ] Task 8: Final verification (AC: 1-13)
  - [ ] Run `uv run pytest tests/test_ml/test_worker.py`.
  - [ ] Run `uv run pytest` to ensure worker changes do not regress queue, adaptation, or API behavior.
  - [ ] Smoke-check the daemon entrypoint with `uv run python -m gym_coach_brain.ml --help` or the implemented equivalent if the module exposes CLI arguments.

## Dev Notes

- This story adds the first long-running ML process to the repo. The API side already enqueues `PREDICT` jobs during `handle_workout_start(...)`; do not redesign that flow. The worker must consume the existing DB queue contract instead of inventing a second IPC mechanism.
- `data.queue.py` is already the canonical queue layer. Reuse `get_pending_jobs()`, `update_job_status()`, and the existing `MLJob` schema; do not duplicate queue SQL in `worker.py` unless a missing helper is required and added back into `data.queue.py`.
- `adaptation/engine.py` already reads `RPEPrediction` rows by `(session_id, exercise_id)` and expects `source_label`, `anomaly_flag`, `core_weight_kg`, `ml_weight_kg`, and `ml_adjustment_kg` to be coherent. The worker must write predictions that preserve this contract.
- Current repo state:
  - `gym-coach-brain/src/gym_coach_brain/ml/model.py` and `ml/ewc.py` exist from Story 5.2.
  - `gym-coach-brain/src/gym_coach_brain/ml/worker.py` and `ml/__main__.py` do not exist yet.
  - `gym-coach-brain/systemd/` does not exist yet and must be created by this story.
- Scope boundary:
  - Build daemon orchestration, dispatch, persistence, supervision unit, and tests here.
  - Do not fully solve model versioning/backup workflows beyond what is required for anomaly rollback hooks; Story 5.4 owns the full versioning lifecycle.
  - Do not move prediction logic into `api/handlers.py` or `adaptation/engine.py`; the whole point of this story is process isolation.

### Technical Requirements

- `MLWorker` should expose testable, non-blocking units such as `poll_once()`, `process_job(job_id)`, or similarly scoped methods. Do not bury all behavior in an infinite `while True` loop that tests cannot control.
- Use one DB session context per polling/processing unit and make job state transitions explicit:
  - load pending jobs
  - move selected job to `processing`
  - execute
  - commit `done` or `failed`
- For `PREDICT` jobs, persist one `RPEPrediction` per `(session_id, exercise_id)` from the queued workout plan. The planned payload is exercise-level, so use the planned exercise values for `target_weight_kg` and `target_reps`; if a synthetic set number is needed for feature building, standardize on `set_number=1` and cover it in tests.
- Do not import underscored helpers from `adaptation/engine.py`. If worker logic needs shared feature assembly or fatigue estimation, extract a reusable helper into a lower-level module (`data/` or `ml/`) rather than creating an upward dependency on `adaptation`.
- Prediction persistence must be idempotent enough for worker restarts: if a job is already terminal, skip it; if a prediction for the same `(session_id, exercise_id)` is being rewritten, do so deliberately and document whether you append a new row or update the latest row. The existing adaptation path selects the newest row, so duplicate writes must stay deterministic.
- Treat malformed `planned_exercises`, missing sessions, and corrupt model files as job failures or operational warnings with structured logs. Never crash the daemon loop on bad data from one job.

### Architecture Compliance

- Follow absolute imports only, matching the architecture decision document and current codebase.
- Keep `ScienceConfig` injected into worker startup; do not create a module-level singleton configuration object in `worker.py`.
- Preserve the DB-mediated boundary between the API process and ML process:
  - API writes `ml_jobs`
  - worker reads `ml_jobs`
  - worker writes `rpe_predictions`
  - adaptation reads `rpe_predictions`
- Respect the queue state machine exactly: `pending -> processing -> done|failed`. No hidden retry state and no automatic mutation of stuck rows back to `pending`.
- Keep worker orchestration testable without real PyTorch:
  - inject a mock model into `MLWorker`
  - avoid module-level `import torch` in `worker.py`
  - keep PyTorch-specific behavior delegated to `ml/model.py`
- Continue using SQLAlchemy ORM and context managers. No raw SQL and no ad hoc sqlite3 access.

### Library / Framework Requirements

- Runtime versions pinned in `gym-coach-brain/pyproject.toml` today:
  - Python `>=3.14`
  - SQLAlchemy `>=2.0.48`
  - Alembic `>=1.18.4`
  - loguru `>=0.7.3`
  - torch `>=2.10.0`
- PyTorch guardrail from current official docs: keep checkpoint handling `state_dict`-based and prefer safe `torch.load(..., weights_only=True)` semantics where the local torch version supports it. If Story 5.3 adds direct version-load helpers, align them with this guidance so Story 5.4 does not need to undo unsafe checkpoint code.
- systemd guardrail from current official docs:
  - `Restart=on-failure` is the correct supervision behavior for a daemon that should recover from crashes.
  - modern resource control prefers `MemoryMax=`; this story still needs to satisfy the epic acceptance wording around an 8 GB memory cap, so document any compatibility decision clearly in the unit file comments.

### File Structure Requirements

- New source files expected in this story:
  - `gym-coach-brain/src/gym_coach_brain/ml/worker.py`
  - `gym-coach-brain/src/gym_coach_brain/ml/__main__.py`
  - `gym-coach-brain/tests/test_ml/test_worker.py`
  - `gym-coach-brain/systemd/gym-coach-brain-ml.service`
- Existing files likely touched:
  - `gym-coach-brain/src/gym_coach_brain/ml/__init__.py` only if exporting worker symbols is useful
  - `gym-coach-brain/src/gym_coach_brain/ml/constants.py` only if shared defaults need explicit worker constants
  - `gym-coach-brain/src/gym_coach_brain/data/queue.py` only if a missing queue helper must be added in the canonical layer
- Do not create a second service-definition location under `src/`; the service file belongs in the package root `systemd/` directory.
- Do not create a second feature-builder path in the worker. Reuse `data.features.build_feature_vector()` and extract shared helpers downward if needed.

### Testing Requirements

- Use the existing in-memory SQLite fixtures pattern from `tests/conftest.py`.
- Add worker tests under `gym-coach-brain/tests/test_ml/test_worker.py`, not under `test_data/` or `test_api/`.
- Avoid real sleeps in tests:
  - inject `sleep_fn`
  - or expose `poll_once()`
  - or pass a bounded loop count for deterministic execution
- Cover at least these scenarios:
  - `PREDICT` before `FINE_TUNE`
  - terminal jobs are ignored
  - failed job logs and loop continues
  - threshold not met -> no fine-tune execution
  - threshold met -> fine-tune path runs
  - anomaly counter increments on anomalous persisted prediction
  - anomaly counter resets on normal persisted prediction
  - rollback attempted at threshold and missing prior version degrades safely
- Add at least one import-safety assertion proving worker orchestration can be imported and tested with a mock model without requiring real torch execution.

### Previous Story Intelligence

- Story 5.2 established two rules that this story must not violate:
  - PyTorch imports stay inside model-specific methods so orchestration remains lightweight and testable.
  - `FEATURE_FIELD_ORDER` in `ml/model.py` and the canonical builder in `data/features.py` are now the single source of truth for model input ordering.
- Story 5.2 also expanded `RPEPrediction` with `core_weight_kg`, `ml_weight_kg`, `ml_adjustment_kg`, `anomaly_flag`, and `source_label`. Worker code must persist data that leaves these fields meaningful for downstream adaptation and debugging.
- `adaptation/engine.py` already formats anomaly and confidence fallback labels. Worker-side anomaly tracking must preserve those semantics instead of inventing a competing interpretation.
- Do not regress Story 5.1 queue guarantees:
  - `PREDICT` idempotency per session
  - `PREDICT > FINE_TUNE` ordering
  - `session_ids` stored as JSON arrays

### Git Intelligence Summary

- Recent git history is documentation-heavy (`README` and project-state sync) and does not introduce a competing implementation pattern for the worker. Follow the existing source conventions in `src/gym_coach_brain/` and `tests/`, not the commit history, for code style decisions.
- The absence of recent ML-worker commits is itself useful: this story is the first real implementation of the daemon, so keep the surface area narrow and avoid speculative abstractions that are not required by the acceptance criteria.

### Latest Technical Information

- As of March 9, 2026, current official PyTorch serialization guidance still centers on saving/loading `state_dict`s and using safer `torch.load` behavior for weight-only checkpoint consumption. This matters because the worker will likely be the first place that performs recurring model load/reload operations in production.
- As of March 9, 2026, current official systemd documentation still recommends `Restart=on-failure` for crash recovery and documents `MemoryMax=` as the active resource-control directive replacing older `MemoryLimit` wording. Use this to avoid writing a stale or misleading service unit.

### Project Context Reference

- Project-context rules that apply directly here:
  - SQLAlchemy Declarative models remain the single source of truth.
  - Type hints are mandatory for new worker APIs.
  - Unit/integration tests should use `sqlite:///:memory:`.
  - No raw SQL and no stateful global command handlers.
- The architecture document adds worker-specific constraints:
  - DB queue is the only API/worker contract.
  - `MLWorker` handles queue polling and dispatch; `RPEModel` handles PyTorch behavior.
  - Structured logs should use per-job context, not unscoped string logs.

### Project Structure Notes

- The current repo already matches the planned module split for `data/`, `adaptation/`, `ml/`, and `api/`. This story fits the intended architecture cleanly.
- One variance from the architecture document is that `systemd/` does not exist yet. Create it at the `gym-coach-brain/` root rather than relocating service files under `src/`.
- Another variance is that feature-building and fatigue estimation currently live partly inside `adaptation/engine.py` private helpers. If the worker needs the same logic, refactor that logic downward instead of importing private adaptation helpers across module boundaries.

### References

- Epic definition and acceptance criteria: [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Story 5.3]
- Epic contracts and sequencing: [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Epic 5 Contract Snapshot v1] [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Epic 5 Contract Snapshot v2] [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Epic 5 Contract Snapshot v3]
- Architecture decisions, ML worker lifecycle, naming, and structure: [Source: _bmad-output/planning-artifacts/architecture.md#ML Worker Process Lifecycle] [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns & Consistency Rules] [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries]
- Project-level AI implementation rules: [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- Queue implementation and invariants: [Source: gym-coach-brain/src/gym_coach_brain/data/queue.py]
- Current data contracts: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#MLJob] [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#RPEPrediction] [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#WorkoutSession]
- Existing API enqueue integration: [Source: gym-coach-brain/src/gym_coach_brain/api/handlers.py#handle_workout_start]
- Existing adaptation consumer contract: [Source: gym-coach-brain/src/gym_coach_brain/adaptation/engine.py]
- Existing ML model contract and constants: [Source: gym-coach-brain/src/gym_coach_brain/ml/model.py] [Source: gym-coach-brain/src/gym_coach_brain/ml/interface.py] [Source: gym-coach-brain/src/gym_coach_brain/ml/constants.py]
- Previous story learnings: [Source: _bmad-output/implementation-artifacts/5-2-rpe-model-pytorch.md#Completion Notes List] [Source: _bmad-output/implementation-artifacts/5-2-rpe-model-pytorch.md#Architecture Compliance Checklist]
- Current official docs checked on 2026-03-09:
  - PyTorch saving/loading tutorial: https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html
  - PyTorch serialization notes (`torch.load`, `weights_only`): https://docs.pytorch.org/docs/stable/notes/serialization.html
  - systemd service restart behavior: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
  - systemd memory control (`MemoryMax`, `MemoryLimit`): https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (create-story)

### Debug Log References

- `cat _bmad/core/tasks/workflow.xml`
- `cat _bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`
- `cat _bmad-output/implementation-artifacts/sprint-status.yaml`
- `cat _bmad-output/planning-artifacts/epics/epic-5-ai.md`
- `cat _bmad-output/planning-artifacts/architecture.md`
- `cat _bmad-output/project-context.md`
- `cat _bmad-output/implementation-artifacts/5-2-rpe-model-pytorch.md`
- `cat gym-coach-brain/src/gym_coach_brain/data/queue.py`
- `cat gym-coach-brain/src/gym_coach_brain/data/models.py`
- `cat gym-coach-brain/src/gym_coach_brain/api/handlers.py`
- `cat gym-coach-brain/src/gym_coach_brain/adaptation/engine.py`
- `git log --oneline -5`

### Completion Notes List

- 2026-03-09: Story 5.3 created via the BMAD create-story workflow in automated mode.
- 2026-03-09: Story context includes queue invariants, current worker gaps, prior-story learnings, current official systemd/PyTorch guidance, and a narrowed file-touch plan.
- 2026-03-09: Validation workflow file `_bmad/core/tasks/validate-workflow.xml` was not present in this repo, so checklist validation must be performed manually against `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`.

### File List

- `gym-coach-brain/src/gym_coach_brain/ml/worker.py`
- `gym-coach-brain/src/gym_coach_brain/ml/__main__.py`
- `gym-coach-brain/systemd/gym-coach-brain-ml.service`
- `gym-coach-brain/tests/test_ml/test_worker.py`
- `gym-coach-brain/src/gym_coach_brain/data/queue.py` (only if canonical queue helpers need extension)
- `gym-coach-brain/src/gym_coach_brain/ml/constants.py` (only if worker defaults need shared constants)

### Story Completion Status

- Story status set to `ready-for-dev`.
- Sprint status must move `5-3-ml-worker-daemon` from `backlog` to `ready-for-dev`.
- Completion note for sprint tracking: `Ultimate context engine analysis completed - comprehensive developer guide created`.

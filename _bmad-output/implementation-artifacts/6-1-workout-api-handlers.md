# Story 6.1: Complete API Handlers for All Workout Intents

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an athlete,
I want all workout intents to be handled by gym-coach-brain,
so that the complete training workflow is available as a deterministic backend API.

## Acceptance Criteria

1. **Given** Epic 3 and Epic 4 are implemented in code, and Epic 5 data/ML surfaces already exist in the repo  
   **When** the agent completes the workout API surface  
   **Then** the backend supports these intents through the API layer:
   - `workout_start`
   - `workout_log_set`
   - `workout_finish`
   - `workout_recap`
   - `workout_summary`
   - `workout_status`
   - `readiness_log` (existing handler kept compatible)

2. The API exposes a machine-readable JSON envelope for subprocess callers.
   Required top-level keys remain:
   - `intent`
   - `argv`
   - `stdout`
   - `exit_code`

3. To satisfy Epic 6 orchestration needs without breaking the existing four-key contract, the API may add an **optional additive** top-level `data` object for structured flags and identifiers, for example:
   - `orphaned_session`
   - `orphaned_session_id`
   - `orphaned_session_date`
   - `second_session_today`
   - `split_day_label`
   - `session_id`
   The four required keys above must stay stable.

4. `exit_code` semantics stay aligned with existing handler conventions:
   - `0` = success
   - `1` = user/domain error
   - `2` = system error

5. `ScienceLimitError` is converted at the API boundary into `exit_code=1` with a user-readable message, not an uncaught traceback.

6. `workout_start` enforces orphan/duplicate-session rules before creating a new session:
   - if any existing `WorkoutSession.status == "active"` exists, return `exit_code=1`, keep the current session untouched, and expose orphan metadata in the JSON response
   - if a completed workout already exists for today, return `exit_code=1` plus `second_session_today=true` unless the caller passes an explicit confirmation flag
   - when the caller confirms a second session on the same day, the new session must reuse the same `split_day_label` as today’s completed session so the split cycle does not advance

7. `workout_start` persists a new `WorkoutSession` with:
   - `status="active"` in the current schema
   - `planned_exercises` stored as JSON
   - `split_day_label` from the generated plan
   - pre-workout fields stored in the row (`sleep_hours`, `pre_readiness`) when explicitly supplied
   - a `PREDICT` ML job enqueued via `data.queue.enqueue_predict()`

8. `workout_start` returns a readable plan where every exercise line includes `exercise_id`, because Story 6.4 will need that ID for later tool calls. Format stays consistent with the existing handler pattern:
   - `Сегодня — [muscle groups]`
   - `[N]. [Exercise] (id:[exercise_id]): [sets]x[min]-[max] @ [weight]кг`

9. Recovery input resolution for `workout_start` is backward-compatible with the current repo:
   - keep support for explicit CLI flags `--sleep-hours` and `--pre-readiness`
   - if readiness data for today exists in `ReadinessLog`, compute `RecoverySignal` from it
   - if no readiness data exists, proceed with `recovery_signal=None`
   - do not block session creation just because readiness is missing

10. `workout_status` reports the active workout using the stored plan plus logged sets:
    - if there is an active session, return `exit_code=0`
    - output must show each planned exercise with progress such as `✅ done_sets/planned_sets` or `⏳ not started`
    - include all currently logged `WorkoutSet` rows for that session
    - if no active session exists, return `exit_code=1` with a clear message

11. `workout_log_set` accepts structured input with `exercise_id`, `set_number`, `weight_kg`, `reps`, and `rir` and enforces:
    - `weight_kg >= 0.0`
    - `reps >= 1`
    - `rir in [0, 4]`
    - duplicate `(session_id, exercise_id, set_number)` returns `exit_code=1` without overwriting data
    - `WorkoutSet.rir` is stored exactly
    - `WorkoutSet.rpe` is computed as `10.0 - rir`
    - if `set_number` exceeds the plan, the set is still logged with `exit_code=0` and stdout includes a warning about going beyond plan

12. `workout_log_set` returns the next-set recommendation using existing progression code:
    - use `core.apre.calculate_apre_adjustment()` for the in-session next-set recommendation
    - use `core.apre.rpe_from_rir()` or the same formula source for `RPE = 10.0 - RIR`
    - round displayed recommended loads via `core.weight_utils.round_to_equipment_increment()`
    - do **not** misuse `calculate_double_progression()` for intra-session guidance

13. `workout_finish` closes the active session safely:
    - active session status becomes `completed`
    - repeated finish on an already completed or missing active session returns `exit_code=1`
    - stdout includes the generated Summary from `adaptation/summary.py`

14. `workout_recap` remains a separate intent that returns the latest pre-workout recap via `adaptation/recap.py`.

15. `workout_summary` remains a separate intent for later re-reading of a completed session summary:
    - allow an optional `session_id`
    - if omitted, default to the most recent completed session
    - use `adaptation/summary.generate_summary()`

16. The package provides a real API entrypoint for subprocess callers:
    - `python -m gym_coach_brain.api --intent <intent> ...`
    - intent dispatch lives in the API module, not in `gym_coach_brain.__init__.py`
    - the API boundary is responsible for loading config/session, invoking handlers, mapping exceptions, and serializing JSON

17. Tests cover the full story surface:
    - `workout_start`: orphaned active session, second session today, confirmed second session, recovery input, `exercise_id` in stdout, `split_day_label` persistence, `PREDICT` job creation
    - `workout_log_set`: validation errors, RIR→RPE, duplicate set number, beyond-plan set number
    - `workout_status`: active session present vs absent
    - `workout_finish`: completion, auto-summary, repeated finish
    - `workout_recap` and `workout_summary`: correct delegation and missing-history behavior
    - JSON contract tests for `exit_code` mapping and optional `data` payload

## Tasks / Subtasks

- [x] Task 1: Create the API composition root and JSON contract surface (AC: 2-5, 16)
  - [x] Create `gym-coach-brain/src/gym_coach_brain/api/contract.py` to build the response envelope.
  - [x] Create `gym-coach-brain/src/gym_coach_brain/api/main.py` for intent dispatch, session/config bootstrapping, exception mapping, and JSON serialization.
  - [x] Create `gym-coach-brain/src/gym_coach_brain/api/__main__.py` so Story 6.4 can call `python -m gym_coach_brain.api`.
  - [x] Keep `handlers.py` return shape as `(stdout, exit_code)`; do not move commit/JSON responsibilities into handlers.
  - [x] If `data` is added to the JSON contract, update `docs/api-contracts.md` so the additive extension is documented.

- [x] Task 2: Extend `handle_workout_start()` instead of rewriting it from scratch (AC: 6-9)
  - [x] Preserve current onboarding/profile validation and `WorkoutPlanner` reuse.
  - [x] Add orphaned active-session detection before plan generation.
  - [x] Add same-day second-session detection and a confirmation flag such as `--confirm-second true|false` or a boolean switch.
  - [x] Ensure confirmed second sessions reuse the current day’s `split_day_label` rather than advancing the split cycle.
  - [x] Keep ML job creation through `enqueue_predict()` inside the same DB transaction.
  - [x] Keep `exercise_id` in each stdout plan line.

- [x] Task 3: Add `handle_workout_status()` using the stored plan as the source of truth (AC: 10)
  - [x] Find the current active session.
  - [x] Parse `WorkoutSession.planned_exercises` safely.
  - [x] Join/log `WorkoutSet` rows by `exercise_id`.
  - [x] Format per-exercise progress without inventing a second plan representation.

- [x] Task 4: Add `handle_workout_log_set()` with strict validation and recommendation logic (AC: 11-12)
  - [x] Parse `--exercise-id`, `--set-number`, `--weight-kg`, `--reps`, `--rir`.
  - [x] Require an active session and verify the `exercise_id` exists in the current session plan.
  - [x] Prevent duplicate set insertion before flush, and still rely on the unique constraint as the last line of defense.
  - [x] Persist `WorkoutSet.rir` and computed `WorkoutSet.rpe`.
  - [x] Build the next-set recommendation from `calculate_apre_adjustment()` plus equipment rounding.
  - [x] For beyond-plan sets, log successfully and append the warning text rather than rejecting the set.

- [x] Task 5: Add finish/recap/summary handlers by reusing existing adaptation modules (AC: 13-15)
  - [x] `handle_workout_finish()` should mark the active session completed and call `generate_summary()`.
  - [x] `handle_workout_recap()` should delegate to `adaptation.recap.generate_recap()`.
  - [x] `handle_workout_summary()` should delegate to `adaptation.summary.generate_summary()` for a specified or latest completed session.
  - [x] Do not duplicate recap/summary formatting logic inside handlers.

- [x] Task 6: Keep helper logic small, shared, and repo-consistent (AC: 6-15)
  - [x] If safe JSON parsing of `planned_exercises` is needed in multiple handlers, extract a narrow helper inside `api/` rather than copy-pasting parsing blocks.
  - [x] If second-session confirmation needs planner support, extend `WorkoutPlanner` with a narrow override hook instead of forking planner logic in the handler.
  - [x] Keep all imports absolute.

- [x] Task 7: Add focused API tests and contract tests (AC: 17)
  - [x] Extend `gym-coach-brain/tests/test_api/test_handlers.py` for the new workout handlers.
  - [x] Add `gym-coach-brain/tests/test_api/test_contract.py` for JSON envelope behavior.
  - [x] Reuse the in-memory SQLite fixture style already used across `tests/test_api/`.
  - [x] Keep tests deterministic; no wall-clock string assertions beyond normalized date-only checks.

- [x] Task 8: Final verification (AC: 1-17)
  - [x] Run `uv run --group dev pytest tests/test_api/test_handlers.py`.
  - [x] Run `uv run --group dev pytest tests/test_api/test_readiness_handler.py`.
  - [x] Run `uv run --group dev pytest tests/test_adaptation/test_recap.py`.
  - [x] Run `uv run --group dev pytest tests/test_adaptation/test_summary.py`.
  - [x] Run a manual CLI smoke test through `uv run python -m gym_coach_brain.api --intent workout_status`.

## Dev Notes

- This story is a repo-alignment story, not just a handler-addition story.
  - Epic 6 assumes a callable API entrypoint, but the repo does **not** currently have `api/main.py`, `api/contract.py`, or `api/__main__.py`.
  - `gym-coach-brain/src/gym_coach_brain/__init__.py` still prints `"Hello from gym-coach-brain!"` and is not a usable API boundary.

- Current repo reality that must shape the implementation:
  - `gym-coach-brain/src/gym_coach_brain/api/handlers.py` already implements onboarding, profile, `readiness_log`, and a first version of `workout_start`.
  - `gym-coach-brain/src/gym_coach_brain/core/planner.py` already produces `WorkoutPlan` and persists `split_day_label` + `planned_exercises` through the existing `workout_start`.
  - `gym-coach-brain/src/gym_coach_brain/adaptation/recap.py` and `gym-coach-brain/src/gym_coach_brain/adaptation/summary.py` already exist and should be reused directly.
  - `gym-coach-brain/src/gym_coach_brain/data/models.py` already defines `WorkoutSession`, `WorkoutSet`, `ReadinessLog`, and `MLJob`.
  - `gym-coach-brain/src/gym_coach_brain/data/queue.py` already provides idempotent `enqueue_predict()`.

- Critical mismatch to resolve before coding:
  - Epic text says `in_progress` workout sessions.
  - The current ORM/schema and tests use `WorkoutSession.status in ('planned', 'active', 'completed')`.
  - For this story, treat Epic 6's `in_progress` wording as the existing DB value `active`.
  - Do **not** rename the DB enum to `in_progress` inside this story unless you intentionally take on a migration + test-surface expansion. That is outside the clean scope of 6.1.

- Another critical mismatch:
  - Epic 6 wants machine-readable flags like `orphaned_session=true`.
  - The architecture docs currently show the four-field response envelope only.
  - The safest path is an additive `data` object while keeping `intent`, `argv`, `stdout`, and `exit_code` unchanged.

- Dependency and sequencing note:
  - Epic 6 says "Requires Epic 5 completed", but current `sprint-status.yaml` still shows `5-4-model-versioning: review` and `5-5-simulation-e2e: ready-for-dev`.
  - Do not block Story 6.1 on that mismatch, but do not introduce new assumptions about finished Epic 5 orchestration either.

### Technical Requirements

- Reuse these existing code paths instead of duplicating logic:
  - `gym_coach_brain.core.planner.WorkoutPlanner`
  - `gym_coach_brain.core.readiness.calculate_recovery_signal`
  - `gym_coach_brain.core.apre.calculate_apre_adjustment`
  - `gym_coach_brain.core.apre.rpe_from_rir`
  - `gym_coach_brain.core.weight_utils.round_to_equipment_increment`
  - `gym_coach_brain.adaptation.recap.generate_recap`
  - `gym_coach_brain.adaptation.summary.generate_summary`
  - `gym_coach_brain.data.queue.enqueue_predict`

- Keep handler transaction semantics unchanged.
  - Handlers may `session.add()` and `session.flush()`.
  - The API boundary owns `commit()` / rollback and JSON serialization.

- Keep `workout_start` backward-compatible with the current test surface.
  - Existing tests already call `handle_workout_start(["--sleep-hours", "7.5", "--pre-readiness", "5"], ...)`.
  - Do not break that path while adding orphan/second-session behavior.

- For second-session-today confirmation, avoid planner drift.
  - `WorkoutPlanner.generate()` currently advances based on the last completed session.
  - A confirmed second session on the same day must reuse the prior `split_day_label`.
  - If necessary, add a small planner override parameter or helper rather than duplicating split logic in the handler.

- `workout_log_set` must be strict about session state.
  - No active session: `exit_code=1`.
  - Unknown `exercise_id` for the active plan: `exit_code=1`.
  - Duplicate set number for the same exercise/session: `exit_code=1`.
  - Beyond-plan set number: log successfully, but warn clearly in stdout.

- Recommendation logic guardrail:
  - In-session recommendation = APRE.
  - Next-session planning = Double Progression.
  - Do not cross those responsibilities.

- Summary/recap guardrail:
  - `generate_summary()` already handles malformed `planned_exercises` JSON safely.
  - Reuse that pattern rather than inventing a brittle parser in handlers.

### Architecture Compliance

- Respect the intended boundary:
  - `api/main.py` (or equivalent API entrypoint) is the composition root.
  - `api/handlers.py` contains domain handlers.
  - `api/contract.py` serializes the subprocess response envelope.

- Preserve the DB-mediated ML contract.
  - `workout_start` creates the session and enqueues a `PREDICT` job through `data.queue`.
  - Do not call ML code directly from the handler.

- Keep SQLAlchemy 2.x patterns consistent with the repo:
  - use ORM models as the schema source of truth
  - use session context managers at the boundary
  - avoid raw SQL

- Preserve typed-exception flow:
  - internal code raises typed exceptions
  - API layer converts them to `exit_code`
  - handler layer should not emit traceback-shaped strings for routine domain errors

- Do not widen scope into bot transport concerns.
  - No aiogram work belongs in this story.
  - No Telegram state machine belongs in this story.
  - Story 6.1 is the deterministic backend API that later bot stories will call.

### Library / Framework Requirements

- Local pinned/runtime expectations from `gym-coach-brain/pyproject.toml`:
  - Python `>=3.14`
  - SQLAlchemy `>=2.0.48`
  - Alembic `>=1.18.4`
  - loguru `>=0.7.3`
  - pytest `>=9.0.2`

- Latest official guidance relevant to this story as of March 9, 2026:
  - SQLAlchemy 2.x docs still recommend keeping `Session` lifecycle external and scoped with context managers.
  - SQLAlchemy 2.x docs still note that autoflush occurs before ORM queries / `Session.execute()` and on commit, which matters when handlers create rows and then immediately query dependent state.
  - Python 3.14 `argparse` still supports the current `ArgumentParser(..., add_help=False)` handler pattern.
  - Pytest fixture docs still recommend reusable fixtures and `yield`-style teardown where setup becomes shared across multiple API test files.

- Implementation guidance from those docs:
  - Stay with the existing `add_help=False` + `SystemExit` catch pattern unless you migrate all handlers consistently.
  - Keep transaction boundaries explicit around session creation, set logging, and finish flows.
  - Prefer shared test fixtures over repeated ad hoc DB setup if `test_handlers.py` grows much further.

### File Structure Requirements

- Files expected to be created:
  - `gym-coach-brain/src/gym_coach_brain/api/contract.py`
  - `gym-coach-brain/src/gym_coach_brain/api/main.py`
  - `gym-coach-brain/src/gym_coach_brain/api/__main__.py`
  - `gym-coach-brain/tests/test_api/test_contract.py`

- Existing files expected to be modified:
  - `gym-coach-brain/src/gym_coach_brain/api/handlers.py`
  - `gym-coach-brain/src/gym_coach_brain/core/planner.py` only if a narrow second-session override is required
  - `gym-coach-brain/tests/test_api/test_handlers.py`
  - `gym-coach-brain/tests/test_api/test_readiness_handler.py` only if fixture reuse or contract integration needs light adjustment
  - `docs/api-contracts.md`

- Files that should **not** be the main target of this story:
  - `gym-coach-brain/src/gym_coach_brain/ml/*`
  - `gym-coach-brain/src/gym_coach_brain/bot/*`
  - broad schema migrations unrelated to workout API behavior

### Testing Requirements

- Extend handler tests with the repo’s current style:
  - in-memory SQLite via `create_engine("sqlite:///:memory:")`
  - `Base.metadata.create_all(engine)`
  - `seed_all(session)` before scenario setup

- Add explicit coverage for `workout_start`:
  - active orphaned session blocks new session creation
  - completed session today blocks unconfirmed second session
  - confirmed second session reuses today's `split_day_label`
  - readiness log present -> plan still created and session persisted
  - no readiness log -> session still created
  - `PREDICT` job is enqueued exactly once per new session

- Add explicit coverage for `workout_log_set`:
  - invalid weight/reps/rir
  - duplicate set number
  - beyond-plan set number warning with successful insert
  - `rpe` stored as `10.0 - rir`
  - recommendation string includes rounded next-set guidance

- Add explicit coverage for `workout_status`:
  - no active session
  - active session with zero logged sets
  - active session with partially completed sets

- Add explicit coverage for `workout_finish`, `workout_recap`, and `workout_summary`:
  - finish marks session completed and includes summary
  - repeated finish returns `exit_code=1`
  - recap returns the latest completed-session recap
  - summary defaults to latest completed session
  - summary with explicit `session_id` returns the targeted session

- Add explicit contract tests:
  - required JSON envelope keys always present
  - `ScienceLimitError` becomes `exit_code=1`
  - unexpected exception becomes `exit_code=2`
  - optional `data` fields serialize only when provided

### Latest Technical Information

- Official SQLAlchemy 2.x session docs: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
  - Relevant here because the handler layer already uses `flush()` and the new API boundary will own `commit()` / rollback.

- Official Python 3.14 `argparse` docs: https://docs.python.org/3.14/library/argparse.html
  - Relevant here because the repo already standardizes on lightweight handler-local parsers with `add_help=False`.

- Official pytest fixture docs: https://docs.pytest.org/en/stable/how-to/fixtures.html
  - Relevant here because Story 6.1 expands the API test matrix and should stay maintainable.

- No library upgrade is required for this story.
  - Stay on the repo’s pinned versions and follow current official usage patterns rather than mixing in speculative framework changes.

### Project Context Reference

- From `_bmad-output/project-context.md`, these rules apply directly:
  - SQLAlchemy declarative models remain the schema source of truth.
  - Type hints are mandatory for new APIs/helpers.
  - Every new feature needs pytest coverage.
  - Use `sqlite:///:memory:` for unit/integration tests.
  - No raw SQL.
  - Keep command handlers stateless; persist workflow state in SQLite models, not globals.

- Additional repo-specific reminders:
  - Keep absolute imports only.
  - Preserve Russian user-facing output where the existing API already does that.
  - Do not silently drop `exercise_id` from stdout, because Story 6.4 depends on it.

### Story Completion Status

- Story status set to `review`.
- Output path: `_bmad-output/implementation-artifacts/6-1-workout-api-handlers.md`
- Sprint status must be updated to:
  - `epic-6: in-progress`
  - `6-1-workout-api-handlers: review`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `uv run --group dev pytest tests/test_api/test_contract.py`
- `uv run --group dev pytest tests/test_api/test_handlers.py`
- `uv run --group dev pytest tests/test_api/test_readiness_handler.py`
- `uv run --group dev pytest tests/test_adaptation/test_recap.py`
- `uv run --group dev pytest tests/test_adaptation/test_summary.py`
- `uv run python -m gym_coach_brain.api --intent workout_status`

### Completion Notes List

- 2026-03-24: Added the structured API boundary in `api/main.py`, `api/contract.py`, and `api/__main__.py` so subprocess callers can use `python -m gym_coach_brain.api --intent ...`.
- 2026-03-24: Extended workout handlers for orphan detection, same-day second-session confirmation, active-session status, structured set logging, finish/recap/summary delegation, and additive `data` payload support without changing the `(stdout, exit_code)` handler contract.
- 2026-03-24: Added a narrow `WorkoutPlanner` split-label override to keep confirmed second sessions on the same split day instead of advancing the cycle.
- 2026-03-24: Expanded API tests and contract tests; verification passed for handlers, readiness, recap, summary, and CLI smoke behavior.

### File List

- `_bmad-output/implementation-artifacts/6-1-workout-api-handlers.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/api-contracts.md`
- `gym-coach-brain/src/gym_coach_brain/api/__main__.py`
- `gym-coach-brain/src/gym_coach_brain/api/contract.py`
- `gym-coach-brain/src/gym_coach_brain/api/handlers.py`
- `gym-coach-brain/src/gym_coach_brain/api/main.py`
- `gym-coach-brain/src/gym_coach_brain/core/planner.py`
- `gym-coach-brain/tests/test_api/test_contract.py`
- `gym-coach-brain/tests/test_api/test_handlers.py`

## Change Log

- 2026-03-24: Implemented Story 6.1 workout API handlers and composition root, documented the additive `data` contract, added focused tests, and moved the story to `review`.

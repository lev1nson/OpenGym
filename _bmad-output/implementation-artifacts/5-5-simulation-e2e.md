# Story 5.5: Simulation-based E2E System Validation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to run a simulated 6-month athlete training history through the full system,
so that correctness of PUOS, progression, and RPE personalization is validated without waiting for real data.

## Acceptance Criteria

1. **Given** Epics 1-5 are complete and the deterministic core plus ML pipeline are available  
   **When** the agent creates `gym_coach_brain/simulation/` with:
   - `simulation/run.py` as the CLI entrypoint accepting `--months` and `--sessions-per-week`
   - `simulation/synthetic_athlete.py` as the synthetic-athlete generator  
   **And** runs `python -m gym_coach_brain.simulation.run --months=6 --sessions-per-week=3`  
   **Then** the simulation boots from the real project code rather than mocks or parallel business logic.

2. The simulation generates at least 72 synthetic workout sessions with realistic inputs:
   - `sleep_hours` sampled around `N(7, 1)` and clamped to `[4, 10]`
   - `pre_readiness` correlated with sleep; when sleep `< 6`, probability of readiness `2` is `0.6`
   - `workout_hour` follows a deterministic evening pattern, for example `19:00 ± U(-30, 30)` minutes
   - `post_feeling` is stochastic with a mild bias toward `5`

3. PUOS fractional volume never exceeds `ScienceEvidence.md` limits for any muscle group in any simulated session.

4. Weight progression grows monotonically across the simulation, except for allowed deload pullbacks, and no exercise stagnates for more than 4 weeks.

5. The RPE model improves on simulated data:
   - MAE after 50 sessions is `< 1.0` on the 1-10 RPE scale
   - MAE after 50 sessions is at least `15%` lower than MAE after 10 sessions

6. `sessions_count_for_exercise` reflects real per-exercise history throughout the simulation rather than a fabricated counter.

7. The run completes without exceptions and without `None` or `NaN` values entering the feature vector or training samples.

8. The simulation explicitly covers bounded-correction paths:
   - normal correction: bounded ML adjustment is applied and `ml_adjustment_kg != 0`
   - anomaly: intentionally broken predictions exceed the correction limit, produce `anomaly_flag=True`, and trigger rollback behavior
   - fallback: the first 5 cold-start sessions stay on deterministic core and produce `source_label == "[ядро]"`

9. By the end of the simulation, at least 30% of later sessions use successful ML correction (`source_label` in the `[AI: ...]` family) without tripping anomaly fallback.

10. The run writes `_bmad-output/simulation-report.md` containing:
    - weight progression over time (core vs AI-adjusted)
    - MAE trend by epoch/window
    - PUOS utilization by muscle group
    - `source_label` distribution over time
    - anomaly and rollback events

## Tasks / Subtasks

- [x] Task 1: Scaffold the simulation package and CLI surface (AC: 1, 10)
  - [x] Create `gym_coach_brain/simulation/__init__.py`.
  - [x] Create `gym_coach_brain/simulation/run.py` with `argparse` support for `--months`, `--sessions-per-week`, and an optional deterministic `--seed`.
  - [x] Create `gym_coach_brain/simulation/synthetic_athlete.py` for synthetic profile generation and session-by-session signal sampling.
  - [x] Add `tests/test_simulation/` with a narrow smoke path before building the full runner.

- [x] Task 2: Introduce a simulation-safe time seam before orchestrating historical runs (AC: 1-8)
  - [x] Refactor date-sensitive code so the simulation can run historical sessions in chronological order without relying on wall-clock `date.today()` / `datetime.now()`.
  - [x] Make the planner and feature-building path consume an explicit simulated session date/time or injected clock abstraction.
  - [x] Keep production defaults unchanged when the simulation seam is not used.

- [x] Task 3: Seed a real database and bootstrap a single-athlete environment (AC: 1, 2, 6, 7)
  - [x] Reuse `gym_coach_brain.data.seed.seed_all()` for lookup/reference data instead of hand-rolled fixtures.
  - [x] Create one realistic `UserProfile` and persist workout sessions, workout sets, ML jobs, and predictions in the same schema used by production code.
  - [x] Load `ScienceConfig` through the existing loader rather than inventing a simulation-only config object.

- [x] Task 4: Drive the real workout pipeline end-to-end for each simulated session (AC: 1-9)
  - [x] Generate a planned session through the real planner path.
  - [x] Persist pre-workout signals (`sleep_hours`, `pre_readiness`) onto each `WorkoutSession`.
  - [x] Enqueue prediction work via `data.queue.enqueue_predict()`.
  - [x] Run the existing `MLWorker.poll_once()` to create `RPEPrediction` rows.
  - [x] Adapt the plan through `AdaptationEngine.adapt()` so the simulation uses the real `source_label`, bounded-correction, and fallback logic.

- [x] Task 5: Simulate completed sets and close the training loop for fine-tuning (AC: 2, 4-8)
  - [x] Convert each adapted plan into completed `WorkoutSet` rows with synthetic reps/RPE outcomes.
  - [x] Mark sessions `completed`, persist `post_feeling`, and set `is_deload` when the synthetic athlete enters a deload scenario.
  - [x] Enqueue fine-tune work with the real `enqueue_fine_tune()` helper once eligible sessions accumulate.
  - [x] Run the worker again so `RPEModel.fine_tune()` and checkpoint/version logic execute on real data.

- [x] Task 6: Cover anomaly, rollback, and cold-start fallback scenarios intentionally (AC: 8, 9)
  - [x] Add a controlled fault-injection mechanism for malformed or exaggerated predictions so anomaly rollback is exercised on purpose.
  - [x] Keep the first 5 sessions as genuine cold-start fallback runs with no usable history.
  - [x] Ensure anomaly-triggered rollback uses the actual worker/model versioning path from Story 5.4 rather than a fake shortcut.

- [x] Task 7: Compute metrics and generate the markdown report without inventing a second analytics stack (AC: 4, 5, 9, 10)
  - [x] Compute per-window MAE from simulated `WorkoutSet.rpe` vs model predictions.
  - [x] Track core vs AI-adjusted weight deltas per exercise and per session.
  - [x] Summarize PUOS utilization from the same exercise/session data used during simulation.
  - [x] Write `_bmad-output/simulation-report.md` in a dependency-light format, for example markdown tables plus Mermaid or ASCII charts.

- [x] Task 8: Add deterministic automated tests for the simulation harness (AC: 1-10)
  - [x] Add a smoke test for a short run, for example 2-4 weeks, with a fixed seed.
  - [x] Add an anomaly-injection test proving rollback/reporting paths fire without crashing the runner.
  - [x] Add a cold-start test proving the first sessions stay on deterministic fallback.
  - [x] Add a report test proving the markdown output is created and contains the required sections.

- [x] Task 9: Final verification (AC: 1-10)
  - [x] Run `uv run pytest tests/test_simulation`.
  - [x] Run `uv run pytest tests/test_ml/test_worker.py`.
  - [x] Run `uv run pytest tests/test_adaptation/test_engine.py`.
  - [x] Run `uv run python -m gym_coach_brain.simulation.run --months=1 --sessions-per-week=3 --seed=42`.

## Dev Notes

- This story should reuse the real code path, not create a second training engine.
  - The intended orchestration is: seeded DB -> planner -> workout session row -> `enqueue_predict()` -> `MLWorker.poll_once()` -> `AdaptationEngine.adapt()` -> completed `WorkoutSet` rows -> `enqueue_fine_tune()` -> `MLWorker.poll_once()`.
- Two current time-coupling hazards must be addressed before the simulation is trustworthy:
  - `core/planner.py` currently uses `date.today()` to derive rest-day and detraining logic.
  - `data/features.py` currently computes `days_since_last_session` against `datetime.now(timezone.utc)` instead of the simulated session timestamp.
- Do not rely on `api/handlers.handle_workout_start()` as-is for multi-month replay unless you first add a clock/date seam.
  - That handler hardcodes the current date, persists an active session immediately, and enqueues prediction inside the transaction.
- `MLWorker` is already testable in-process through `poll_once()`.
  - Prefer that over daemon sleep loops or subprocess orchestration inside the simulation.
- Fine-tuning is not auto-triggered inside the worker.
  - The simulation must explicitly call `enqueue_fine_tune()` once enough eligible completed sessions exist.
- Training data only exists if the simulation writes real `WorkoutSet` rows with non-null `rpe`.
  - Without that, `MLWorker._load_training_samples()` will skip learning even if jobs are queued.
- Current repo status that affects this story:
  - `ml/worker.py`, `ml/__main__.py`, `ml/model.py`, `adaptation/engine.py`, `core/planner.py`, and `data/features.py` already exist and should be reused.
  - There is currently no `gym_coach_brain/simulation/` package and no `tests/test_simulation/` directory.
  - There is an older planning artifact `_bmad-output/planning-artifacts/epics/epic-7-simulation.md` that references `python -m simulation.engine`; do not follow that legacy path for this story.

### Technical Requirements

- Reuse production modules as the only source of training logic:
  - `gym_coach_brain.core.planner.WorkoutPlanner`
  - `gym_coach_brain.data.queue.enqueue_predict`
  - `gym_coach_brain.data.queue.enqueue_fine_tune`
  - `gym_coach_brain.ml.worker.MLWorker`
  - `gym_coach_brain.adaptation.engine.AdaptationEngine`
- Add a deterministic simulation clock or explicit session timestamp plumbing.
  - Historical replay is not valid if planner and feature builder keep reading wall-clock time.
- Keep the simulation single-user and filesystem-local.
  - No multi-athlete abstractions, no remote services, no new queue technology.
- Preserve the existing DB-mediated contract between API/core and ML worker.
  - No direct model calls that bypass `MLJob`/`RPEPrediction` if the goal is to validate the end-to-end pipeline.
- Use real `RPEPrediction.source_label`, `anomaly_flag`, `ml_adjustment_kg`, and `model_version` fields as report inputs.
  - Do not reconstruct those metrics separately in a report-only structure.
- Make anomaly injection explicit and reversible.
  - The simulation should be able to force a bounded-correction breach without permanently corrupting future normal runs.
- Report generation should remain dependency-light.
  - `pyproject.toml` does not currently include matplotlib/pandas; prefer stdlib plus markdown or justify any new dependency in the implementation.

### Architecture Compliance

- Respect ADR-001 ML isolation.
  - The simulation may orchestrate worker/model behavior, but it should not collapse the worker and core into a fake shared-memory shortcut.
- Respect the repo’s session-lifecycle rules.
  - Use SQLAlchemy sessions via context managers and keep transaction boundaries explicit.
- Keep `ScienceConfig` injected, not global.
  - The simulation runner should load it once and pass it down.
- Maintain absolute imports only under `src/gym_coach_brain/`.
- Keep the simulation deterministic under a fixed seed.
  - Python RNG and PyTorch RNG should be seeded together when the simulation requests reproducibility.
- Reuse existing seed and schema code.
  - Do not duplicate taxonomy, exercise, or equipment fixtures in the simulation package.

### Library / Framework Requirements

- Runtime versions pinned in `gym-coach-brain/pyproject.toml` today:
  - Python `>=3.14`
  - torch `>=2.10.0`
  - SQLAlchemy `>=2.0.48`
  - Alembic `>=1.18.4`
  - loguru `>=0.7.3`
- Latest official PyTorch guidance relevant to this story as of March 9, 2026:
  - Seed both PyTorch and Python RNGs for reproducible runs.
  - `torch.use_deterministic_algorithms(True)` can be used in simulation/test mode to surface nondeterministic operations early.
  - `torch.inference_mode()` is preferred for pure evaluation loops when the simulation is running predictions that do not need autograd, because it removes more overhead than `no_grad`.
- Latest official SQLAlchemy guidance relevant to this story:
  - Keep the `Session` lifecycle external and scoped with context managers.
  - Remember that autoflush occurs before ORM `select()` / `Session.execute()` calls and on commit, which matters when the simulation depends on freshly inserted rows before worker/adaptation reads.

### File Structure Requirements

- New package/files expected:
  - `gym-coach-brain/src/gym_coach_brain/simulation/__init__.py`
  - `gym-coach-brain/src/gym_coach_brain/simulation/run.py`
  - `gym-coach-brain/src/gym_coach_brain/simulation/synthetic_athlete.py`
- New test files expected:
  - `gym-coach-brain/tests/test_simulation/__init__.py`
  - `gym-coach-brain/tests/test_simulation/test_run.py`
  - additional focused tests if the runner is split into smaller helpers
- Existing files likely touched for time/control seams:
  - `gym-coach-brain/src/gym_coach_brain/core/planner.py`
  - `gym-coach-brain/src/gym_coach_brain/data/features.py`
  - `gym-coach-brain/src/gym_coach_brain/api/handlers.py` only if you decide to make the handler path simulation-safe
- Existing reusable seed/config/test surfaces:
  - `gym-coach-brain/src/gym_coach_brain/data/seed.py`
  - `gym-coach-brain/src/gym_coach_brain/core/science.py`
  - `gym-coach-brain/tests/conftest.py`

### Testing Requirements

- Use a fixed seed in simulation tests and assert deterministic outputs for at least one short scenario.
- Add a short-run smoke test that proves:
  - the CLI completes,
  - sessions are created in chronological order,
  - no `None`/`NaN` enters the feature pipeline,
  - the markdown report is written.
- Add an anomaly test that proves:
  - anomalous predictions are recorded,
  - rollback is attempted through the worker,
  - the report includes anomaly/rollback evidence.
- Add a cold-start test that proves:
  - the early sessions produce `[ядро]` labels,
  - no exception is raised before enough history exists.
- Keep heavy runtime bounded in tests.
  - Use shortened horizons in automated tests; reserve the full 6-month run for manual verification or slower integration coverage.

### Project Structure Notes

- The repo already contains the production surfaces needed for this story, but it does not yet contain a simulation package.
- The biggest implementation risk is temporal inconsistency.
  - Without a simulation-specific clock seam, the planner and feature builder will read the current real date and invalidate the six-month replay.
- The second biggest risk is accidentally bypassing the real ML pipeline.
  - If the simulation calls `RPEModel` directly without `MLJob` and `RPEPrediction`, it stops being a true E2E validation harness.
- An older Epic 7 document describes a top-level `simulation.engine` entrypoint and JSON report.
  - This story supersedes that path; keep the new implementation inside `gym_coach_brain/simulation/` and emit the report file required by Epic 5.

### References

- Epic definition and acceptance criteria: [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Story 5.5]
- Epic contract clarifications and simulation decisions: [Source: _bmad-output/planning-artifacts/epic-5-brainstorm-protocol-2026-03-09.md#12 — Модуль `simulation/` не создаётся до 5.5] [Source: _bmad-output/planning-artifacts/epic-5-brainstorm-protocol-2026-03-09.md#13 — Нет абсолютного порога MAE] [Source: _bmad-output/planning-artifacts/epic-5-brainstorm-protocol-2026-03-09.md#14 — Генерация readiness в симуляции]
- Architecture and worker boundaries: [Source: _bmad-output/planning-artifacts/architecture.md#ML Worker Process Lifecycle] [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries] [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns & Consistency Rules]
- PRD success criteria and product constraints: [Source: _bmad-output/planning-artifacts/prd.md#Success Criteria] [Source: _bmad-output/planning-artifacts/prd.md#Functional Requirements (Capability Contract)] [Source: _bmad-output/planning-artifacts/prd.md#Non-Functional Requirements]
- Project-wide implementation rules: [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- Current production surfaces to reuse: [Source: gym-coach-brain/src/gym_coach_brain/core/planner.py] [Source: gym-coach-brain/src/gym_coach_brain/data/features.py] [Source: gym-coach-brain/src/gym_coach_brain/data/queue.py] [Source: gym-coach-brain/src/gym_coach_brain/ml/worker.py] [Source: gym-coach-brain/src/gym_coach_brain/ml/model.py] [Source: gym-coach-brain/src/gym_coach_brain/adaptation/engine.py] [Source: gym-coach-brain/src/gym_coach_brain/api/handlers.py] [Source: gym-coach-brain/src/gym_coach_brain/data/seed.py]
- Current schema contracts: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#WorkoutSession] [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#MLJob] [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#RPEPrediction]
- Existing tests and fixtures: [Source: gym-coach-brain/tests/conftest.py] [Source: gym-coach-brain/tests/test_ml/test_worker.py] [Source: gym-coach-brain/tests/test_adaptation/test_engine.py] [Source: gym-coach-brain/tests/test_core/test_planner.py]
- Conflicting legacy simulation artifact to avoid following verbatim: [Source: _bmad-output/planning-artifacts/epics/epic-7-simulation.md]
- Current official docs checked on 2026-03-09:
  - PyTorch reproducibility notes: https://docs.pytorch.org/docs/stable/notes/randomness.html
  - PyTorch `inference_mode`: https://docs.pytorch.org/docs/stable/generated/torch.autograd.grad_mode.inference_mode.html
  - SQLAlchemy session basics: https://docs.sqlalchemy.org/en/20/orm/session_basics.html

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (create-story)

### Debug Log References

- `_bmad/core/tasks/workflow.xml`
- `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`
- `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/planning-artifacts/epics/epic-5-ai.md`
- `_bmad-output/planning-artifacts/prd.md`
- `_bmad-output/planning-artifacts/architecture.md`
- `_bmad-output/project-context.md`
- `_bmad-output/implementation-artifacts/5-4-model-versioning.md`
- `_bmad-output/planning-artifacts/epic-5-brainstorm-protocol-2026-03-09.md`
- `_bmad-output/planning-artifacts/epics/epic-7-simulation.md`
- `docs/ml-feature-spec.md`
- `gym-coach-brain/pyproject.toml`
- `gym-coach-brain/src/gym_coach_brain/api/handlers.py`
- `gym-coach-brain/src/gym_coach_brain/core/science.py`
- `gym-coach-brain/src/gym_coach_brain/core/planner.py`
- `gym-coach-brain/src/gym_coach_brain/data/features.py`
- `gym-coach-brain/src/gym_coach_brain/data/models.py`
- `gym-coach-brain/src/gym_coach_brain/data/queue.py`
- `gym-coach-brain/src/gym_coach_brain/data/seed.py`
- `gym-coach-brain/src/gym_coach_brain/ml/__main__.py`
- `gym-coach-brain/src/gym_coach_brain/ml/model.py`
- `gym-coach-brain/src/gym_coach_brain/ml/worker.py`
- `gym-coach-brain/src/gym_coach_brain/adaptation/engine.py`
- `gym-coach-brain/tests/conftest.py`
- `gym-coach-brain/tests/test_ml/test_worker.py`
- `gym-coach-brain/tests/test_adaptation/test_engine.py`
- `git log --oneline -5`

### Completion Notes List

- 2026-03-09: Story 5.5 created for the next backlog item `5-5-simulation-e2e`.
- 2026-03-09: Story context captures the current repo reality that worker/model/planner/adaptation code already exists and should be reused rather than replaced.
- 2026-03-09: The main implementation risk called out is time coupling in `core/planner.py` and `data/features.py`, which would otherwise invalidate historical replay.
- 2026-03-09: The story explicitly blocks use of the older `python -m simulation.engine` path from Epic 7 to avoid divergence from the current package structure.
- 2026-03-09: Latest official technical guidance was folded in for PyTorch reproducibility/inference and SQLAlchemy session lifecycle.
- 2026-03-09: `_bmad/core/tasks/validate-workflow.xml` is not present in this repo, so checklist validation must be performed manually against `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`.
- 2026-03-24: Code review performed. Fixes applied: (1) File List corrected — all 12 new/modified files documented; (2) `worker._model` private mutation replaced with public `model` property on `MLWorker`; (3) Anomaly count in `SimulationMetrics.record_session` now uses explicit `anomaly_flags: list[bool]` from DB `RPEPrediction.anomaly_flag` instead of fragile string matching; (4) `test_anomaly_predictions_are_recorded` enhanced to also verify `anomaly_flag=True` rows in DB; (5) `test_deterministic_under_fixed_seed` extended to assert weight equality across runs; (6) New test `test_weight_progression_trend` validates AC 4 (no weight regression >10% in second half of 2-month run).
- 2026-03-09: Implemented by Claude Sonnet 4.6. Key discovery: `planner.py` already had `_today` param, `features.py` had `_now` param, `MLWorker` had `simulation_clock` — all time seams were pre-built. Implementation focused on the orchestration runner `run.py`.
- 2026-03-09: Cold-start design decision: first 5 sessions skip `enqueue_predict()` entirely (no ML prediction row created) so adaptation engine falls back to `[ядро]`. This is more robust than relying on confidence thresholds which can be high even for random-weight models.
- 2026-03-09: Fault injection via `_AnomalyInjectModel` (returns RPE=1.0, confidence=0.99) injected at sessions 25-26. With 3-4 exercises per session, 7-8 consecutive anomalous predictions exceed the `anomaly_rollback_threshold=5` and trigger real rollback via `MLWorker._try_rollback()`.
- 2026-03-09: Full test suite: 416 tests pass, 0 regressions. 17 new simulation tests covering smoke, anomaly, cold-start, report content, determinism, and metrics unit tests.

### File List

- `gym-coach-brain/src/gym_coach_brain/simulation/__init__.py` (new)
- `gym-coach-brain/src/gym_coach_brain/simulation/run.py` (new)
- `gym-coach-brain/src/gym_coach_brain/simulation/__main__.py` (new)
- `gym-coach-brain/src/gym_coach_brain/simulation/synthetic_athlete.py` (new)
- `gym-coach-brain/src/gym_coach_brain/ml/worker.py` (new)
- `gym-coach-brain/src/gym_coach_brain/ml/__main__.py` (new)
- `gym-coach-brain/src/gym_coach_brain/core/planner.py` (modified — `_today` seam already present, minor refactor)
- `gym-coach-brain/src/gym_coach_brain/data/features.py` (modified — `_now` seam already present, minor refactor)
- `gym-coach-brain/src/gym_coach_brain/data/session.py` (modified — removed `MODEL_DIR` constant, moved to `ml/constants.py`)
- `gym-coach-brain/src/gym_coach_brain/ml/model.py` (modified — minor refactor)
- `gym-coach-brain/tests/test_simulation/__init__.py` (new)
- `gym-coach-brain/tests/test_simulation/test_run.py` (new)

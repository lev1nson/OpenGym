# Story 6.2: Fractional volume analytics

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an athlete,
I want to see my historical fractional training volume by muscle group,
so that I can verify the system is distributing load correctly across muscle groups.

## Acceptance Criteria

1. A new workout analytics intent named `volume_report` is available through the gym-coach-brain API surface and returns a deterministic text report for a lookback window defined by `weeks`.
   - The handler accepts `--weeks <int>` as the lookback parameter.
   - Invalid values (`<= 0`, non-integer, or unreasonably large windows such as `> 52`) return `exit_code=1` with a clear validation message.

2. The report is computed from actual completed training history, not from planned workouts.
   - Only `WorkoutSession.status == "completed"` sessions inside the lookback window are included.
   - Volume is derived from persisted `WorkoutSet` rows joined to `Exercise` / `MuscleGroup` metadata.
   - `planned_exercises` JSON must not be used as the historical truth source for this story.

3. Fractional volume math stays aligned with the existing PUOS implementation.
   - Each logged set contributes `1.0` to the exercise primary muscle.
   - Each logged set contributes `0.5` to each secondary muscle listed in `Exercise.secondary_muscle_ids`.
   - The story must reuse the existing coefficient source from `core/puos.py`; do not duplicate `1.0` / `0.5` constants in a second analytics implementation.

4. The report compares historical load against recommended science ranges in a way that matches the time scale.
   - The report shows total fractional sets over the selected `N`-week window.
   - The report also shows average weekly fractional sets (`total_sets / weeks`).
   - Comparison against recommended ranges from `ScienceConfig` is performed on the average weekly value, not the raw multi-week total.

5. `ScienceConfig` is extended so the recommended volume ranges are data-driven and validated, not hardcoded.
   - Add a typed configuration section for per-muscle weekly volume landmarks in `core/science.py`.
   - Populate the corresponding section in `ScienceEvidence.md`.
   - The config must be keyed by the canonical seeded muscle names already used by the repo (`chest`, `back`, `shoulders`, `trapezius`, `biceps`, `triceps`, `quadriceps`, `hamstrings`, `glutes`, `calves`, `abs`, `lower_back`).

6. The report includes science-range status for each muscle group.
   - At minimum, each row identifies whether the average weekly fractional volume is below range, in range, or above range.
   - The row also exposes the configured landmark values used for the comparison.
   - Muscles with zero volume in the selected window are still handled deterministically and should not crash the report.

7. PUOS warning semantics remain session-based even when the report spans multiple weeks.
   - A muscle group is flagged with `⚠️` only when at least one completed session in the lookback window exceeded that muscle’s effective PUOS session limit.
   - The report text makes it clear that this warning reflects session-level overload events inside the selected period, not that the multi-week total itself violated PUOS.

8. Output format is stable and readable for both direct CLI use and future LLM tool-calling.
   - Header includes the lookback window and covered date span.
   - Per-muscle rows are ordered deterministically, preferably by descending total fractional volume.
   - Each row includes: muscle name, total fractional sets, average weekly sets, science-range comparison, and optional `⚠️` marker.
   - Empty-history output returns `exit_code=0` with a clear “no completed workouts in range” message.

9. The story preserves the current handler contract and layering introduced in Story 6.1.
   - Handler returns `(stdout: str, exit_code: int)` and does not commit the transaction.
   - Any JSON envelope / subprocess serialization remains the responsibility of the API boundary from Story 6.1.
   - Do not create a parallel analytics entrypoint outside the `api/` flow.

10. Automated coverage proves the implementation with seeded and synthetic data.
   - `pytest gym-coach-brain/tests/test_api/test_handlers.py -k volume_report` passes.
   - Science-config validation tests cover the new volume-landmark section.
   - Core-level tests cover aggregation and PUOS-overload flagging behavior over completed session history.

## Tasks / Subtasks

- [x] Task 1: Extend science configuration for weekly volume landmarks (AC: 4-6)
  - [x] Add typed Pydantic models in `gym-coach-brain/src/gym_coach_brain/core/science.py` for per-muscle weekly volume ranges.
  - [x] Populate `gym-coach-brain/ScienceEvidence.md` with the canonical landmark data used by the report.
  - [x] Keep validation strict enough to prevent missing muscles, inverted ranges, or malformed values.

- [x] Task 2: Reuse and minimally extend PUOS/fractional-volume core logic (AC: 2-4, 7)
  - [x] Add a narrow helper in `gym-coach-brain/src/gym_coach_brain/core/puos.py` or another clearly justified core location to aggregate fractional volume from historical `WorkoutSet` rows without duplicating coefficient logic.
  - [x] Add helper logic for detecting whether any completed session in the lookback window exceeded the effective PUOS limit for a muscle group.
  - [x] Keep PUOS overload detection grounded in existing `validate_puos()` semantics instead of inventing a second limit formula.

- [x] Task 3: Implement `handle_volume_report()` in the existing API handler style (AC: 1-3, 6-9)
  - [x] Add the handler to `gym-coach-brain/src/gym_coach_brain/api/handlers.py`.
  - [x] Parse and validate `--weeks`.
  - [x] Query completed sessions in-range, eagerly loading the relationships needed for aggregation.
  - [x] Format a deterministic text report with stable ordering and explicit status labels.

- [x] Task 4: Wire the intent into the Story 6.1 API boundary without duplicating architecture work (AC: 1, 9)
  - [x] If Story 6.1 has already introduced `api/main.py`, register `volume_report` there.
  - [x] If Story 6.1 is still not merged in code, add only the minimum `6.2`-specific routing hook needed to keep the implementation aligned with the future `api/main.py` boundary.
  - [x] Update any local API contract documentation that enumerates supported intents.

- [x] Task 5: Add focused automated tests (AC: 10)
  - [x] Extend `gym-coach-brain/tests/test_api/test_handlers.py` with a happy-path `test_volume_report`.
  - [x] Add validation-path tests for bad `--weeks` values.
  - [x] Add a no-history test for the empty-period message.
  - [x] Add core/science tests proving landmark config validation and per-session PUOS warning logic.

- [x] Task 6: Verification (AC: 1-10)
  - [x] Run `uv run pytest gym-coach-brain/tests/test_api/test_handlers.py -k volume_report`.
  - [x] Run `uv run pytest gym-coach-brain/tests/test_core/test_puos.py`.
  - [x] Run `uv run pytest gym-coach-brain/tests/test_core/test_science.py`.

## Dev Notes

- This story has a hidden architecture dependency on Story 6.1.
  - The planning docs assume an API surface with intent dispatch.
  - The current repo still only has `api/handlers.py`; `api/main.py` is part of Story 6.1, not yet present in code.
  - Implement `6.2` so the handler is ready immediately, but do not fork a separate routing architecture to work around missing `6.1` code.

- Current repo reality that must shape the implementation:
  - `gym-coach-brain/src/gym_coach_brain/core/puos.py` already defines the canonical fractional coefficients and current PUOS validation behavior.
  - `gym-coach-brain/src/gym_coach_brain/data/models.py` already provides `WorkoutSession`, `WorkoutSet`, `Exercise`, and `MuscleGroup`.
  - `gym-coach-brain/src/gym_coach_brain/data/seed.py` already defines the canonical muscle names that the science config must match.
  - `gym-coach-brain/src/gym_coach_brain/api/handlers.py` already establishes the current handler style: parse args, return `(stdout, exit_code)`, flush if needed, never commit.

- Critical mismatch to resolve in this story:
  - Epic 6 requires comparison with recommended ranges from `ScienceConfig`.
  - The current `ScienceConfig` model has no weekly volume landmarks at all.
  - The safest implementation is to add a typed, validated config section and update `ScienceEvidence.md`; do not hardcode MEV/MAV/MRV-style numbers inside the handler.

- Another critical mismatch:
  - The legacy monolith docs describe `program analyze` / `muscle report` and mention `MUSCLE_VOLUME_LANDMARKS`.
  - The modular codebase has no migrated equivalent yet.
  - Use that legacy behavior as a conceptual reference only; the new implementation must stay inside the modular `core/` + `api/` architecture.

### Developer Context

- Historical volume must come from logged sets, not planned exercises.
  - `planned_exercises` describes intended work for a session.
  - Fractional volume analytics is historical load analysis and must use the sets the athlete actually performed.

- Compare weekly science ranges against weeklyized output.
  - If the user asks for `weeks=8`, reporting `48.0` total chest sets against a weekly science range would be mathematically wrong.
  - Compute `average_weekly_sets = total_fractional_sets / weeks` and compare that value against the configured weekly landmarks.

- Keep PUOS semantics correct.
  - PUOS is a per-session limit in this project.
  - A multi-week report can summarize session-level overages, but it must not reinterpret PUOS as a rolling-period cap.

- Canonical muscle names come from the taxonomy seed, not ad hoc report labels.
  - Use the seeded English identifiers everywhere in config keys and internal logic.
  - If you want user-facing prettification in the report, keep it as a formatting layer over canonical keys.

### Technical Requirements

- Reuse existing coefficient sources from `core/puos.py`.
  - Do not create separate `AGONIST = 1.0` / `SYNERGIST = 0.5` constants inside the handler.

- Historical aggregation should avoid N+1 query behavior.
  - Fetch the relevant completed sessions and associated `WorkoutSet.exercise` data in a way that does not lazy-load each exercise one by one.
  - Prefer an eager-loading approach compatible with the repo’s SQLAlchemy usage.

- Date filtering must respect the existing storage format.
  - `WorkoutSession.session_date` is stored as ISO date / datetime strings.
  - Normalize comparisons carefully so a lookback window is based on the calendar date, not on fragile string slicing assumptions scattered through the code.

- Science-range configuration must be explicit and typed.
  - Use nested Pydantic models rather than raw unvalidated dictionaries where practical.
  - Validation should fail loudly for missing landmark data or invalid range ordering.

- The report should remain text-first.
  - Story 6.4 will call this as a tool and feed the result back into a conversational agent.
  - Do not switch the handler to a custom JSON payload for this story unless the existing Story 6.1 API boundary explicitly supports additive structured data without breaking callers.

### Architecture Compliance

- Respect the intended module boundaries:
  - `core/` owns deterministic computation and science rules.
  - `api/handlers.py` owns argument parsing and text formatting.
  - The API boundary from Story 6.1 owns intent dispatch, transaction commit/rollback, and any subprocess JSON envelope.

- Preserve SQLAlchemy repo conventions.
  - Use ORM models as the schema source of truth.
  - Do not introduce raw SQL for aggregation.
  - Do not refactor unrelated handler code solely to chase a different query style.

- Preserve deterministic science-over-AI behavior.
  - Volume landmarks must come from `ScienceEvidence.md` through `ScienceConfig`.
  - The report must not rely on LLM interpretation or hardcoded “recommended” text.

### Library / Framework Requirements

- Stay on the project’s existing Pydantic 2 model style in `core/science.py`.
  - The repo already uses `BaseModel`, `Field`, and `model_validator`.
  - Extend that pattern rather than introducing a second config-validation style.

- Stay compatible with SQLAlchemy 2.x.
  - The official SQLAlchemy 2.0 docs show `2.0.48` as the current stable release on March 2, 2026, while `2.1.0b1` is still beta.
  - New work in this story should target stable `2.0.x` behavior, not beta-only features.

- Use official eager-loading patterns where useful.
  - SQLAlchemy’s relationship loading guide recommends `selectinload()` as the simple and efficient collection-loading strategy in most cases.
  - Apply that guidance only where it improves this report’s query path without forcing a repo-wide query-style rewrite.

- Keep science config extensions compatible with current Pydantic guidance.
  - Current Pydantic docs continue to treat nested `BaseModel` structures plus `model_validator()` as the standard way to validate structured config additions.

### File Structure Requirements

- Expected primary files to touch:
  - `gym-coach-brain/ScienceEvidence.md`
  - `gym-coach-brain/src/gym_coach_brain/core/science.py`
  - `gym-coach-brain/src/gym_coach_brain/core/puos.py`
  - `gym-coach-brain/src/gym_coach_brain/api/handlers.py`
  - `gym-coach-brain/tests/test_api/test_handlers.py`
  - `gym-coach-brain/tests/test_core/test_puos.py`
  - `gym-coach-brain/tests/test_core/test_science.py`
  - `docs/api-contracts.md` if intent coverage is documented there

- Avoid unnecessary new modules.
  - A narrow helper addition in `core/puos.py` is reasonable.
  - A brand new analytics subsystem for one report is not.

### Testing Requirements

- Cover the aggregation math directly.
  - Primary muscle contribution: `+1.0`
  - Secondary muscle contribution: `+0.5`
  - Mixed sessions across multiple workouts in the same period

- Cover the period logic directly.
  - In-range completed sessions included
  - Out-of-range sessions excluded
  - Non-completed sessions excluded

- Cover the science comparison directly.
  - Below-range
  - In-range
  - Above-range

- Cover the PUOS warning logic directly.
  - No warning when period volume is high but no individual session breached PUOS
  - Warning when at least one completed session in-range breached the effective session limit

- Cover output determinism.
  - Stable muscle ordering
  - Stable formatting for empty history and non-empty history

### Previous Story Intelligence

- Story 6.1 established the intended API contract direction even though implementation is still pending.
  - Keep handler outputs text-based and deterministic.
  - Keep structured transport concerns at the boundary, not inside individual handlers.

- Story 6.1 also documented an additive-contract mindset.
  - If future tool-calling needs more structure, prefer additive changes at the API envelope level rather than changing handler return types in this story.

### Git Intelligence Summary

- Recent project work added and expanded:
  - readiness/check-in fields on `WorkoutSession`
  - ML queue infrastructure in `data/queue.py`
  - recap / summary deterministic output modules
  - planner and handler surfaces with repo-consistent absolute imports and session-bound writes

- Practical implication for this story:
  - follow the same absolute-import pattern
  - keep the handler thin
  - keep deterministic calculations in core modules
  - add tests alongside implementation rather than as a later cleanup pass

### Latest Tech Information

- SQLAlchemy:
  - Official SQLAlchemy docs list `2.0.48` as the current stable `2.0` release on March 2, 2026; `2.1.0b1` is explicitly beta only.
  - Official ORM docs describe the `Query` object as a legacy facade over the `2.0` system and recommend `select()`-based querying for new 2.x-style work, while still supporting existing `Query` usage.
  - Official relationship-loading docs describe `selectinload()` as the simple and efficient option for most collection eager-loading cases. That is relevant if `volume_report` loads session sets plus exercises and needs to avoid N+1 queries.

- Pydantic:
  - Official Pydantic docs continue to center nested `BaseModel` composition for structured data and `model_validator()` for whole-model validation.
  - The Pydantic changelog lists `v2.12.5` on November 26, 2025 as the latest stable 2.12 patch line at the time of this story creation.
  - For this story, that supports adding a nested science-landmarks model instead of untyped dict parsing.

### Project Structure Notes

- Repo alignment:
  - This story should extend the existing modular codebase, not recreate legacy `gym_coach.py` command logic.
  - The report belongs in the deterministic backend and should remain reusable by the future Telegram/OpenRouter agent layer.

- Detected conflict or variance:
  - Legacy docs talk in MEV/MAV/MRV constants, but the current modular science config does not yet encode those values.
  - Resolve that variance in this story by migrating the landmarks into `ScienceEvidence.md` and `ScienceConfig`.

### References

- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/epics/epic-6.md#Story-6.2-Fractional-volume-analytics]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/6-1-workout-api-handlers.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/project-context.md#Critical-Implementation-Rules]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/prd.md#Capability-Area-Data--Operations]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/architecture.md#Requirements-to-Structure-Mapping]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/docs/api-contracts.md#program-analyze]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/docs/source-tree-analysis.md#Logical-Layers-in-gym_coachpy-current-monolith]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/core/puos.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/api/handlers.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/core/science.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/data/models.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/data/seed.py]
- [Source: https://www.sqlalchemy.org/blog/2026/03/02/sqlalchemy-2.0.48-released/]
- [Source: https://docs.sqlalchemy.org/20/orm/queryguide/relationships.html]
- [Source: https://docs.sqlalchemy.org/en/20/orm/queryguide/]
- [Source: https://docs.pydantic.dev/latest/concepts/models/]
- [Source: https://docs.pydantic.dev/latest/concepts/validators/]
- [Source: https://docs.pydantic.dev/changelog/]

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Story source selection: first backlog story from `sprint-status.yaml` was `6-2-fractional-volume-analytics`
- Planning artifacts loaded: Epic 6, PRD, Architecture, Project Context
- Previous story context loaded: `6-1-workout-api-handlers.md`
- Repo surfaces analyzed: `core/puos.py`, `core/science.py`, `api/handlers.py`, `data/models.py`, `data/seed.py`, tests
- Latest-technology references checked: official SQLAlchemy and Pydantic documentation
- Added typed weekly volume landmarks to `ScienceEvidence.md` and `core/science.py`, including strict ordering validation for MV/MEV/MAV/MRV
- Added `aggregate_historical_volume()` to `core/puos.py` to reuse fractional-volume math and session-level PUOS validation across history
- Added `handle_volume_report()` plus `volume_report` intent registration in `api/main.py` and documented the API contract in `docs/api-contracts.md`
- Validation completed with `.venv/bin/pytest` in `gym-coach-brain/`: 444 passed, 1 warning (torch reported missing optional `numpy`)

### Completion Notes List

- Story converted from placeholder template to implementation-ready context document.
- Hidden dependency on Story 6.1 API routing was made explicit.
- ScienceConfig gap for volume landmarks was surfaced as an explicit implementation requirement.
- Weekly-range comparison and session-based PUOS warning semantics were clarified to prevent incorrect implementations.
- Implemented typed weekly volume landmarks for all canonical seeded muscle groups and loaded them from `ScienceEvidence.md`.
- Implemented historical fractional-volume aggregation over completed `WorkoutSet` history with session-level PUOS overload flag reuse via `validate_puos()`.
- Added deterministic `volume_report` handler output with stable sorting, empty-history handling, and `--weeks` validation.
- Added focused API/core/science tests plus fixture updates; full `gym-coach-brain` regression suite passed.

### File List

- gym-coach-brain/ScienceEvidence.md
- gym-coach-brain/src/gym_coach_brain/core/science.py
- gym-coach-brain/src/gym_coach_brain/core/puos.py
- gym-coach-brain/src/gym_coach_brain/api/handlers.py
- gym-coach-brain/src/gym_coach_brain/api/main.py
- gym-coach-brain/tests/conftest.py
- gym-coach-brain/tests/test_api/test_handlers.py
- gym-coach-brain/tests/test_api/test_readiness_handler.py
- gym-coach-brain/tests/test_core/test_puos.py
- gym-coach-brain/tests/test_core/test_science.py
- gym-coach-brain/tests/test_adaptation/test_summary.py
- docs/api-contracts.md

## Change Log

- 2026-03-24: Implemented Story 6.2 fractional volume analytics with typed science landmarks, historical PUOS-aware aggregation, `volume_report` API intent wiring, deterministic text output, and focused regression coverage.
- 2026-03-24: Code review pass — added DB-level date filter to `handle_volume_report` query (handlers.py:907-913) to avoid loading all completed sessions; added missing negative PUOS warning test `test_volume_report_no_puos_warning_when_no_session_exceeded_limit`. 451 tests passing.

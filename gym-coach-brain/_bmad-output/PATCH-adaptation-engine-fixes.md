# PATCH DOCUMENT: Adaptation Engine Fixes
## gym-coach-brain — Confirmed Bug Fixes and Controlled Follow-ups

**Document Version:** 2.0
**Date:** 2026-03-25
**Author:** Party Mode Review Rewrite
**Status:** Implementation Complete (2026-03-25)

---

## Executive Summary

This rewrite narrows the patch scope to defects that are directly confirmed in code and separates them from behavior-changing enhancements.

### Confirmed P0 Bugs

1. **`target_rpe` is not a first-class field in the planner/API path**
   - Confirmed in `src/gym_coach_brain/core/planner.py`
   - Persisted via `asdict()` in `src/gym_coach_brain/api/handlers.py`
   - Effect: production-created sessions can lose session intent for ML weight correction

2. **Recovery is applied after ML weight selection**
   - Confirmed in `src/gym_coach_brain/adaptation/engine.py`
   - Effect: ML corrections are multiplied down together with the recovery penalty

### P1 Safe Follow-up

3. **Deload sessions are not explicitly protected in adaptation flow**
   - `WorkoutSession.is_deload` exists
   - Adaptation currently does not branch on it

### Deferred Enhancements

The following are not treated as patch-level bug fixes in this document:

- reward mechanism for high readiness
- muscle-specific recovery
- trend/streak-based recovery floors

Those items may be useful, but they change adaptation policy and should be introduced only after the confirmed bugs are fixed and re-simulated.

---

## What Changed From Version 1

Version 1 mixed two kinds of work:

- direct defect correction
- algorithm redesign

This version keeps the patch implementable, testable, and attributable. If we change too many adaptation rules at once, we will not know which change fixed the observed oscillation and under-progression.

---

## Code-Confirmed Findings

## 1. `target_rpe` Loss in the Planner/API Path

### Severity
CRITICAL

### Confirmed Evidence

`PlannedExercise` does not contain `target_rpe`:

```python
@dataclass
class PlannedExercise:
    exercise_id: int
    exercise_name: str
    sets: int
    rep_range: tuple[int, int]
    target_weight_kg: float
    slot_id: str | None = None
    selection_reason: str | None = None
    primary_muscle_name: str | None = None
```

`WorkoutSession.planned_exercises` is created from `asdict(exercise)`:

```python
planned_exercises = [asdict(exercise) for exercise in plan.exercises]
```

### Scope Clarification

This is definitely a real bug for the planner/API flow.

However, the simulation path already injects `target_rpe` into planned exercise JSON in `src/gym_coach_brain/simulation/run.py`. Therefore, this defect is **not automatically sufficient to explain the simulation report by itself**. It still must be fixed, but root-cause attribution for the simulation should remain explicit.

### Root Cause

`target_rpe` exists conceptually in the adaptation and ML pipeline, but it has no stable source of truth in the live planner/session creation path.

### Required Fix

Add `target_rpe` to `PlannedExercise` and define how it is assigned in the real planning flow.

```python
@dataclass
class PlannedExercise:
    exercise_id: int
    exercise_name: str
    sets: int
    rep_range: tuple[int, int]
    target_weight_kg: float
    target_rpe: float | None = None
    slot_id: str | None = None
    selection_reason: str | None = None
    primary_muscle_name: str | None = None
```

### Design Note

Adding the field is necessary but not sufficient. Implementation must also define the source of truth for `target_rpe` in non-simulation flows.

Acceptable options:

- derive it from session-level methodology or science config
- pass it into planner generation explicitly
- store it on the session and propagate it into each planned exercise

---

## 2. Recovery Is Applied After ML Selection

### Severity
CRITICAL

### Confirmed Evidence

Current code:

```python
new_weight = round_to_equipment_increment(
    final_weight_before_recovery * recovery_coeff,
    equipment_type,
    science,
)
```

This means:

```text
final = ml_weight * recovery_coeff
```

When recovery is below `1.0`, the ML-selected load is reduced together with the base load.

### Why This Is a Real Bug

The system currently computes:

```text
core baseline -> ML correction -> recovery penalty
```

That composition suppresses ML intent. If recovery is poor, the model may select a slightly higher load but that correction gets attenuated as part of the final multiplier.

### Required Fix

Split the result into:

- recovery-adjusted base load
- ML delta on top of that base

Proposed implementation:

```python
base_weight_after_recovery = core_weight_kg * recovery_coeff
ml_delta = (ml_weight_kg - core_weight_kg) if used_ml else 0.0
new_weight = round_to_equipment_increment(
    base_weight_after_recovery + ml_delta,
    equipment_type,
    science,
)
```

### Mandatory Decision Before Coding

The team must choose one explicit invariant:

1. **Full ML delta preservation**
   - `base * recovery + full_ml_delta`

2. **Partial ML delta preservation**
   - `base * recovery + scaled_ml_delta`

Version 1 was internally inconsistent here: the sample code preserved the full ML delta, while the expected-results table later assumed partial preservation under low recovery.

This document standardizes on **full ML delta preservation for P0**, because it is the smallest correction to the current bug. If a scaled-ML policy is desired, it should be introduced later as an intentional algorithm change.

---

## 3. Deload Handling in Adaptation

### Severity
MEDIUM

### Current State

`WorkoutSession.is_deload` exists in the data model. The adaptation flow currently extracts recovery but does not explicitly branch for deload sessions.

### Why It Matters

Deload is usually an intentional training-mode override, not merely a readiness penalty. Stacking normal recovery reduction on top of deload logic may over-reduce loads and distort program intent.

### Proposed P1 Fix

```python
recovery_coeff = recovery_signal.coefficient if recovery_signal is not None else 1.0

if session.is_deload:
    recovery_coeff = max(recovery_coeff, 0.95)
```

### Note

This is safe enough for a follow-up patch, but it is not required to validate the two main defects first.

---

## Deferred Items

## A. Reward Mechanism for High Recovery

### Status
Deferred

### Reason

Current recovery design is explicitly clamped to `[0.0, 1.0]` in `src/gym_coach_brain/core/readiness.py`. Introducing recovery bonuses above `1.0` is a product and science decision, not a localized bug fix.

### Recommendation

Do not include in the first patch. Revisit only after P0 is validated.

---

## B. Muscle-Specific Recovery

### Status
Deferred

### Reason

The codebase already computes `muscle_group_fatigue_estimate` for features, but the adaptation decision itself still operates on a global recovery coefficient. Moving to muscle-aware recovery changes system behavior materially and needs a separate design pass.

### Recommendation

Treat as Phase 2 design work, not as part of the initial recovery bug fix.

---

## C. Streak Protection / Trend-Aware Recovery Floors

### Status
Deferred

### Reason

This is a policy layer. It may reduce oscillation, but it can also hide legitimate fatigue or overrule recovery signals. It should not ship in the same patch as the core bug fixes because that would make regression analysis ambiguous.

### Recommendation

Evaluate only after the baseline system is retested with:

- fixed `target_rpe` propagation
- corrected recovery/ML composition

---

## Final Patch Scope

## Phase 1: Must Ship

1. Add `target_rpe` to `PlannedExercise`
2. Define and implement `target_rpe` source of truth for planner/API-created sessions
3. Ensure `target_rpe` persists into `WorkoutSession.planned_exercises`
4. Change recovery composition to apply recovery to the core baseline before adding ML delta
5. Add regression tests for both paths

## Phase 2: Safe Follow-up

6. Add explicit deload handling
7. Re-run simulation and compare progression metrics against baseline

## Phase 3: Separate Design Track

8. Reward mechanism
9. Muscle-specific recovery
10. Trend/streak-based floors

---

## File Impact

## Required

1. `src/gym_coach_brain/core/planner.py`
   - add `target_rpe` field
   - populate it from the chosen source of truth

2. `src/gym_coach_brain/api/handlers.py`
   - verify session creation path persists the new field correctly

3. `src/gym_coach_brain/adaptation/engine.py`
   - replace final weight composition logic
   - optionally add deload guard in follow-up patch

## Optional or Deferred

4. `src/gym_coach_brain/core/readiness.py`
   - no P0 changes required
   - only revisit if reward semantics change

---

## Test Plan

## Test 1: `target_rpe` Persistence in Planner/API Flow

```python
# Given
plan = WorkoutPlanner().generate(...)

# When
planned_exercises = [asdict(exercise) for exercise in plan.exercises]

# Then
# each exercise retains target_rpe in serialized session JSON
```

Expected:

- `target_rpe` is present in `WorkoutSession.planned_exercises`
- adaptation resolves the intended session target, not fallback midpoint

## Test 2: `_resolve_target_rpe()` Uses Real Value

```python
planned_ex = {"target_rpe": 8.0}
assert _resolve_target_rpe(planned_ex, science) == 8.0
```

Control:

```python
planned_ex = {}
assert _resolve_target_rpe(planned_ex, science) == 7.75
```

## Test 3: Recovery No Longer Suppresses ML Delta

```python
core_weight = 40.0
ml_weight = 42.5
recovery = 0.73

base_after_recovery = 29.2
ml_delta = 2.5
expected = 31.7
```

Expected:

- old behavior: `31.0`
- new behavior: `31.7` before equipment rounding

## Test 4: No-ML Path Remains Stable

```python
used_ml = False
core_weight = 40.0
recovery = 0.73
expected = 29.2
```

Expected:

- deterministic fallback behavior unchanged except for refactor

## Test 5: Deload Guard

Only for Phase 2.

```python
session.is_deload = True
recovery = 0.75
expected_effective_recovery = 0.95
```

---

## Rollout Plan

## Day 1

1. Implement `target_rpe` propagation in planner/API flow
2. Implement recovery composition fix
3. Add focused unit tests

## Day 2

4. Run full existing test suite
5. Run targeted simulation scenarios
6. Compare key exercises against baseline report

## Day 3

7. Decide whether deload handling is required immediately
8. Freeze patch release notes

---

## Acceptance Criteria

- planner/API-created sessions persist `target_rpe`
- adaptation reads the persisted `target_rpe`
- ML delta is no longer unintentionally multiplied down by recovery
- no regression in no-ML fallback path
- tests clearly distinguish defect fixes from deferred policy changes

---

## Open Questions

1. What is the canonical source of `target_rpe` in live sessions outside simulation?
2. Should future low-recovery behavior preserve full ML delta or a scaled ML delta?
3. Is deload intended to be a readiness overlay or a separate programming mode?

---

## Recommendation

Implement P0 exactly as scoped above, rerun the 8-week simulation, and only then decide whether the remaining items are still needed.

That sequence gives the cleanest attribution, the lowest regression risk, and the fastest path to a trustworthy adaptation engine patch.

---

## Review Notes

- Adversarial review completed
- Findings: 3 total, 1 fixed (F3 dead code removal), 2 skipped (F1 = intentional P0 fix, F2 = pre-existing fields)
- Resolution approach: auto-fix

# ML Feature Specification

**Version:** 1.0.0
**Date:** 2026-03-08
**Status:** Ready for Architect Review (pre-Epic 5)

## Overview

This document defines the complete 19-dimensional feature payload used as input for the RPEModel (see Epic 5). The first 18 features are assembled at runtime by `gym_coach_brain.data.features.build_feature_vector()`, and `muscle_group_fatigue_estimate` is appended by `AdaptationEngine`.

All features are numeric (float or int). No None, no NaN — cold start fallbacks guarantee complete vectors even for new athletes.

---

## Feature Payload: 19 Features

| # | Feature Name | Type | Range | Normalization | Source (table.column) | Cold Start Fallback |
|---|---|---|---|---|---|---|
| 1 | `exercise_id` | int | 1–N | Embedding (per-athlete, per-exercise) | `exercises.id` | N/A (required) |
| 2 | `movement_pattern_id` | int | 1–7 | Embedding | `movement_patterns.id` via `exercises.movement_pattern_id` | N/A (required) |
| 3 | `primary_muscle_id` | int | 1–12 | Embedding | `muscle_groups.id` via `exercises.primary_muscle_id` | N/A (required) |
| 4 | `is_compound` | int | 0 or 1 | None (binary) | `exercises.is_compound` → `int()` | N/A (required) |
| 5 | `stretch_mediated` | int | 0 or 1 | None (binary) | `exercises.stretch_mediated` → `int()` | N/A (required) |
| 6 | `equipment_type_int` | int | 0–7 | Embedding | `exercises.equipment_type` → alphabetical ordinal | N/A (required) |
| 7 | `set_number` | int | 1–N | Min-max (1–5 typical) | Caller-provided | N/A (required) |
| 8 | `weight_kg` | float | 0–500 | Z-score per exercise | Caller-provided | N/A (required) |
| 9 | `reps` | int | 1–30 | Min-max (1–20 typical) | Caller-provided | N/A (required) |
| 10 | `historical_rpe` | float | 6.0–10.0 | Min-max (6–10) | `workout_sets.rpe` last row for athlete+exercise | **6.0** |
| 11 | `avg_rpe_last_3_sessions_for_exercise` | float | 6.0–10.0 | Min-max (6–10) | AVG(`workout_sets.rpe`) last 3 sessions | **6.0** |
| 12 | `sessions_count_for_exercise` | int | 0–N | Log1p | COUNT(DISTINCT `workout_sets.session_id`) for exercise | **0** |
| 13 | `readiness_score` | float | 1.0–10.0 | Min-max (1–10) | `readiness_logs.recovery_score` (most recent) | **5.0** |
| 14 | `days_since_last_session` | int | 0–N | Log1p | Days since last `workout_sessions` with `status='completed'` | **0** |
| 15 | `sleep_hours` | float | 0.0–24.0 | Min-max (4–10 typical) | `workout_sessions.sleep_hours` | **7.5** |
| 16 | `pre_readiness` | int | 1–10 | Min-max (1–10) | `workout_sessions.pre_readiness` | **5** |
| 17 | `workout_hour_sin` | float | -1.0–1.0 | Already cyclic | `sin(2π * hour / 24)` from `workout_sessions.session_date` | **0.0** |
| 18 | `workout_hour_cos` | float | -1.0–1.0 | Already cyclic | `cos(2π * hour / 24)` from `workout_sessions.session_date` | **-1.0** |
| 19 | `muscle_group_fatigue_estimate` | float | 0.0–1.0 | Already normalized | Derived by `AdaptationEngine._estimate_muscle_group_fatigue()` | **0.0** |

---

## Equipment Type Encoding

`equipment_type_int` is the alphabetical ordinal (0-indexed) of the `EquipmentType` enum value. This ensures **stable encoding** regardless of enum declaration order.

| Ordinal | Equipment Type |
|---|---|
| 0 | `barbell` |
| 1 | `bodyweight` |
| 2 | `cable` |
| 3 | `dips_bar` |
| 4 | `dumbbell` |
| 5 | `machine` |
| 6 | `pullup_bar` |
| 7 | `resistance_band` |

**⚠️ Warning:** Adding new `EquipmentType` values will shift ordinals. This requires model retraining. Validate with `python -m gym_coach_brain.data.validate_features` before any enum change.

---

## Cold Start Fallbacks

When an athlete has no prior history for an exercise, the following fallbacks apply:

| Feature | Fallback Value | Rationale |
|---|---|---|
| `historical_rpe` | **6.0** | Moderate perceived effort — global median for untrained athletes |
| `avg_rpe_last_3_sessions_for_exercise` | **6.0** | Same as historical_rpe |
| `sessions_count_for_exercise` | **0** | Explicit "no history" signal |
| `readiness_score` | **5.0** | Neutral recovery — midpoint of 1–10 scale |
| `days_since_last_session` | **0** | No gap implied for first session |
| `sleep_hours` | **7.5** | Average sleep duration for cold start |
| `pre_readiness` | **5** | Neutral pre-workout readiness |
| `workout_hour_sin` | **0.0** | Hour=12 fallback → `sin(π)` |
| `workout_hour_cos` | **-1.0** | Hour=12 fallback → `cos(π)` |
| `muscle_group_fatigue_estimate` | **0.0** | No recent same-muscle history |

---

## Normalization for PyTorch RPEModel

### Recommended normalization per feature type:

| Strategy | Features | Notes |
|---|---|---|
| **Embedding** | `exercise_id`, `movement_pattern_id`, `primary_muscle_id`, `equipment_type_int` | Learn dense representation |
| **Binary passthrough** | `is_compound`, `stretch_mediated` | Already 0/1 |
| **Min-max [0,1]** | `historical_rpe`, `avg_rpe_last_3`, `readiness_score`, `sleep_hours`, `pre_readiness`, `weight_kg`, `reps`, `set_number` | Bound range |
| **Log1p → [0,1]** | `sessions_count_for_exercise`, `days_since_last_session` | Handles long tail |
| **Cyclic passthrough** | `workout_hour_sin`, `workout_hour_cos` | Preserve 24h periodicity |
| **Normalized passthrough** | `muscle_group_fatigue_estimate` | Already bounded to [0,1] |

### Suggested normalization constants (to be calibrated from real data):

```python
# Approximate ranges for min-max normalization
FEATURE_RANGES = {
    "weight_kg": (0.0, 300.0),
    "reps": (1, 20),
    "set_number": (1, 5),
    "historical_rpe": (6.0, 10.0),
    "avg_rpe_last_3_sessions_for_exercise": (6.0, 10.0),
    "readiness_score": (1.0, 10.0),
    "sleep_hours": (4.0, 10.0),
    "pre_readiness": (1.0, 10.0),
}
```

---

## Key SQL Queries

### `historical_rpe` — last RPE for this athlete+exercise

```sql
SELECT rpe FROM workout_sets
WHERE exercise_id = :exercise_id
  AND session_id != :session_id
  AND rpe IS NOT NULL
ORDER BY id DESC
LIMIT 1;
```

### `avg_rpe_last_3_sessions_for_exercise`

```sql
SELECT AVG(rpe) FROM workout_sets
WHERE exercise_id = :exercise_id
  AND session_id IN (
    SELECT DISTINCT session_id FROM workout_sets
    WHERE exercise_id = :exercise_id AND rpe IS NOT NULL
    ORDER BY session_id DESC LIMIT 3
  )
  AND rpe IS NOT NULL;
```

### `sessions_count_for_exercise`

```sql
SELECT COUNT(DISTINCT session_id) FROM workout_sets
WHERE exercise_id = :exercise_id
  AND session_id != :session_id;
```

### `readiness_score`

```sql
SELECT recovery_score FROM readiness_logs
ORDER BY session_date DESC LIMIT 1;
```

### `days_since_last_session`

```sql
SELECT session_date FROM workout_sessions
WHERE status = 'completed' AND id != :session_id
ORDER BY session_date DESC LIMIT 1;
```

### `sleep_hours` / `pre_readiness`

```sql
SELECT sleep_hours, pre_readiness FROM workout_sessions
WHERE id = :session_id;
```

### `workout_hour_sin` / `workout_hour_cos`

Derived from the workout session timestamp:

```python
hour = dt.hour + dt.minute / 60.0
workout_hour_sin = math.sin(2 * math.pi * hour / 24)
workout_hour_cos = math.cos(2 * math.pi * hour / 24)
```

### `muscle_group_fatigue_estimate`

Computed in `AdaptationEngine` from recent same-muscle completed sessions:

```python
total_sets / (science.puos.max_sets_per_group * science.ml.fatigue_lookback_sessions)
```

---

## Implementation

- **Feature builder:** `gym_coach_brain/data/features.py` — `build_feature_vector()`
- **Schema validator:** `gym_coach_brain/data/validate_features.py` — `python -m gym_coach_brain.data.validate_features`
- **Tests:** `tests/test_data/test_features.py`

### Usage example

```python
from sqlalchemy.orm import Session
from gym_coach_brain.data.features import build_feature_vector

with Session(engine) as session:
    fv = build_feature_vector(
        exercise_id=3,
        session_id=42,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=session,
    )
    # fv.historical_rpe, fv.sleep_hours, etc. — all float/int, never None
```

---

## Definition of Done (Epic 2)

This document must pass architect review before Epic 5 (ML) begins. Confirm:

- [ ] Feature payload is sufficient for RPEModel training (19 features cover exercise context + athlete history + readiness + fatigue)
- [ ] Cold start strategy is acceptable (6.0 RPE fallback is a reasonable prior)
- [ ] Normalization strategy is compatible with the planned PyTorch architecture
- [ ] `sessions_count_for_exercise` provides enough signal despite log1p compression

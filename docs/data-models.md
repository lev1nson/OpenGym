# Data Models — gym-coach skill

**Generated:** 2026-03-01
**Source:** `gym_coach.py` — `SCHEMA_SQL` (lines 78-192) + `ensure_schema()` (lines 238-259)

---

## Schema Overview

12 tables, 3 indexes. All in single SQLite file: `gym_coach.sqlite`.

```
meta                    ← key-value session state store
program_days            ← training program structure (days)
program_exercises       ─┘ exercises per day
exercise_aliases        ← NL normalization dictionary
workout_sessions        ← session lifecycle (active/completed/aborted/skipped)
exercise_sets           ─┘ individual logged sets per session
muscle_groups           ← catalog of muscle names
exercise_muscles        ← exercise-to-muscle activation mappings
user_profile            ← singleton user settings row (id=1)
readiness_logs          ← daily recovery/readiness entries
adaptation_decisions    ← history of adaptation recommendations
session_exercise_substitutions ← exercise swap events per session
```

---

## Table Definitions

### `meta`
Key-value store. Stores active workout session state.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| key | TEXT | PRIMARY KEY | `active_session_id`, `last_exercise_name`, `active_session_paused` |
| value | TEXT | NOT NULL | String value |

**Known keys at runtime:**
- `active_session_id` — ID of current active workout session
- `last_exercise_name` — last logged exercise (for omitting exercise in repeat sets)
- `active_session_paused` — `"1"` if session is paused

**⚠️ Issue:** State in `meta` can become stale if process crashes mid-workout. No cleanup mechanism.

---

### `program_days`
Defines the ordered sequence of training days in the program.

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL UNIQUE |
| position | INTEGER | NOT NULL |

---

### `program_exercises`
Exercises belonging to each program day.

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| day_id | INTEGER | NOT NULL, FK → program_days(id) |
| name | TEXT | NOT NULL |
| position | INTEGER | NOT NULL |
| target_sets | INTEGER | nullable |
| target_reps | TEXT | nullable, e.g. `"8-10"` |

---

### `exercise_aliases`
Maps user input aliases to canonical exercise names.

| Column | Type | Constraints |
|---|---|---|
| alias | TEXT | PRIMARY KEY (stored lowercase) |
| canonical_name | TEXT | NOT NULL |

**Example:** `"жим"` → `"Bench Press"`, `"bench"` → `"Bench Press"`

---

### `workout_sessions`
Core workout session record. One per training session.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| date | TEXT | NOT NULL | `YYYY-MM-DD` format |
| day_name | TEXT | nullable | Program day name |
| raw_text | TEXT | nullable | Accumulated raw log text |
| created_at | TEXT | NOT NULL | ISO UTC timestamp |
| status | TEXT | NOT NULL DEFAULT `'active'` | `active`, `completed`, `aborted`, `skipped` |
| completed_at | TEXT | nullable | Set on `workout done` |
| aborted_at | TEXT | nullable | Set on `workout abort` |
| is_extra | INTEGER | DEFAULT 0 | `1` = extra/unplanned session (excluded from `next`) |

**Status lifecycle:**
```
start → active
done  → completed
abort → aborted
skip  → skipped (inserted directly with status='skipped')
```

**⚠️ Issue:** `cmd_log` inserts without specifying `status`, so historical imports get `status='active'` — semantically incorrect. Should be `'completed'`.

**Indexes:**
- `idx_sessions_date` on `date`

---

### `exercise_sets`
Individual sets logged within a session.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| session_id | INTEGER | NOT NULL, FK → workout_sessions(id) | |
| exercise_name | TEXT | NOT NULL | Canonical name after alias resolution |
| set_index | INTEGER | NOT NULL | Per-exercise index within session (1-based) |
| weight | REAL | nullable | kg |
| reps | INTEGER | nullable | |
| rpe | REAL | nullable | Rate of Perceived Exertion 1-10 |
| notes | TEXT | nullable | Free-form notes |

**Indexes:**
- `idx_sets_exercise_name` on `exercise_name`

---

### `muscle_groups`
Catalog/registry of known muscle group names.

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL UNIQUE |

**Seeded by `init`:** chest, back, lats, upper_back, rear_delts, front_delts, side_delts, biceps, triceps, quads, hamstrings, glutes, calves, abs

---

### `exercise_muscles`
Activation mapping between exercises and muscle groups.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| exercise_name | TEXT | NOT NULL, PK part | |
| muscle_name | TEXT | NOT NULL, PK part | |
| weight | REAL | DEFAULT 1.0 | Activation fraction (0.0–1.0) |

**Primary key:** `(exercise_name, muscle_name)`

**Index:** `idx_exercise_muscles_muscle` on `muscle_name`

**Seeded by `init`** from `DEFAULT_EXERCISE_MUSCLES` dict (30+ exercises, EN + RU aliases).

---

### `user_profile`
Singleton row (id=1). User coaching preferences.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | CHECK(id=1) — singleton |
| goal | TEXT | e.g. `"strength+hypertrophy"` |
| priority | TEXT | e.g. `"aesthetics+strength"` |
| periodization | TEXT | `"linear"`, `"undulating"`, `"block"` |
| rest_seconds_compound | INTEGER | DEFAULT 120 |
| rest_seconds_isolation | INTEGER | DEFAULT 90 |
| updated_at | TEXT | ISO UTC |
| days_per_week | INTEGER | Added via ALTER TABLE |
| session_minutes | INTEGER | Added via ALTER TABLE |
| injuries | TEXT | Added via ALTER TABLE |
| experience | TEXT | Added via ALTER TABLE (`"beginner"`, `"intermediate"`, `"advanced"`) |

**⚠️ Issue:** `days_per_week`, `session_minutes`, `injuries`, `experience` are added via `ALTER TABLE` in `ensure_schema()` and `onboard.py` independently — same migration logic duplicated in two places.

---

### `readiness_logs`
Daily recovery/readiness check-ins.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| date | TEXT | NOT NULL | `YYYY-MM-DD` |
| sleep_hours | REAL | nullable | 0–24 |
| stress | INTEGER | nullable | 1–10 |
| fatigue | INTEGER | nullable | 1–10 |
| soreness | INTEGER | nullable | 1–10 |
| pain | INTEGER | nullable | 1–10 |
| mood | INTEGER | nullable | 1–10 |
| notes | TEXT | nullable | |
| created_at | TEXT | NOT NULL | ISO UTC |

**Index:** `idx_readiness_date` on `date`

---

### `adaptation_decisions`
Audit log of all adaptation recommendations generated.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| date | TEXT | `YYYY-MM-DD` |
| exercise_name | TEXT | nullable |
| decision | TEXT | `"keep"`, `"progress"`, `"deload"`, `"plateau"` |
| load_adjust_pct | REAL | e.g. `5.0`, `-10.0` |
| reps_adjust | INTEGER | currently always 0 |
| reason_codes | TEXT | comma-separated, e.g. `"at_top_of_rep_range,rpe_below_8"` |
| inputs_json | TEXT | JSON snapshot of readiness + session count |
| created_at | TEXT | ISO UTC |

**Index:** `idx_adapt_date` on `date`

---

### `session_exercise_substitutions`
Records exercise swap events during a session.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| session_id | INTEGER | FK → workout_sessions(id) |
| original_exercise | TEXT | |
| substituted_exercise | TEXT | |
| reason | TEXT | nullable |
| created_at | TEXT | ISO UTC |

---

## In-Memory Constants (not in DB)

Two large dictionaries defined in `gym_coach.py` — **data that arguably belongs in the DB:**

### `DEFAULT_EXERCISE_MUSCLES` (line 16–59)
30+ exercise→muscle activation mappings. Seeded into `exercise_muscles` on `init`.
Exists both in-memory (for fallback) and in DB. **Duplication.**

### `MUSCLE_VOLUME_LANDMARKS` (line 62–76)
MEV/MAV/MRV per muscle group (Mike Israetel science-based volumes).
**Hardcoded only** — never stored in DB, no user override possible.

---

## Relationship Diagram

```
program_days (1) ──< program_exercises (N)

workout_sessions (1) ──< exercise_sets (N)
workout_sessions (1) ──< session_exercise_substitutions (N)

exercise_sets.exercise_name >── exercise_muscles.exercise_name >── muscle_groups

exercise_aliases ──> exercise_sets.exercise_name (via normalization)

adaptation_decisions (standalone — exercise_name is denormalized string)
readiness_logs (standalone)
meta (standalone key-value)
user_profile (singleton)
```

---

## Schema Evolution Notes

Schema is evolved via `ensure_schema()` using manual `PRAGMA table_info` + `ALTER TABLE`:
- No migration versioning
- Idempotent (checks column existence before adding)
- `onboard.py` duplicates the same migration logic for its extra columns
- **Recommendation:** Extract shared migration logic or use a simple version counter in `meta`

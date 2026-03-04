# Architecture — gym-coach skill

**Generated:** 2026-03-01
**Scan level:** exhaustive (all source files read)

---

## Executive Summary

`gym-coach` — это персональный тренировочный трекер для Макса, реализованный как OpenClaw skill. Система принимает естественный язык (русский/английский mix), конвертирует его в структурированные CLI-команды и сохраняет данные в локальную SQLite БД.

**Текущее состояние:** MVP-монолит в продакшне без тестов. Работает, но хрупкий: два критических regex-бага, semantic bug в логировании, нет покрытия.

**Готовность к refactoring:** Высокая. Логические слои чётко видны, разбивка на модули не требует переработки бизнес-логики.

---

## System Context

```
┌─────────────────────────────────────────────────────┐
│                 OpenClaw Platform                    │
│                                                      │
│  User (Telegram)                                     │
│       │ text message                                 │
│       ▼                                              │
│  Main Agent (AGENTS.md)                              │
│       │ detects fitness intent                       │
│       │ calls router --text "..." --json             │
│       ▼                                              │
│  ┌─────────────────────────────────────────────┐     │
│  │           gym-coach skill                   │     │
│  │                                             │     │
│  │  router.py → gym_coach.py → SQLite          │     │
│  │                                             │     │
│  └─────────────────────────────────────────────┘     │
│       │ JSON response                                │
│       ▼                                              │
│  Main Agent formats → Telegram reply                 │
└─────────────────────────────────────────────────────┘
```

---

## Architecture Pattern: CLI Monolith + NL Proxy

### Current Architecture

```
┌──────────────────────────────────────────────────────────┐
│  router.py  (NL Proxy Layer — 358 LOC)                   │
│                                                          │
│  Input:  raw user text (RU/EN mixed)                     │
│  Output: JSON {intent, argv, stdout, exit_code}          │
│                                                          │
│  ┌──────────────────────┐  ┌────────────────────────┐   │
│  │  Intent Detection    │  │  Entity Extraction     │   │
│  │  (regex + has_any)   │  │  weight, reps, RPE,    │   │
│  │                      │  │  RIR→RPE conversion,   │   │
│  │  19 intent classes   │  │  exercise name,        │   │
│  │  priority-ordered    │  │  day name              │   │
│  └──────────┬───────────┘  └───────────┬────────────┘   │
│             └──────────────┬───────────┘                 │
│                            │ RouteResult(intent, argv)   │
│                            ▼                             │
│                    subprocess.run(gym_coach.py)          │
└────────────────────────────┬─────────────────────────────┘
                             │ structured argv
                             ▼
┌──────────────────────────────────────────────────────────┐
│  gym_coach.py  (CLI Engine Monolith — 2029 LOC)          │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  build_parser() — argparse (108 lines)          │    │
│  │  main() — 30+ elif dispatch branches            │    │
│  └─────────────┬───────────────────────────────────┘    │
│                │                                         │
│                ▼                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Command Handlers (mixed in single file)        │    │
│  │                                                 │    │
│  │  Program:   import, show, analyze, next         │    │
│  │  Workout:   start, status, set, done, pause,    │    │
│  │             resume, abort, undo, skip, swap,    │    │
│  │             suggest                             │    │
│  │  Profile:   show, set                           │    │
│  │  Muscle:    map, report                         │    │
│  │  Readiness: log, last                           │    │
│  │  Adapt:     recommend (194 LOC)                 │    │
│  │  Program:   analyze (301 LOC)                   │    │
│  └─────────────┬───────────────────────────────────┘    │
│                │                                         │
│                ▼                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Shared Utilities                               │    │
│  │  connect(), ensure_schema(), meta_get/set/del() │    │
│  │  normalize_exercise(), parse_line()             │    │
│  │  validate_*(), estimate_1rm()                   │    │
│  │  calc_accumulated_readiness(), detect_plateau() │    │
│  └─────────────┬───────────────────────────────────┘    │
│                │                                         │
│                ▼                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  SQLite (WAL mode)  gym_coach.sqlite            │    │
│  │  12 tables, 5 indexes                           │    │
│  └─────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

---

## Core Subsystems

### 1. NL Parsing Layer (`router.py`)

**Responsibility:** Convert free-form user text to structured argv.

**How it works:**
- Priority-ordered regex checks using `has_any()` word matching
- Specific entity extraction via compiled regexes (`RE_WEIGHT_REPS_X`, `RE_RPE`, `RE_RIR`)
- RIR→RPE conversion at this layer (RPE = 10 - RIR)
- 19 intent classes — returns `RouteResult(intent, argv, needs_clarification)`
- Subprocess spawn to `gym_coach.py` with structured argv

**Strengths:**
- Clean separation from CLI engine
- Handles bilingual input well
- `--dry-run` mode for testing without side effects
- `--json` mode for machine-readable agent integration

**Weaknesses:**
- `subprocess.TimeoutExpired` not caught → unhandled exception (`router.py:298`)
- Intent priority ordering is implicit — no documentation of conflict resolution
- `workout_done` triggers on "всё", "готово" — high false-positive risk in casual conversation

---

### 2. Parsing Engine (`parse_line` in `gym_coach.py:801-869`)

**Responsibility:** Parse free-form set text → `(exercise_name, [(weight, reps)], rpe, notes)`.

**Supported formats:**
| Format | Example | Supported |
|---|---|---|
| `weight x reps x sets` | `bench 60x8x3` | ✅ |
| `weight x reps` | `bench 60x8` | ✅ |
| `comma-separated sets` | `80x5, 82x4, 84x3` | ✅ |
| RPE `@N` | `bench 70x6 @8` | ✅ |
| RPE `rpe N` | `bench 70x6 rpe 8` | ❌ **BUG** |
| Cyrillic `х` | `жим 70х6` | ❌ **BUG** |
| RIR `rir N` | `bench 70x6 rir 2` | ❌ (only in router, not parse_line) |
| Russian "на" | `70 на 6` | ❌ (only in router) |

**Root cause of bugs:** Two different `RE_RPE` definitions exist — one in `router.py` (supports `rpe N`) and one in `gym_coach.py` (only `@N`). Same for Cyrillic `х`.

---

### 3. Session State Machine (`meta` table + session lifecycle)

**States:**
```
         workout start
              │
              ▼
           active ◄──────── pause/resume (meta flag only, status stays 'active')
              │
     ┌────────┼────────┐
     │        │        │
  abort      done     (process crash — state stuck in meta)
     │        │
  aborted  completed
```

**Session state stored in `meta` table (key-value):**
- `active_session_id` — current session ID
- `last_exercise_name` — for "default exercise" behaviour
- `active_session_paused` — "1" when paused

**Gap:** If process crashes during active workout, `meta` retains stale `active_session_id`. Next `workout start` will detect existing session and print warning (good), but requires `--force` to recover (acceptable).

**`workout skip`** creates a session record with `status='skipped'` — does NOT affect `cmd_next` sequence. Correct behaviour.

**`is_extra=1`** sessions are excluded from `cmd_next` sequence. Correct behaviour.

---

### 4. Adaptation Engine (`cmd_adapt_recommend`, lines 1116–1310)

**Responsibility:** Deterministic load adjustment recommendation.

**Inputs:**
- 7-day weighted readiness (fatigue, pain, sleep, stress)
- Last 6 session history for exercise (per-session aggregates)
- Target reps from program
- Periodization setting from user profile
- Weeks since last deload

**Decision table (priority order):**
```
1. pain_acc >= 7          → deload -10%
2. fatigue_acc >= 8       → deload -7.5%
3. sleep_avg <= 5h        → deload -5%
4. plateau_score >= 2     → plateau (no weight change, suggest variation)
5. at top of rep range
   AND rpe <= 8           → progress (+5% linear / +2.5% other)
6. reps↑ AND rpe↓         → progress +2.5%
7. reps↓ AND rpe↑         → deload -5%
8. weeks_since_deload >= 8 → deload -5%
default                   → keep
```

**Strengths:** Fully deterministic — no LLM hallucination risk. Grounded in evidence-based training science (MEV/MAV/MRV by Mike Israetel, Brzycki 1RM formula).

**Weaknesses:**
- Priority ordering means pain/fatigue always override progress — no compound scoring
- `weeks_since_deload` only starts counting after first deload (returns `None` for new users)
- Suggested weight rounded to nearest 2.5kg (correct for barbell; wrong for dumbbells/machines)

---

### 5. Volume Analysis (`cmd_program_analyze`, lines 1551–1852)

**Responsibility:** Full training dashboard — muscle volumes vs MEV/MAV/MRV, per-exercise trends, computed recommendations.

**Key computations:**
- Muscle volume: weighted set count (activation fraction × sets) per muscle this week
- Push:Pull ratio for shoulder health tracking
- Per-exercise: 1RM trend (Brzycki), plateau detection, tonnage trend, progression readiness
- `computed_recommendations` — pre-computed list (not LLM-generated)

**Output format:** Human-readable or `--json` for agent consumption.

---

## Data Flow: Full Workout Session

```
User: "начать тренировку push"
  → router.py detects workout_start, day=Push
  → gym_coach.py workout start --day Push
  → INSERT workout_sessions(status='active') → session_id=42
  → meta: active_session_id=42

User: "жим 70x6 rpe 8"
  → router.py detects workout_set, weight=70, reps=6, rpe=8, exercise=None
  → gym_coach.py workout set --structured --weight 70 --reps 6 --rpe 8
  → (exercise defaults to last → None → error: "provide --exercise once")
  ⚠️  First set of session requires explicit exercise name

User: "жим 70x6 rpe 8"  (after router extracted exercise from preceding text)
  → gym_coach.py workout set --structured --exercise "Bench Press" --weight 70 --reps 6 --rpe 8
  → normalize_exercise("жим") → "Bench Press" (via exercise_aliases)
  → validate_set_values(70, 6, 8) → OK
  → INSERT exercise_sets(session_id=42, exercise_name="Bench Press", set_index=1, ...)
  → meta: last_exercise_name="Bench Press"

User: "закончил"
  → router.py detects workout_done
  → gym_coach.py workout done
  → UPDATE workout_sessions SET status='completed', completed_at=now WHERE id=42
  → DELETE meta: active_session_id, last_exercise_name, active_session_paused
  → print summary
```

---

## Identified Issues — Severity Matrix

### 🔴 Critical (block correct operation)

| ID | Issue | Location | Impact |
|---|---|---|---|
| C1 | `parse_line` doesn't support `rpe N` format | `gym_coach.py:796` | Free-form sets with "rpe 8" silently drop RPE |
| C2 | `parse_line` doesn't support Cyrillic `х` | `gym_coach.py:798` | "жим 70х6" fails to parse in `--text` mode |
| C3 | Zero test coverage | — | Any change risks silent regression |

### 🟡 Medium (semantic bugs / reliability)

| ID | Issue | Location | Impact |
|---|---|---|---|
| M1 | `cmd_log` inserts with `status='active'` | `gym_coach.py:884` | Historical imports pollute session state |
| M2 | `subprocess.TimeoutExpired` not caught | `router.py:298` | Unhandled exception crashes router on timeout |
| M3 | Schema migration logic duplicated | `gym_coach.py:252`, `onboard.py:116` | Risk of drift; extra columns inconsistently added |
| M4 | `--limit` not validated in `history` | `gym_coach.py:935` | Negative/zero limit causes unexpected SQLite behaviour |
| M5 | `workout_done` triggers on "всё", "готово" | `router.py:147` | High false-positive in casual conversation |

### 🟢 Low (tech debt / improvement)

| ID | Issue | Location | Impact |
|---|---|---|---|
| L1 | `DEFAULT_EXERCISE_MUSCLES` exists in-memory AND DB | `gym_coach.py:16` | Double source of truth for exercise definitions |
| L2 | `MUSCLE_VOLUME_LANDMARKS` hardcoded | `gym_coach.py:62` | Can't be customized per user |
| L3 | `build_parser()` is 108 lines in monolith | `gym_coach.py:1855` | Hard to navigate |
| L4 | `main()` has 30+ elif branches | `gym_coach.py:1966` | Scales poorly with new commands |
| L5 | `onboard.py` imports `SCHEMA_SQL` from monolith | `onboard.py:42` | Tight coupling |
| L6 | No CI/CD pipeline | — | Manual testing only |
| L7 | `reps_adjust` always 0 in adaptation_decisions | `gym_coach.py:1291` | Incomplete feature |

---

## What Works Well ✅

1. **Subprocess isolation** — router.py is fully stateless, no shared memory with CLI engine
2. **Deterministic adaptation** — no LLM hallucinations in training recommendations
3. **Zero external dependencies** — trivial to deploy anywhere with Python
4. **Exercise alias system** — clean normalization before DB writes
5. **WAL mode + FK constraints** — proper SQLite configuration
6. **`is_extra` flag** — correctly excludes unplanned sessions from program sequence
7. **Brzycki 1RM formula** — valid science-based strength estimation
8. **MEV/MAV/MRV volume landmarks** — evidence-based training science (Israetel)
9. **Weighted readiness averaging** — recency-weighted 7-day window is sensible
10. **RIR→RPE conversion in router** — single conversion point, CLI stays clean

---

## Recommended Refactoring Roadmap

### Phase 1 — Bug fixes (no architecture change needed)
1. Fix `RE_RPE` in `parse_line` → add `rpe N` support (2 lines)
2. Fix `RE_WXRX` in `parse_line` → add Cyrillic `х` (1 line)
3. Fix `cmd_log` → set `status='completed'` + backfill existing (5 lines)
4. Fix `router.py` → catch `subprocess.TimeoutExpired` (3 lines)
5. Add `--limit` validation in `cmd_history` (2 lines)
6. Write 10–15 pytest tests covering P0 fixes

### Phase 2 — Stabilisation
1. Deduplicate schema migration logic into shared function
2. Improve `workout_done` intent detection (avoid false positives on "всё")
3. Add JSON error contract to router (`error_type`, `error_message` fields)

### Phase 3 — Monolith decomposition
Decompose `gym_coach.py` into package per source-tree-analysis.md proposal:
- `gym_coach/db.py` — schema, connection, meta helpers
- `gym_coach/parsing.py` — parse_line, normalize_exercise, regexes
- `gym_coach/constants.py` — exercise/muscle dicts
- `gym_coach/commands/*.py` — one file per command group
- `cli.py` — thin build_parser() + main()

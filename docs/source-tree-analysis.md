# Source Tree Analysis — gym-coach skill

**Generated:** 2026-03-01
**Scan level:** exhaustive

---

## Directory Structure

```
workspace/skills/gym-coach/
│
├── gym_coach.py          ★ CORE MONOLITH (2029 lines)
│                           Contains everything: schema, DB helpers, CLI parser,
│                           all command handlers, parsing engine, adaptation engine
│
├── router.py             ★ NL PROXY LAYER (358 lines)
│                           Natural-language intent detection + entity extraction
│                           Dispatches to gym_coach.py via subprocess
│
├── onboard.py              USER ONBOARDING CLI (204 lines)
│                           Collects user profile + equipment interactively or via args
│                           Imports SCHEMA_SQL from gym_coach.py (tight coupling)
│
├── SKILL.md                AGENT INTERFACE SPEC
│                           Trigger patterns, CLI reference, agent integration contract
│                           Used by OpenClaw agent to know WHEN and HOW to invoke this skill
│
├── coach-prompt.md         AI COACHING BEHAVIOR SPEC
│                           Session protocol, adaptation interpretation, response templates
│                           Injected as system prompt when gym-coach skill activates
│
├── program.example.json    SAMPLE PROGRAM DATA
│                           Minimal Push/Pull program example
│                           Used for testing and as template for program generation
│
├── gym_coach.sqlite        DATABASE (gitignored)
│                           Single SQLite file, WAL mode
│                           Contains all user data
│
└── .gitignore              Excludes: __pycache__/, *.pyc, gym_coach.sqlite
```

---

## Logical Layers in `gym_coach.py` (current monolith)

The 2029-line file has these logical sections — **all mixed together:**

```
gym_coach.py
│
├── [L1-59]   CONSTANTS — DEFAULT_EXERCISE_MUSCLES dict (30+ exercises)
├── [L62-76]  CONSTANTS — MUSCLE_VOLUME_LANDMARKS dict (MEV/MAV/MRV)
├── [L78-192] SCHEMA_SQL — full DDL for 12 tables + 5 indexes
│
├── [L195-230] DB HELPERS
│               connect(), now_utc_iso(), parse_iso_date()
│               validate_set_values(), validate_score(), avg_or_none()
│
├── [L238-275] SCHEMA MANAGEMENT
│               ensure_schema() — DDL + ALTER TABLE migrations
│               meta_get(), meta_set(), meta_del()
│
├── [L278-317] cmd_init()
│
├── [L320-325] normalize_exercise()  ← alias resolution helper
│
├── [L328-408] PROGRAM COMMANDS
│               cmd_program_import(), cmd_program_show()
│
├── [L410-459] cmd_next()
│
├── [L462-466] SESSION STATE CONSTANTS
│               ACTIVE_SESSION_KEY, LAST_EXERCISE_KEY, PAUSED_SESSION_KEY
│
├── [L468-511] SESSION STATE HELPERS
│               get_active_session_id(), get_last_exercise()
│               rebuild_session_raw_text_from_sets(), is_active_session_paused()
│
├── [L513-648] WORKOUT SESSION COMMANDS
│               cmd_workout_start(), cmd_workout_status(), cmd_workout_set()
│
├── [L651-736] PROFILE COMMANDS
│               get_profile(), cmd_workout_done(), cmd_profile_show(), cmd_profile_set()
│
├── [L739-793] MUSCLE COMMANDS
│               cmd_muscle_map(), week_start(), cmd_muscle_report()
│
├── [L795-869] PARSING ENGINE
│               RE_RPE, RE_WXRXS, RE_WXRX constants
│               parse_line() — free-form text → (exercise, sets, rpe, notes)
│
├── [L872-963] LOG + HISTORY COMMANDS
│               cmd_log(), cmd_last(), cmd_history()
│
├── [L966-1027] READINESS COMMANDS
│                cmd_readiness_log(), cmd_readiness_last()
│
├── [L1030-1113] ANALYSIS HELPERS
│                 estimate_1rm() — Brzycki formula
│                 calc_accumulated_readiness() — 7-day weighted average
│                 get_exercise_session_history() — per-session aggregates
│                 detect_plateau() — variance-based plateau detection
│                 weeks_since_deload()
│
├── [L1116-1310] cmd_adapt_recommend()
│                 — LARGEST COMMAND: full adaptation engine (194 lines)
│                 — Deterministic decision table (pain/fatigue/plateau/RPE)
│                 — 1RM estimation, tonnage trends, rep range check
│                 — Persists decision to DB
│
├── [L1313-1425] cmd_workout_suggest()  ← exercise similarity search
│
├── [L1428-1548] WORKOUT CONTROL COMMANDS
│                 cmd_workout_pause(), cmd_workout_resume(), cmd_workout_abort()
│                 cmd_workout_undo(), cmd_workout_skip(), cmd_workout_swap()
│
├── [L1551-1852] cmd_program_analyze()
│                 — SECOND LARGEST COMMAND: 301 lines
│                 — Full training dashboard: volumes, trends, recommendations
│                 — Muscle volume vs MEV/MAV/MRV analysis
│                 — Push:Pull ratio, per-exercise analysis, deload recommendations
│
├── [L1855-1963] build_parser()
│                 — 108 lines of argparse setup (entire CLI surface)
│
└── [L1966-2029] main()
                  — Dispatch table: 30+ elif branches
                  — Global sqlite3.Error handler
```

---

## Coupling Map

```
router.py
  └── imports: nothing from gym_coach
  └── spawns:  gym_coach.py (subprocess) ← loose coupling ✓

onboard.py
  └── imports: SCHEMA_SQL from gym_coach  ← tight coupling ⚠️
  └── duplicates: ensure_schema() migration logic ← duplication ⚠️

SKILL.md
  └── references: router.py paths, gym_coach.py paths (documentation only)

coach-prompt.md
  └── references: gym_coach.py CLI commands (documentation only)
```

---

## Proposed Module Split (for future refactoring)

```
gym-coach/
│
├── gym_coach/              ← package (replaces monolith)
│   ├── __init__.py
│   ├── db.py               ← connect(), SCHEMA_SQL, ensure_schema(), meta_*
│   ├── constants.py        ← DEFAULT_EXERCISE_MUSCLES, MUSCLE_VOLUME_LANDMARKS
│   ├── parsing.py          ← parse_line(), normalize_exercise(), RE_* patterns
│   ├── models.py           ← validate_set_values(), validate_score(), estimate_1rm()
│   │
│   └── commands/
│       ├── __init__.py
│       ├── workout.py      ← start, status, set, done, pause, resume, abort, undo,
│       │                      skip, swap, suggest
│       ├── program.py      ← import, show, analyze, next
│       ├── readiness.py    ← log, last
│       ├── adapt.py        ← recommend (+ analysis helpers)
│       ├── muscle.py       ← map, report
│       ├── profile.py      ← show, set
│       └── log.py          ← log, last, history
│
├── cli.py                  ← build_parser() + main() (thin dispatch layer)
├── router.py               ← unchanged (already separate)
├── onboard.py              ← simplified (imports from gym_coach.db)
│
├── tests/
│   ├── conftest.py         ← tmp DB fixture
│   ├── test_parsing.py
│   ├── test_router.py
│   ├── test_commands_workout.py
│   ├── test_commands_readiness.py
│   └── test_adapt.py
│
├── SKILL.md
├── coach-prompt.md
└── program.example.json
```

---

## Entry Points

| Entry point | Purpose | Invoked by |
|---|---|---|
| `gym_coach.py` (main) | All structured CLI commands | subprocess from router, direct CLI |
| `router.py` (main) | NL text → intent → CLI dispatch | OpenClaw agent |
| `onboard.py` (main) | User profile setup | Manual run / setup script |

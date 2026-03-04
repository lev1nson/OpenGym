# Technology Stack — gym-coach skill

**Generated:** 2026-03-01
**Project root:** `/home/ubuntu/.openclaw/workspace/skills/gym-coach`
**Scan level:** exhaustive

---

## Stack Overview

| Category | Technology | Version | Justification |
|---|---|---|---|
| Language | Python 3 | 3.14 (pyc cache) | Single language across all files |
| Database | SQLite | stdlib (3.x) | Embedded DB, WAL journal mode |
| DB access | sqlite3 | stdlib | Raw SQL, Row factory |
| CLI framework | argparse | stdlib | Nested subcommands (`cmd > subcmd`) |
| Process dispatch | subprocess | stdlib | router.py → gym_coach.py via spawn |
| Type hints | typing | stdlib | Dict, List, Tuple, Optional annotations |
| Date/time | datetime | stdlib | UTC timestamps, date arithmetic |
| Serialization | json | stdlib | JSON output for agent-readable responses |
| Pattern matching | re | stdlib | NL parsing: weight×reps, RPE, RIR |
| Data classes | dataclasses | stdlib | `RouteResult` in router.py |
| Path handling | pathlib | stdlib | router.py uses `Path` |
| No external deps | — | — | Zero pip dependencies |

---

## Architecture Pattern

**Pattern:** CLI Monolith with NL Proxy Layer

```
User / OpenClaw Agent
        │
        ▼
  router.py  ←─── NL text (Russian/English mixed)
   (NL proxy)       intent detection + entity extraction
        │
        │  subprocess spawn
        ▼
  gym_coach.py  ←── structured argv
   (CLI engine)     argparse + SQLite + business logic
        │
        ▼
  gym_coach.sqlite  ←── SQLite WAL
   (persistence)
```

**Onboarding path (separate):**
```
onboard.py → imports SCHEMA_SQL from gym_coach.py → gym_coach.sqlite
```

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| No external dependencies | stdlib only | Zero-install for OpenClaw agent environment |
| subprocess dispatch | router.py spawns gym_coach.py | Isolation; router stays stateless |
| WAL journal mode | `PRAGMA journal_mode=WAL` | Concurrent read access |
| Session state in meta table | key-value in SQLite | Survives process restart |
| Dual parsing modes | `--text` (free-form) vs `--structured` (NL-preprocessed) | Supports both direct CLI and agent dispatch |
| RIR→RPE conversion in router | Before CLI dispatch | Single conversion point; CLI deals only with RPE |

---

## Known Tech Debt

| Item | Location | Severity |
|---|---|---|
| Schema migration via manual ALTER TABLE | `ensure_schema()`, `onboard.py` | Medium — works but fragile without versioning |
| Hardcoded DB path | `DB_PATH = BASE_DIR / gym_coach.sqlite` | Low — intentional for skill isolation |
| Cyrillic `х` missing from `parse_line` regex | `gym_coach.py:797` | High — breaks common RU input |
| `rpe N` pattern missing from `parse_line` | `gym_coach.py:796` | High — doc/code mismatch |
| `cmd_log` inserts with `status='active'` default | `gym_coach.py:884-889` | Medium — semantic bug |
| No subprocess timeout error handling | `router.py:298` | Medium — unhandled `TimeoutExpired` |
| No input tests | — | High — zero coverage |

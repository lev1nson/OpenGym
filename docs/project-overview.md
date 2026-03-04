# Project Overview — gym-coach skill

**Generated:** 2026-03-01
**Project root:** `/home/ubuntu/.openclaw/workspace/skills/gym-coach`

---

## What It Is

`gym-coach` — персональный тренировочный трекер для Макса, интегрированный как OpenClaw skill. Принимает команды на естественном языке (RU/EN), логирует тренировки в SQLite, предоставляет научно-обоснованные рекомендации по нагрузке.

---

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Language | Python 3.11+, stdlib only |
| Persistence | SQLite (WAL, FK) |
| NL interface | Regex-based intent detection (router.py) |
| CLI | argparse nested subcommands |
| Process model | Subprocess spawn (router → gym_coach) |
| External deps | **Zero** |

---

## Architecture Type

**CLI Monolith + NL Proxy**

```
Telegram → OpenClaw Agent → router.py (NL proxy) → gym_coach.py (CLI engine) → SQLite
```

---

## Repository Structure

**Type:** Monolith — single Python module + NL proxy layer

```
gym-coach/
├── gym_coach.py     # 2029 LOC — core engine (schema, commands, parsing, adaptation)
├── router.py        # 358 LOC  — NL proxy (intent detection, subprocess dispatch)
├── onboard.py       # 204 LOC  — user profile setup
├── SKILL.md         # OpenClaw agent interface spec
├── coach-prompt.md  # AI coaching behaviour instructions
└── program.example.json
```

---

## Key Capabilities

| Capability | Commands |
|---|---|
| Session tracking | `workout start/status/set/done/pause/resume/abort/undo` |
| Program management | `program import/show/analyze`, `next` |
| Exercise substitution | `workout suggest/swap/skip` |
| Readiness logging | `readiness log/last` |
| Load adaptation | `adapt recommend` (deterministic, science-based) |
| Volume analysis | `program analyze` (MEV/MAV/MRV, Push:Pull ratio) |
| User profile | `profile show/set`, `onboard.py` |
| Muscle mapping | `muscle map/report` |
| NL interface | `router.py --text "начать тренировку push" --json` |

---

## Current Health

| Metric | Status |
|---|---|
| Functional | ✅ Works in production |
| Test coverage | ❌ Zero |
| Critical bugs | ⚠️ 2 (regex parser) |
| Medium bugs | ⚠️ 5 |
| Documentation | ✅ SKILL.md + coach-prompt.md |
| CI/CD | ❌ None |
| External dependencies | ✅ Zero |

---

## Getting Started

```bash
python3 gym_coach.py init
python3 gym_coach.py program import program.example.json
python3 gym_coach.py next
```

Full setup: see [Development Guide](./development-guide.md)

# Documentation Index — gym-coach skill

**Generated:** 2026-03-01
**Project root:** `/home/ubuntu/.openclaw/workspace/skills/gym-coach`
**Scan level:** exhaustive

> This is the primary entry point for AI-assisted development on gym-coach.
> Start here for any feature work, bug fixes, or architecture decisions.

---

## Project at a Glance

- **Type:** CLI Monolith + NL Proxy (Python, zero external deps)
- **Language:** Python 3.11+
- **Architecture:** `router.py (NL) → gym_coach.py (CLI) → SQLite`
- **Entry point:** `router.py --text "<message>" --json`
- **Size:** 2591 LOC across 3 Python files
- **Tests:** ❌ None
- **Critical bugs:** ⚠️ 2 (parser regex mismatch)

---

## Generated Documentation

| Document | Description |
|---|---|
| [Project Overview](./project-overview.md) | Executive summary, stack, capabilities, health |
| [Architecture](./architecture.md) | **← Start here.** System design, all subsystems, issues, roadmap |
| [Data Models](./data-models.md) | All 12 SQLite tables, relationships, schema evolution |
| [API Contracts](./api-contracts.md) | All 22 CLI commands + 19 NL intents with examples |
| [Source Tree Analysis](./source-tree-analysis.md) | File structure, monolith map by line numbers, proposed split |
| [Technology Stack](./technology-stack.md) | Stack decisions, known tech debt |
| [Development Guide](./development-guide.md) | Setup, test patterns, known issues, fix recipes |
| [Project Scan Report](./project-scan-report.json) | Raw JSON scan data from automated project analysis |

---

## Existing Skill Documentation

| Document | Description |
|---|---|
| [SKILL.md](../workspace/skills/gym-coach/SKILL.md) | OpenClaw agent interface spec, trigger patterns, CLI reference |
| [coach-prompt.md](../workspace/skills/gym-coach/coach-prompt.md) | AI coaching behaviour, session protocol, response templates |
| [program.example.json](../workspace/skills/gym-coach/program.example.json) | Sample training program format |

---

## Getting Started

```bash
cd /home/ubuntu/.openclaw/workspace/skills/gym-coach
python3 gym_coach.py init
python3 gym_coach.py program import program.example.json
python3 gym_coach.py next
python3 router.py --text "начать тренировку push" --json
```

---

## Priority Issues — Fix These First

| # | Severity | File | Line | Issue |
|---|---|---|---|---|
| C1 | 🔴 Critical | `gym_coach.py` | 796 | `parse_line` RE_RPE missing `rpe N` pattern |
| C2 | 🔴 Critical | `gym_coach.py` | 798 | `parse_line` RE_WXRX missing Cyrillic `х` |
| C3 | 🔴 Critical | — | — | Zero test coverage |
| M1 | 🟡 Medium | `gym_coach.py` | 884 | `cmd_log` inserts `status='active'` instead of `'completed'` |
| M2 | 🟡 Medium | `router.py` | 298 | `subprocess.TimeoutExpired` not caught |

Full issues list: [Architecture → Issues Matrix](./architecture.md#identified-issues--severity-matrix)
Fix recipes: [Development Guide → Known Issues](./development-guide.md#known-issues-summary)

---

## Brownfield PRD — Where to Look

| Task | Read first |
|---|---|
| Adding new command | [API Contracts](./api-contracts.md) + [Source Tree — Adding Command](./development-guide.md#adding-a-new-command) |
| Fixing parser bugs | [Architecture — Parsing Engine](./architecture.md#2-parsing-engine-parse_line-in-gym_coachpy801-869) + [Dev Guide — Extending Parser](./development-guide.md#extending-the-parser-parse_line) |
| Splitting the monolith | [Source Tree — Proposed Split](./source-tree-analysis.md#proposed-module-split-for-future-refactoring) |
| Writing tests | [Dev Guide — Testing](./development-guide.md#testing) |
| Schema change | [Data Models](./data-models.md) + [Schema Evolution Notes](./data-models.md#schema-evolution-notes) |
| Adaptation logic | [Architecture — Adaptation Engine](./architecture.md#4-adaptation-engine-cmd_adapt_recommend-lines-11161310) |
| Volume analysis | [Architecture — Volume Analysis](./architecture.md#5-volume-analysis-cmd_program_analyze-lines-15511852) |

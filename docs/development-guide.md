# Development Guide — gym-coach skill

**Generated:** 2026-03-01

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Uses `dt.UTC` (3.11+), `match/case` not used |
| sqlite3 | bundled | stdlib, no install needed |
| pip dependencies | **none** | Zero external packages |

**Python 3.11+ recommended** — `dt.datetime.now(dt.UTC)` requires 3.11+. On 3.10 use `dt.datetime.utcnow().isoformat() + "Z"`.

---

## Initial Setup

```bash
# 1. Navigate to skill directory
cd /home/ubuntu/.openclaw/workspace/skills/gym-coach

# 2. Initialize DB schema + seed defaults
python3 gym_coach.py init

# 3. (Optional) Run onboarding to set user profile
python3 onboard.py

# 4. Import a training program
python3 gym_coach.py program import program.example.json

# 5. Verify
python3 gym_coach.py next
python3 gym_coach.py program show
```

---

## Common Development Commands

```bash
# Check next workout
python3 gym_coach.py next

# Full training dashboard
python3 gym_coach.py program analyze

# Start a session
python3 gym_coach.py workout start --day Push

# Log a set (structured mode - preferred)
python3 gym_coach.py workout set --structured --exercise "Bench Press" --weight 70 --reps 6 --rpe 8

# Log a set (text mode)
python3 gym_coach.py workout set --text "bench 70x6 @8"

# Finish session
python3 gym_coach.py workout done

# Adaptation recommendation
python3 gym_coach.py adapt recommend --exercise "Bench Press"

# Log readiness
python3 gym_coach.py readiness log --sleep-hours 7.5 --stress 3 --fatigue 4

# Test NL router
python3 router.py --text "начать тренировку push" --json
python3 router.py --text "жим 70x6 rpe 8" --json
python3 router.py --text "закончил" --dry-run --json
```

---

## Testing

**Currently: zero tests exist.**

Recommended test setup when writing tests:

```bash
# Install pytest (only dev dependency)
pip install pytest

# Run tests (once written)
pytest tests/ -v

# Run with temp DB (tests should use tmp path via monkeypatch or conftest fixture)
```

**Recommended `conftest.py` pattern:**
```python
import pytest, tempfile, os
from pathlib import Path

@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "test.sqlite"
    monkeypatch.setenv("GYM_COACH_DB", str(db))
    # or monkeypatch gym_coach.DB_PATH directly
    import gym_coach
    monkeypatch.setattr(gym_coach, "DB_PATH", str(db))
    return db
```

**Priority test areas (P0):**
1. `parse_line()` — canonical input formats
2. `route_text()` in router — intent detection coverage
3. `cmd_log()` — status should be `'completed'`
4. `validate_set_values()` / `validate_score()` — boundary values
5. `cmd_workout_start/set/done` — full session lifecycle

---

## DB Management

```bash
# Inspect DB directly
sqlite3 gym_coach.sqlite

# Useful queries
sqlite3 gym_coach.sqlite "SELECT * FROM workout_sessions ORDER BY id DESC LIMIT 5;"
sqlite3 gym_coach.sqlite "SELECT * FROM meta;"
sqlite3 gym_coach.sqlite "SELECT * FROM readiness_logs ORDER BY date DESC LIMIT 3;"
sqlite3 gym_coach.sqlite "SELECT exercise_name, COUNT(*) FROM exercise_sets GROUP BY exercise_name;"

# Reset active session (if stuck)
sqlite3 gym_coach.sqlite "DELETE FROM meta WHERE key='active_session_id';"

# Fix cmd_log status bug (one-time backfill)
sqlite3 gym_coach.sqlite "
  UPDATE workout_sessions
  SET status='completed', completed_at=created_at
  WHERE status='active'
    AND id NOT IN (SELECT CAST(value AS INTEGER) FROM meta WHERE key='active_session_id');
"
```

---

## Adding a New Command

1. **Add handler function** in `gym_coach.py`:
```python
def cmd_my_command(args: argparse.Namespace) -> None:
    conn = connect()
    ensure_schema(conn)
    # ... logic ...
    print("OK: ...")
```

2. **Register in `build_parser()`:**
```python
my_cmd = sub.add_parser("my-command")
my_cmd.add_argument("--foo", required=True)
```

3. **Add dispatch branch in `main()`:**
```python
elif args.cmd == "my-command":
    cmd_my_command(args)
```

4. **Add NL intent in `router.py`** (if NL-accessible):
```python
if has_any(low, ["ключевое слово", "keyword"]):
    return RouteResult("my_intent", ["my-command", "--foo", extracted_value])
```

5. **Update `SKILL.md`** — add to commands section.

---

## Extending the Parser (`parse_line`)

Current gaps to fix (see issues section):

```python
# Current (gym_coach.py:796) — ONLY supports @8 format:
RE_RPE = re.compile(r"@\s*(\d+(?:\.\d+)?)\b")

# Fix — support both @8 and "rpe 8":
RE_RPE = re.compile(r"(?:rpe\s+|@\s*)(\d+(?:\.\d+)?)\b", re.IGNORECASE)

# Current RE_WXRX (gym_coach.py:798) — missing Cyrillic х:
RE_WXRX = re.compile(r"(?P<w>\d+(?:\.\d+)?)\s*[x×]\s*(?P<r>\d+)\b")

# Fix — add Cyrillic х:
RE_WXRX = re.compile(r"(?P<w>\d+(?:\.\d+)?)\s*[xх×]\s*(?P<r>\d+)\b", re.IGNORECASE)
```

---

## Deployment / Integration with OpenClaw

The skill is invoked by the OpenClaw agent when trigger patterns match (see `SKILL.md`).

**Recommended agent workflow:**
1. Agent receives user message
2. Pattern match → calls `router.py --text "<message>" --json`
3. Router returns JSON with `intent`, `stdout`, `exit_code`
4. If `needs_clarification=true` → agent asks user one question
5. If `exit_code=0` → agent formats `stdout` as user-friendly reply
6. If `exit_code!=0` → agent reports error briefly

**Key paths hardcoded in router.py:**
```python
GYM_COACH_PATH = BASE_DIR / "gym_coach.py"  # relative to router.py location
```
No config file — paths are resolved relative to script location.

---

## Known Issues Summary

| # | Severity | Location | Description |
|---|---|---|---|
| 1 | 🔴 High | `gym_coach.py:796` | `parse_line` RE_RPE missing `rpe N` pattern |
| 2 | 🔴 High | `gym_coach.py:797-798` | `parse_line` RE_WxR missing Cyrillic `х` |
| 3 | 🔴 High | — | Zero test coverage |
| 4 | 🟡 Med | `gym_coach.py:884` | `cmd_log` inserts `status='active'` (should be `'completed'`) |
| 5 | 🟡 Med | `router.py:298` | `subprocess.TimeoutExpired` not caught |
| 6 | 🟡 Med | `gym_coach.py:252-258` | Schema migrations duplicated in `onboard.py` |
| 7 | 🟡 Med | `gym_coach.py:935` | `--limit` in `history` not validated |
| 8 | 🟢 Low | `gym_coach.py:16-76` | `DEFAULT_EXERCISE_MUSCLES` exists in-memory AND in DB (duplication) |
| 9 | 🟢 Low | `gym_coach.py` | `MUSCLE_VOLUME_LANDMARKS` hardcoded, not user-configurable |
| 10 | 🟢 Low | — | No CI/CD pipeline |

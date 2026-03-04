---
title: 'Fix gym-coach bugs: parser, status, timeout + tests'
slug: 'gym-coach-bug-fixes'
created: '2026-03-01'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack:
  - Python 3.11+
  - sqlite3 (stdlib)
  - subprocess (stdlib)
  - pytest (dev only)
files_to_modify:
  - workspace/skills/gym-coach/gym_coach.py
  - workspace/skills/gym-coach/router.py
files_to_create:
  - workspace/skills/gym-coach/tests/__init__.py
  - workspace/skills/gym-coach/tests/conftest.py
  - workspace/skills/gym-coach/tests/test_parse_line.py
  - workspace/skills/gym-coach/tests/test_router.py
  - workspace/skills/gym-coach/tests/test_cmd_log.py
code_patterns:
  - Module-level RE constants above parse_line() at gym_coach.py:796-798
  - run_gym_coach() at router.py:296-298 returns CompletedProcess directly
  - cmd_log INSERT at gym_coach.py:884-888 — status defaults to 'active' via schema DEFAULT
  - workout_sessions schema: status TEXT DEFAULT 'active', completed_at TEXT (nullable)
  - Existing cmd_workout_done at gym_coach.py:677 sets status='completed' AND completed_at — use same pattern
test_patterns:
  - pytest monkeypatch on gym_coach.DB_PATH (module-level str, gym_coach.py:13)
  - '@pytest.mark.parametrize for parse_line input matrix'
  - Direct import of gym_coach and router modules (no subprocess in tests)
---

# Tech-Spec: Fix gym-coach bugs: parser, status, timeout + tests

**Created:** 2026-03-01

## Overview

### Problem Statement

The gym-coach skill has 5 confirmed bugs blocking correct usage:
1. `parse_line()` silently ignores `rpe N` notation (only `@N` works)
2. `parse_line()` fails to parse sets with Cyrillic `х` separator (e.g. `жим 70х6`)
3. `cmd_log` inserts workout sessions with `status='active'` instead of `'completed'`
4. `run_gym_coach()` crashes with unhandled `TimeoutExpired` if gym_coach.py takes >30s
5. Zero automated tests — regressions are invisible

### Solution

Apply 4 targeted one-line / two-line code fixes from `docs/development-guide.md`, and create a pytest suite covering parse_line, route_text, and cmd_log status.

### Scope

**In Scope:**
- C1: Fix `RE_RPE` at `gym_coach.py:796` — support `rpe N` in addition to `@N`
- C2: Fix `RE_WXRXS` at `gym_coach.py:797` and `RE_WXRX` at `gym_coach.py:798` — add Cyrillic `х` to character class
- M1: Fix `cmd_log` at `gym_coach.py:884-888` — INSERT with explicit `status='completed'` and `completed_at=created_at`
- M2: Catch `subprocess.TimeoutExpired` in `router.py:296-298` — return error `CompletedProcess`
- C3: Create `tests/` directory with conftest, test_parse_line, test_router, test_cmd_log

**Out of Scope:**
- Issues 6–10 from Known Issues (schema duplication, --limit validation, hardcoded landmarks, CI/CD)
- Adding `на`/`по` separators to `parse_line` (router handles it; parse_line gets Cyrillic `х` only)
- DB backfill of existing sessions with wrong status (see dev guide for one-time SQL if needed)

---

## Context for Development

### Codebase Patterns

- **No external runtime dependencies** — stdlib only (re, sqlite3, subprocess, argparse). Pytest is the sole dev dependency.
- **RE constants** are module-level, defined at `gym_coach.py:796-798`, used only in `parse_line()`. Fix is in-place replacement — group names and group numbering must be preserved.
- **router.py RE patterns** at lines 46-49 are more complete (Cyrillic `х`, `rpe|@` syntax) — they are the reference.
- **`run_gym_coach()`** at `router.py:296-298` is a 2-line thin wrapper. Callers in `main()` inspect `.returncode`, `.stdout`, `.stderr`. A fake `CompletedProcess` with `returncode=1` is safe.
- **`DB_PATH`** is a module-level string at `gym_coach.py:13`. Tests must monkeypatch `gym_coach.DB_PATH` (not env var) per the dev guide pattern.
- **`cmd_log` INSERT** at `gym_coach.py:886` omits `status` → gets schema DEFAULT `'active'`. Schema at line 113: `status TEXT NOT NULL DEFAULT 'active'`. Fix must add both `status='completed'` and `completed_at=created_at` (matching `cmd_workout_done` at line 677).
- **`ensure_schema`** at line ~220 must be called before any DB operation in tests that use `cmd_log`.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `workspace/skills/gym-coach/gym_coach.py` | `DB_PATH:13`, schema:107-116, RE constants:796-798, `parse_line():801-869`, `cmd_log():872-904` |
| `workspace/skills/gym-coach/router.py` | `run_gym_coach():296-298`, `route_text():115-293`, reference RE:46-49 |
| `docs/development-guide.md` | Exact fix recipes for C1, C2; conftest.py pattern; test priority list |

### Technical Decisions

- **M2 error return**: `subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="gym_coach timed out after 30s")` — safe; callers only inspect attributes, never re-raise.
- **C2 scope**: Fix both `RE_WXRXS:797` AND `RE_WXRX:798` — both use `[x×]`. Dev guide only shows RE_WXRX but RE_WXRXS has the same bug.
- **M1 completeness**: Set `status='completed'` AND `completed_at=created_at` to match `cmd_workout_done` pattern. `created_at` is already computed on line 882 before the INSERT.
- **Tests location**: `workspace/skills/gym-coach/tests/` — co-located with skill files, standard pytest discovery.

---

## Implementation Plan

### Tasks

- [x] Task 1: Fix RE_RPE — support `rpe N` notation (C1)
  - File: `workspace/skills/gym-coach/gym_coach.py`
  - Line: 796
  - Action: Replace the line:
    ```python
    RE_RPE = re.compile(r"@\s*(\d+(?:\.\d+)?)\b")
    ```
    with:
    ```python
    RE_RPE = re.compile(r"(?:rpe\s+|@\s*)(\d+(?:\.\d+)?)\b", re.IGNORECASE)
    ```
  - Notes: Capturing group is group(1) — preserved. `re.IGNORECASE` handles `RPE`, `Rpe`, etc.

- [x] Task 2: Fix RE_WXRXS — add Cyrillic х (C2, part 1)
  - File: `workspace/skills/gym-coach/gym_coach.py`
  - Line: 797
  - Action: Replace the line:
    ```python
    RE_WXRXS = re.compile(r"(?P<w>\d+(?:\.\d+)?)\s*[x×]\s*(?P<r>\d+)\s*[x×]\s*(?P<s>\d+)\b")
    ```
    with:
    ```python
    RE_WXRXS = re.compile(r"(?P<w>\d+(?:\.\d+)?)\s*[xх×]\s*(?P<r>\d+)\s*[xх×]\s*(?P<s>\d+)\b", re.IGNORECASE)
    ```
  - Notes: Named groups `w`, `r`, `s` are preserved. Cyrillic `х` is U+0445.

- [x] Task 3: Fix RE_WXRX — add Cyrillic х (C2, part 2)
  - File: `workspace/skills/gym-coach/gym_coach.py`
  - Line: 798
  - Action: Replace the line:
    ```python
    RE_WXRX = re.compile(r"(?P<w>\d+(?:\.\d+)?)\s*[x×]\s*(?P<r>\d+)\b")
    ```
    with:
    ```python
    RE_WXRX = re.compile(r"(?P<w>\d+(?:\.\d+)?)\s*[xх×]\s*(?P<r>\d+)\b", re.IGNORECASE)
    ```
  - Notes: Named groups `w`, `r` are preserved. Same fix as Task 2.

- [x] Task 4: Fix cmd_log INSERT — set status='completed' (M1)
  - File: `workspace/skills/gym-coach/gym_coach.py`
  - Lines: 885-888
  - Action: Replace:
    ```python
        cur = conn.execute(
            "INSERT INTO workout_sessions(date, day_name, raw_text, created_at) VALUES(?, ?, ?, ?)",
            (date, day, text, created_at),
        )
    ```
    with:
    ```python
        cur = conn.execute(
            "INSERT INTO workout_sessions(date, day_name, raw_text, created_at, status, completed_at)"
            " VALUES(?, ?, ?, ?, 'completed', ?)",
            (date, day, text, created_at, created_at),
        )
    ```
  - Notes: `created_at` is already defined at line 882. `completed_at=created_at` matches the `cmd_workout_done` pattern at line 677.

- [x] Task 5: Catch TimeoutExpired in run_gym_coach (M2)
  - File: `workspace/skills/gym-coach/router.py`
  - Lines: 296-298
  - Action: Replace:
    ```python
    def run_gym_coach(argv: List[str]) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(GYM_COACH_PATH), *argv]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    ```
    with:
    ```python
    def run_gym_coach(argv: List[str]) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(GYM_COACH_PATH), *argv]
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="gym_coach timed out after 30s")
    ```
  - Notes: No imports needed — `subprocess` is already imported.

- [x] Task 6: Create tests directory and conftest (C3, infrastructure)
  - Files to create:
    - `workspace/skills/gym-coach/tests/__init__.py` — empty file
    - `workspace/skills/gym-coach/tests/conftest.py` — content:
      ```python
      import pytest
      import gym_coach


      @pytest.fixture
      def tmp_db(monkeypatch, tmp_path):
          db = tmp_path / "test.sqlite"
          monkeypatch.setattr(gym_coach, "DB_PATH", str(db))
          return db
      ```
  - Notes: `monkeypatch.setattr` on the module attribute, not env var. Must import `gym_coach` (not `from gym_coach import DB_PATH`) so the monkeypatch affects the module-level reference.

- [x] Task 7: Write test_parse_line.py (C3)
  - File: `workspace/skills/gym-coach/tests/test_parse_line.py`
  - Content:
    ```python
    import pytest
    from gym_coach import parse_line


    @pytest.mark.parametrize("line,expected_rpe", [
        ("bench press 70x6 @8", 8.0),
        ("bench press 70x6 rpe 8", 8.0),
        ("bench press 70x6 RPE 8.5", 8.5),
        ("bench press 70x6", None),
    ])
    def test_rpe_parsing(line, expected_rpe):
        _, _, rpe, _ = parse_line(line)
        assert rpe == expected_rpe


    @pytest.mark.parametrize("line,expected_w,expected_r", [
        ("жим 70x6", 70.0, 6),        # Latin x
        ("жим 70х6", 70.0, 6),        # Cyrillic х
        ("жим 70×6", 70.0, 6),        # Unicode multiplication sign
        ("bench 82.5x4", 82.5, 4),
    ])
    def test_weight_reps_parsing(line, expected_w, expected_r):
        _, sets, _, _ = parse_line(line)
        assert len(sets) == 1
        w, r = sets[0]
        assert w == expected_w
        assert r == expected_r


    def test_wxrxs_format():
        _, sets, _, _ = parse_line("squat 100x5x3")
        assert len(sets) == 3
        assert all(w == 100.0 and r == 5 for w, r in sets)


    def test_wxrxs_cyrillic():
        _, sets, _, _ = parse_line("присед 100х5х3")
        assert len(sets) == 3


    def test_exercise_name_only():
        name, sets, rpe, _ = parse_line("pull-up")
        assert name == "pull-up"
        assert sets == []
        assert rpe is None


    def test_empty_line():
        name, sets, rpe, notes = parse_line("")
        assert name == ""
        assert sets == []
    ```

- [x] Task 8: Write test_router.py (C3)
  - File: `workspace/skills/gym-coach/tests/test_router.py`
  - Content:
    ```python
    import subprocess
    import pytest
    from router import route_text, run_gym_coach


    def test_route_workout_start():
        result = route_text("начать тренировку push")
        assert result.intent == "workout_start"
        assert not result.needs_clarification
        assert "Push" in result.argv


    def test_route_workout_set():
        result = route_text("жим 70x6 rpe 8")
        assert result.intent == "workout_set"
        assert not result.needs_clarification
        assert "8" in result.argv


    def test_route_workout_set_cyrillic_x():
        result = route_text("жим 70х6")
        assert result.intent == "workout_set"
        assert not result.needs_clarification


    def test_route_workout_done():
        result = route_text("закончил")
        assert result.intent == "workout_done"
        assert not result.needs_clarification


    def test_route_unknown():
        result = route_text("абракадабра xyz")
        assert result.needs_clarification


    def test_run_gym_coach_timeout(monkeypatch):
        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=30)
        monkeypatch.setattr(subprocess, "run", fake_run)
        result = run_gym_coach(["--help"])
        assert result.returncode == 1
        assert "timed out" in result.stderr
    ```

- [x] Task 9: Write test_cmd_log.py (C3)
  - File: `workspace/skills/gym-coach/tests/test_cmd_log.py`
  - Content:
    ```python
    import argparse
    import sqlite3
    import pytest
    import gym_coach
    from gym_coach import cmd_log, connect, ensure_schema


    def test_cmd_log_status_is_completed(tmp_db):
        # Arrange: initialise schema
        conn = connect()
        ensure_schema(conn)
        conn.close()

        # Act: log a session
        args = argparse.Namespace(
            date="today",
            day="Push",
            text="bench press 70x6 @8",
        )
        cmd_log(args)

        # Assert: status = 'completed'
        conn = connect()
        row = conn.execute(
            "SELECT status, completed_at FROM workout_sessions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert row["status"] == "completed"
        assert row["completed_at"] is not None
    ```
  - Notes: `args.date="today"` relies on `parse_iso_date` which accepts "today" — verify this is supported, or use an ISO date string like `"2026-03-01"` to be safe. Use `"2026-03-01"` if uncertain.

---

### Acceptance Criteria

- [x] AC 1: Given `parse_line("bench press 70x6 rpe 8")` is called, when executed, then `rpe == 8.0` is returned.
- [x] AC 2: Given `parse_line("жим 70х6")` (Cyrillic х, U+0445) is called, when executed, then `sets == [(70.0, 6)]` is returned.
- [x] AC 3: Given `parse_line("squat 100х5х3")` (Cyrillic х in WxRxS format) is called, when executed, then `len(sets) == 3` and each set is `(100.0, 5)`.
- [x] AC 4: Given `cmd_log` is called with any valid text, when the session row is read from DB, then `status == 'completed'` and `completed_at IS NOT NULL`.
- [x] AC 5: Given `subprocess.run` raises `TimeoutExpired`, when `run_gym_coach` is called, then a `CompletedProcess` with `returncode=1` and `"timed out"` in `stderr` is returned — no exception propagates.
- [x] AC 6: Given `pytest tests/ -v` is run from `workspace/skills/gym-coach/`, when all 4 code fixes are applied, then all tests pass with zero failures.

---

## Additional Context

### Dependencies

- `pytest` — dev only, not in requirements: `pip install pytest`
- No new runtime imports needed (all fixes use already-imported modules)
- `subprocess` already imported in `router.py`; `re` already imported in `gym_coach.py`

### Testing Strategy

- **Unit tests** (`test_parse_line.py`): pure function, no DB, no subprocess — fast and hermetic
- **Unit tests** (`test_router.py`): `route_text` is pure; `run_gym_coach` timeout tested via monkeypatch of `subprocess.run`
- **Integration test** (`test_cmd_log.py`): uses `tmp_db` fixture to isolate DB; calls `cmd_log` via real function import
- **Manual smoke test** after applying fixes:
  ```bash
  cd workspace/skills/gym-coach
  python3 gym_coach.py init
  python3 router.py --text "жим 70х6 rpe 8" --json
  # expect: intent=workout_set, no errors
  pytest tests/ -v
  # expect: all green
  ```

### Notes

- **`parse_iso_date("today")`**: verify this helper accepts `"today"` before using it in `test_cmd_log.py`. If not, use `"2026-03-01"` (ISO string). Check `gym_coach.py` around line 870-876.
- **RE_WXRXS and RE_WXRX are used inside `parse_line` AND in the multi-set list parsing block** (lines 852-866 also call `RE_WXRX.search`). The fix at line 798 covers all three usages — nothing else to change.
- **`@pytest.fixture` scope**: `tmp_db` is function-scoped (default) — each test gets a fresh DB. Do not widen to session scope.
- **Known Issue 6** (schema duplication in `onboard.py`) is out of scope but worth noting: after this fix, `ensure_schema` remains the single source of truth for the schema used in tests.

## Review Notes

- Adversarial review completed
- Findings: 12 total, 8 fixed, 4 skipped (noise)
- Resolution approach: auto-fix
- Post-fix test run: 20 passed, 0 failed

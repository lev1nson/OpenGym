# API Contracts — gym-coach CLI

**Generated:** 2026-03-01
**Entry points:** `gym_coach.py`, `router.py`, `onboard.py`

---

## gym_coach.py — CLI Commands

All commands: `python3 gym_coach.py <command> [subcommand] [args]`

Exit codes: `0` = success, non-zero = error (via `SystemExit`).

---

### `init`
Initialize DB schema and seed default data.

```bash
python3 gym_coach.py init
```

**Output:** `OK: initialized DB at <path>`
**Side effects:** Creates all tables, seeds muscle groups and exercise-to-muscle mappings, creates user_profile singleton.
**Idempotent:** Yes.

---

### `program import <path>`
Import training program from JSON file. Replaces existing program.

```bash
python3 gym_coach.py program import program.example.json
```

**Input format:**
```json
{
  "days": [
    {
      "name": "Push",
      "exercises": [
        {"name": "Bench Press", "targetSets": 3, "targetReps": "8-10"}
      ]
    }
  ],
  "exerciseAliases": {
    "жим": "Bench Press"
  }
}
```

**Output:** `OK: program imported`
**Side effects:** Deletes all existing program_days, program_exercises, exercise_aliases; inserts new.

---

### `program show`
Display current program.

```bash
python3 gym_coach.py program show
```

**Output:** Formatted text — days and exercises with target sets/reps.

---

### `program analyze [--weeks N] [--json]`
Full training dashboard: volumes, trends, fatigue, recommendations.

```bash
python3 gym_coach.py program analyze
python3 gym_coach.py program analyze --weeks 8 --json
```

**Output (JSON):**
```json
{
  "analysis_date": "2026-03-01",
  "period_weeks": 4,
  "fatigue_state": {
    "accumulated_fatigue_score": 5.2,
    "accumulated_pain_score": 2.1,
    "sleep_avg_7d": 7.5,
    "deload_recommended": false
  },
  "training_block": {
    "weeks_since_deload": 3,
    "total_sessions_this_period": 12,
    "deload_urgency": "low"
  },
  "muscle_volumes_this_week": {
    "chest": {"sets": 9.0, "mev": 8, "mav": 16, "mrv": 22, "status": "in_range", "pct_of_mav": 56}
  },
  "push_pull_ratio": 0.83,
  "exercise_analysis": {
    "Bench Press": {
      "estimated_1rm": 95.0, "plateau_status": "progressing",
      "readiness_for_progression": true
    }
  },
  "computed_recommendations": [
    {"type": "progress", "exercise": "Bench Press", "detail": "+2.5% (at top of 8-10 range, RPE 7.5)"}
  ]
}
```

---

### `next`
Show next planned workout day based on program sequence.

```bash
python3 gym_coach.py next
```

**Logic:** Finds last completed non-extra session → advances to next day in sequence (circular).
**Output:** `Next workout: Push (after last logged: Pull on 2026-02-28)` + exercise list.

---

### `workout start`
Start a new workout session.

```bash
python3 gym_coach.py workout start [--date YYYY-MM-DD] [--day Push] [--notes "..."] [--force] [--extra]
```

| Arg | Default | Notes |
|---|---|---|
| `--date` | today | Session date |
| `--day` | None | Program day name (e.g. Push, Pull, Legs) |
| `--notes` | None | Optional starting notes |
| `--force` | False | Abort existing active session and start new |
| `--extra` | False | Mark as extra/unplanned (excluded from `next` sequence) |

**Output:** `OK: workout started — session 42 on 2026-03-01 (Push)`
**Error:** If session already active and no `--force`: prints warning, returns.

---

### `workout status`
Show current active session status.

```bash
python3 gym_coach.py workout status
```

**Output:** Session info + sets per exercise.

---

### `workout set`
Log a set in the active session. Two modes:

**Mode A — free-form text:**
```bash
python3 gym_coach.py workout set --text "bench 70x6 @8"
```
Parsed by `parse_line()`. Supports: `WxR`, `WxRxS`, `W,R list`.
**⚠️ Warning:** Only `@8` RPE format supported in this mode — NOT `rpe 8`.

**Mode B — structured (recommended for agent use):**
```bash
python3 gym_coach.py workout set --structured \
  --exercise "Bench Press" --weight 70 --reps 6 [--rpe 8] [--notes "..."]
```

| Arg | Required | Notes |
|---|---|---|
| `--exercise` | No | Defaults to last exercise |
| `--weight` | Yes | kg, float |
| `--reps` | Yes | int |
| `--rpe` | No | float 1–10 |
| `--notes` | No | free text |

**Validation:** weight: (0, 1000], reps: [1, 100], rpe: [1, 10].
**Output:** `OK: saved Bench Press — 70.0x6`
**Error:** No active session → exit; session paused → exit.

---

### `workout done`
Complete the active session.

```bash
python3 gym_coach.py workout done
```

**Output:** Session summary + sets per exercise + rest time defaults.
**Side effects:** Sets `status='completed'`, clears meta keys.

---

### `workout pause` / `workout resume`
Pause/resume the active session (blocks `workout set` while paused).

```bash
python3 gym_coach.py workout pause
python3 gym_coach.py workout resume
```

---

### `workout abort`
Abort the active session.

```bash
python3 gym_coach.py workout abort
```

**Side effects:** Sets `status='aborted'`, clears meta keys.

---

### `workout undo`
Remove the last logged set in the active session.

```bash
python3 gym_coach.py workout undo
```

**Side effects:** Deletes last `exercise_sets` row, rebuilds `raw_text`, updates `last_exercise`.

---

### `workout skip`
Record a skipped session (does NOT advance program sequence).

```bash
python3 gym_coach.py workout skip [--date YYYY-MM-DD] [--day Push] [--reason "business trip"]
```

---

### `workout swap`
Substitute an exercise during a session.

```bash
python3 gym_coach.py workout swap --to "Dumbbell Press" [--from "Bench Press"] [--reason "machine broken"]
```

**Side effects:** Inserts into `session_exercise_substitutions`, updates `last_exercise`.

---

### `workout suggest`
Find muscle-similar exercise alternatives.

```bash
python3 gym_coach.py workout suggest --exercise "Bench Press" [--exclude-equipment barbell] [--json]
```

**Algorithm:** Cosine-similarity-like dot product of muscle activation vectors.
**Output:** Top 5 alternatives with similarity score.

---

### `profile show` / `profile set`
Read/write user training preferences.

```bash
python3 gym_coach.py profile show
python3 gym_coach.py profile set --goal "hypertrophy" --periodization "linear" \
  --rest-compound 180 --rest-isolation 90
```

---

### `muscle map`
Map an exercise to a muscle group with activation weight.

```bash
python3 gym_coach.py muscle map --exercise "Hack Squat" --muscle quads --weight 0.9
```

---

### `muscle report`
Weekly volume (sets) per muscle group for current week.

```bash
python3 gym_coach.py muscle report
```

---

### `log`
Import a historical workout session from free-form text.

```bash
python3 gym_coach.py log --text "Bench Press 70x6x3\nSquat 80x8x4" --date 2026-02-28 --day Push
```

**⚠️ Bug:** Inserts session with `status='active'` (default) instead of `'completed'`. Will pollute `cmd_next` logic until fixed.

---

### `last`
Show last logged session summary.

```bash
python3 gym_coach.py last
```

---

### `history`
Show recent sets for a specific exercise.

```bash
python3 gym_coach.py history --exercise "Bench Press" [--limit 10]
```

**⚠️ Issue:** `--limit` not validated — negative values cause unexpected behaviour.

---

### `readiness log`
Log daily recovery metrics.

```bash
python3 gym_coach.py readiness log \
  --sleep-hours 7.5 --stress 4 --fatigue 3 --soreness 2 --pain 1 --mood 8
```

All fields optional. At least one required.
**Validation:** sleep_hours: [0, 24]; stress/fatigue/soreness/pain/mood: [1, 10].

---

### `readiness last`
Show recent readiness entries.

```bash
python3 gym_coach.py readiness last [--limit 5]
```

---

### `adapt recommend`
Generate load adaptation recommendation for an exercise.

```bash
python3 gym_coach.py adapt recommend [--exercise "Bench Press"]
```

**Output (JSON):**
```json
{
  "exercise": "Bench Press",
  "decision": "progress",
  "load_adjust_pct": 5.0,
  "suggested_next_weight": 72.5,
  "reason_codes": ["at_top_of_rep_range", "rpe_below_8"],
  "computed_data": {
    "plateau_score": 0,
    "estimated_1rm": 90.0,
    "accumulated_fatigue": 3.2,
    "deload_recommended": false
  }
}
```

**Decision logic (deterministic table):**

| Priority | Condition | Decision | Adjust |
|---|---|---|---|
| 1 | `pain >= 7` | deload | -10% |
| 2 | `fatigue >= 8` | deload | -7.5% |
| 3 | `sleep_avg <= 5h` | deload | -5% |
| 4 | `plateau_score >= 2` | plateau | 0% |
| 5 | at top of rep range AND rpe <= 8 | progress | +5% linear / +2.5% other |
| 6 | reps up AND rpe down | progress | +2.5% |
| 7 | reps down AND rpe up | deload | -5% |
| 8 | `weeks_since_deload >= 8` | deload | -5% |
| default | — | keep | 0% |

**Side effects:** Persists decision to `adaptation_decisions` table.

---

## router.py — NL Router

```bash
python3 router.py --text "<natural language>" [--dry-run] [--json]
```

### Detected Intents

| Intent | Example trigger phrases | Dispatches to |
|---|---|---|
| `workout_status` | "статус", "что сейчас" | `workout status` |
| `workout_pause` | "пауза", "перерыв" | `workout pause` |
| `workout_resume` | "продолж", "возобнов" | `workout resume` |
| `workout_undo` | "undo", "откат" | `workout undo` |
| `workout_abort` | "прервать", "abort" | `workout abort` |
| `workout_skip` | "пропускаю", "rest day" | `workout skip` |
| `workout_done` | "закончил", "done", "готово" | `workout done` |
| `next` | "следующ", "что завтра" | `next` |
| `program_generate` | "составь программу" | LLM signal (no CLI call) |
| `program_analyze` | "анализ программы" | `program analyze --json` |
| `adapt_recommend` | "адапт", "нагрузк" | `adapt recommend` |
| `readiness_log` | "сон", "стресс", "усталость" | `readiness log --sleep-hours ...` |
| `readiness_last` | "послед", "покажи готовность" | `readiness last` |
| `exercise_swap_suggest` | "замени" + known exercise | `workout suggest --exercise X` |
| `exercise_swap` | "замени на X" | `workout swap --to X` |
| `workout_start` | "начать тренировку", "погнали" | `workout start [--day X]` |
| `workout_extra` | "внеплановая", "доп тренировка" | `workout start --extra` |
| `workout_set` | "жим 70x6", "70 на 8 rpe 8" | `workout set --structured ...` |
| `needs_clarification` | ambiguous input | Returns `needs_clarification: true` |
| `unknown` | unrecognised | Returns `needs_clarification: true` |

### JSON Response Format

**Success (with CLI execution):**
```json
{
  "intent": "workout_set",
  "needs_clarification": false,
  "argv": ["workout", "set", "--structured", "--weight", "70", "--reps", "6"],
  "exit_code": 0,
  "stdout": "OK: saved Bench Press — 70.0x6",
  "stderr": ""
}
```

**Needs clarification:**
```json
{
  "intent": "set_ambiguous",
  "needs_clarification": true,
  "clarification": "Не распознал вес/повторы. Пример: 'жим 70x6' или 'жим 70 на 6 rpe 8'."
}
```

**⚠️ Issue:** `subprocess.TimeoutExpired` not caught in `run_gym_coach()` — unhandled exception propagates to caller.

---

## onboard.py — User Onboarding CLI

```bash
python3 onboard.py                        # interactive mode
python3 onboard.py --goal "hypertrophy" --days-per-week 4  # non-interactive
```

| Arg | Notes |
|---|---|
| `--goal` | e.g. `"strength+hypertrophy"` |
| `--priority` | e.g. `"aesthetics+strength"` |
| `--periodization` | e.g. `"alt_week_heavy_light"` |
| `--days-per-week` | int |
| `--session-min` | int, minutes |
| `--equipment` | comma-separated string |
| `--injuries` | text |
| `--experience` | text |

**⚠️ Coupling:** `onboard.py` does `from gym_coach import SCHEMA_SQL` — tight import coupling to monolith.

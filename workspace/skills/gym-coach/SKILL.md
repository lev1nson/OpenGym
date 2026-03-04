---
name: gym-coach
description: "Gym coach + workout logger for Max. Stores program + workout history in SQLite; answers: what's tomorrow's workout; logs sets/reps/weight from free-form messages."
triggers:
  - type: text_message
    pattern: "(тренировк|тренируюсь|качаюсь|жим|присед|тяга|подтягивания|workout|начать трен|старт трен|закончил|сет|подход|readiness|самочув|усталость|адаптация|deload|прогрессия|следующая трен|что сегодня|что завтра)"
  - type: text_message
    pattern: "(gym|fitness|training|exercise|bench|squat|deadlift|rpe|rir|reps|sets|weight)"
system_prompt: coach-prompt.md
---

# Gym Coach (Agent-ready)

This skill provides a local workout tracking + adaptation backend for Макс.

## Data store
- SQLite DB: `~/.openclaw/workspace/skills/gym-coach/gym_coach.sqlite`

## CLI
Run via:
```bash
python3 /home/ubuntu/.openclaw/workspace/skills/gym-coach/gym_coach.py <command> [args]
```

Natural-language router (for OpenClaw agent):
```bash
python3 /home/ubuntu/.openclaw/workspace/skills/gym-coach/router.py --text "начать тренировку push"
```

### Commands
- `init` — create DB schema
- `program import <program.json>` — import/replace program (ordered days + exercises)
- `program show` — show current program
- `next` — show next planned workout day (sequence-based)
- `workout start|status|set|pause|resume|undo|abort|done` — active workout session controls
- `profile show|set` — store coaching preferences (goal/periodization/rest)
- `muscle map|report` — map exercises to muscle groups + weekly volume report
- `readiness log|last` — store and inspect recovery/readiness indicators
- `adapt recommend --exercise <name>` — recommendation engine based on readiness + recent performance
- `log --date YYYY-MM-DD --day <DayName> --text "..."` — log performed workout (free-form text)
- `history --exercise "Bench Press" --limit 10` — show recent sets
- `last` — show last logged session summary

## Agent integration contract (OpenClaw)
Recommended flow for natural language:
1. Agent extracts intent (`start_workout`, `log_set`, `pause`, `finish`, `readiness_log`, `adapt_recommend`).
2. Agent resolves entities (exercise, weight, reps, rpe, notes, date).
3. Agent calls structured CLI whenever possible:
   - `workout set --structured --exercise ... --weight ... --reps ... [--rpe ...]`
   - `readiness log --sleep-hours ... --fatigue ... --pain ...`
4. If ambiguity is high, agent asks 1 short clarification question before tool call.
5. Agent returns human-friendly summary after command execution.

This keeps voice/text UX comfortable while preserving deterministic DB writes.

### Router usage examples
- Start workout:
  - `python3 .../router.py --text "начать тренировку push"`
- Log set:
  - `python3 .../router.py --text "жим 70x6 rpe 8"`
- Pause/resume:
  - `python3 .../router.py --text "пауза"`
  - `python3 .../router.py --text "продолжай"`
- Finish:
  - `python3 .../router.py --text "закончил тренировку"`
- Readiness log:
  - `python3 .../router.py --text "сон 7.5 стресс 4 усталость 5 боль 2 настроение 7"`
- Adapt recommendation:
  - `python3 .../router.py --text "дай адаптацию по жиму"`

For machine-readable integration:
- `python3 .../router.py --text "жим 70x6" --json`

For routing test without execution:
- `python3 .../router.py --text "жим 70x6" --dry-run`

## Logging format (accepted patterns)
Within `--text`, each line is treated as an exercise entry.
Supported patterns:
- `bench press 60x8x3` (weight x reps x sets)
- `squat 80x5, 80x5, 80x5` (list of sets)
- optional: `@8` or `rpe 8` for RPE (e.g., `deadlift 120x5x3 @8`)
- optional: `rir 2` or `2 rir` for Reps In Reserve — automatically converted to RPE (RPE = 10 - RIR)

Anything unparsed is still saved as raw text for the session.

## System prompt
Agent coaching behavior is guided by `coach-prompt.md` in this directory. Read it for tone, session protocol, adaptation logic, and response templates.

## Notes
- Uses **sequence** logic for `next`: cycles through program days in order and picks day after last logged day.
- Session state now supports pause/resume/abort for interruption handling.
- Includes readiness memory and simple adaptation recommendations for load adjustments.

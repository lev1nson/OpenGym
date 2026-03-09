"""
Pre-workout Recap generator.

Implements FR15: pre-workout Recap of previous session.
Pure DB read — no LLM, no computation. Data is presented as-is
from the most recent completed WorkoutSession.

References:
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.6]
    [Source: _bmad-output/planning-artifacts/architecture.md#FR15: Recap]
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

_NO_HISTORY_MSG = "Первая тренировка — история пока пуста"


def generate_recap(db_session: "SASession") -> str:
    """Generate pre-workout Recap from the most recent completed session.

    Reads last WorkoutSession with status='completed', groups WorkoutSet
    records by exercise, and formats one line per exercise with all sets.

    Format per exercise:
        "Жим лёжа: 80.0кг × 8, 80.0кг × 7, 77.5кг × 8"
    For bodyweight exercises (weight_kg=0.0):
        "Подтягивания: × 12, × 10, × 11"

    Args:
        db_session: Active SQLAlchemy Session (read-only, no commit)

    Returns:
        Formatted recap string, or _NO_HISTORY_MSG if no completed sessions.
    """
    from gym_coach_brain.data.models import WorkoutSession, WorkoutSet, Exercise

    # Find the most recent completed session
    last_session = (
        db_session.query(WorkoutSession)
        .filter(WorkoutSession.status == "completed")
        .order_by(WorkoutSession.session_date.desc(), WorkoutSession.id.desc())
        .first()
    )

    if last_session is None:
        return _NO_HISTORY_MSG

    # Load all sets for this session ordered by exercise + set_number
    sets = (
        db_session.query(WorkoutSet)
        .filter(WorkoutSet.session_id == last_session.id)
        .order_by(WorkoutSet.exercise_id, WorkoutSet.set_number)
        .all()
    )

    if not sets:
        return _NO_HISTORY_MSG

    # Group sets by exercise, preserving order
    exercise_sets: dict[int, list] = defaultdict(list)

    for ws in sets:
        exercise_sets[ws.exercise_id].append(ws)

    exercise_ids = list(exercise_sets.keys())
    exercises = db_session.query(Exercise).filter(Exercise.id.in_(exercise_ids)).all()
    exercise_names = {ex.id: ex.name for ex in exercises}

    lines: list[str] = []
    for exercise_id, ex_sets in exercise_sets.items():
        name = exercise_names.get(exercise_id, f"exercise_{exercise_id}")
        set_strs: list[str] = []
        for ws in ex_sets:
            if ws.weight_kg == 0.0:
                set_strs.append(f"× {ws.reps}")
            else:
                weight_str = f"{int(ws.weight_kg)}" if ws.weight_kg.is_integer() else f"{ws.weight_kg}"
                set_strs.append(f"{weight_str}кг × {ws.reps}")
        lines.append(f"{name}: {', '.join(set_strs)}")

    return "\n".join(lines)

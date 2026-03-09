"""
Post-workout Summary generator.

Implements FR16: post-workout Summary with fatigue assessment and plan/actual comparison.
Deterministic — all data from DB and ScienceConfig, no LLM.

References:
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.6]
    [Source: _bmad-output/planning-artifacts/architecture.md#FR16: Summary]
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import WorkoutSession
    from sqlalchemy.orm import Session as SASession


def generate_summary(
    session: "WorkoutSession",
    db_session: "SASession",
    science: "ScienceConfig",
) -> str:
    """Generate post-workout Summary for a completed session.

    Computes:
    - Total sets performed
    - Average RPE and fatigue assessment (vs science.summary thresholds)
    - Plan vs actual exercise comparison (missed / extra exercises)

    Args:
        session: Completed WorkoutSession ORM object (status='completed')
        db_session: Active SQLAlchemy Session (read-only)
        science: ScienceConfig with summary.rpe_easy_threshold and rpe_fatigue_threshold

    Returns:
        Multi-line summary string for stdout → Telegram.
    """
    from gym_coach_brain.data.models import WorkoutSet, Exercise

    sets = (
        db_session.query(WorkoutSet)
        .filter(WorkoutSet.session_id == session.id)
        .order_by(WorkoutSet.exercise_id, WorkoutSet.set_number)
        .all()
    )

    total_sets = len(sets)

    # ── RPE trend ────────────────────────────────────────────────────────────
    rpe_values = [ws.rpe for ws in sets if ws.rpe is not None]
    avg_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None

    # Weight decline trend: check if last set weight < first set weight per exercise
    weight_declined = _detect_weight_decline(sets)

    fatigue_label = _assess_fatigue(avg_rpe, weight_declined, science)

    # ── Plan vs actual ───────────────────────────────────────────────────────
    planned_names = _load_planned_names(session)

    actual_exercise_ids = {ws.exercise_id for ws in sets}
    actual_names: set[str] = set()
    if actual_exercise_ids:
        exercises = db_session.query(Exercise).filter(Exercise.id.in_(actual_exercise_ids)).all()
        actual_names = {ex.name for ex in exercises}

    missed = planned_names - actual_names
    extra = actual_names - planned_names

    # ── Build output ─────────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append("📊 Итоги тренировки")
    lines.append(f"Выполнено подходов: {total_sets}")

    if avg_rpe is not None:
        lines.append(f"Средний RPE: {avg_rpe:.1f} — {fatigue_label}")
    else:
        lines.append(f"RPE: не зафиксирован — {fatigue_label}")

    for name in sorted(missed):
        lines.append(f"❌ Пропущено: {name}")
    for name in sorted(extra):
        lines.append(f"➕ Дополнительно: {name}")

    return "\n".join(lines)


def _assess_fatigue(
    avg_rpe: float | None,
    weight_declined: bool,
    science: "ScienceConfig",
) -> str:
    """Return fatigue label based on avg_rpe and weight trend."""
    if weight_declined:
        return "Видно что устал 😤"
    if avg_rpe is None:
        return "Нормальная нагрузка"
    if avg_rpe >= science.summary.rpe_fatigue_threshold:
        return "Видно что устал 😤"
    if avg_rpe < science.summary.rpe_easy_threshold:
        return "Объёмы хорошие 💪"
    return "Нормальная нагрузка"


def _detect_weight_decline(sets: list) -> bool:
    """Return True if majority of multi-set exercises had a weight decline."""
    from collections import defaultdict
    exercise_sets: dict[int, list] = defaultdict(list)
    for ws in sets:
        exercise_sets[ws.exercise_id].append(ws)

    declined_count = 0
    multi_set_count = 0
    for ex_sets in exercise_sets.values():
        sorted_sets = sorted(ex_sets, key=lambda s: s.set_number)
        if len(sorted_sets) >= 2:
            multi_set_count += 1
            first_w = sorted_sets[0].weight_kg
            last_w = sorted_sets[-1].weight_kg
            if last_w < first_w:
                declined_count += 1
                
    return declined_count > 0 and declined_count >= (multi_set_count / 2.0)


def _load_planned_names(session: "WorkoutSession") -> set[str]:
    """Parse planned exercise names, degrading safely on malformed JSON."""
    try:
        planned_raw = json.loads(session.planned_exercises or "[]")
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse planned_exercises for session {id}: {exc}",
            id=session.id,
            exc=exc,
        )
        return set()

    if not isinstance(planned_raw, list):
        return set()

    return {
        exercise_name
        for ex in planned_raw
        if isinstance(ex, dict)
        for exercise_name in [ex.get("exercise_name", "")]
        if exercise_name
    }

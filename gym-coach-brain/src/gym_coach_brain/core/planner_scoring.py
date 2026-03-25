"""
Deterministic scoring for slot-based planner candidate ranking.

Provides scoring components for exercise candidates per slot:
- availability_score
- slot_fit_score
- anchor_score
- fatigue_cost_score
- novelty_score
- equipment_preference_score
- secondary_coverage_score
- progression_continuity_score
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import Exercise, UserProfile
    from gym_coach_brain.core.planner_slots import Slot


EQUIPMENT_QUALITY_MULTIPLIER: dict[str, float] = {
    "barbell": 1.0,
    "dumbbell": 0.95,
    "machine": 0.90,
    "cable": 0.95,
    "bodyweight": 0.85,
    "resistance_band": 0.80,
    "pullup_bar": 0.90,
    "dips_bar": 0.90,
}


@dataclass
class CandidateScore:
    total_score: float
    availability_score: float
    slot_fit_score: float
    anchor_score: float
    fatigue_cost_score: float
    novelty_score: float
    equipment_preference_score: float
    secondary_coverage_score: float
    progression_continuity_score: float
    selection_source: str = "deterministic"


@dataclass
class ScoredCandidate:
    exercise: "Exercise"
    slot: "Slot"
    score: CandidateScore


def score_candidate(
    exercise: "Exercise",
    slot: "Slot",
    user_profile: "UserProfile",
    today_date: date,
    db_session: "SASession",
    science: "ScienceConfig",
    history_days_since_use: int | None = None,
    anchor_exercise_id: int | None = None,
) -> CandidateScore:
    availability_score = _compute_availability_score(exercise, user_profile)
    slot_fit_score = _compute_slot_fit_score(exercise, slot)
    anchor_score = _compute_anchor_score(exercise, slot, anchor_exercise_id)
    fatigue_cost_score = _compute_fatigue_cost_score(exercise, today_date, db_session, science)
    novelty_score = _compute_novelty_score(exercise, today_date, db_session, history_days_since_use)
    equipment_preference_score = _compute_equipment_preference_score(exercise, user_profile)
    secondary_coverage_score = _compute_secondary_coverage_score(exercise, slot, db_session)
    progression_continuity_score = _compute_progression_continuity_score(
        exercise, today_date, db_session
    )

    total_score = (
        availability_score * 1.0
        + slot_fit_score * 0.8
        + anchor_score * 0.7
        + fatigue_cost_score * 0.5
        + novelty_score * 0.4
        + equipment_preference_score * 0.3
        + secondary_coverage_score * 0.3
        + progression_continuity_score * 0.6
    )

    return CandidateScore(
        total_score=total_score,
        availability_score=availability_score,
        slot_fit_score=slot_fit_score,
        anchor_score=anchor_score,
        fatigue_cost_score=fatigue_cost_score,
        novelty_score=novelty_score,
        equipment_preference_score=equipment_preference_score,
        secondary_coverage_score=secondary_coverage_score,
        progression_continuity_score=progression_continuity_score,
    )


def _compute_availability_score(exercise: "Exercise", user_profile: "UserProfile") -> float:
    from gym_coach_brain.core.equipment_inventory import exercise_available_for_profile

    if exercise_available_for_profile(exercise, user_profile, allow_bodyweight_fallback=True):
        return 1.0
    return 0.0


def _compute_slot_fit_score(exercise: "Exercise", slot: "Slot") -> float:
    score = 0.0

    movement_pattern = exercise.movement_pattern.name if exercise.movement_pattern else ""
    if movement_pattern in slot.movement_preferences:
        score += 0.5

    primary_muscle = exercise.primary_muscle.name if exercise.primary_muscle else ""
    if primary_muscle in slot.target_muscles:
        score += 0.5

    return min(1.0, score)


def _compute_anchor_score(
    exercise: "Exercise",
    slot: "Slot",
    anchor_exercise_id: int | None,
) -> float:
    if anchor_exercise_id is None:
        return 0.5

    if slot.anchor_policy.value == "stable":
        return 1.0 if exercise.id == anchor_exercise_id else 0.0

    if slot.anchor_policy.value == "semi_stable":
        return 0.8 if exercise.id == anchor_exercise_id else 0.3

    return 0.3


def _compute_fatigue_cost_score(
    exercise: "Exercise",
    today_date: date,
    db_session: "SASession",
    science: "ScienceConfig",
) -> float:
    from gym_coach_brain.data.models import WorkoutSession, WorkoutSet

    last_trained = (
        db_session.query(WorkoutSession.session_date)
        .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
        .filter(
            WorkoutSession.status == "completed",
            WorkoutSet.exercise_id == exercise.id,
        )
        .order_by(WorkoutSession.session_date.desc())
        .first()
    )

    if last_trained is None:
        return 1.0

    last_date = date.fromisoformat(last_trained[0][:10])
    days_since = (today_date - last_date).days
    min_rest = science.planning.min_rest_days_per_muscle_group

    if days_since < min_rest:
        return 0.0

    return min(1.0, days_since / (min_rest * 2))


def _compute_novelty_score(
    exercise: "Exercise",
    today_date: date,
    db_session: "SASession",
    history_days_since_use: int | None,
) -> float:
    if history_days_since_use is not None:
        days_since = history_days_since_use
    else:
        from gym_coach_brain.data.models import WorkoutSession, WorkoutSet

        last_used = (
            db_session.query(WorkoutSession.session_date)
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .filter(
                WorkoutSession.status == "completed",
                WorkoutSet.exercise_id == exercise.id,
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )
        if last_used is None:
            return 1.0
        last_date = date.fromisoformat(last_used[0][:10])
        days_since = (today_date - last_date).days

    if days_since > 42:
        return 1.0
    return 0.3 + (days_since / 42) * 0.7


def _compute_equipment_preference_score(exercise: "Exercise", user_profile: "UserProfile") -> float:
    equipment_type = exercise.equipment_type.value if hasattr(exercise.equipment_type, "value") else str(exercise.equipment_type)
    return EQUIPMENT_QUALITY_MULTIPLIER.get(equipment_type, 0.8)


def _compute_secondary_coverage_score(
    exercise: "Exercise",
    slot: "Slot",
    db_session: "SASession",
) -> float:
    if not slot.target_muscles:
        return 0.5

    covered: int = 0
    total: int = len(slot.target_muscles)

    secondary_ids = json.loads(exercise.secondary_muscle_ids or "[]")
    primary_muscle_name = exercise.primary_muscle.name if exercise.primary_muscle else ""

    if primary_muscle_name in slot.target_muscles:
        covered += 1

    for sid in secondary_ids:
        from gym_coach_brain.data.models import MuscleGroup
        mg = db_session.query(MuscleGroup).filter_by(id=sid).first()
        if mg and mg.name in slot.target_muscles:
            covered += 1

    return covered / max(1, total)


def _compute_progression_continuity_score(
    exercise: "Exercise",
    today_date: date,
    db_session: "SASession",
) -> float:
    from gym_coach_brain.data.models import WorkoutSession, WorkoutSet

    last_session_row = (
        db_session.query(WorkoutSession.session_date)
        .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
        .filter(
            WorkoutSession.status == "completed",
            WorkoutSet.exercise_id == exercise.id,
        )
        .order_by(WorkoutSession.session_date.desc())
        .first()
    )

    if last_session_row is None:
        return 0.5

    last_date = date.fromisoformat(last_session_row[0][:10])
    days_gap = (today_date - last_date).days

    if days_gap <= 14:
        return 0.8
    elif days_gap <= 28:
        return 0.5
    return 0.2


def rank_candidates(
    candidates: list["ScoredCandidate"],
    today_date: date,
) -> list["ScoredCandidate"]:
    valid = [c for c in candidates if c.score.availability_score > 0]
    valid.sort(key=lambda c: c.score.total_score, reverse=True)

    if len(valid) <= 1:
        return valid

    top_score = valid[0].score.total_score
    threshold = top_score * 0.9

    near_top = [c for c in valid if c.score.total_score >= threshold]

    if len(near_top) > 1:
        rng = random.Random(today_date.isoformat())
        rng.shuffle(near_top)
        return near_top

    return valid


def get_anchor_exercise_id_for_slot(
    slot: "Slot",
    today_date: date,
    db_session: "SASession",
) -> int | None:
    from gym_coach_brain.data.models import WorkoutSession, WorkoutSet, Exercise

    anchor_window_days = 21
    if slot.anchor_policy.value == "free_rotation":
        return None

    candidate_ids = [
        ex.id
        for ex in db_session.query(Exercise).all()
        if ex.primary_muscle and ex.primary_muscle.name in slot.target_muscles
    ]

    most_recent: tuple[int, int] | None = None

    for ex_id in candidate_ids:
        last_session_row = (
            db_session.query(WorkoutSession.session_date)
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .filter(
                WorkoutSession.status == "completed",
                WorkoutSet.exercise_id == ex_id,
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )
        if last_session_row is None:
            continue
        last_date = date.fromisoformat(last_session_row[0][:10])
        days_since = (today_date - last_date).days
        if days_since > anchor_window_days:
            continue
        if most_recent is None or days_since < most_recent[0]:
            most_recent = (days_since, ex_id)

    return most_recent[1] if most_recent is not None else None

"""
Onboarding question templates and coefficient mapping.

Maps athlete answers deterministically to numerical training parameters.
No LLM interpretation of training load parameters — pure algorithmic conversion.

FR9: Interactive onboarding → UserProfile
FR13-FR14: Answer → coefficient mapping (deterministic, not LLM-driven)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from gym_coach_brain.core.equipment_inventory import (
    SUPPORTED_INVENTORY_IDS,
    exercise_available_for_profile,
    resolve_equipment_answer,
)
from gym_coach_brain.data.models import EquipmentType, Exercise, TrainingSplit, UserProfile

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig


class QuestionType(str, Enum):
    NUMERIC = "numeric"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    TEXT = "text"


@dataclass
class OnboardingQuestion:
    id: str
    text: str
    type: QuestionType
    options: list[str] | None = None
    min_val: float | None = None
    max_val: float | None = None


QUESTIONS: list[OnboardingQuestion] = [
    OnboardingQuestion(
        id="age",
        text="Сколько вам лет?",
        type=QuestionType.NUMERIC,
        min_val=10,
        max_val=100,
    ),
    OnboardingQuestion(
        id="experience_level",
        text="Ваш уровень подготовки?",
        type=QuestionType.SINGLE_CHOICE,
        options=["beginner", "intermediate", "advanced"],
    ),
    OnboardingQuestion(
        id="goal",
        text="Ваша основная цель тренировок?",
        type=QuestionType.SINGLE_CHOICE,
        options=["strength", "hypertrophy", "endurance"],
    ),
    OnboardingQuestion(
        id="bodyweight_kg",
        text="Вес тела (кг)?",
        type=QuestionType.NUMERIC,
        min_val=30,
        max_val=250,
    ),
    OnboardingQuestion(
        id="equipment",
        text=(
            "Какое оборудование вам доступно? Можно перечислять конкретные тренажёры "
            "и инвентарь: smith machine, chest press machine, lat pulldown, dumbbells, barbell"
        ),
        type=QuestionType.MULTI_CHOICE,
        options=list(SUPPORTED_INVENTORY_IDS) + [e.value for e in EquipmentType],
    ),
    OnboardingQuestion(
        id="training_days_per_week",
        text="Сколько раз в неделю тренируешься?",
        type=QuestionType.SINGLE_CHOICE,
        options=["3", "4", "5", "6"],
    ),
    OnboardingQuestion(
        id="training_split",
        text="Предпочтение сплита?",
        type=QuestionType.SINGLE_CHOICE,
        options=["full_body", "upper_lower", "ppl", "custom"],
    ),
    OnboardingQuestion(
        id="sleep_quality",
        text="Как вы оцениваете качество вашего сна?",
        type=QuestionType.SINGLE_CHOICE,
        options=["poor", "average", "good"],
    ),
    OnboardingQuestion(
        id="stress_level",
        text="Ваш текущий уровень стресса?",
        type=QuestionType.SINGLE_CHOICE,
        options=["high", "moderate", "low"],
    ),
]

# Deterministic mappings — DO NOT use LLM for these
_TRAINING_SPLIT_MAP: dict[str, TrainingSplit] = {
    "full_body": TrainingSplit.full_body,
    "upper_lower": TrainingSplit.upper_lower,
    "ppl": TrainingSplit.ppl,
    "custom": TrainingSplit.custom,
    # Legacy Russian labels (for OpenClaw chat compatibility)
    "Фулбоди": TrainingSplit.full_body,
    "Верх-Низ": TrainingSplit.upper_lower,
    "ТТН": TrainingSplit.ppl,
    "Своя": TrainingSplit.custom,
}

_EXPERIENCE_LEVEL_OPTIONS = {"beginner", "intermediate", "advanced"}
_GOAL_OPTIONS = {"strength", "hypertrophy", "endurance"}
_TRAINING_DAYS_OPTIONS = {"3", "4", "5", "6"}
_SLEEP_QUALITY_MAP: dict[str, float] = {
    "poor": 0.3,
    "average": 0.6,
    "good": 1.0,
}

_STRESS_LEVEL_MAP: dict[str, float] = {
    "high": 0.3,
    "moderate": 0.6,
    "low": 1.0,
}


def map_answer_to_coefficients(question_id: str, answer: str) -> dict[str, float | str]:
    """Map a single onboarding answer to numerical coefficients.

    Returns a dict suitable for merging into UserProfile update kwargs.
    All mappings are deterministic — no LLM interpretation.

    Args:
        question_id: Question identifier (must match QUESTIONS[i].id)
        answer: Raw answer string from athlete

    Returns:
        dict with one or more UserProfile field updates
    """
    if question_id == "bodyweight_kg":
        return {"bodyweight_kg": float(answer)}

    if question_id == "training_days_per_week":
        if answer not in _TRAINING_DAYS_OPTIONS:
            raise ValueError(f"Unknown training_days_per_week answer: {answer!r}")
        return {"training_days_per_week": int(answer)}

    if question_id == "training_split":
        split = _TRAINING_SPLIT_MAP.get(answer)
        if split is None:
            raise ValueError(f"Unknown training_split answer: {answer!r}")
        return {"training_split": split}

    if question_id == "equipment":
        return resolve_equipment_answer(answer)

    if question_id == "experience_level":
        if answer not in _EXPERIENCE_LEVEL_OPTIONS:
            raise ValueError(f"Unknown experience_level answer: {answer!r}")
        return {"experience_level": answer}

    if question_id == "sleep_quality":
        if answer not in _SLEEP_QUALITY_MAP:
            raise ValueError(f"Unknown sleep_quality answer: {answer!r}")
        return {"sleep_quality_score": _SLEEP_QUALITY_MAP[answer]}

    if question_id == "stress_level":
        if answer not in _STRESS_LEVEL_MAP:
            raise ValueError(f"Unknown stress_level answer: {answer!r}")
        return {"stress_score": _STRESS_LEVEL_MAP[answer]}

    if question_id == "age":
        return {"age": int(float(answer))}

    if question_id == "goal":
        if answer not in _GOAL_OPTIONS:
            raise ValueError(f"Unknown goal answer: {answer!r}")
        return {"goal": answer}

    return {}


def compute_initial_weight_for_pattern(
    user_profile: UserProfile,
    science: ScienceConfig,
    pattern_name: str,
) -> float:
    """Return a conservative baseline load for a movement pattern.

    The returned value is intentionally conservative. It is a starter reference,
    not a claim about the athlete's current working weight for a specific exercise.
    """
    bodyweight = user_profile.bodyweight_kg
    if not bodyweight or bodyweight <= 0:
        raise ValueError("bodyweight_kg must be set and positive before computing initial weights")

    experience_level = user_profile.experience_level or "beginner"
    table = getattr(science, "initial_weight_table", {})
    if not table:
        return 0.0

    level_table = table.get(experience_level, table.get("beginner", {}))
    coef = float(level_table.get(pattern_name, 0.0))
    return round(bodyweight * coef, 1)


def compute_initial_weights(user_profile: UserProfile, science: ScienceConfig) -> dict[str, float]:
    """Compute conservative starter baselines for all movement patterns.

    Formula: bodyweight_kg * initial_weight_table[experience_level][movement_pattern]
    Result is stored in UserProfile.initial_weight_coefficients as JSON and later
    adapted by the planner per exercise and equipment family.

    Args:
        user_profile: UserProfile with bodyweight_kg set (non-None, non-zero)
        science: ScienceConfig with initial_weight_table populated

    Returns:
        dict mapping movement_pattern_name → starting weight in kg (rounded to 1 decimal)

    Raises:
        ValueError: if bodyweight_kg is None/zero, or experience_level missing from table
    """
    table = getattr(science, "initial_weight_table", {})
    if not table:
        return {}

    # Determine experience level — use persistent column or default to "beginner"
    experience_level = user_profile.experience_level or "beginner"
    level_table = table.get(experience_level, table.get("beginner", {}))
    return {
        pattern: compute_initial_weight_for_pattern(user_profile, science, pattern)
        for pattern in level_table
    }


def get_available_exercises(user_profile: UserProfile, session: Session) -> list[Exercise]:
    """Return exercises filtered by athlete's available equipment.

    Uses UserProfile.available_equipment (JSON list of EquipmentType values).
    If available_equipment is empty or None, returns an empty list.

    Args:
        user_profile: UserProfile with available_equipment set
        session: SQLAlchemy Session (in-memory or production)

    Returns:
        List of Exercise objects matching at least one equipment type in available_equipment
    """
    equipment_list = json.loads(user_profile.available_equipment or "[]")
    inventory_list = json.loads(user_profile.available_equipment_inventory or "[]")
    if not equipment_list and not inventory_list:
        return []

    exercises = session.query(Exercise).all()
    return [
        exercise
        for exercise in exercises
        if exercise_available_for_profile(
            exercise,
            user_profile,
            allow_bodyweight_fallback=False,
            allow_unrestricted_if_empty=False,
        )
    ]

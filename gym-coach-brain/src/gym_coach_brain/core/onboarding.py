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
        text="Какое оборудование вам доступно? (можно выбрать несколько)",
        type=QuestionType.MULTI_CHOICE,
        options=[e.value for e in EquipmentType],
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
        return {"training_days_per_week": int(answer)}

    if question_id == "training_split":
        split = _TRAINING_SPLIT_MAP.get(answer)
        if split is None:
            raise ValueError(f"Unknown training_split answer: {answer!r}")
        return {"training_split": split}

    if question_id == "equipment":
        # answer expected as comma-separated or JSON list
        if answer.startswith("["):
            items = json.loads(answer)
        else:
            items = [a.strip() for a in answer.split(",") if a.strip()]
        # validate each item is a valid EquipmentType
        validated = [EquipmentType(item) for item in items]
        return {"available_equipment": json.dumps([e.value for e in validated])}

    if question_id == "experience_level":
        return {"experience_level": answer}

    if question_id == "sleep_quality":
        return {"sleep_quality_score": _SLEEP_QUALITY_MAP.get(answer, 0.5)}

    if question_id == "stress_level":
        return {"stress_score": _STRESS_LEVEL_MAP.get(answer, 0.5)}

    if question_id == "age":
        return {"age": int(float(answer))}

    if question_id == "goal":
        return {"goal": answer}

    return {}


def compute_initial_weights(user_profile: UserProfile, science: ScienceConfig) -> dict[str, float]:
    """Compute initial weight coefficients for all movement patterns.

    Formula: bodyweight_kg * initial_weight_table[experience_level][movement_pattern]
    Result is stored in UserProfile.initial_weight_coefficients as JSON.

    Args:
        user_profile: UserProfile with bodyweight_kg set (non-None, non-zero)
        science: ScienceConfig with initial_weight_table populated

    Returns:
        dict mapping movement_pattern_name → starting weight in kg (rounded to 1 decimal)

    Raises:
        ValueError: if bodyweight_kg is None/zero, or experience_level missing from table
    """
    bodyweight = user_profile.bodyweight_kg
    if not bodyweight or bodyweight <= 0:
        raise ValueError("bodyweight_kg must be set and positive before computing initial weights")

    # Determine experience level — use persistent column or default to "beginner"
    experience_level = user_profile.experience_level or "beginner"

    table = getattr(science, "initial_weight_table", {})
    if not table:
        return {}

    level_table = table.get(experience_level, table.get("beginner", {}))
    return {
        pattern: round(bodyweight * coef, 1)
        for pattern, coef in level_table.items()
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
    if not equipment_list:
        return []

    return (
        session.query(Exercise)
        .filter(Exercise.equipment_type.in_(equipment_list))
        .all()
    )

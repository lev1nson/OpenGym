"""
Tests for core/onboarding.py: question templates and coefficient mapping.

Fixtures from tests/conftest.py (created in Story 3.3):
    - db_session: in-memory SQLite session with schema
    - mock_science_config: minimal ScienceConfig for testing
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.core.onboarding import (
    QUESTIONS,
    QuestionType,
    compute_initial_weights,
    get_available_exercises,
    map_answer_to_coefficients,
)
from gym_coach_brain.data.models import Base, EquipmentType, Exercise, TrainingSplit, UserProfile
from gym_coach_brain.data.seed import seed_exercises, seed_taxonomy


# ─── Question Structure Tests ──────────────────────────────────────────────────

def test_questions_list_not_empty():
    assert len(QUESTIONS) >= 9


def test_questions_have_unique_ids():
    ids = [q.id for q in QUESTIONS]
    assert len(ids) == len(set(ids)), "Duplicate question IDs found"


def test_required_questions_present():
    ids = {q.id for q in QUESTIONS}
    required = {"bodyweight_kg", "equipment", "training_days_per_week", "training_split"}
    assert required.issubset(ids)


def test_bodyweight_question_is_numeric():
    q = next(q for q in QUESTIONS if q.id == "bodyweight_kg")
    assert q.type == QuestionType.NUMERIC
    assert q.min_val == 30
    assert q.max_val == 250


def test_equipment_question_is_multi_choice():
    q = next(q for q in QUESTIONS if q.id == "equipment")
    assert q.type == QuestionType.MULTI_CHOICE
    assert q.options is not None
    assert "bodyweight" in q.options


def test_training_days_question_has_correct_options():
    q = next(q for q in QUESTIONS if q.id == "training_days_per_week")
    assert q.type == QuestionType.SINGLE_CHOICE
    assert set(q.options) == {"3", "4", "5", "6"}


def test_training_split_question_has_correct_options():
    q = next(q for q in QUESTIONS if q.id == "training_split")
    assert q.type == QuestionType.SINGLE_CHOICE
    assert set(q.options) == {"full_body", "upper_lower", "ppl", "custom"}


# ─── map_answer_to_coefficients Tests ─────────────────────────────────────────

def test_map_bodyweight_kg():
    result = map_answer_to_coefficients("bodyweight_kg", "75")
    assert result == {"bodyweight_kg": 75.0}


def test_map_training_days_per_week():
    for days in ["3", "4", "5", "6"]:
        result = map_answer_to_coefficients("training_days_per_week", days)
        assert result["training_days_per_week"] == int(days)


def test_map_training_split_full_body():
    result = map_answer_to_coefficients("training_split", "full_body")
    assert result["training_split"] == TrainingSplit.full_body


def test_map_training_split_upper_lower():
    result = map_answer_to_coefficients("training_split", "upper_lower")
    assert result["training_split"] == TrainingSplit.upper_lower


def test_map_training_split_ppl():
    result = map_answer_to_coefficients("training_split", "ppl")
    assert result["training_split"] == TrainingSplit.ppl


def test_map_training_split_custom():
    result = map_answer_to_coefficients("training_split", "custom")
    assert result["training_split"] == TrainingSplit.custom


def test_map_equipment_single():
    result = map_answer_to_coefficients("equipment", "bodyweight")
    equipment = json.loads(result["available_equipment"])
    assert equipment == ["bodyweight"]
    inventory = json.loads(result["available_equipment_inventory"])
    assert inventory == ["bodyweight"]


def test_map_equipment_multiple_comma_separated():
    result = map_answer_to_coefficients("equipment", "barbell, dumbbell, bodyweight")
    equipment = json.loads(result["available_equipment"])
    assert set(equipment) == {"barbell", "dumbbell", "bodyweight"}
    inventory = json.loads(result["available_equipment_inventory"])
    assert set(inventory) == {"barbell", "dumbbells", "bodyweight"}


def test_map_equipment_json_list():
    result = map_answer_to_coefficients("equipment", '["barbell", "bodyweight"]')
    equipment = json.loads(result["available_equipment"])
    assert set(equipment) == {"barbell", "bodyweight"}
    inventory = json.loads(result["available_equipment_inventory"])
    assert set(inventory) == {"barbell", "bodyweight"}


def test_map_equipment_specific_inventory_derives_broad_types():
    result = map_answer_to_coefficients(
        "equipment",
        "smith machine, chest press machine, leg curl machine, lat pulldown, dumbbells, barbell, adjustable bench",
    )
    equipment = json.loads(result["available_equipment"])
    inventory = json.loads(result["available_equipment_inventory"])
    assert set(equipment) == {"machine", "cable", "dumbbell", "barbell"}
    assert set(inventory) == {
        "smith_machine",
        "chest_press_machine",
        "leg_curl_machine",
        "high_pulley_cable",
        "dumbbells",
        "barbell",
        "adjustable_bench",
    }


def test_map_invalid_training_split_raises():
    with pytest.raises((ValueError, KeyError)):
        map_answer_to_coefficients("training_split", "invalid_split")


# ─── compute_initial_weights Tests ────────────────────────────────────────────

@pytest.fixture
def mock_science_config_with_table(mock_science_config):
    """Extend mock_science_config with initial_weight_table for testing."""
    mock_science_config.__dict__["initial_weight_table"] = {
        "beginner": {
            "horizontal_push": 0.40, "vertical_push": 0.30,
            "horizontal_pull": 0.35, "vertical_pull": 0.30,
            "squat": 0.60, "hinge": 0.50, "carry": 0.25,
        },
        "intermediate": {
            "horizontal_push": 0.70, "vertical_push": 0.55,
            "horizontal_pull": 0.60, "vertical_pull": 0.55,
            "squat": 1.00, "hinge": 0.90, "carry": 0.45,
        },
        "advanced": {
            "horizontal_push": 1.00, "vertical_push": 0.80,
            "horizontal_pull": 0.90, "vertical_pull": 0.80,
            "squat": 1.50, "hinge": 1.30, "carry": 0.65,
        },
    }
    return mock_science_config


def _make_user_profile(bodyweight_kg: float, experience_level: str) -> UserProfile:
    """Create a minimal UserProfile for testing (not persisted)."""
    return UserProfile(bodyweight_kg=bodyweight_kg, experience_level=experience_level)


def test_compute_initial_weights_beginner(mock_science_config_with_table):
    profile = _make_user_profile(70.0, "beginner")
    result = compute_initial_weights(profile, mock_science_config_with_table)
    assert result["horizontal_push"] == pytest.approx(28.0, rel=1e-2)
    assert result["squat"] == pytest.approx(42.0, rel=1e-2)


def test_compute_initial_weights_intermediate(mock_science_config_with_table):
    profile = _make_user_profile(80.0, "intermediate")
    result = compute_initial_weights(profile, mock_science_config_with_table)
    assert result["squat"] == pytest.approx(80.0, rel=1e-2)
    assert result["horizontal_push"] == pytest.approx(56.0, rel=1e-2)


def test_compute_initial_weights_returns_all_7_patterns(mock_science_config_with_table):
    profile = _make_user_profile(75.0, "advanced")
    result = compute_initial_weights(profile, mock_science_config_with_table)
    expected_patterns = {
        "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
        "squat", "hinge", "carry"
    }
    assert set(result.keys()) == expected_patterns


def test_compute_initial_weights_no_bodyweight_raises(mock_science_config_with_table):
    profile = UserProfile(bodyweight_kg=None)
    with pytest.raises(ValueError, match="bodyweight_kg"):
        compute_initial_weights(profile, mock_science_config_with_table)


def test_compute_initial_weights_empty_table(mock_science_config):
    """When initial_weight_table is absent/empty, return empty dict (graceful degradation)."""
    profile = _make_user_profile(70.0, "beginner")
    result = compute_initial_weights(profile, mock_science_config)
    assert result == {}


# ─── get_available_exercises Tests ────────────────────────────────────────────

@pytest.fixture
def seeded_session():
    """In-memory DB session with seed data (muscle groups, exercises, equipment)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_taxonomy(session)
        seed_exercises(session)
        session.commit()
        yield session


def test_get_available_exercises_bodyweight_only(seeded_session):
    profile = UserProfile(available_equipment=json.dumps(["bodyweight"]))
    exercises = get_available_exercises(profile, seeded_session)
    assert len(exercises) > 0
    assert all(ex.equipment_type == EquipmentType.bodyweight for ex in exercises)


def test_get_available_exercises_multiple_equipment(seeded_session):
    profile = UserProfile(available_equipment=json.dumps(["barbell", "bodyweight"]))
    exercises = get_available_exercises(profile, seeded_session)
    types = {ex.equipment_type for ex in exercises}
    assert EquipmentType.barbell in types or EquipmentType.bodyweight in types


def test_get_available_exercises_specific_inventory_filters_same_broad_type(seeded_session):
    profile = UserProfile(
        available_equipment=json.dumps(["cable"]),
        available_equipment_inventory=json.dumps(["high_pulley_cable"]),
    )
    exercises = get_available_exercises(profile, seeded_session)
    names = {ex.name for ex in exercises}
    assert "Lat Pulldown" in names
    assert "Tricep Pushdown" in names
    assert "Cable Row" not in names


def test_get_available_exercises_empty_equipment_returns_empty(seeded_session):
    profile = UserProfile(available_equipment=json.dumps([]))
    exercises = get_available_exercises(profile, seeded_session)
    assert exercises == []


def test_get_available_exercises_no_equipment_set_returns_empty(seeded_session):
    profile = UserProfile(available_equipment=None)
    exercises = get_available_exercises(profile, seeded_session)
    assert exercises == []

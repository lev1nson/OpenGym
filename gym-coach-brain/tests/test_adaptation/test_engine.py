"""
Tests for AdaptationEngine and plateau detection (_is_plateau helper).

All tests use in-memory SQLite via db_session fixture and mock fixtures
from conftest.py — no file I/O, no real PyTorch model required.
"""
import json
import pytest
from unittest.mock import Mock

from gym_coach_brain.adaptation.engine import (
    AdaptationEngine,
    AdaptationResult,
    _is_plateau,
)
from gym_coach_brain.data.models import (
    Exercise,
    EquipmentType,
    MuscleGroup,
    MovementPattern,
    WorkoutSession,
    WorkoutSet,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_muscle_group(db_session):
    mg = MuscleGroup(name="chest", body_region="upper", is_push=True, is_pull=False, stretch_mediated=False)
    db_session.add(mg)
    db_session.flush()
    return mg


def _make_movement_pattern(db_session):
    mp = MovementPattern(name="horizontal_push", category="push")
    db_session.add(mp)
    db_session.flush()
    return mp


def _make_exercise(db_session, equipment_type: EquipmentType = EquipmentType.barbell, is_compound: bool = True):
    mg = _make_muscle_group(db_session)
    mp = _make_movement_pattern(db_session)
    ex = Exercise(
        name="Bench Press",
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        is_compound=is_compound,
        equipment_type=equipment_type,
    )
    db_session.add(ex)
    db_session.flush()
    return ex


def _make_user_profile():
    """Create a mock UserProfile without DB — avoids SQLAlchemy instrumentation issues."""
    user = Mock()
    user.goal = "hypertrophy"
    user.experience_level = "intermediate"
    user.training_days_per_week = 3
    user.available_equipment = "[]"
    user.onboarding_complete = True
    return user


def _make_session(db_session, exercises: list[dict], status: str = "planned") -> WorkoutSession:
    sess = WorkoutSession(
        session_date="2026-03-08",
        status=status,
        planned_exercises=json.dumps(exercises),
    )
    db_session.add(sess)
    db_session.flush()
    return sess


def _make_completed_session_with_sets(db_session, exercise_id: int, date: str, weight_kg: float, reps: int) -> WorkoutSession:
    sess = WorkoutSession(
        session_date=date,
        status="completed",
    )
    db_session.add(sess)
    db_session.flush()
    ws = WorkoutSet(
        session_id=sess.id,
        exercise_id=exercise_id,
        set_number=1,
        weight_kg=weight_kg,
        reps=reps,
    )
    db_session.add(ws)
    db_session.flush()
    return sess


# ─── Test: Weight Rounding ─────────────────────────────────────────────────────

def test_barbell_weight_rounded_to_2_5kg(mock_science_config, db_session):
    """Barbell exercises: weight must be rounded to 2.5kg increments."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    # Use rpe_model=None → double progression fallback
    # last_weight=80.0, rep_max=12 → progression increases weight by 2.5 → 82.5
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert len(result.exercises) == 1
    weight = result.exercises[0].target_weight_kg
    # Weight must be a multiple of 2.5
    assert weight % 2.5 == 0.0, f"Expected barbell weight to be multiple of 2.5, got {weight}"


def test_dumbbell_weight_rounded_to_1kg(mock_science_config, db_session):
    """Dumbbell exercises: weight must be rounded to 1.0kg increments."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.dumbbell, is_compound=False)
    user = _make_user_profile()

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Dumbbell Curl", "sets": 3, "target_weight_kg": 15.3}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert len(result.exercises) == 1
    weight = result.exercises[0].target_weight_kg
    # Weight must be a multiple of 1.0
    assert weight % 1.0 == 0.0, f"Expected dumbbell weight to be multiple of 1.0, got {weight}"


# ─── Test: Plateau Detection ───────────────────────────────────────────────────

def test_plateau_detected_after_n_identical_sessions(mock_science_config, db_session):
    """N identical sessions (same weight and reps) → plateau warning detected."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    n = mock_science_config.plateau_detection_sessions  # = 3

    for i in range(n):
        _make_completed_session_with_sets(
            db_session, ex.id, f"2026-03-0{i+1}", weight_kg=80.0, reps=8
        )

    assert _is_plateau(exercise_id=ex.id, n_sessions=n, db_session=db_session) is True


def test_no_plateau_when_weight_increases(mock_science_config, db_session):
    """Increasing weight across sessions → no plateau."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    n = mock_science_config.plateau_detection_sessions  # = 3

    for i in range(n):
        _make_completed_session_with_sets(
            db_session, ex.id, f"2026-03-0{i+1}", weight_kg=80.0 + i * 2.5, reps=8
        )

    assert _is_plateau(exercise_id=ex.id, n_sessions=n, db_session=db_session) is False


def test_no_plateau_when_volume_increases(mock_science_config, db_session):
    """Same weight but increasing reps (volume) → no plateau."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    n = mock_science_config.plateau_detection_sessions  # = 3

    for i in range(n):
        _make_completed_session_with_sets(
            db_session, ex.id, f"2026-03-0{i+1}", weight_kg=80.0, reps=8 + i
        )

    assert _is_plateau(exercise_id=ex.id, n_sessions=n, db_session=db_session) is False


# ─── Test: ML vs Fallback ──────────────────────────────────────────────────────

def test_low_confidence_triggers_double_progression_fallback(mock_science_config, db_session):
    """Confidence < threshold → used_ml=False, Double Progression applied."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    low_conf_model = Mock()
    low_conf_model.predict.return_value = (7.5, 0.3)  # conf 0.3 < threshold 0.6

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=low_conf_model)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is False


def test_high_confidence_uses_ml_prediction(mock_science_config, mock_rpe_model, db_session):
    """Confidence >= threshold → used_ml=True."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()
    # mock_rpe_model returns (7.5, 0.85) — confidence 0.85 >= threshold 0.6

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=mock_rpe_model)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is True


def test_no_rpe_model_uses_double_progression(mock_science_config, db_session):
    """rpe_model=None → used_ml=False for all exercises."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0},
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    for adapted_ex in result.exercises:
        assert adapted_ex.used_ml is False


def test_science_version_in_result(mock_science_config, db_session):
    """AdaptationResult.science_version matches science.version."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.science_version == mock_science_config.version

"""
Tests for data/features.py — ML feature vector builder.

Uses in-memory DB with seed data. Validates:
- No None/NaN in feature vector for seeded exercises
- Cold start fallbacks work correctly
- Historical RPE aggregation
- Numeric type constraints
"""
import math

import pytest

from gym_coach_brain.data.features import FeatureVector, build_feature_vector, _EQUIPMENT_ORDER
from gym_coach_brain.data.models import (
    Base, Exercise, MuscleGroup, ReadinessLog, WorkoutSession, WorkoutSet,
)
from gym_coach_brain.data.seed import seed_taxonomy, seed_exercises


@pytest.fixture
def feature_session(db_session):
    """Reuse db_session from conftest.py, seeding taxonomy + exercises."""
    seed_taxonomy(db_session)
    seed_exercises(db_session)
    db_session.commit()
    return db_session


@pytest.fixture
def session_id(feature_session):
    """Create a placeholder workout session and return its ID."""
    ws = WorkoutSession(
        session_date="2026-03-08T10:00:00",
        status="active",
        sleep_hours=8.0,
        pre_readiness=7,
    )
    feature_session.add(ws)
    feature_session.flush()
    return ws.id


def _get_first_exercise(session) -> Exercise:
    return session.query(Exercise).first()


# ─── PRIMARY TESTS (required by AC) ───────────────────────────────────────────

def test_feature_vector_no_none_nan(feature_session, session_id):
    """Feature vector has no None or NaN for seed exercise (cold start). [AC primary]"""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    # Check all 18 base fields
    for field_name, value in vars(fv).items():
        assert value is not None, f"Field {field_name} is None"
        if isinstance(value, float):
            assert not math.isnan(value), f"Field {field_name} is NaN"


def test_cold_start(feature_session, session_id):
    """Cold start: athlete with no history uses fallback values (not None, not NaN). [AC cold_start]"""
    exercise = _get_first_exercise(feature_session)
    cold_start_session = WorkoutSession(session_date="2026-03-08T12:00:00", status="active")
    feature_session.add(cold_start_session)
    feature_session.flush()
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=cold_start_session.id,
        set_number=1,
        weight_kg=80.0,
        reps=8,
        session=feature_session,
    )
    # Cold start expectations
    assert fv.historical_rpe == 6.0, f"Expected cold start RPE 6.0, got {fv.historical_rpe}"
    assert fv.avg_rpe_last_3_sessions_for_exercise == 6.0
    assert fv.sessions_count_for_exercise == 0
    assert fv.readiness_score == 5.0  # default readiness
    assert fv.days_since_last_session == 0  # no prior sessions
    assert fv.sleep_hours == pytest.approx(7.5)
    assert fv.pre_readiness == 5
    assert fv.workout_hour_sin == pytest.approx(0.0)
    assert fv.workout_hour_cos == pytest.approx(-1.0)

    # Verify no None / NaN anywhere
    for field_name, value in vars(fv).items():
        assert value is not None, f"Cold start field {field_name} is None"
        if isinstance(value, float):
            assert not math.isnan(value), f"Cold start field {field_name} is NaN"


def test_feature_vector_uses_workout_session_checkin_fields(feature_session):
    """Feature vector should pull sleep, readiness, and cyclic hour features from WorkoutSession."""
    exercise = _get_first_exercise(feature_session)
    ws = WorkoutSession(
        session_date="2026-03-08T06:30:00",
        status="active",
        sleep_hours=6.5,
        pre_readiness=9,
    )
    feature_session.add(ws)
    feature_session.flush()

    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=ws.id,
        set_number=2,
        weight_kg=82.5,
        reps=8,
        session=feature_session,
    )

    expected_hour = 6.5
    assert fv.sleep_hours == pytest.approx(6.5)
    assert fv.pre_readiness == 9
    assert fv.workout_hour_sin == pytest.approx(math.sin(2 * math.pi * expected_hour / 24))
    assert fv.workout_hour_cos == pytest.approx(math.cos(2 * math.pi * expected_hour / 24))


# ─── SUPPORTING TESTS ─────────────────────────────────────────────────────────

def test_feature_vector_with_history(feature_session):
    """Feature vector with 3 prior sessions computes avg RPE correctly."""
    exercise = _get_first_exercise(feature_session)

    # Create 3 completed sessions with known RPE data
    sessions = []
    for i in range(3):
        ws = WorkoutSession(
            session_date=f"2026-03-0{i+1}T10:00:00",
            status="completed",
        )
        feature_session.add(ws)
        feature_session.flush()
        wset = WorkoutSet(
            session_id=ws.id,
            exercise_id=exercise.id,
            set_number=1,
            weight_kg=100.0,
            reps=5,
            rpe=7.0 + i,  # 7.0, 8.0, 9.0
        )
        feature_session.add(wset)
        sessions.append(ws.id)

    # Current session (not completed)
    current_ws = WorkoutSession(session_date="2026-03-08T10:00:00", status="active")
    feature_session.add(current_ws)
    feature_session.flush()

    feature_session.commit()

    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=current_ws.id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )

    # avg of [7.0, 8.0, 9.0] = 8.0
    assert abs(fv.avg_rpe_last_3_sessions_for_exercise - 8.0) < 0.01
    assert fv.sessions_count_for_exercise == 3
    assert fv.historical_rpe == 9.0  # most recent set
    assert fv.days_since_last_session >= 0


def test_equipment_type_is_int(feature_session, session_id):
    """equipment_type_int is an integer in range 0-7."""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    assert isinstance(fv.equipment_type_int, int)
    assert 0 <= fv.equipment_type_int <= 7, f"equipment_type_int={fv.equipment_type_int} out of range"


def test_all_features_numeric(feature_session, session_id):
    """All 18 base feature vector fields are float or int (never str, bool, None)."""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    for field_name, value in vars(fv).items():
        assert isinstance(value, (int, float)), (
            f"Field {field_name} is {type(value).__name__}, expected int or float"
        )
        # bool is subclass of int in Python — disallow it
        assert not isinstance(value, bool), f"Field {field_name} is bool, use int 0/1 instead"


def test_is_compound_and_stretch_mediated_are_int(feature_session, session_id):
    """is_compound and stretch_mediated are int 0 or 1 (not Python bool)."""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    assert fv.is_compound in (0, 1)
    assert fv.stretch_mediated in (0, 1)
    assert not isinstance(fv.is_compound, bool)
    assert not isinstance(fv.stretch_mediated, bool)


def test_equipment_order_is_stable():
    """_EQUIPMENT_ORDER is deterministic — critical for feature encoding stability."""
    order1 = sorted(e.value for e in __import__("gym_coach_brain.data.models", fromlist=["EquipmentType"]).EquipmentType)
    assert _EQUIPMENT_ORDER == order1, "Equipment ordering must be alphabetically sorted and stable"
    assert len(_EQUIPMENT_ORDER) == 8

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
from gym_coach_brain.core.readiness import RecoverySignal
from gym_coach_brain.data.models import (
    Exercise,
    EquipmentType,
    MuscleGroup,
    MovementPattern,
    RPEPrediction,
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


def _make_rpe_prediction(
    db_session,
    session_id: int,
    exercise_id: int,
    predicted_rpe: float,
    confidence_score: float,
    model_version: str = "test-model",
) -> RPEPrediction:
    prediction = RPEPrediction(
        session_id=session_id,
        exercise_id=exercise_id,
        predicted_rpe=predicted_rpe,
        confidence_score=confidence_score,
        model_version=model_version,
    )
    db_session.add(prediction)
    db_session.flush()
    return prediction


# ─── Test: Weight Rounding ─────────────────────────────────────────────────────

def test_barbell_weight_rounded_to_2_5kg(mock_science_config, db_session):
    """Barbell exercises: weight must be rounded to 2.5kg increments."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 79.3}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert len(result.exercises) == 1
    weight = result.exercises[0].target_weight_kg
    assert weight == pytest.approx(80.0)
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


# ─── Test: Review Follow-up Fixes ─────────────────────────────────────────────

def test_plateau_detected_on_regression(mock_science_config, db_session):
    """Regression pattern (80→82.5→80 over N sessions) → plateau detected.

    The old equality check (max==min) would miss this because max=82.5 != min=80.
    The new comparison (most_recent <= oldest) correctly identifies no net progress.
    """
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    n = mock_science_config.plateau_detection_sessions  # = 3

    # Create sessions oldest→newest so DESC query gives newest first
    weights_by_date = [
        ("2026-03-01", 80.0),   # oldest
        ("2026-03-02", 82.5),   # middle peak
        ("2026-03-03", 80.0),   # most recent — regressed back
    ]
    for date, weight in weights_by_date:
        _make_completed_session_with_sets(db_session, ex.id, date, weight_kg=weight, reps=8)

    # Most recent weight (80.0) is not better than oldest (80.0) → plateau
    assert _is_plateau(exercise_id=ex.id, n_sessions=n, db_session=db_session) is True


def test_bad_planned_exercises_json_returns_empty_result(mock_science_config, db_session):
    """Malformed planned_exercises JSON → graceful handling, empty exercises list."""
    from gym_coach_brain.data.models import WorkoutSession as WS
    user = _make_user_profile()

    sess = WS(
        session_date="2026-03-08",
        status="planned",
        planned_exercises="not valid json{{",
    )
    db_session.add(sess)
    db_session.flush()

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(sess, user, None, mock_science_config, db_session)

    assert result.exercises == []


def test_rpe_easy_threshold_from_science_config(mock_science_config, db_session):
    """Low RPE from ML (below rpe_easy_threshold) → weight increases (ML path used)."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    # RPE 5.0 < rpe_easy_threshold (default 7.0), confidence 0.85 >= 0.6 → ML path, weight increases
    low_rpe_model = Mock()
    low_rpe_model.predict.return_value = (5.0, 0.85)

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=low_rpe_model)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is True
    assert result.exercises[0].target_weight_kg > 80.0  # weight should have increased


def test_rpe_hard_threshold_from_science_config(mock_science_config, db_session):
    """High RPE from ML (above rpe_hard_threshold) → weight decreases or holds (ML path)."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    # RPE 9.5 > rpe_hard_threshold (default 8.5), confidence 0.85 >= 0.6 → ML path, weight decreases
    high_rpe_model = Mock()
    high_rpe_model.predict.return_value = (9.5, 0.85)

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=high_rpe_model)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is True
    assert result.exercises[0].target_weight_kg < 80.0  # weight should have decreased


def test_latest_db_prediction_is_selected_for_exercise(mock_science_config, db_session):
    """Newest DB prediction for (session, exercise) must win over older rows."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    _make_rpe_prediction(
        db_session,
        session_id=session.id,
        exercise_id=ex.id,
        predicted_rpe=7.5,
        confidence_score=0.20,
        model_version="old-low-confidence",
    )
    _make_rpe_prediction(
        db_session,
        session_id=session.id,
        exercise_id=ex.id,
        predicted_rpe=7.5,
        confidence_score=0.90,
        model_version="new-high-confidence",
    )

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is True
    assert result.exercises[0].target_weight_kg == pytest.approx(80.0)


def test_double_progression_fallback_uses_previous_completed_reps(mock_science_config, db_session):
    """Fallback must use real previous performance, not assume rep-max completion."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-07",
        weight_kg=80.0,
        reps=6,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is False
    assert result.exercises[0].target_weight_kg == pytest.approx(80.0)
    assert result.exercises[0].target_reps == 7


def test_adaptation_result_exposes_adapted_repetitions(mock_science_config, db_session):
    """Adapted exercises must expose target reps alongside target weight."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-07",
        weight_kg=80.0,
        reps=12,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].target_reps == 6
    assert result.exercises[0].target_weight_kg == pytest.approx(82.5)


def test_direct_ml_path_uses_real_feature_vector_context(mock_science_config, db_session):
    """Direct model call should receive feature-vector data from real DB context."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    completed_session = _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-06T10:00:00",
        weight_kg=77.5,
        reps=8,
    )
    completed_set = (
        db_session.query(WorkoutSet)
        .filter_by(session_id=completed_session.id, exercise_id=ex.id, set_number=1)
        .one()
    )
    completed_set.rpe = 8.0
    db_session.flush()

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ], status="active")

    captured: dict = {}

    def predict(features: dict) -> tuple[float, float]:
        captured.update(features)
        return (7.5, 0.85)

    model = Mock()
    model.predict.side_effect = predict

    recovery_signal = RecoverySignal(
        coefficient=0.82,
        sleep_component=0.9,
        stress_component=0.8,
        hrv_component=0.7,
    )

    engine = AdaptationEngine(rpe_model=model)
    result = engine.adapt(session, user, recovery_signal, mock_science_config, db_session)

    assert result.exercises[0].used_ml is True
    assert captured["historical_rpe"] == pytest.approx(8.0)
    assert captured["sessions_count_for_exercise"] == 1
    assert captured["reps"] == 8
    assert captured["readiness_score"] == pytest.approx(0.82)


def test_direct_ml_path_uses_planned_set_count_in_feature_vector(mock_science_config, db_session):
    """Direct model path should pass the planned set count instead of hardcoding set 1."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-06T10:00:00",
        weight_kg=77.5,
        reps=8,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 4, "target_weight_kg": 80.0}
    ], status="active")

    captured: dict = {}

    def predict(features: dict) -> tuple[float, float]:
        captured.update(features)
        return (7.5, 0.85)

    model = Mock()
    model.predict.side_effect = predict

    engine = AdaptationEngine(rpe_model=model)
    engine.adapt(session, user, None, mock_science_config, db_session)

    assert captured["set_number"] == 4


def test_direct_ml_path_includes_muscle_group_fatigue_estimate(mock_science_config, db_session):
    """Direct model path should pass muscle_group_fatigue_estimate to ML features."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    for day in ("2026-03-03T10:00:00", "2026-03-05T10:00:00"):
        _make_completed_session_with_sets(
            db_session,
            exercise_id=ex.id,
            date=day,
            weight_kg=80.0,
            reps=8,
        )

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 82.5}
    ], status="active")

    captured: dict = {}

    def predict(features: dict) -> tuple[float, float]:
        captured.update(features)
        return (7.5, 0.85)

    model = Mock()
    model.predict.side_effect = predict

    engine = AdaptationEngine(rpe_model=model)
    engine.adapt(session, user, None, mock_science_config, db_session)

    assert "muscle_group_fatigue_estimate" in captured
    assert captured["muscle_group_fatigue_estimate"] > 0.0


def test_no_history_does_not_reactively_progress_planned_values(mock_science_config, db_session):
    """Without completed history, fallback should preserve the planned recommendation."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    session = _make_session(db_session, [
        {
            "exercise_id": ex.id,
            "exercise_name": "Bench Press",
            "sets": 3,
            "target_reps": 10,
            "target_weight_kg": 80.0,
        }
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is False
    assert result.exercises[0].target_weight_kg == pytest.approx(80.0)
    assert result.exercises[0].target_reps == 10


def test_no_history_applies_recovery_coefficient_to_planned_weight(mock_science_config, db_session):
    """No-history fallback should still scale the planned weight by recovery coeff."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    session = _make_session(db_session, [
        {
            "exercise_id": ex.id,
            "exercise_name": "Bench Press",
            "sets": 3,
            "target_reps": 10,
            "target_weight_kg": 80.0,
        }
    ])
    recovery_signal = RecoverySignal(
        coefficient=0.82,
        sleep_component=0.9,
        stress_component=0.8,
        hrv_component=0.7,
    )

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, recovery_signal, mock_science_config, db_session)

    assert result.exercises[0].used_ml is False
    assert result.exercises[0].target_weight_kg == pytest.approx(65.0)
    assert result.exercises[0].target_reps == 10


def test_canonical_exercise_name_from_db_is_used_in_result_and_explanation(
    mock_science_config,
    db_session,
):
    """DB canonical exercise name should override typoed planned JSON names."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press typo", "sets": 3, "target_weight_kg": 80.0}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].exercise_name == "Bench Press"
    assert result.exercises[0].explanation.startswith("[ядро] Bench Press:")


def test_previous_performance_prefers_working_set_weight_for_pyramid_sessions(
    mock_science_config,
    db_session,
):
    """Pyramid sessions should use the repeated working weight, not a single top set."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    completed_session = WorkoutSession(
        session_date="2026-03-07T10:00:00",
        status="completed",
    )
    db_session.add(completed_session)
    db_session.flush()
    db_session.add_all([
        WorkoutSet(
            session_id=completed_session.id,
            exercise_id=ex.id,
            set_number=1,
            weight_kg=100.0,
            reps=5,
        ),
        WorkoutSet(
            session_id=completed_session.id,
            exercise_id=ex.id,
            set_number=2,
            weight_kg=90.0,
            reps=8,
        ),
        WorkoutSet(
            session_id=completed_session.id,
            exercise_id=ex.id,
            set_number=3,
            weight_kg=90.0,
            reps=8,
        ),
    ])
    db_session.flush()

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 90.0}
    ])

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].target_weight_kg == pytest.approx(90.0)
    assert result.exercises[0].target_reps == 9


def test_direct_ml_path_scales_final_weight_by_recovery_coefficient(
    mock_science_config,
    db_session,
):
    """Direct ML path should apply recovery scaling to the final recommended weight."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-07T10:00:00",
        weight_kg=80.0,
        reps=8,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ], status="active")
    recovery_signal = RecoverySignal(
        coefficient=0.82,
        sleep_component=0.9,
        stress_component=0.8,
        hrv_component=0.7,
    )

    model = Mock()
    model.predict.return_value = (5.0, 0.85)

    engine = AdaptationEngine(rpe_model=model)
    result = engine.adapt(session, user, recovery_signal, mock_science_config, db_session)

    assert result.exercises[0].used_ml is True
    assert result.exercises[0].target_weight_kg == pytest.approx(70.0)


def test_fatigue_lookback_sessions_is_independent_from_rest_days(mock_science_config, db_session):
    """Fatigue estimation should use ML-configured session lookback, not rest-day values."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    mock_science_config.planning.min_rest_days_per_muscle_group = 7
    mock_science_config.ml.fatigue_lookback_sessions = 2

    for day in ("2026-03-03T10:00:00", "2026-03-05T10:00:00", "2026-03-07T10:00:00"):
        _make_completed_session_with_sets(
            db_session,
            exercise_id=ex.id,
            date=day,
            weight_kg=80.0,
            reps=8,
        )

    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 82.5}
    ], status="active")

    captured: dict = {}

    def predict(features: dict) -> tuple[float, float]:
        captured.update(features)
        return (7.5, 0.85)

    model = Mock()
    model.predict.side_effect = predict

    engine = AdaptationEngine(rpe_model=model)
    engine.adapt(session, user, None, mock_science_config, db_session)

    expected_sets = 2
    # Capacity is PUOS limit * lookback sessions
    capacity = mock_science_config.puos.max_sets_per_group * mock_science_config.ml.fatigue_lookback_sessions
    expected_fatigue = expected_sets / capacity
    assert captured["muscle_group_fatigue_estimate"] == pytest.approx(expected_fatigue)


def test_plateau_detection_uses_session_id_as_same_day_tiebreaker(
    mock_science_config,
    db_session,
):
    """Same-day sessions should use the higher session id as the true most-recent session."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    n = mock_science_config.plateau_detection_sessions

    _make_completed_session_with_sets(
        db_session,
        ex.id,
        "2026-03-06T10:00:00",
        weight_kg=80.0,
        reps=8,
    )
    _make_completed_session_with_sets(
        db_session,
        ex.id,
        "2026-03-07T10:00:00",
        weight_kg=80.0,
        reps=8,
    )
    _make_completed_session_with_sets(
        db_session,
        ex.id,
        "2026-03-07T10:00:00",
        weight_kg=82.5,
        reps=8,
    )

    assert n == 3
    assert _is_plateau(exercise_id=ex.id, n_sessions=n, db_session=db_session) is False


def test_ml_path_increments_reps_on_easy_rpe_when_weight_holds(mock_science_config, db_session):
    """ML path: RPE < easy_threshold (e.g. 5.0) but weight stays same (e.g. no rounding change) → reps increment."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-07T10:00:00",
        weight_kg=80.0,
        reps=8,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    # RPE 5.0 is easy, but if weight stays 80.0 (e.g. maybe increment was small), reps should go 8->9
    model = Mock()
    model.predict.return_value = (5.0, 0.85)

    engine = AdaptationEngine(rpe_model=model)
    result = engine.adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].target_weight_kg == pytest.approx(85.0)
    assert result.exercises[0].target_reps == 6 # reset to min because weight increased

    # Case 2: keep the same final weight by zeroing ML sensitivity.
    mock_science_config.ml.rpe_weight_sensitivity = 0.0
    result = engine.adapt(session, user, None, mock_science_config, db_session)
    assert result.exercises[0].target_weight_kg == 80.0
    assert result.exercises[0].target_reps == 9 # Reps incremented because weight stayed same


def test_bounded_correction_within_limit(mock_science_config, db_session):
    """Small delta should apply ML and write transparency fields to RPEPrediction."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()
    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-07T10:00:00",
        weight_kg=80.0,
        reps=8,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ], status="active")
    prediction = _make_rpe_prediction(
        db_session,
        session_id=session.id,
        exercise_id=ex.id,
        predicted_rpe=7.2,
        confidence_score=0.81,
    )

    result = AdaptationEngine(rpe_model=None).adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is True
    assert result.exercises[0].explanation.startswith("[AI:")
    assert prediction.anomaly_flag is False
    assert prediction.source_label.startswith("[AI:")
    assert prediction.core_weight_kg == pytest.approx(80.0)
    assert prediction.ml_weight_kg == pytest.approx(81.1)
    assert prediction.ml_adjustment_kg == pytest.approx(1.1)


def test_bounded_correction_exceeds_limit(mock_science_config, db_session):
    """Large delta should be blocked and marked as anomaly."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()
    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-07T10:00:00",
        weight_kg=80.0,
        reps=8,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ], status="active")
    prediction = _make_rpe_prediction(
        db_session,
        session_id=session.id,
        exercise_id=ex.id,
        predicted_rpe=1.0,
        confidence_score=0.9,
    )

    result = AdaptationEngine(rpe_model=None).adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is False
    assert result.exercises[0].target_weight_kg == pytest.approx(80.0)
    assert "заблокирован" in result.exercises[0].explanation
    assert prediction.anomaly_flag is True
    assert "заблокирован" in prediction.source_label


def test_bounded_correction_low_confidence(mock_science_config, db_session):
    """Low confidence should fall back to core weight without anomaly."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()
    _make_completed_session_with_sets(
        db_session,
        exercise_id=ex.id,
        date="2026-03-07T10:00:00",
        weight_kg=80.0,
        reps=8,
    )
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ], status="active")
    prediction = _make_rpe_prediction(
        db_session,
        session_id=session.id,
        exercise_id=ex.id,
        predicted_rpe=7.2,
        confidence_score=0.43,
    )

    result = AdaptationEngine(rpe_model=None).adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].used_ml is False
    assert result.exercises[0].target_weight_kg == pytest.approx(80.0)
    assert "[ядро:" in result.exercises[0].explanation
    assert prediction.anomaly_flag is False
    assert prediction.source_label == "[ядро: confidence 43% < порога]"


def test_bounded_correction_no_prediction(mock_science_config, db_session):
    """Without any prediction row, the engine should emit the plain core source label."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()
    session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])

    result = AdaptationEngine(rpe_model=None).adapt(session, user, None, mock_science_config, db_session)

    assert result.exercises[0].explanation.startswith("[ядро] ")


def test_history_lookup_ignores_future_sessions(mock_science_config, db_session):
    """History lookup should only see sessions BEFORE the current one."""
    ex = _make_exercise(db_session, equipment_type=EquipmentType.barbell)
    user = _make_user_profile()

    # Current session is on March 8
    current_session = _make_session(db_session, [
        {"exercise_id": ex.id, "exercise_name": "Bench Press", "sets": 3, "target_weight_kg": 80.0}
    ])
    current_session.session_date = "2026-03-08T10:00:00"
    db_session.flush()

    # Past session (correctly found)
    _make_completed_session_with_sets(
        db_session,
        ex.id,
        "2026-03-07T10:00:00",
        weight_kg=70.0,
        reps=10,
    )

    # Future session (should be ignored)
    _make_completed_session_with_sets(
        db_session,
        ex.id,
        "2026-03-09T10:00:00",
        weight_kg=100.0,
        reps=12,
    )

    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(current_session, user, None, mock_science_config, db_session)

    # Should have adapted from the 70kg session, not the 100kg one
    # 70kg x 10 -> 70kg x 11 (next step in double progression)
    assert result.exercises[0].target_weight_kg == pytest.approx(70.0)
    assert result.exercises[0].target_reps == 11

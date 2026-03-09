"""
Tests for api/handlers.py — exercise_add intent handler.
Uses in-memory DB with taxonomy + exercise seed data.
No conftest.py — project convention: each test file defines fixtures locally.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.api.handlers import (
    handle_exercise_add,
    handle_onboarding_answer,
    handle_onboarding_complete,
    handle_onboarding_start,
    handle_profile_show,
    handle_profile_update_equipment,
    handle_profile_update_split,
    handle_workout_start,
)
from gym_coach_brain.core.science import (
    MethodologiesConfig,
    MethodologySpec,
    PUOSConfig,
    PlanningConfig,
    ProgressionConfig,
    RecoveryConfig,
    ScienceConfig,
)
from gym_coach_brain.core.puos import fractional_volume
from gym_coach_brain.data.models import (
    Base,
    Exercise,
    MLJob,
    MuscleGroup,
    ReadinessLog,
    TrainingSplit,
    UserProfile,
    WorkoutSession,
)
from gym_coach_brain.data.seed import seed_all, seed_exercises, seed_taxonomy


@pytest.fixture
def handler_session():
    """In-memory session with taxonomy + equipment + exercises seed data.
    Ensures the test environment mirrors the expected production state.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
        yield session


# ─── PRIMARY TEST (required by AC) ────────────────────────────────────────────

def test_exercise_add(handler_session):
    """exercise_add creates a new exercise and returns exit_code 0. [AC primary]"""
    argv = [
        "--name", "Box Jump",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "bodyweight",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)

    assert exit_code == 0, f"Expected exit_code 0, got {exit_code}: {stdout}"

    exercise = handler_session.query(Exercise).filter_by(name="Box Jump").first()
    assert exercise is not None, "Box Jump not found in DB after exercise_add"
    assert exercise.primary_muscle.name == "quadriceps"
    assert exercise.movement_pattern.name == "squat"
    assert exercise.equipment_type == "bodyweight"
    assert exercise.secondary_muscle_ids == "[]"
    assert exercise.is_compound is True     # default: true
    assert exercise.stretch_mediated is False  # default: false


# ─── SUPPORTING TESTS ─────────────────────────────────────────────────────────

def test_exercise_add_with_secondary_muscles(handler_session):
    """--secondary stores valid muscle IDs in secondary_muscle_ids JSON."""
    argv = [
        "--name", "Box Jump Variant",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "bodyweight",
        "--secondary", "glutes,hamstrings",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 0

    exercise = handler_session.query(Exercise).filter_by(name="Box Jump Variant").first()
    assert exercise is not None
    secondary_ids = json.loads(exercise.secondary_muscle_ids)
    assert len(secondary_ids) == 2
    # Verify IDs are valid MuscleGroup PKs
    valid_ids = {mg.id for mg in handler_session.query(MuscleGroup).all()}
    assert all(mid in valid_ids for mid in secondary_ids)


def test_exercise_add_available_for_puos(handler_session):
    """Exercise added via handler is immediately available for fractional_volume calculation. [AC: PUOS]"""
    argv = [
        "--name", "PUOS Test",
        "--muscle", "chest",
        "--pattern", "horizontal_push",
        "--equipment", "barbell",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 0

    exercise = handler_session.query(Exercise).filter_by(name="PUOS Test").first()
    chest = handler_session.query(MuscleGroup).filter_by(name="chest").first()
    result = fractional_volume(exercise.id, chest.id, handler_session)
    assert result == 1.0, f"Expected 1.0 for primary muscle, got {result}"


def test_exercise_add_duplicate_name_returns_error(handler_session):
    """Duplicate exercise name returns exit_code 1 (user error)."""
    argv = [
        "--name", "Bench Press",  # already seeded
        "--muscle", "chest",
        "--pattern", "horizontal_push",
        "--equipment", "barbell",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1, f"Expected exit_code 1 for duplicate, got {exit_code}"


def test_exercise_add_unknown_muscle_returns_error(handler_session):
    """Unknown primary muscle name returns exit_code 1."""
    argv = [
        "--name", "Phantom Move",
        "--muscle", "nonexistent_muscle",
        "--pattern", "squat",
        "--equipment", "bodyweight",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1


def test_exercise_add_invalid_equipment_returns_error(handler_session):
    """Invalid equipment type string returns exit_code 1."""
    argv = [
        "--name", "Some Move",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "invalid_equipment",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1


def test_exercise_add_unknown_secondary_muscle_returns_error(handler_session):
    """Unknown secondary muscle name returns exit_code 1."""
    argv = [
        "--name", "Mystery Move",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "bodyweight",
        "--secondary", "nonexistent_muscle",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1


@pytest.fixture
def onboarding_session():
    """In-memory session with seed data for onboarding handlers tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
        yield session


@pytest.fixture
def mock_science():
    """Minimal ScienceConfig with initial_weight_table for deterministic tests."""
    cfg = ScienceConfig(
        version="test-1.0",
        puos=PUOSConfig(max_sets_per_group=11, smh_volume_multiplier=1.2),
        progression=ProgressionConfig(
            compound_increment_kg=2.5,
            isolation_increment_kg=1.25,
            apre_6_step_min_kg=2.5,
            apre_6_step_max_kg=5.0,
            hypertrophy_rep_min=6,
            hypertrophy_rep_max=12,
        ),
        recovery=RecoveryConfig(hrv_weight=0.5, sleep_weight=0.3, stress_weight=0.2),
        exercises={},
        methodologies=MethodologiesConfig(
            strength=MethodologySpec(rep_min=1, rep_max=5, frequency_per_week_min=2, frequency_per_week_max=4),
            hypertrophy=MethodologySpec(rep_min=6, rep_max=12, frequency_per_week_min=2, frequency_per_week_max=4),
            endurance=MethodologySpec(rep_min=15, rep_max=30, frequency_per_week_min=3, frequency_per_week_max=5),
        ),
        planning=PlanningConfig(min_rest_days_per_muscle_group=2, min_rest_days_compound=3),
    )
    cfg.__dict__["initial_weight_table"] = {
        "beginner": {
            "horizontal_push": 0.40,
            "vertical_push": 0.30,
            "horizontal_pull": 0.35,
            "vertical_pull": 0.30,
            "squat": 0.60,
            "hinge": 0.50,
            "carry": 0.25,
        },
        "intermediate": {
            "horizontal_push": 0.70,
            "vertical_push": 0.55,
            "horizontal_pull": 0.60,
            "vertical_pull": 0.55,
            "squat": 1.00,
            "hinge": 0.90,
            "carry": 0.45,
        },
    }
    return cfg


def test_onboarding_start_returns_first_question(onboarding_session, mock_science):
    stdout, exit_code = handle_onboarding_start([], onboarding_session, mock_science)
    assert exit_code == 0
    assert "Вопрос 1/" in stdout


def test_onboarding_start_with_existing_complete_profile_warns(onboarding_session, mock_science):
    profile = UserProfile(onboarding_complete=True)
    onboarding_session.add(profile)
    onboarding_session.flush()

    stdout, exit_code = handle_onboarding_start([], onboarding_session, mock_science)
    assert exit_code == 1
    assert "Профиль уже заполнен" in stdout


def test_onboarding_start_reset_creates_new_profile(onboarding_session, mock_science):
    profile = UserProfile(onboarding_complete=True)
    onboarding_session.add(profile)
    onboarding_session.flush()

    stdout, exit_code = handle_onboarding_start(["--reset"], onboarding_session, mock_science)
    assert exit_code == 0

    new_profile = onboarding_session.query(UserProfile).first()
    assert new_profile is not None
    assert new_profile.onboarding_complete is False


def test_onboarding_answer_bodyweight(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "bodyweight_kg", "--answer", "75"],
        onboarding_session,
        mock_science,
    )
    assert exit_code == 0
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    assert profile.bodyweight_kg == 75.0


def test_onboarding_answer_training_split(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "training_split", "--answer", "full_body"],
        onboarding_session,
        mock_science,
    )
    assert exit_code == 0
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    assert profile.training_split == TrainingSplit.full_body


def test_onboarding_answer_invalid_question_id(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "invalid_question", "--answer", "42"],
        onboarding_session,
        mock_science,
    )
    assert exit_code == 1


def test_onboarding_answer_invalid_split_value(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "training_split", "--answer", "invalid"],
        onboarding_session,
        mock_science,
    )
    assert exit_code == 1


def _setup_profile_for_complete(session, science, bodyweight=70.0, experience="intermediate"):
    handle_onboarding_start([], session, science)
    handle_onboarding_answer(["--question", "bodyweight_kg", "--answer", str(bodyweight)], session, science)
    handle_onboarding_answer(["--question", "experience_level", "--answer", experience], session, science)
    handle_onboarding_answer(["--question", "training_split", "--answer", "full_body"], session, science)
    handle_onboarding_answer(["--question", "training_days_per_week", "--answer", "4"], session, science)
    handle_onboarding_answer(["--question", "equipment", "--answer", "bodyweight"], session, science)


def test_onboarding_complete_computes_weights(onboarding_session, mock_science):
    _setup_profile_for_complete(onboarding_session, mock_science, bodyweight=80.0, experience="intermediate")

    stdout, exit_code = handle_onboarding_complete([], onboarding_session, mock_science)
    assert exit_code == 0

    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    assert profile.onboarding_complete is True
    weights = json.loads(profile.initial_weight_coefficients or "{}")
    assert weights.get("squat") == pytest.approx(80.0, rel=1e-2)


def test_onboarding_complete_without_bodyweight_fails(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_complete([], onboarding_session, mock_science)
    assert exit_code == 1


def test_profile_show_returns_formatted_text(onboarding_session, mock_science):
    _setup_profile_for_complete(onboarding_session, mock_science)
    handle_onboarding_complete([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_show([], onboarding_session)
    assert exit_code == 0
    assert "Профиль атлета" in stdout
    assert "Вес тела" in stdout
    assert "Сплит" in stdout


def test_profile_show_no_profile_returns_error(onboarding_session):
    stdout, exit_code = handle_profile_show([], onboarding_session)
    assert exit_code == 1


def test_profile_update_equipment_valid(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_equipment(
        ["--equipment", "bodyweight,barbell"],
        onboarding_session,
    )
    assert exit_code == 0
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    eq = json.loads(profile.available_equipment)
    assert "bodyweight" in eq
    assert "barbell" in eq


def test_profile_update_equipment_invalid_type(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_equipment(
        ["--equipment", "invalid_equip"],
        onboarding_session,
    )
    assert exit_code == 1


def test_profile_update_split_ppl(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_split(["--split", "ppl"], onboarding_session)
    assert exit_code == 0
    assert "push" in stdout
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    assert profile.training_split == TrainingSplit.ppl


def test_profile_update_split_invalid(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_split(["--split", "invalid"], onboarding_session)
    assert exit_code == 1


def test_workout_start_persists_split_day_label_and_planned_exercises(
    handler_session, mock_science
):
    profile = UserProfile(
        onboarding_complete=True,
        training_split=TrainingSplit.ppl,
        available_equipment=json.dumps(["barbell", "dumbbell"]),
        bodyweight_kg=80.0,
        experience_level="intermediate",
        training_days_per_week=4,
        goal="hypertrophy",
        initial_weight_coefficients=json.dumps({"horizontal_push": 70.0}),
    )
    handler_session.add(profile)
    handler_session.flush()

    readiness = ReadinessLog(
        session_date="2026-03-09",
        sleep_hours=8.0,
        stress_level=2,
        hrv_score=None,
        recovery_score=1.0,
    )
    handler_session.add(readiness)
    handler_session.flush()

    stdout, exit_code = handle_workout_start(
        ["--sleep-hours", "7.5", "--pre-readiness", "5"],
        handler_session,
        mock_science,
    )

    assert exit_code == 0
    assert "id:" in stdout

    workout_session = handler_session.query(WorkoutSession).one()
    assert workout_session.status == "active"
    assert workout_session.split_day_label == "push"
    assert workout_session.planned_exercises is not None
    assert workout_session.sleep_hours == pytest.approx(7.5)
    assert workout_session.pre_readiness == 5

    planned = json.loads(workout_session.planned_exercises)
    assert planned
    assert {"exercise_id", "exercise_name", "sets", "rep_range", "target_weight_kg"} <= set(planned[0])

    ml_job = handler_session.query(MLJob).one()
    assert ml_job.job_type == "PREDICT"
    assert ml_job.session_id == workout_session.id


def test_workout_start_requires_pre_checkin_args(handler_session, mock_science):
    profile = UserProfile(
        onboarding_complete=True,
        training_split=TrainingSplit.ppl,
        available_equipment=json.dumps(["barbell"]),
        bodyweight_kg=80.0,
        experience_level="intermediate",
        training_days_per_week=4,
        goal="hypertrophy",
        initial_weight_coefficients=json.dumps({"horizontal_push": 70.0}),
    )
    handler_session.add(profile)
    handler_session.flush()

    stdout, exit_code = handle_workout_start([], handler_session, mock_science)

    assert exit_code == 1
    assert "--sleep-hours" in stdout
    assert handler_session.query(WorkoutSession).count() == 0

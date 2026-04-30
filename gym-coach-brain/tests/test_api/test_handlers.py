"""
Tests for api/handlers.py — exercise_add intent handler.
Uses in-memory DB with taxonomy + exercise seed data.
No conftest.py — project convention: each test file defines fixtures locally.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.api.handlers import (
    handle_exercise_add,
    handle_onboarding_answer,
    handle_onboarding_complete,
    handle_onboarding_start,
    handle_volume_report,
    handle_profile_show,
    handle_profile_update_equipment,
    handle_profile_update_split,
    handle_workout_finish,
    handle_workout_log_set,
    handle_workout_post_checkin,
    handle_workout_recap,
    handle_workout_start,
    handle_workout_status,
    handle_workout_summary,
)
from gym_coach_brain.core.science import (
    MethodologiesConfig,
    MethodologySpec,
    PUOSConfig,
    PlanningConfig,
    ProgressionConfig,
    RecoveryConfig,
    ScienceConfig,
    WeeklyVolumeLandmark,
    WeeklyVolumeLandmarksConfig,
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
    WorkoutSet,
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
    weekly_volume_landmarks = WeeklyVolumeLandmarksConfig(
        chest=WeeklyVolumeLandmark(mv=8, mev=10, mav_min=12, mav_max=20, mrv=22),
        back=WeeklyVolumeLandmark(mv=8, mev=10, mav_min=14, mav_max=22, mrv=25),
        shoulders=WeeklyVolumeLandmark(mv=0, mev=8, mav_min=16, mav_max=22, mrv=26),
        trapezius=WeeklyVolumeLandmark(mv=0, mev=6, mav_min=10, mav_max=16, mrv=20),
        biceps=WeeklyVolumeLandmark(mv=5, mev=8, mav_min=14, mav_max=20, mrv=26),
        triceps=WeeklyVolumeLandmark(mv=4, mev=6, mav_min=10, mav_max=14, mrv=18),
        quadriceps=WeeklyVolumeLandmark(mv=6, mev=8, mav_min=12, mav_max=18, mrv=20),
        hamstrings=WeeklyVolumeLandmark(mv=4, mev=6, mav_min=10, mav_max=16, mrv=20),
        glutes=WeeklyVolumeLandmark(mv=0, mev=0, mav_min=4, mav_max=12, mrv=16),
        calves=WeeklyVolumeLandmark(mv=6, mev=8, mav_min=12, mav_max=16, mrv=20),
        abs=WeeklyVolumeLandmark(mv=0, mev=8, mav_min=16, mav_max=20, mrv=25),
        lower_back=WeeklyVolumeLandmark(mv=4, mev=6, mav_min=10, mav_max=14, mrv=16),
    )

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
        weekly_volume_landmarks=weekly_volume_landmarks,
    )
    cfg.__dict__["initial_weight_table"] = {
        "beginner": {
            "horizontal_push": 0.25,
            "vertical_push": 0.18,
            "horizontal_pull": 0.22,
            "vertical_pull": 0.20,
            "squat": 0.40,
            "hinge": 0.35,
            "carry": 0.20,
        },
        "intermediate": {
            "horizontal_push": 0.35,
            "vertical_push": 0.25,
            "horizontal_pull": 0.30,
            "vertical_pull": 0.28,
            "squat": 0.50,
            "hinge": 0.45,
            "carry": 0.25,
        },
    }
    return cfg


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def test_onboarding_start_returns_first_question(onboarding_session, mock_science):
    stdout, exit_code = handle_onboarding_start([], onboarding_session, mock_science)
    assert exit_code == 0
    assert "Вопрос 1/" in stdout
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    assert profile.onboarding_status == "in_progress"
    assert profile.onboarding_current_question_id == "age"


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
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    profile.onboarding_current_question_id = "bodyweight_kg"
    onboarding_session.flush()

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
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    profile.onboarding_current_question_id = "training_split"
    onboarding_session.flush()

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
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    profile.onboarding_current_question_id = "training_split"
    onboarding_session.flush()

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "training_split", "--answer", "invalid"],
        onboarding_session,
        mock_science,
    )
    assert exit_code == 1


def test_onboarding_answer_invalid_experience_level_value(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    profile.onboarding_current_question_id = "experience_level"
    onboarding_session.flush()

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "experience_level", "--answer", "novice"],
        onboarding_session,
        mock_science,
    )
    assert exit_code == 1


def _setup_profile_for_complete(session, science, bodyweight=70.0, experience="intermediate"):
    handle_onboarding_start([], session, science)
    answer_flow = [
        ("age", "29"),
        ("experience_level", experience),
        ("goal", "hypertrophy"),
        ("bodyweight_kg", str(bodyweight)),
        ("equipment", "bodyweight"),
        ("training_days_per_week", "4"),
        ("training_split", "full_body"),
        ("sleep_quality", "good"),
        ("stress_level", "low"),
    ]
    for question_id, answer in answer_flow:
        handle_onboarding_answer(["--question", question_id, "--answer", answer], session, science)


def test_onboarding_complete_computes_weights(onboarding_session, mock_science):
    _setup_profile_for_complete(onboarding_session, mock_science, bodyweight=80.0, experience="intermediate")

    stdout, exit_code = handle_onboarding_complete([], onboarding_session, mock_science)
    assert exit_code == 0

    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    assert profile.onboarding_complete is True
    assert profile.onboarding_status == "completed"
    weights = json.loads(profile.initial_weight_coefficients or "{}")
    assert weights.get("squat") == pytest.approx(40.0, rel=1e-2)


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
    assert "Конкретный инвентарь" in stdout


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
    inventory = json.loads(profile.available_equipment_inventory)
    assert "bodyweight" in eq
    assert "barbell" in eq
    assert "bodyweight" in inventory
    assert "barbell" in inventory


def test_profile_update_equipment_specific_inventory(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_equipment(
        ["--equipment", "smith machine, leg curl machine, lat pulldown, dumbbells, adjustable bench"],
        onboarding_session,
    )
    assert exit_code == 0
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None
    eq = json.loads(profile.available_equipment)
    inventory = json.loads(profile.available_equipment_inventory)
    assert set(eq) == {"machine", "cable", "dumbbell"}
    assert set(inventory) == {
        "smith_machine",
        "leg_curl_machine",
        "high_pulley_cable",
        "dumbbells",
        "adjustable_bench",
    }
    assert "Инвентарь" in stdout


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
    today = _today_iso()
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
        session_date=today,
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


def test_workout_start_without_pre_checkin_args_still_creates_session(handler_session, mock_science):
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

    assert exit_code == 0
    workout_session = handler_session.query(WorkoutSession).one()
    assert workout_session.sleep_hours is None
    assert workout_session.pre_readiness is None


def _create_ready_profile(session: Session) -> UserProfile:
    profile = UserProfile(
        onboarding_complete=True,
        training_split=TrainingSplit.ppl,
        available_equipment=json.dumps(["barbell", "dumbbell", "bodyweight", "pullup_bar"]),
        bodyweight_kg=80.0,
        experience_level="intermediate",
        training_days_per_week=4,
        goal="hypertrophy",
        initial_weight_coefficients=json.dumps(
            {
                "horizontal_push": 70.0,
                "horizontal_pull": 65.0,
                "squat": 80.0,
            }
        ),
    )
    session.add(profile)
    session.flush()
    return profile


def _start_workout(session: Session, science: ScienceConfig) -> WorkoutSession:
    stdout, exit_code = handle_workout_start([], session, science)
    assert exit_code == 0, stdout
    return session.query(WorkoutSession).order_by(WorkoutSession.id.desc()).first()


def test_workout_start_blocks_orphaned_active_session(handler_session, mock_science):
    today = _today_iso()
    _create_ready_profile(handler_session)
    orphan = WorkoutSession(session_date=today, status="active", split_day_label="push")
    handler_session.add(orphan)
    handler_session.flush()

    stdout, exit_code = handle_workout_start([], handler_session, mock_science)

    assert exit_code == 1
    assert "активная" in stdout.lower()
    assert handler_session.info["response_data"]["orphaned_session"] is True
    assert handler_session.info["response_data"]["orphaned_session_id"] == orphan.id
    assert handler_session.query(WorkoutSession).count() == 1


def test_workout_start_requires_confirmation_for_second_session_today(handler_session, mock_science):
    today = _today_iso()
    _create_ready_profile(handler_session)
    completed = WorkoutSession(
        session_date=today,
        status="completed",
        split_day_label="push",
        planned_exercises="[]",
    )
    handler_session.add(completed)
    handler_session.flush()

    stdout, exit_code = handle_workout_start([], handler_session, mock_science)

    assert exit_code == 1
    assert "подтверждения" in stdout.lower()
    assert handler_session.info["response_data"]["second_session_today"] is True
    assert handler_session.info["response_data"]["split_day_label"] == "push"


def test_workout_start_confirmed_second_session_reuses_split_label(handler_session, mock_science):
    today = _today_iso()
    _create_ready_profile(handler_session)
    completed = WorkoutSession(
        session_date=today,
        status="completed",
        split_day_label="pull",
        planned_exercises="[]",
    )
    handler_session.add(completed)
    handler_session.flush()

    stdout, exit_code = handle_workout_start(["--confirm-second"], handler_session, mock_science)

    assert exit_code == 0
    active = (
        handler_session.query(WorkoutSession)
        .filter_by(status="active")
        .order_by(WorkoutSession.id.desc())
        .one()
    )
    assert active.split_day_label == "pull"
    assert "id:" in stdout


def test_workout_start_without_readiness_log_still_enqueues_predict(handler_session, mock_science):
    _create_ready_profile(handler_session)

    stdout, exit_code = handle_workout_start([], handler_session, mock_science)

    assert exit_code == 0
    assert handler_session.query(WorkoutSession).count() == 1
    assert handler_session.query(MLJob).count() == 1


def test_workout_status_returns_error_without_active_session(handler_session):
    stdout, exit_code = handle_workout_status([], handler_session)

    assert exit_code == 1
    assert "не найдена" in stdout.lower()


def test_workout_status_zero_logged_sets_shows_not_started(handler_session, mock_science):
    """workout_status with no logged sets shows ⏳ not started for all exercises. [AC 10]"""
    _create_ready_profile(handler_session)
    _start_workout(handler_session, mock_science)

    stdout, exit_code = handle_workout_status([], handler_session)

    assert exit_code == 0
    assert "⏳ not started" in stdout


def test_workout_status_shows_progress_and_logged_sets(handler_session, mock_science):
    _create_ready_profile(handler_session)
    workout_session = _start_workout(handler_session, mock_science)
    planned = json.loads(workout_session.planned_exercises)
    exercise_id = planned[0]["exercise_id"]

    stdout, exit_code = handle_workout_log_set(
        [
            "--exercise-id", str(exercise_id),
            "--set-number", "1",
            "--weight-kg", "70",
            "--reps", "8",
            "--rir", "2",
        ],
        handler_session,
        mock_science,
    )
    assert exit_code == 0

    stdout, exit_code = handle_workout_status([], handler_session)

    assert exit_code == 0
    assert "✅ 1/" in stdout
    assert "set 1" in stdout


def test_workout_post_checkin_persists_backend_field(handler_session, mock_science):
    _create_ready_profile(handler_session)
    workout_session = _start_workout(handler_session, mock_science)
    # post_checkin requires a completed session
    workout_session.status = "completed"
    handler_session.flush()

    stdout, exit_code = handle_workout_post_checkin(
        ["--session-id", str(workout_session.id), "--post-feeling", "9"],
        handler_session,
    )

    assert exit_code == 0
    handler_session.refresh(workout_session)
    assert workout_session.post_feeling == 9
    assert handler_session.info["response_data"]["session_id"] == workout_session.id
    assert handler_session.info["response_data"]["post_feeling"] == 9
    assert "saved" in stdout.lower()


def test_workout_log_set_validation_duplicate_and_beyond_plan(handler_session, mock_science):
    _create_ready_profile(handler_session)
    workout_session = _start_workout(handler_session, mock_science)
    planned = json.loads(workout_session.planned_exercises)
    exercise = planned[0]
    exercise_id = exercise["exercise_id"]

    stdout, exit_code = handle_workout_log_set(
        [
            "--exercise-id", str(exercise_id),
            "--set-number", "1",
            "--weight-kg", "70",
            "--reps", "8",
            "--rir", "2",
        ],
        handler_session,
        mock_science,
    )
    assert exit_code == 0
    workout_set = handler_session.query(WorkoutSet).one()
    assert workout_set.rir == 2
    assert workout_set.rpe == pytest.approx(8.0)
    assert "Рекомендация" in stdout

    stdout, exit_code = handle_workout_log_set(
        [
            "--exercise-id", str(exercise_id),
            "--set-number", "1",
            "--weight-kg", "70",
            "--reps", "8",
            "--rir", "2",
        ],
        handler_session,
        mock_science,
    )
    assert exit_code == 1

    beyond_plan_set = exercise["sets"] + 1
    stdout, exit_code = handle_workout_log_set(
        [
            "--exercise-id", str(exercise_id),
            "--set-number", str(beyond_plan_set),
            "--weight-kg", "67.5",
            "--reps", "6",
            "--rir", "1",
        ],
        handler_session,
        mock_science,
    )
    assert exit_code == 0
    assert "сверх плана" in stdout.lower()


def test_workout_log_set_rejects_unknown_exercise_and_invalid_values(handler_session, mock_science):
    _create_ready_profile(handler_session)
    _start_workout(handler_session, mock_science)

    stdout, exit_code = handle_workout_log_set(
        [
            "--exercise-id", "9999",
            "--set-number", "1",
            "--weight-kg", "70",
            "--reps", "8",
            "--rir", "2",
        ],
        handler_session,
        mock_science,
    )
    assert exit_code == 1

    stdout, exit_code = handle_workout_log_set(
        [
            "--exercise-id", "1",
            "--set-number", "1",
            "--weight-kg", "-1",
            "--reps", "0",
            "--rir", "7",
        ],
        handler_session,
        mock_science,
    )
    assert exit_code == 1


def test_workout_finish_marks_completed_and_repeated_finish_fails(handler_session, mock_science):
    _create_ready_profile(handler_session)
    workout_session = _start_workout(handler_session, mock_science)
    planned = json.loads(workout_session.planned_exercises)
    exercise_id = planned[0]["exercise_id"]

    stdout, exit_code = handle_workout_log_set(
        [
            "--exercise-id", str(exercise_id),
            "--set-number", "1",
            "--weight-kg", "70",
            "--reps", "8",
            "--rir", "2",
        ],
        handler_session,
        mock_science,
    )
    assert exit_code == 0

    stdout, exit_code = handle_workout_finish([], handler_session, mock_science)

    assert exit_code == 0
    assert "Итоги тренировки" in stdout
    handler_session.refresh(workout_session)
    assert workout_session.status == "completed"

    stdout, exit_code = handle_workout_finish([], handler_session, mock_science)
    assert exit_code == 1


def test_workout_recap_and_summary_delegate_to_adaptation_modules(handler_session, mock_science):
    today = _today_iso()
    _create_ready_profile(handler_session)
    bench = handler_session.query(Exercise).filter_by(name="Bench Press").one()
    completed = WorkoutSession(
        session_date=today,
        status="completed",
        planned_exercises=json.dumps([{"exercise_name": "Bench Press"}]),
        split_day_label="push",
    )
    handler_session.add(completed)
    handler_session.flush()
    handler_session.add(
        WorkoutSet(
            session_id=completed.id,
            exercise_id=bench.id,
            set_number=1,
            weight_kg=80.0,
            reps=8,
            rir=2,
            rpe=8.0,
        )
    )
    handler_session.flush()

    stdout, exit_code = handle_workout_recap([], handler_session)
    assert exit_code == 0
    assert "Bench Press" in stdout

    stdout, exit_code = handle_workout_summary([], handler_session, mock_science)
    assert exit_code == 0
    assert "Итоги тренировки" in stdout

    stdout, exit_code = handle_workout_summary(
        ["--session-id", str(completed.id)],
        handler_session,
        mock_science,
    )
    assert exit_code == 0
    assert "Выполнено подходов" in stdout


def test_workout_summary_returns_error_when_history_missing(handler_session, mock_science):
    stdout, exit_code = handle_workout_summary([], handler_session, mock_science)

    assert exit_code == 1
    assert "пуста" in stdout.lower()


def _create_session_with_sets(
    session: Session,
    *,
    status: str,
    session_date: str,
    exercise_name: str,
    set_count: int,
) -> WorkoutSession:
    exercise = session.query(Exercise).filter_by(name=exercise_name).one()
    workout_session = WorkoutSession(
        session_date=session_date,
        status=status,
        planned_exercises="[]",
    )
    session.add(workout_session)
    session.flush()

    for set_number in range(1, set_count + 1):
        session.add(
            WorkoutSet(
                session_id=workout_session.id,
                exercise_id=exercise.id,
                set_number=set_number,
                weight_kg=80.0,
                reps=8,
                rir=2,
                rpe=8.0,
            )
        )

    session.flush()
    return workout_session


def test_volume_report(handler_session, mock_science):
    today = datetime.now(timezone.utc).date()
    _create_session_with_sets(
        handler_session,
        status="completed",
        session_date=(today - timedelta(days=10)).isoformat(),
        exercise_name="Bench Press",
        set_count=4,
    )
    _create_session_with_sets(
        handler_session,
        status="completed",
        session_date=(today - timedelta(days=2)).isoformat(),
        exercise_name="Bench Press",
        set_count=14,
    )
    _create_session_with_sets(
        handler_session,
        status="completed",
        session_date=(today - timedelta(days=20)).isoformat(),
        exercise_name="Bench Press",
        set_count=10,
    )
    _create_session_with_sets(
        handler_session,
        status="active",
        session_date=(today - timedelta(days=1)).isoformat(),
        exercise_name="Bench Press",
        set_count=10,
    )

    stdout, exit_code = handle_volume_report(["--weeks", "2"], handler_session, mock_science)

    assert exit_code == 0
    assert "Fractional volume report" in stdout
    assert "Lookback: 2 weeks" in stdout
    assert "Completed sessions: 2" in stdout
    assert "chest | total=18.0 | avg_weekly=9.0 | status=below_range" in stdout
    assert "science=MV 8 / MEV 10 / MAV 12-20 / MRV 22 | ⚠️" in stdout
    assert "shoulders | total=9.0 | avg_weekly=4.5 | status=below_range" in stdout


@pytest.mark.parametrize("weeks_value", ["0", "-1", "53", "abc"])
def test_volume_report_rejects_invalid_weeks(handler_session, mock_science, weeks_value):
    stdout, exit_code = handle_volume_report(["--weeks", weeks_value], handler_session, mock_science)

    assert exit_code == 1
    assert "--weeks" in stdout


def test_volume_report_empty_period_returns_clear_message(handler_session, mock_science):
    stdout, exit_code = handle_volume_report(["--weeks", "4"], handler_session, mock_science)

    assert exit_code == 0
    assert "no completed workouts in range" in stdout.lower()


def test_volume_report_no_puos_warning_when_no_session_exceeded_limit(
    handler_session, mock_science
):
    """High total volume but each session stays under PUOS limit → no ⚠️ marker."""
    today = datetime.now(timezone.utc).date()
    # 3 sessions × 8 sets = 24 total chest sets; 8 < 11 (max_sets_per_group) per session
    for days_ago in [2, 5, 8]:
        _create_session_with_sets(
            handler_session,
            status="completed",
            session_date=(today - timedelta(days=days_ago)).isoformat(),
            exercise_name="Bench Press",
            set_count=8,
        )

    stdout, exit_code = handle_volume_report(["--weeks", "2"], handler_session, mock_science)

    assert exit_code == 0
    chest_lines = [line for line in stdout.splitlines() if line.startswith("chest")]
    assert len(chest_lines) == 1
    assert "⚠️" not in chest_lines[0]

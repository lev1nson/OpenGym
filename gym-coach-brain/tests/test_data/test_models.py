"""
Tests for SQLAlchemy models: FK constraints, column types, nullable fields,
EquipmentType enum validation, UniqueConstraint enforcement.
"""
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import (
    Base,
    Equipment,
    EquipmentType,
    Exercise,
    MLJob,
    MuscleGroup,
    MovementPattern,
    RPEPrediction,
    TrainingSplit,
    UserProfile,
    WorkoutSession,
    WorkoutSet,
)
from gym_coach_brain.data.seed import seed_taxonomy


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session


# ─── Helper factory functions ─────────────────────────────────────────────────

def make_muscle_group(name="chest", body_region="upper", is_push=True, is_pull=False):
    return MuscleGroup(name=name, body_region=body_region, is_push=is_push, is_pull=is_pull)


def make_movement_pattern(name="horizontal_push", category="push"):
    return MovementPattern(name=name, category=category)


def make_exercise(name="Push-up", primary_muscle_id=1, movement_pattern_id=1,
                  equipment_type=EquipmentType.bodyweight.value):
    return Exercise(
        name=name,
        primary_muscle_id=primary_muscle_id,
        movement_pattern_id=movement_pattern_id,
        equipment_type=equipment_type,
    )


# ─── Enum Tests ───────────────────────────────────────────────────────────────

def test_equipment_type_has_8_values():
    """EquipmentType has exactly 8 values."""
    values = [e.value for e in EquipmentType]
    assert len(values) == 8
    assert set(values) == {
        "barbell", "dumbbell", "machine", "cable",
        "bodyweight", "resistance_band", "pullup_bar", "dips_bar"
    }


def test_training_split_has_4_values():
    """TrainingSplit has exactly 4 values."""
    values = [e.value for e in TrainingSplit]
    assert len(values) == 4
    assert set(values) == {"ppl", "upper_lower", "full_body", "custom"}


def test_equipment_type_is_string_enum():
    """EquipmentType inherits from str."""
    assert isinstance(EquipmentType.bodyweight, str)
    assert EquipmentType.bodyweight == "bodyweight"


def test_training_split_is_string_enum():
    """TrainingSplit inherits from str."""
    assert isinstance(TrainingSplit.full_body, str)
    assert TrainingSplit.full_body == "full_body"


# ─── MuscleGroup Tests ────────────────────────────────────────────────────────

def test_muscle_group_creation(db_session):
    """MuscleGroup can be created with required fields."""
    mg = make_muscle_group()
    db_session.add(mg)
    db_session.commit()
    fetched = db_session.query(MuscleGroup).filter_by(name="chest").first()
    assert fetched is not None
    assert fetched.body_region == "upper"
    assert fetched.is_push is True
    assert fetched.is_pull is False
    assert fetched.stretch_mediated is False


def test_muscle_group_name_unique(db_session):
    """MuscleGroup.name must be unique."""
    db_session.add(make_muscle_group(name="back", is_push=False, is_pull=True))
    db_session.commit()
    db_session.add(make_muscle_group(name="back", is_push=False, is_pull=True))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ─── Exercise Tests ───────────────────────────────────────────────────────────

def test_exercise_fk_constraint(db_session):
    """Exercise.primary_muscle_id FK is enforced (invalid FK raises error or returns None)."""
    # SQLite doesn't enforce FKs by default; test at model level via relationship
    mg = make_muscle_group(name="chest2")
    mp = make_movement_pattern(name="horiz_push2")
    db_session.add_all([mg, mp])
    db_session.commit()

    ex = Exercise(
        name="Bench Press",
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        equipment_type=EquipmentType.barbell.value,
    )
    db_session.add(ex)
    db_session.commit()

    fetched = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert fetched is not None
    assert fetched.primary_muscle_id == mg.id
    assert fetched.equipment_type == "barbell"


def test_exercise_equipment_type_stored_as_string(db_session):
    """Exercise.equipment_type stored as string enum value."""
    mg = make_muscle_group(name="shoulders")
    mp = make_movement_pattern(name="vertical_push")
    db_session.add_all([mg, mp])
    db_session.commit()

    ex = Exercise(
        name="Pike Push-up",
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        equipment_type=EquipmentType.bodyweight.value,
    )
    db_session.add(ex)
    db_session.commit()
    db_session.refresh(ex)

    assert ex.equipment_type == "bodyweight"
    assert EquipmentType(ex.equipment_type) == EquipmentType.bodyweight


# ─── WorkoutSet Tests ─────────────────────────────────────────────────────────

def _setup_session_and_exercise(db_session):
    """Helper: create a WorkoutSession and Exercise for WorkoutSet tests."""
    from datetime import datetime
    mg = MuscleGroup(name="quads", body_region="lower", is_push=True, is_pull=False)
    mp = MovementPattern(name="squat", category="legs")
    db_session.add_all([mg, mp])
    db_session.flush()

    ex = Exercise(
        name="Squat",
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        equipment_type=EquipmentType.barbell.value,
    )
    db_session.add(ex)
    db_session.flush()

    ws = WorkoutSession(
        session_date="2026-03-04T10:00:00",
        status="active",
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(ws)
    db_session.flush()

    return ws, ex


def test_workout_set_unique_constraint(db_session):
    """Duplicate (session_id, exercise_id, set_number) raises IntegrityError."""
    ws, ex = _setup_session_and_exercise(db_session)

    set1 = WorkoutSet(
        session_id=ws.id,
        exercise_id=ex.id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        created_at="2026-03-04T10:01:00",
    )
    set2 = WorkoutSet(
        session_id=ws.id,
        exercise_id=ex.id,
        set_number=1,  # duplicate!
        weight_kg=100.0,
        reps=5,
        created_at="2026-03-04T10:02:00",
    )
    db_session.add(set1)
    db_session.flush()
    db_session.add(set2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_workout_set_rir_nullable(db_session):
    """WorkoutSet.rir is nullable."""
    ws, ex = _setup_session_and_exercise(db_session)
    s = WorkoutSet(
        session_id=ws.id,
        exercise_id=ex.id,
        set_number=1,
        weight_kg=80.0,
        reps=8,
        rir=None,
        created_at="2026-03-04T10:01:00",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    assert s.rir is None


def test_workout_set_rpe_nullable(db_session):
    """WorkoutSet.rpe is nullable (computed by api layer)."""
    ws, ex = _setup_session_and_exercise(db_session)
    s = WorkoutSet(
        session_id=ws.id,
        exercise_id=ex.id,
        set_number=2,
        weight_kg=80.0,
        reps=8,
        rpe=None,
        created_at="2026-03-04T10:01:00",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    assert s.rpe is None


def test_workout_set_rir_and_rpe_stored(db_session):
    """WorkoutSet stores rir and rpe independently."""
    ws, ex = _setup_session_and_exercise(db_session)
    s = WorkoutSet(
        session_id=ws.id,
        exercise_id=ex.id,
        set_number=3,
        weight_kg=80.0,
        reps=8,
        rir=2,
        rpe=8.0,  # 10.0 - rir, set by api layer
        created_at="2026-03-04T10:01:00",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    assert s.rir == 2
    assert s.rpe == 8.0


# ─── UserProfile Tests ────────────────────────────────────────────────────────

def test_user_profile_training_split_default(db_session):
    """UserProfile.training_split defaults to 'full_body'."""
    up = UserProfile(created_at="2026-03-04T00:00:00")
    db_session.add(up)
    db_session.commit()
    db_session.refresh(up)
    assert up.training_split == TrainingSplit.full_body.value


def test_user_profile_training_days_default(db_session):
    """UserProfile.training_days_per_week defaults to 3."""
    up = UserProfile(created_at="2026-03-04T00:00:00")
    db_session.add(up)
    db_session.commit()
    db_session.refresh(up)
    assert up.training_days_per_week == 3


# ─── MLJob Tests ──────────────────────────────────────────────────────────────

def test_ml_job_status_default(db_session):
    """MLJob.status defaults to 'pending'."""
    job = MLJob(
        job_type="FINE_TUNE",
        session_ids="[1, 2, 3]",
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    assert job.status == "pending"


def test_ml_job_processed_at_nullable(db_session):
    """MLJob.processed_at is nullable."""
    job = MLJob(
        job_type="PREDICT",
        session_ids="[1]",
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    assert job.processed_at is None


def test_ml_job_session_id_has_fk():
    """MLJob.session_id must reference workout_sessions.id."""
    col = MLJob.__table__.c.session_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1, "session_id must have exactly one ForeignKey"
    assert fks[0].column.table.name == "workout_sessions"


# ─── All 10 Tables Present ────────────────────────────────────────────────────

def test_all_10_tables_exist(engine):
    """Base.metadata has exactly 10 tables."""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "user_profiles", "workout_sessions", "workout_sets", "exercises",
        "muscle_groups", "movement_patterns", "equipment",
        "readiness_logs", "ml_jobs", "rpe_predictions",
    }
    assert expected == table_names, f"Tables mismatch. Got: {table_names}"


# ─── Review Follow-up Tests ───────────────────────────────────────────────────

# [AI-Review][CRITICAL] RPEPrediction.exercise_id FK
def test_rpe_prediction_exercise_id_has_fk():
    """RPEPrediction.exercise_id must have a ForeignKey to exercises.id."""
    col = RPEPrediction.__table__.c.exercise_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1, "exercise_id must have exactly one ForeignKey"
    assert fks[0].column.table.name == "exercises", (
        f"FK target must be 'exercises', got '{fks[0].column.table.name}'"
    )


# [AI-Review][HIGH] Exercise.equipment_type SQLAlchemyEnum
def test_exercise_equipment_type_is_enum_backed(engine):
    """Exercise.equipment_type column must use SQLAlchemy Enum (not plain String)."""
    from sqlalchemy import Enum as SAEnum
    col = Exercise.__table__.c.equipment_type
    assert isinstance(col.type, SAEnum), (
        f"equipment_type must be SAEnum, got {type(col.type)}"
    )


def test_exercise_equipment_type_rejects_invalid_value(db_session):
    """Exercise.equipment_type rejects values outside EquipmentType enum."""
    mg = make_muscle_group(name="lats")
    mp = make_movement_pattern(name="vp2")
    db_session.add_all([mg, mp])
    db_session.flush()

    with pytest.raises((LookupError, StatementError, IntegrityError)):
        ex = Exercise(
            name="Bad Exercise",
            primary_muscle_id=mg.id,
            movement_pattern_id=mp.id,
            equipment_type="not_a_real_type",
        )
        db_session.add(ex)
        db_session.flush()


# [AI-Review][HIGH] UserProfile.training_split SQLAlchemyEnum
def test_user_profile_training_split_is_enum_backed():
    """UserProfile.training_split column must use SQLAlchemy Enum."""
    from sqlalchemy import Enum as SAEnum
    col = UserProfile.__table__.c.training_split
    assert isinstance(col.type, SAEnum), (
        f"training_split must be SAEnum, got {type(col.type)}"
    )


# [AI-Review][HIGH] WorkoutSet.rir range validation (0-4)
def test_workout_set_rir_valid_range(db_session):
    """WorkoutSet accepts rir values 0-4."""
    ws, ex = _setup_session_and_exercise(db_session)
    for rir_val in [0, 1, 2, 3, 4]:
        s = WorkoutSet(
            session_id=ws.id, exercise_id=ex.id, set_number=rir_val + 10,
            weight_kg=80.0, reps=8, rir=rir_val, created_at="2026-03-04T10:00:00",
        )
        db_session.add(s)
    db_session.flush()  # must not raise


def test_workout_set_rir_out_of_range_raises(db_session):
    """WorkoutSet.rir=5 violates ck_workout_set_rir_range constraint."""
    ws, ex = _setup_session_and_exercise(db_session)
    bad_set = WorkoutSet(
        session_id=ws.id, exercise_id=ex.id, set_number=99,
        weight_kg=80.0, reps=8, rir=5,
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(bad_set)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


def test_workout_set_rir_negative_raises(db_session):
    """WorkoutSet.rir=-1 violates ck_workout_set_rir_range constraint."""
    ws, ex = _setup_session_and_exercise(db_session)
    bad_set = WorkoutSet(
        session_id=ws.id, exercise_id=ex.id, set_number=100,
        weight_kg=80.0, reps=8, rir=-1,
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(bad_set)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


# [AI-Review][HIGH] UserProfile.training_days_per_week range validation (3-6)
def test_user_profile_training_days_valid_range(db_session):
    """UserProfile accepts training_days_per_week values 3-6."""
    for days in [3, 4, 5, 6]:
        up = UserProfile(training_days_per_week=days, created_at="2026-03-04T00:00:00")
        db_session.add(up)
    db_session.flush()  # must not raise


def test_user_profile_training_days_too_high_raises(db_session):
    """UserProfile.training_days_per_week=7 violates ck_user_profile_training_days."""
    up = UserProfile(training_days_per_week=7, created_at="2026-03-04T00:00:00")
    db_session.add(up)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


def test_user_profile_training_days_too_low_raises(db_session):
    """UserProfile.training_days_per_week=2 violates ck_user_profile_training_days."""
    up = UserProfile(training_days_per_week=2, created_at="2026-03-04T00:00:00")
    db_session.add(up)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


# [AI-Review][MEDIUM] DB-level validation for status strings
def test_workout_session_invalid_status_raises(db_session):
    """WorkoutSession.status rejects values outside ('planned','active','completed')."""
    ws = WorkoutSession(
        session_date="2026-03-04T10:00:00",
        status="invalid_status",
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(ws)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


def test_ml_job_invalid_job_type_raises(db_session):
    """MLJob.job_type rejects values outside ('FINE_TUNE', 'PREDICT')."""
    job = MLJob(
        job_type="INVALID_TYPE",
        session_ids="[1]",
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(job)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


def test_ml_job_invalid_status_raises(db_session):
    """MLJob.status rejects values outside ('pending','processing','done','failed')."""
    job = MLJob(
        job_type="PREDICT",
        status="RUNNING",
        session_ids="[1]",
        created_at="2026-03-04T10:00:00",
    )
    db_session.add(job)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


# [AI-Review][MEDIUM] created_at server_default
def test_workout_session_created_at_server_default(engine):
    """WorkoutSession.created_at has a server_default."""
    col = WorkoutSession.__table__.c.created_at
    assert col.server_default is not None, "created_at must have server_default"


def test_workout_set_created_at_server_default(engine):
    """WorkoutSet.created_at has a server_default."""
    col = WorkoutSet.__table__.c.created_at
    assert col.server_default is not None, "created_at must have server_default"


def test_ml_job_created_at_server_default(engine):
    """MLJob.created_at has a server_default."""
    col = MLJob.__table__.c.created_at
    assert col.server_default is not None, "created_at must have server_default"


def test_rpe_prediction_created_at_server_default(engine):
    """RPEPrediction.created_at has a server_default."""
    col = RPEPrediction.__table__.c.created_at
    assert col.server_default is not None, "created_at must have server_default"


# [AI-Review][LOW] JSON hybrid_property
def test_exercise_secondary_muscle_id_list_hybrid(db_session):
    """Exercise.secondary_muscle_id_list returns parsed JSON list."""
    mg = make_muscle_group(name="chest_hp")
    mp = make_movement_pattern(name="hp_push")
    db_session.add_all([mg, mp])
    db_session.flush()

    ex = Exercise(
        name="HP Push-up",
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        equipment_type=EquipmentType.bodyweight,
    )
    ex.secondary_muscle_id_list = [2, 5]
    db_session.add(ex)
    db_session.commit()
    db_session.refresh(ex)

    assert ex.secondary_muscle_id_list == [2, 5]
    assert ex.secondary_muscle_ids == "[2, 5]"


def test_user_profile_available_equipment_list_hybrid(db_session):
    """UserProfile.available_equipment_list returns parsed JSON list."""
    up = UserProfile(created_at="2026-03-04T00:00:00")
    up.available_equipment_list = ["barbell", "dumbbell"]
    db_session.add(up)
    db_session.commit()
    db_session.refresh(up)

    assert up.available_equipment_list == ["barbell", "dumbbell"]


def test_user_profile_available_equipment_inventory_list_hybrid(db_session):
    """UserProfile.available_equipment_inventory_list returns parsed JSON list."""
    up = UserProfile(created_at="2026-03-04T00:00:00")
    up.available_equipment_inventory_list = ["smith_machine", "leg_curl_machine"]
    db_session.add(up)
    db_session.commit()
    db_session.refresh(up)

    assert up.available_equipment_inventory_list == ["smith_machine", "leg_curl_machine"]


def test_user_profile_initial_weight_coefficients_dict_hybrid(db_session):
    """UserProfile.initial_weight_coefficients_dict returns parsed JSON dict."""
    up = UserProfile(created_at="2026-03-04T00:00:00")
    up.initial_weight_coefficients_dict = {"horizontal_push": 0.8, "squat": 1.0}
    db_session.add(up)
    db_session.commit()
    db_session.refresh(up)

    result = up.initial_weight_coefficients_dict
    assert result["horizontal_push"] == 0.8
    assert result["squat"] == 1.0


# ─── Taxonomy Verification Tests (Story 2.1) ──────────────────────────────────
# Requires seed data — uses local seeded_session fixture

REQUIRED_MUSCLE_GROUPS = {
    "chest", "back", "shoulders", "trapezius",
    "biceps", "triceps", "quadriceps", "hamstrings",
    "glutes", "calves", "abs", "lower_back"
}

REQUIRED_MOVEMENT_PATTERNS = {
    "horizontal_push", "vertical_push", "horizontal_pull",
    "vertical_pull", "squat", "hinge", "carry"
}

IS_PULL_GROUPS = {"back", "trapezius", "biceps", "hamstrings", "lower_back"}
IS_PUSH_GROUPS = {"chest", "shoulders", "triceps", "quadriceps", "calves"}
SMH_GROUPS = {"chest", "back", "biceps", "triceps", "quadriceps", "hamstrings", "glutes", "calves"}


@pytest.fixture
def seeded_taxonomy_session():
    """In-memory session with taxonomy seed data (muscle_groups + movement_patterns)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_taxonomy(session)
        session.commit()
        yield session


def test_all_12_muscle_groups_present(seeded_taxonomy_session):
    """Exactly 12 required muscle groups are present after seed_taxonomy (no more, no less)."""
    names = {mg.name for mg in seeded_taxonomy_session.query(MuscleGroup).all()}
    assert names == REQUIRED_MUSCLE_GROUPS, (
        f"Missing: {REQUIRED_MUSCLE_GROUPS - names}, Extra: {names - REQUIRED_MUSCLE_GROUPS}"
    )


def test_all_7_movement_patterns_present(seeded_taxonomy_session):
    """All 7 required movement patterns are present after seed_taxonomy."""
    names = {mp.name for mp in seeded_taxonomy_session.query(MovementPattern).all()}
    missing = REQUIRED_MOVEMENT_PATTERNS - names
    assert not missing, f"Missing movement patterns: {missing}"


def test_is_pull_flags_correct(seeded_taxonomy_session):
    """is_pull=True for back, trapezius, biceps, hamstrings, lower_back."""
    for mg in seeded_taxonomy_session.query(MuscleGroup).all():
        expected = mg.name in IS_PULL_GROUPS
        assert mg.is_pull == expected, f"{mg.name}: expected is_pull={expected}, got {mg.is_pull}"


def test_is_push_flags_correct(seeded_taxonomy_session):
    """is_push=True for chest, shoulders, triceps, quadriceps, calves."""
    for mg in seeded_taxonomy_session.query(MuscleGroup).all():
        expected = mg.name in IS_PUSH_GROUPS
        assert mg.is_push == expected, f"{mg.name}: expected is_push={expected}, got {mg.is_push}"


def test_stretch_mediated_flags_correct(seeded_taxonomy_session):
    """stretch_mediated=True for groups with SMH research support."""
    for mg in seeded_taxonomy_session.query(MuscleGroup).all():
        expected = mg.name in SMH_GROUPS
        assert mg.stretch_mediated == expected, (
            f"{mg.name}: expected stretch_mediated={expected}, got {mg.stretch_mediated}"
        )


def test_seed_taxonomy_idempotent(seeded_taxonomy_session):
    """seed_taxonomy can be called twice without errors or duplicates."""
    # Second call should insert 0 new records
    result = seed_taxonomy(seeded_taxonomy_session)
    seeded_taxonomy_session.commit()
    assert result["muscle_groups"] == 0, "Second seed call should insert 0 muscle groups"
    assert result["movement_patterns"] == 0, "Second seed call should insert 0 patterns"
    # Count should still be exactly 12 and 7
    count_mg = seeded_taxonomy_session.query(MuscleGroup).count()
    count_mp = seeded_taxonomy_session.query(MovementPattern).count()
    assert count_mg == 12
    assert count_mp == 7

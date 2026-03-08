"""
Tests that verify seed data coverage requirements:
- Every MuscleGroup has at least one Exercise with equipment_type=bodyweight
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import (
    Base,
    Equipment,
    EquipmentType,
    Exercise,
    MLJob,
    MovementPattern,
    MuscleGroup,
)


# ─── Seed helper (replicates 002_seed_data upgrade logic for in-memory tests) ──

def apply_seed_data(conn):
    """Apply seed data directly to an in-memory database (mirrors 002_seed_data.py)."""
    conn.execute(text("""
        INSERT INTO muscle_groups (name, body_region, is_push, is_pull, stretch_mediated) VALUES
        ('chest',      'upper', 1, 0, 1),
        ('back',       'upper', 0, 1, 1),
        ('shoulders',  'upper', 1, 0, 0),
        ('biceps',     'upper', 0, 1, 1),
        ('triceps',    'upper', 1, 0, 1),
        ('quadriceps', 'lower', 1, 0, 1),
        ('hamstrings', 'lower', 0, 1, 1),
        ('glutes',     'lower', 0, 0, 1),
        ('calves',     'lower', 1, 0, 1),
        ('abs',        'core',  0, 0, 0),
        ('trapezius',  'upper', 0, 1, 0),
        ('lower_back', 'core',  0, 1, 0)
    """))
    conn.execute(text("""
        INSERT INTO movement_patterns (name, category) VALUES
        ('horizontal_push', 'push'),
        ('vertical_push',   'push'),
        ('horizontal_pull', 'pull'),
        ('vertical_pull',   'pull'),
        ('squat',           'legs'),
        ('hinge',           'legs'),
        ('carry',           'carry')
    """))
    conn.execute(text("""
        INSERT INTO equipment (name, type, available_home, available_gym) VALUES
        ('Barbell',           'barbell',          0, 1),
        ('Dumbbell (pair)',   'dumbbell',          1, 1),
        ('Cable Machine',     'cable',             0, 1),
        ('Resistance Band',   'resistance_band',   1, 1),
        ('Pull-up Bar',       'pullup_bar',         1, 1),
        ('Dip Bars',          'dips_bar',           1, 1),
        ('Smith Machine',     'machine',            0, 1),
        ('Leg Press Machine', 'machine',            0, 1),
        ('Cable Fly Station', 'cable',              0, 1),
        ('Bodyweight',        'bodyweight',         1, 1)
    """))
    # Resolve name → id for all muscle groups and movement patterns
    mg_ids = {
        name: conn.execute(text("SELECT id FROM muscle_groups WHERE name=:n"), {"n": name}).scalar()
        for name in (
            "chest", "back", "shoulders", "biceps", "triceps",
            "quadriceps", "hamstrings", "glutes", "calves", "abs",
            "trapezius", "lower_back",
        )
    }
    mp_ids = {
        name: conn.execute(text("SELECT id FROM movement_patterns WHERE name=:n"), {"n": name}).scalar()
        for name in (
            "horizontal_push", "vertical_push", "horizontal_pull",
            "vertical_pull", "squat", "hinge", "carry",
        )
    }

    # (name, primary_muscle, movement_pattern, secondary_muscle_ids, is_compound, stretch_mediated, equipment_type)
    exercises = [
        ("Push-up",               "chest",       "horizontal_push", "[]",     1, 1, "bodyweight"),
        ("Bench Press",           "chest",       "horizontal_push", "[]",     1, 1, "barbell"),
        ("Dumbbell Fly",          "chest",       "horizontal_push", "[]",     0, 1, "dumbbell"),
        ("Incline Dumbbell Press","chest",       "horizontal_push", "[]",     1, 1, "dumbbell"),
        ("Inverted Row",          "back",        "horizontal_pull", "[]",     1, 1, "bodyweight"),
        ("Pull-up",               "back",        "vertical_pull",   "[]",     1, 1, "pullup_bar"),
        ("Barbell Row",           "back",        "horizontal_pull", "[]",     1, 1, "barbell"),
        ("Cable Row",             "back",        "horizontal_pull", "[]",     1, 0, "cable"),
        ("Deadlift",              "back",        "hinge",           "[]",     1, 1, "barbell"),
        ("Pike Push-up",          "shoulders",   "vertical_push",   "[]",     0, 0, "bodyweight"),
        ("Overhead Press",        "shoulders",   "vertical_push",   "[]",     1, 0, "barbell"),
        ("Lateral Raise",         "shoulders",   "vertical_push",   "[]",     0, 0, "dumbbell"),
        ("Bodyweight Chin-up",    "biceps",      "vertical_pull",   "[]",     1, 1, "bodyweight"),
        ("Chin-up",               "biceps",      "vertical_pull",   "[]",     1, 1, "pullup_bar"),
        ("Dumbbell Curl",         "biceps",      "horizontal_pull", "[]",     0, 1, "dumbbell"),
        ("Resistance Band Curl",  "biceps",      "horizontal_pull", "[]",     0, 1, "resistance_band"),
        ("Dip",                   "triceps",     "horizontal_push", "[]",     1, 1, "dips_bar"),
        ("Diamond Push-up",       "triceps",     "horizontal_push", "[]",     0, 1, "bodyweight"),
        ("Tricep Pushdown",       "triceps",     "horizontal_push", "[]",     0, 1, "cable"),
        ("Bodyweight Squat",      "quadriceps",  "squat",           "[]",     1, 1, "bodyweight"),
        ("Barbell Squat",         "quadriceps",  "squat",           "[]",     1, 1, "barbell"),
        ("Leg Press",             "quadriceps",  "squat",           "[]",     1, 1, "machine"),
        ("Nordic Curl",           "hamstrings",  "hinge",           "[]",     0, 1, "bodyweight"),
        ("Romanian Deadlift",     "hamstrings",  "hinge",           "[]",     1, 1, "barbell"),
        ("Good Morning",          "hamstrings",  "hinge",           "[]",     1, 1, "barbell"),
        ("Glute Bridge",          "glutes",      "hinge",           "[]",     0, 1, "bodyweight"),
        ("Hip Thrust",            "glutes",      "hinge",           "[]",     1, 1, "barbell"),
        ("Cable Pull-Through",    "glutes",      "hinge",           "[]",     0, 1, "cable"),
        ("Calf Raise (standing)", "calves",      "squat",           "[]",     0, 1, "bodyweight"),
        ("Seated Calf Raise",     "calves",      "squat",           "[]",     0, 1, "machine"),
        ("Dumbbell Calf Raise",   "calves",      "squat",           "[]",     0, 1, "dumbbell"),
        ("Plank",                 "abs",         "carry",           "[]",     0, 0, "bodyweight"),
        ("Hanging Leg Raise",     "abs",         "vertical_pull",   "[]",     0, 0, "pullup_bar"),
        ("Ab Wheel Rollout",      "abs",         "carry",           "[]",     0, 1, "bodyweight"),
        ("Prone Y-Raise",         "trapezius",   "carry",           "[]",     0, 0, "bodyweight"),
        ("Superman Hold",         "lower_back",  "hinge",           "[]",     0, 0, "bodyweight"),
    ]
    for name, mg_name, mp_name, sec_ids, compound, stretch, equip in exercises:
        conn.execute(text("""
            INSERT INTO exercises
                (name, primary_muscle_id, movement_pattern_id,
                 secondary_muscle_ids, is_compound, stretch_mediated, equipment_type)
            SELECT :name, :mg_id, :mp_id, :sec, :compound, :stretch, :equip
            WHERE NOT EXISTS (SELECT 1 FROM exercises WHERE name=:name)
        """), {
            "name": name, "mg_id": mg_ids[mg_name], "mp_id": mp_ids[mp_name],
            "sec": sec_ids, "compound": compound, "stretch": stretch, "equip": equip,
        })
    conn.commit()


@pytest.fixture(scope="module")
def seeded_engine():
    """In-memory engine with schema + seed data applied."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        apply_seed_data(conn)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session_with_seed(seeded_engine):
    with Session(seeded_engine) as session:
        yield session


# ─── Coverage Tests ───────────────────────────────────────────────────────────

def test_muscle_groups_count(db_session_with_seed):
    """At least 12 MuscleGroups seeded."""
    count = db_session_with_seed.query(MuscleGroup).count()
    assert count >= 12, f"Expected ≥12 muscle groups, got {count}"


def test_movement_patterns_count(db_session_with_seed):
    """Exactly 7 MovementPatterns seeded."""
    count = db_session_with_seed.query(MovementPattern).count()
    assert count == 7, f"Expected 7 movement patterns, got {count}"


def test_equipment_count(db_session_with_seed):
    """At least 10 Equipment records seeded."""
    count = db_session_with_seed.query(Equipment).count()
    assert count >= 10, f"Expected ≥10 equipment records, got {count}"


def test_exercises_count(db_session_with_seed):
    """At least 30 exercises seeded."""
    count = db_session_with_seed.query(Exercise).count()
    assert count >= 30, f"Expected ≥30 exercises, got {count}"


def test_each_muscle_group_has_bodyweight_exercise(db_session_with_seed):
    """Every MuscleGroup has at least one Exercise with equipment_type=bodyweight."""
    muscle_groups = db_session_with_seed.query(MuscleGroup).all()
    assert len(muscle_groups) >= 12

    for mg in muscle_groups:
        bodyweight_count = (
            db_session_with_seed.query(Exercise)
            .filter(
                Exercise.primary_muscle_id == mg.id,
                Exercise.equipment_type == EquipmentType.bodyweight.value,
            )
            .count()
        )
        assert bodyweight_count >= 1, (
            f"No bodyweight exercise for muscle group '{mg.name}' (id={mg.id})"
        )


def test_all_7_movement_patterns_present(db_session_with_seed):
    """All 7 required movement patterns are present."""
    expected_patterns = {
        "horizontal_push", "vertical_push", "horizontal_pull",
        "vertical_pull", "squat", "hinge", "carry"
    }
    actual_patterns = {
        mp.name for mp in db_session_with_seed.query(MovementPattern).all()
    }
    assert expected_patterns == actual_patterns


def test_equipment_types_coverage(db_session_with_seed):
    """At least one equipment of each core type is seeded."""
    core_types = {"barbell", "dumbbell", "cable", "bodyweight", "pullup_bar", "dips_bar"}
    seeded_types = {
        eq.type for eq in db_session_with_seed.query(Equipment).all()
    }
    missing = core_types - seeded_types
    assert not missing, f"Missing equipment types: {missing}"


def test_exercises_have_valid_equipment_types(db_session_with_seed):
    """All exercises have valid EquipmentType values."""
    valid_values = {e.value for e in EquipmentType}
    exercises = db_session_with_seed.query(Exercise).all()
    for ex in exercises:
        assert ex.equipment_type in valid_values, (
            f"Exercise '{ex.name}' has invalid equipment_type: {ex.equipment_type}"
        )

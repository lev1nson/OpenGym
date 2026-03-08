"""
Tests for Story 2.2: Exercise library with secondary muscle metadata.
Uses fresh in-memory DB — no dependency on Alembic migrations.
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import Base, Exercise, MuscleGroup, MovementPattern, Equipment
from gym_coach_brain.data.seed import seed_taxonomy, seed_exercises, seed_equipment, seed_all
from gym_coach_brain.core.puos import fractional_volume


REQUIRED_PATTERNS = {
    "horizontal_push", "vertical_push", "horizontal_pull",
    "vertical_pull", "squat", "hinge", "carry"
}


@pytest.fixture
def seeded_exercise_session():
    """In-memory session with taxonomy + equipment + exercises seed data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
        yield session


def test_seed_equipment_seeded_correctly(seeded_exercise_session):
    """At least 10 Equipment records are seeded. [Story 2.3 AC]"""
    count = seeded_exercise_session.query(Equipment).count()
    assert count >= 10, f"Expected ≥10 equipment records, got {count}"
    
    # Check for specific equipment type mentioned in AC
    types = {eq.type for eq in seeded_exercise_session.query(Equipment).all()}
    expected_types = {"barbell", "dumbbell", "cable", "resistance_band", "pullup_bar", "dips_bar", "machine", "bodyweight"}
    missing = expected_types - types
    assert not missing, f"Missing equipment types: {missing}"


def test_seed_equipment_idempotent(seeded_exercise_session):
    """seed_equipment can be called twice without errors or duplicates."""
    # Second call should insert 0 new records
    touched = seed_equipment(seeded_exercise_session)
    assert touched == 0, f"Second seed_equipment call touched {touched} (expected 0)"


def test_exercises_total_count_at_least_35(seeded_exercise_session):
    count = seeded_exercise_session.query(Exercise).count()
    assert count >= 35, f"Expected ≥35 exercises, got {count}"


def test_all_patterns_have_at_least_4_exercises(seeded_exercise_session):
    patterns = seeded_exercise_session.query(MovementPattern).all()
    for pattern in patterns:
        count = (
            seeded_exercise_session.query(Exercise)
            .filter(Exercise.movement_pattern_id == pattern.id)
            .count()
        )
        assert count >= 4, f"Pattern '{pattern.name}' has only {count} exercises (expected ≥4)"


def test_carry_pattern_at_least_2_exercises(seeded_exercise_session):
    """Carry pattern exception: 2-4 exercises allowed by nature of the pattern."""
    pattern = seeded_exercise_session.query(MovementPattern).filter_by(name="carry").first()
    count = (
        seeded_exercise_session.query(Exercise)
        .filter(Exercise.movement_pattern_id == pattern.id)
        .count()
    )
    assert count >= 2, f"Carry pattern has only {count} exercises (expected ≥2)"


def test_fractional_volume_bench_press_primary(seeded_exercise_session):
    """Bench Press primary = chest → fractional_volume == 1.0 [domain-research §8.1]"""
    exercise = seeded_exercise_session.query(Exercise).filter_by(name="Bench Press").first()
    chest = seeded_exercise_session.query(MuscleGroup).filter_by(name="chest").first()
    assert exercise is not None, "Bench Press not found in seed"
    result = fractional_volume(exercise.id, chest.id, seeded_exercise_session)
    assert result == 1.0, f"Bench Press/chest: expected 1.0, got {result}"


def test_fractional_volume_bench_press_synergist(seeded_exercise_session):
    """Bench Press secondary = [shoulders, triceps] → 0.5 each [domain-research §8.1]"""
    exercise = seeded_exercise_session.query(Exercise).filter_by(name="Bench Press").first()
    triceps = seeded_exercise_session.query(MuscleGroup).filter_by(name="triceps").first()
    result = fractional_volume(exercise.id, triceps.id, seeded_exercise_session)
    assert result == 0.5, f"Bench Press/triceps: expected 0.5, got {result}"


def test_fractional_volume_bench_press_unrelated(seeded_exercise_session):
    """Bench Press has no back contribution → 0.0"""
    exercise = seeded_exercise_session.query(Exercise).filter_by(name="Bench Press").first()
    back = seeded_exercise_session.query(MuscleGroup).filter_by(name="back").first()
    result = fractional_volume(exercise.id, back.id, seeded_exercise_session)
    assert result == 0.0, f"Bench Press/back: expected 0.0, got {result}"


def test_fractional_volume_pull_up_primary(seeded_exercise_session):
    """Pull-up primary = back → 1.0 [domain-research §8.6]"""
    exercise = seeded_exercise_session.query(Exercise).filter_by(name="Pull-up").first()
    back = seeded_exercise_session.query(MuscleGroup).filter_by(name="back").first()
    result = fractional_volume(exercise.id, back.id, seeded_exercise_session)
    assert result == 1.0, f"Pull-up/back: expected 1.0, got {result}"


def test_fractional_volume_pull_up_synergist(seeded_exercise_session):
    """Pull-up secondary = [biceps, trapezius] → 0.5 [domain-research §8.6]"""
    exercise = seeded_exercise_session.query(Exercise).filter_by(name="Pull-up").first()
    biceps = seeded_exercise_session.query(MuscleGroup).filter_by(name="biceps").first()
    result = fractional_volume(exercise.id, biceps.id, seeded_exercise_session)
    assert result == 0.5, f"Pull-up/biceps: expected 0.5, got {result}"


def test_fractional_volume_ohp_trapezius_synergist(seeded_exercise_session):
    """Overhead Press secondary includes trapezius → 0.5 [domain-research §8.4]"""
    exercise = seeded_exercise_session.query(Exercise).filter_by(name="Overhead Press").first()
    trapezius = seeded_exercise_session.query(MuscleGroup).filter_by(name="trapezius").first()
    result = fractional_volume(exercise.id, trapezius.id, seeded_exercise_session)
    assert result == 0.5, f"OHP/trapezius: expected 0.5, got {result}"


def test_secondary_muscle_ids_valid_json(seeded_exercise_session):
    """All exercises have valid JSON in secondary_muscle_ids."""
    exercises = seeded_exercise_session.query(Exercise).all()
    for ex in exercises:
        try:
            ids = json.loads(ex.secondary_muscle_ids)
            assert isinstance(ids, list), f"'{ex.name}' secondary_muscle_ids not a list"
        except (json.JSONDecodeError, TypeError) as e:
            pytest.fail(f"'{ex.name}' has invalid JSON in secondary_muscle_ids: {e}")


def test_secondary_muscle_ids_reference_valid_groups(seeded_exercise_session):
    """All IDs in secondary_muscle_ids exist in muscle_groups table."""
    valid_ids = {mg.id for mg in seeded_exercise_session.query(MuscleGroup).all()}
    exercises = seeded_exercise_session.query(Exercise).all()
    for ex in exercises:
        secondary_ids = json.loads(ex.secondary_muscle_ids or "[]")
        for mid in secondary_ids:
            assert mid in valid_ids, (
                f"'{ex.name}' secondary_muscle_ids contains invalid MuscleGroup id={mid}"
            )


def test_seed_exercises_idempotent(seeded_exercise_session):
    """Second call to seed_exercises inserts 0 new exercises (all already set)."""
    touched = seed_exercises(seeded_exercise_session)
    assert touched == 0, f"Second seed_exercises call touched {touched} (expected 0)"


def test_seed_exercises_backfill_logic(seeded_exercise_session):
    """Test that existing exercises with '[]' are updated with secondary muscles, pattern, and primary correction."""
    # Create an exercise that mimics Alembic seed (secondary=[])
    mg_wrong = seeded_exercise_session.query(MuscleGroup).filter_by(name="back").first()
    mg_correct = seeded_exercise_session.query(MuscleGroup).filter_by(name="chest").first()
    # Wrong pattern initially
    mp_wrong = seeded_exercise_session.query(MovementPattern).filter_by(name="vertical_pull").first()
    mp_correct = seeded_exercise_session.query(MovementPattern).filter_by(name="horizontal_push").first()
    
    new_ex = Exercise(
        name="Test Backfill Exercise",
        primary_muscle_id=mg_wrong.id,
        movement_pattern_id=mp_wrong.id,
        secondary_muscle_ids="[]",
        is_compound=True,
        stretch_mediated=True,
        equipment_type="barbell"
    )
    seeded_exercise_session.add(new_ex)
    seeded_exercise_session.commit()

    # Define the same exercise in a temporary list to "seed" it
    from gym_coach_brain.data import seed
    original_exercises = seed._EXERCISES
    try:
        seed._EXERCISES = [("Test Backfill Exercise", "chest", "horizontal_push", ["triceps"], True, True, "barbell")]
        touched = seed_exercises(seeded_exercise_session)
        assert touched == 1
        
        updated = seeded_exercise_session.query(Exercise).filter_by(name="Test Backfill Exercise").first()
        assert updated.primary_muscle_id == mg_correct.id
        assert updated.movement_pattern_id == mp_correct.id
        assert json.loads(updated.secondary_muscle_ids) == [
            seeded_exercise_session.query(MuscleGroup).filter_by(name="triceps").first().id
        ]
    finally:
        seed._EXERCISES = original_exercises


def test_deadlift_primary_is_glutes(seeded_exercise_session):
    """Deadlift primary muscle should be 'glutes' for science accuracy."""
    deadlift = seeded_exercise_session.query(Exercise).filter_by(name="Deadlift").first()
    glutes = seeded_exercise_session.query(MuscleGroup).filter_by(name="glutes").first()
    assert deadlift.primary_muscle_id == glutes.id


def test_fractional_volume_invalid_ids(seeded_exercise_session):
    """fractional_volume returns 0.0 for invalid exercise_id."""
    mg = seeded_exercise_session.query(MuscleGroup).first()
    result = fractional_volume(9999, mg.id, seeded_exercise_session)
    assert result == 0.0


def test_fractional_volume_missing_secondary(seeded_exercise_session):
    """fractional_volume handles missing or null secondary_muscle_ids gracefully."""
    mg_primary = seeded_exercise_session.query(MuscleGroup).filter_by(name="chest").first()
    mg_other = seeded_exercise_session.query(MuscleGroup).filter_by(name="back").first()
    
    ex = Exercise(
        name="Null Secondary Exercise",
        primary_muscle_id=mg_primary.id,
        movement_pattern_id=seeded_exercise_session.query(MovementPattern).first().id,
        secondary_muscle_ids=None,
        is_compound=False,
        stretch_mediated=False,
        equipment_type="bodyweight"
    )
    seeded_exercise_session.add(ex)
    seeded_exercise_session.commit()
    
    result = fractional_volume(ex.id, mg_other.id, seeded_exercise_session)
    assert result == 0.0

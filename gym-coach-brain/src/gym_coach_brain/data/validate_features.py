"""
ML feature vector schema validator.

Usage:
    python -m gym_coach_brain.data.validate_features

Validates that all tables and columns required for feature vector assembly
exist in the database schema. Exits 0 on success, 1 on failure.
"""
import sys

from sqlalchemy import create_engine, inspect

from gym_coach_brain.data.models import Base, EquipmentType


# Feature vector schema requirements:
# {table_name: [required_columns]}
REQUIRED_SCHEMA = {
    "exercises": [
        "id", "primary_muscle_id", "movement_pattern_id",
        "is_compound", "stretch_mediated", "equipment_type",
    ],
    "muscle_groups": ["id", "name"],
    "movement_patterns": ["id", "name"],
    "workout_sets": [
        "id", "session_id", "exercise_id",
        "set_number", "weight_kg", "reps", "rpe",
    ],
    "workout_sessions": ["id", "session_date", "status", "sleep_hours", "pre_readiness"],
    "readiness_logs": ["id", "session_date", "recovery_score"],
}

# Expected EquipmentType enum values for feature encoding
EXPECTED_EQUIPMENT_TYPES = sorted(e.value for e in EquipmentType)


def validate_schema(engine) -> list[str]:
    """Return list of validation errors. Empty list = success."""
    errors: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, required_cols in REQUIRED_SCHEMA.items():
        if table not in existing_tables:
            errors.append(f"MISSING TABLE: {table}")
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table)}
        for col in required_cols:
            if col not in existing_cols:
                errors.append(f"MISSING COLUMN: {table}.{col}")

    # Validate equipment type ordering consistency (feature encoding depends on this)
    if len(EXPECTED_EQUIPMENT_TYPES) != 8:
        errors.append(
            f"EquipmentType enum has {len(EXPECTED_EQUIPMENT_TYPES)} values, expected 8. "
            f"feature encoding depends on stable ordering."
        )

    return errors


if __name__ == "__main__":
    # Use database URL if provided, otherwise default to gym_coach.sqlite
    # To truly validate migrations, we do NOT call Base.metadata.create_all(engine)
    # when checking a real file — we want to ensure Alembic did its job.
    db_url = sys.argv[1] if len(sys.argv) > 1 else "sqlite:///gym_coach.sqlite"
    
    # If using memory, we create it for unit test purposes
    engine = create_engine(db_url)
    if ":memory:" in db_url:
        Base.metadata.create_all(engine)

    errors = validate_schema(engine)

    if errors:
        print(f"❌ Feature schema validation FAILED for {db_url}:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"✅ Feature schema validation PASSED for {db_url}")
    print(f"   Tables verified: {list(REQUIRED_SCHEMA.keys())}")
    print(f"   Equipment types ({len(EXPECTED_EQUIPMENT_TYPES)}): {EXPECTED_EQUIPMENT_TYPES}")
    sys.exit(0)

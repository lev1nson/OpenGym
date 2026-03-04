"""seed_data

Revision ID: 20b31ec66e8e
Revises: 4463cdaca3c1
Create Date: 2026-03-04 12:56:40.098240

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20b31ec66e8e'
down_revision: Union[str, Sequence[str], None] = '4463cdaca3c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed reference data: MuscleGroups, MovementPatterns, Equipment, Exercises."""
    conn = op.get_bind()

    # ─── Muscle Groups (10) ────────────────────────────────────────────────────
    conn.execute(sa.text("""
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
        ('abs',        'core',  0, 0, 0)
    """))

    # ─── Movement Patterns (7) ─────────────────────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO movement_patterns (name, category) VALUES
        ('horizontal_push', 'push'),
        ('vertical_push',   'push'),
        ('horizontal_pull', 'pull'),
        ('vertical_pull',   'pull'),
        ('squat',           'legs'),
        ('hinge',           'legs'),
        ('carry',           'carry')
    """))

    # ─── Equipment (10+) ──────────────────────────────────────────────────────
    conn.execute(sa.text("""
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

    # ─── Exercises (34) ───────────────────────────────────────────────────────
    # Uses name-based subqueries instead of hardcoded integer IDs — robust
    # against re-seeding or ID sequence changes.
    exercises = [
        # CHEST — bodyweight: Push-up
        ("Push-up",                "chest",      "horizontal_push", "[5]",     1, 1, "bodyweight"),
        ("Bench Press",            "chest",      "horizontal_push", "[3,5]",   1, 1, "barbell"),
        ("Dumbbell Fly",           "chest",      "horizontal_push", "[]",      0, 1, "dumbbell"),
        ("Incline Dumbbell Press", "chest",      "horizontal_push", "[3,5]",   1, 1, "dumbbell"),

        # BACK — bodyweight: Inverted Row
        ("Inverted Row",           "back",       "horizontal_pull", "[4]",     1, 1, "bodyweight"),
        ("Pull-up",                "back",       "vertical_pull",   "[4]",     1, 1, "pullup_bar"),
        ("Barbell Row",            "back",       "horizontal_pull", "[4]",     1, 1, "barbell"),
        ("Cable Row",              "back",       "horizontal_pull", "[4]",     1, 0, "cable"),
        ("Deadlift",               "back",       "hinge",           "[7,8]",   1, 1, "barbell"),

        # SHOULDERS — bodyweight: Pike Push-up
        ("Pike Push-up",           "shoulders",  "vertical_push",   "[5]",     0, 0, "bodyweight"),
        ("Overhead Press",         "shoulders",  "vertical_push",   "[5]",     1, 0, "barbell"),
        ("Lateral Raise",          "shoulders",  "vertical_push",   "[]",      0, 0, "dumbbell"),

        # BICEPS — bodyweight: Bodyweight Chin-up
        ("Bodyweight Chin-up",     "biceps",     "vertical_pull",   "[2]",     1, 1, "bodyweight"),
        ("Chin-up",                "biceps",     "vertical_pull",   "[2]",     1, 1, "pullup_bar"),
        ("Dumbbell Curl",          "biceps",     "horizontal_pull", "[]",      0, 1, "dumbbell"),
        ("Resistance Band Curl",   "biceps",     "horizontal_pull", "[]",      0, 1, "resistance_band"),

        # TRICEPS — bodyweight: Diamond Push-up
        ("Dip",                    "triceps",    "horizontal_push", "[1,3]",   1, 1, "dips_bar"),
        ("Diamond Push-up",        "triceps",    "horizontal_push", "[1]",     0, 1, "bodyweight"),
        ("Tricep Pushdown",        "triceps",    "horizontal_push", "[]",      0, 1, "cable"),

        # QUADRICEPS — bodyweight: Bodyweight Squat
        ("Bodyweight Squat",       "quadriceps", "squat",           "[8]",     1, 1, "bodyweight"),
        ("Barbell Squat",          "quadriceps", "squat",           "[7,8]",   1, 1, "barbell"),
        ("Leg Press",              "quadriceps", "squat",           "[8]",     1, 1, "machine"),

        # HAMSTRINGS — bodyweight: Nordic Curl
        ("Nordic Curl",            "hamstrings", "hinge",           "[8]",     0, 1, "bodyweight"),
        ("Romanian Deadlift",      "hamstrings", "hinge",           "[8]",     1, 1, "barbell"),
        ("Good Morning",           "hamstrings", "hinge",           "[2]",     1, 1, "barbell"),

        # GLUTES — bodyweight: Glute Bridge
        ("Glute Bridge",           "glutes",     "hinge",           "[7]",     0, 1, "bodyweight"),
        ("Hip Thrust",             "glutes",     "hinge",           "[7]",     1, 1, "barbell"),
        ("Cable Pull-Through",     "glutes",     "hinge",           "[7]",     0, 1, "cable"),

        # CALVES — bodyweight: Calf Raise (standing)
        ("Calf Raise (standing)",  "calves",     "squat",           "[]",      0, 1, "bodyweight"),
        ("Seated Calf Raise",      "calves",     "squat",           "[]",      0, 1, "machine"),
        ("Dumbbell Calf Raise",    "calves",     "squat",           "[]",      0, 1, "dumbbell"),

        # ABS — bodyweight: Plank
        ("Plank",                  "abs",        "carry",           "[]",      0, 0, "bodyweight"),
        ("Hanging Leg Raise",      "abs",        "vertical_pull",   "[]",      0, 0, "pullup_bar"),
        ("Ab Wheel Rollout",       "abs",        "carry",           "[]",      0, 1, "bodyweight"),
    ]

    for name, muscle, pattern, sec_ids, is_compound, stretch, equip in exercises:
        conn.execute(sa.text("""
            INSERT INTO exercises
                (name, primary_muscle_id, movement_pattern_id,
                 secondary_muscle_ids, is_compound, stretch_mediated, equipment_type)
            VALUES (
                :name,
                (SELECT id FROM muscle_groups   WHERE name = :muscle),
                (SELECT id FROM movement_patterns WHERE name = :pattern),
                :sec_ids,
                :is_compound,
                :stretch,
                :equip
            )
        """), {
            "name": name,
            "muscle": muscle,
            "pattern": pattern,
            "sec_ids": sec_ids,
            "is_compound": is_compound,
            "stretch": stretch,
            "equip": equip,
        })


def downgrade() -> None:
    """Remove all seed data."""
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM exercises"))
    conn.execute(sa.text("DELETE FROM equipment"))
    conn.execute(sa.text("DELETE FROM movement_patterns"))
    conn.execute(sa.text("DELETE FROM muscle_groups"))

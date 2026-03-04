"""
Seed functions for reference/lookup data.
Uses SQLAlchemy session (idempotent — safe to run multiple times).

Run manually:
    cd gym-coach-brain
    uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from gym_coach_brain.data.models import Base
from gym_coach_brain.data.seed import seed_all

engine = create_engine('sqlite:///gym_coach.sqlite')
with Session(engine) as s:
    seed_all(s)
    s.commit()
print('Done')
"
"""
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import MuscleGroup, MovementPattern


# ─── Taxonomy seed data ────────────────────────────────────────────────────────

_MUSCLE_GROUPS = [
    # name           body_region  is_push  is_pull  stretch_mediated
    ("chest",        "upper",     True,    False,   True),
    ("back",         "upper",     False,   True,    True),
    ("shoulders",    "upper",     True,    False,   False),  # = deltoids; existing from Story 3.2
    ("trapezius",    "upper",     False,   True,    False),  # NEW in Story 2.1
    ("biceps",       "upper",     False,   True,    True),
    ("triceps",      "upper",     True,    False,   True),
    ("quadriceps",   "lower",     True,    False,   True),
    ("hamstrings",   "lower",     False,   True,    True),
    ("glutes",       "lower",     False,   False,   True),
    ("calves",       "lower",     True,    False,   True),
    ("abs",          "core",      False,   False,   False),
    ("lower_back",   "core",      False,   True,    False),  # NEW in Story 2.1
]

_MOVEMENT_PATTERNS = [
    # name                category
    ("horizontal_push",   "push"),
    ("vertical_push",     "push"),
    ("horizontal_pull",   "pull"),
    ("vertical_pull",     "pull"),
    ("squat",             "legs"),
    ("hinge",             "legs"),
    ("carry",             "carry"),
]


def seed_muscle_groups(session: Session) -> int:
    """Insert missing muscle groups. Returns count of new records inserted."""
    inserted = 0
    for name, body_region, is_push, is_pull, stretch_mediated in _MUSCLE_GROUPS:
        existing = session.query(MuscleGroup).filter_by(name=name).first()
        if not existing:
            session.add(MuscleGroup(
                name=name,
                body_region=body_region,
                is_push=is_push,
                is_pull=is_pull,
                stretch_mediated=stretch_mediated,
            ))
            inserted += 1
    return inserted


def seed_movement_patterns(session: Session) -> int:
    """Insert missing movement patterns. Returns count of new records inserted."""
    inserted = 0
    for name, category in _MOVEMENT_PATTERNS:
        existing = session.query(MovementPattern).filter_by(name=name).first()
        if not existing:
            session.add(MovementPattern(name=name, category=category))
            inserted += 1
    return inserted


def seed_all(session: Session) -> dict[str, int]:
    """Seed all taxonomy data. Idempotent — safe to call multiple times.
    Returns dict with counts of newly inserted records per category.
    """
    mg_count = seed_muscle_groups(session)
    mp_count = seed_movement_patterns(session)
    session.flush()
    return {"muscle_groups": mg_count, "movement_patterns": mp_count}


if __name__ == "__main__":
    from sqlalchemy import create_engine
    from gym_coach_brain.data.models import Base

    engine = create_engine("sqlite:///gym_coach.sqlite")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        result = seed_all(s)
        s.commit()
    print(f"Seeded: {result}")

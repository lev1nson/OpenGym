"""
Seed functions for reference/lookup data.
Uses SQLAlchemy session (idempotent — safe to run multiple times).

Run manually:
    cd gym-coach-brain
    uv run python -m gym_coach_brain.data.seed <database_url>
"""
import json
import sys

from sqlalchemy.orm import Session

from gym_coach_brain.data.models import MuscleGroup, MovementPattern, Exercise, Equipment


# ─── Taxonomy seed data ────────────────────────────────────────────────────────

_TAXONOMY_GROUPS = [
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


# ─── Exercise seed data ────────────────────────────────────────────────────────
# Format: (name, primary_muscle, movement_pattern, secondary_muscles_list, is_compound, stretch_mediated, equipment_type)
# secondary_muscles_list: list of muscle group names — converted to IDs at seed time

# Phase 1: 28 exercises — 4 per pattern
_EXERCISES_PHASE1 = [
    # ─── horizontal_push (4) ───────────────────────────────────────────────────
    # [Source: ExRx.net — Push-up mechanics identical to bench press]
    ("Push-up",               "chest",       "horizontal_push", ["shoulders", "triceps"],            True,  True,  "bodyweight"),
    # [Source: domain-research §8.1 — Bench Press synergists peer-reviewed]
    ("Bench Press",           "chest",       "horizontal_push", ["shoulders", "triceps"],            True,  True,  "barbell"),
    # [Source: ExRx.net — Incline Press synergists analogous to bench press]
    ("Incline Dumbbell Press","chest",       "horizontal_push", ["shoulders", "triceps"],            True,  True,  "dumbbell"),
    # [Source: ExRx.net — Dip forward lean shifts primary to chest; triceps + shoulders secondary]
    ("Dip",                   "chest",       "horizontal_push", ["triceps", "shoulders"],           True,  True,  "dips_bar"),

    # ─── vertical_push (4) ────────────────────────────────────────────────────
    # [Source: ExRx.net — Pike Push-up primarily deltoids with triceps synergist]
    ("Pike Push-up",          "shoulders",   "vertical_push",   ["triceps"],                        False, False, "bodyweight"),
    # [Source: domain-research §8.4 — OHP synergists peer-reviewed (EMG PMC9354811)]
    ("Overhead Press",        "shoulders",   "vertical_push",   ["chest", "triceps", "trapezius"],  True,  False, "barbell"),
    # [Source: ExRx.net — Dumbbell OHP analogous to barbell but trapezius less engaged]
    ("Dumbbell Shoulder Press","shoulders",  "vertical_push",   ["chest", "triceps"],               True,  False, "dumbbell"),
    # [Source: ExRx.net — Lateral Raise: isolation, no meaningful secondary contribution]
    ("Lateral Raise",         "shoulders",   "vertical_push",   [],                                 False, False, "dumbbell"),

    # ─── horizontal_pull (4) ──────────────────────────────────────────────────
    # [Source: ExRx.net — Inverted Row bodyweight horizontal pull; back primary, biceps/trapezius secondary]
    ("Inverted Row",          "back",        "horizontal_pull", ["biceps", "trapezius"],             True,  True,  "bodyweight"),
    # [Source: domain-research §8.5 — Barbell Row synergists peer-reviewed]
    ("Barbell Row",           "back",        "horizontal_pull", ["biceps", "trapezius"],             True,  True,  "barbell"),
    # [Source: ExRx.net — Cable Row same mechanics as barbell row, less stretch at bottom]
    ("Cable Row",             "back",        "horizontal_pull", ["biceps", "trapezius"],             True,  False, "cable"),
    # [Source: ExRx.net — Dumbbell Row unilateral variant of barbell row]
    ("Dumbbell Row",          "back",        "horizontal_pull", ["biceps", "trapezius"],             True,  True,  "dumbbell"),

    # ─── vertical_pull (4) ────────────────────────────────────────────────────
    # [Source: domain-research §8.6 — Pull-up synergists peer-reviewed]
    ("Pull-up",               "back",        "vertical_pull",   ["biceps", "trapezius"],             True,  True,  "pullup_bar"),
    # [Source: ExRx.net — Supinated grip chin-up: biceps primary, back secondary]
    ("Bodyweight Chin-up",    "biceps",      "vertical_pull",   ["back"],                           True,  True,  "bodyweight"),
    # [Source: ExRx.net — Lat Pulldown: same muscles as pull-up, cable variant]
    ("Lat Pulldown",          "back",        "vertical_pull",   ["biceps", "trapezius"],             True,  True,  "cable"),
    # [Source: ExRx.net — Chin-up pullup_bar variant: supinated grip = biceps primary]
    ("Chin-up",               "biceps",      "vertical_pull",   ["back"],                           True,  True,  "pullup_bar"),

    # ─── squat (4) ────────────────────────────────────────────────────────────
    # [Source: ExRx.net — Bodyweight squat: quads primary, glutes synergist]
    ("Bodyweight Squat",      "quadriceps",  "squat",           ["glutes"],                         True,  True,  "bodyweight"),
    # [Source: domain-research §8.2 — Barbell Squat synergists peer-reviewed; calves=soleus per ExRx]
    ("Barbell Squat",         "quadriceps",  "squat",           ["glutes", "calves"],               True,  True,  "barbell"),
    # [Source: domain-research §8.8 — Leg Press synergists peer-reviewed]
    ("Leg Press",             "quadriceps",  "squat",           ["glutes", "hamstrings"],           True,  True,  "machine"),
    # [Source: ExRx.net — Bulgarian Split Squat: high glute + hamstring synergist due to hip position]
    ("Bulgarian Split Squat", "quadriceps",  "squat",           ["glutes", "hamstrings"],           True,  True,  "dumbbell"),

    # ─── hinge (4) ────────────────────────────────────────────────────────────
    # [Source: ExRx.net — Nordic Curl: pure hamstring isolation, no meaningful secondary]
    ("Nordic Curl",           "hamstrings",  "hinge",           [],                                 False, True,  "bodyweight"),
    # [Source: domain-research §8.7 — RDL: hamstrings+glutes co-primary; erector = synergist]
    ("Romanian Deadlift",     "hamstrings",  "hinge",           ["glutes", "lower_back"],           True,  True,  "barbell"),
    # [Source: ExRx.net — Glute Bridge: glutes primary, hamstrings synergist]
    ("Glute Bridge",          "glutes",      "hinge",           ["hamstrings"],                     False, True,  "bodyweight"),
    # [Source: ExRx.net — Hip Thrust: glutes primary; hamstrings + quads as synergists]
    ("Hip Thrust",            "glutes",      "hinge",           ["hamstrings", "quadriceps"],       True,  True,  "barbell"),

    # ─── carry (4) — carry: 4 exercises; pattern allows 2-4 by nature, not by omission ──
    # [Source: ExRx.net — Plank: abs stabilization, no meaningful secondary]
    ("Plank",                 "abs",         "carry",           [],                                 False, False, "bodyweight"),
    # [Source: ExRx.net — Ab Wheel Rollout: abs primary, erector spinae synergist at end range]
    ("Ab Wheel Rollout",      "abs",         "carry",           ["lower_back"],                     False, True,  "bodyweight"),
    # [Source: ExRx.net — Farmer's Walk: trapezius shrug/elevation primary; lower_back + abs stabilizers]
    ("Farmer's Walk",         "trapezius",   "carry",           ["lower_back", "abs"],              True,  False, "dumbbell"),
    # [Source: ExRx.net — Hanging Leg Raise: hip flexors + abs; classified carry as anti-gravity core hold]
    ("Hanging Leg Raise",     "abs",         "carry",           [],                                 False, False, "pullup_bar"),
]

# Phase 2: +9 exercises to reach ≥35
_EXERCISES_PHASE2 = [
    # horizontal_push +3
    # [Source: ExRx.net — Diamond Push-up: narrow grip shifts primary to triceps; chest/shoulders secondary]
    ("Diamond Push-up",       "triceps",     "horizontal_push", ["chest", "shoulders"],             False, True,  "bodyweight"),
    # [Source: ExRx.net — Tricep Pushdown: isolation exercise; no meaningful secondary]
    ("Tricep Pushdown",       "triceps",     "horizontal_push", [],                                 False, False, "cable"),
    # [Source: ExRx.net — Dumbbell Fly: chest isolation; no compound secondary]
    ("Dumbbell Fly",          "chest",       "horizontal_push", [],                                 False, True,  "dumbbell"),

    # horizontal_pull +2
    # [Source: ExRx.net — Dumbbell Curl: biceps isolation; brachialis subsumed in biceps group]
    ("Dumbbell Curl",         "biceps",      "horizontal_pull", [],                                 False, True,  "dumbbell"),
    # [Source: ExRx.net — Resistance Band Curl: same mechanics as dumbbell curl]
    ("Resistance Band Curl",  "biceps",      "horizontal_pull", [],                                 False, True,  "resistance_band"),

    # hinge +3
    # [Source: domain-research §8.3 — Deadlift: ExRx primary=glutes; secondary includes back, 
    #  hamstrings, lower_back. Mapped to 'glutes' primary here as it is the true target,
    #  differing from Alembic 002_seed_data.py 'back' placeholder for better science accuracy.]
    ("Deadlift",              "glutes",      "hinge",           ["back", "hamstrings", "lower_back"], True, True, "barbell"),
    # [Source: ExRx.net — Good Morning: similar mechanics to RDL; hamstrings + lower_back + glutes]
    ("Good Morning",          "hamstrings",  "hinge",           ["lower_back", "glutes"],           True,  True,  "barbell"),
    # [Source: ExRx.net — Cable Pull-Through: glutes primary; hamstrings synergist in hip hinge]
    ("Cable Pull-Through",    "glutes",      "hinge",           ["hamstrings"],                     False, True,  "cable"),

    # squat +1
    # [Source: ExRx.net — Calf Raise: calves isolation; soleus primary, no compound secondary]
    ("Calf Raise (standing)", "calves",      "squat",           [],                                 False, True,  "bodyweight"),
]

# Phase 3: Machine-based exercises for gym members with machine equipment
_EXERCISES_PHASE3 = [
    # horizontal_push +1
    # [Source: ExRx.net — Machine Chest Press: same mechanics as bench press, chest primary]
    ("Machine Chest Press",    "chest",       "horizontal_push", ["shoulders", "triceps"],            True,  False, "machine"),
    # vertical_push +1
    # [Source: ExRx.net — Machine Shoulder Press: same mechanics as OHP, shoulders primary]
    ("Machine Shoulder Press", "shoulders",   "vertical_push",   ["chest", "triceps"],               True,  False, "machine"),
    # squat +1
    # [Source: ExRx.net — Smith Squat: squat pattern on Smith machine, quads primary]
    ("Smith Squat",            "quadriceps",  "squat",           ["glutes"],                         True,  False, "machine"),
    # hinge +1
    # [Source: ExRx.net — Machine Leg Curl: hamstrings isolation, prone or seated]
    ("Machine Leg Curl",       "hamstrings",  "hinge",           [],                                 False, True,  "machine"),
    # squat +1
    # [Source: ExRx.net — Machine Leg Extension: quads isolation, seated or lying]
    ("Machine Leg Extension",  "quadriceps",  "squat",           [],                                 False, False, "machine"),
]


# ─── Equipment seed data ───────────────────────────────────────────────────────
# ⚠️ Names MUST match Alembic 002_seed_data.py exactly — idempotency on prod DB

_EQUIPMENT = [
    # name                  type                available_home  available_gym
    ("Barbell",             "barbell",          False,          True),
    ("Dumbbell (pair)",     "dumbbell",         True,           True),
    ("Cable Machine",       "cable",            False,          True),
    ("Resistance Band",     "resistance_band",  True,           True),
    ("Pull-up Bar",         "pullup_bar",       True,           True),
    ("Dip Bars",            "dips_bar",         True,           True),
    ("Smith Machine",       "machine",          False,          True),
    ("Leg Press Machine",   "machine",          False,          True),
    ("Cable Fly Station",   "cable",            False,          True),
    ("Bodyweight",          "bodyweight",       True,           True),
]


# Merged constant for seed function
# Total: 42 exercises (37 + 5 machine-based)
# Distribution: h_push=8, v_push=5, h_pull=6, v_pull=4, squat=7, hinge=8, carry=4
_EXERCISES = _EXERCISES_PHASE1 + _EXERCISES_PHASE2 + _EXERCISES_PHASE3


def seed_muscle_groups(session: Session) -> int:
    """Insert missing muscle groups. Returns count of new records inserted."""
    inserted = 0
    for name, body_region, is_push, is_pull, stretch_mediated in _TAXONOMY_GROUPS:
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


def seed_taxonomy(session: Session) -> dict[str, int]:
    """Seed all taxonomy data. Idempotent — safe to call multiple times.
    Returns dict with counts of newly inserted records per category.
    """
    mg_count = seed_muscle_groups(session)
    mp_count = seed_movement_patterns(session)
    session.flush()
    return {"muscle_groups": mg_count, "movement_patterns": mp_count}


def seed_equipment(session: Session) -> int:
    """Insert missing equipment records. Returns count of new records inserted.

    Idempotent: matches Alembic 002_seed_data.py exactly.
    Running on prod DB inserts 0 (all 10 already exist from Alembic).
    Running on in-memory test DB inserts all 10.
    """
    inserted = 0
    for name, type_, available_home, available_gym in _EQUIPMENT:
        existing = session.query(Equipment).filter_by(name=name).first()
        if not existing:
            session.add(Equipment(
                name=name,
                type=type_,
                available_home=available_home,
                available_gym=available_gym,
            ))
            inserted += 1
    session.flush()
    return inserted


_EXERCISE_CONCRETE_INVENTORY: dict[str, str] = {
    "Bench Press": "barbell",
    "Incline Dumbbell Press": "dumbbells",
    "Dumbbell Fly": "dumbbells",
    "Machine Chest Press": "chest_press_machine",
    "Machine Shoulder Press": "shoulder_press_machine",
    "Smith Squat": "smith_machine",
    "Machine Leg Curl": "leg_curl_machine",
    "Machine Leg Extension": "leg_extension_machine",
    "Leg Press": "leg_press_machine",
    "Lat Pulldown": "high_pulley_cable",
    "Tricep Pushdown": "high_pulley_cable",
    "Cable Row": "low_pulley_cable",
    "Cable Pull-Through": "low_pulley_cable",
    "Overhead Press": "barbell",
    "Barbell Row": "barbell",
    "Barbell Squat": "barbell",
    "Romanian Deadlift": "barbell",
    "Deadlift": "barbell",
    "Good Morning": "barbell",
    "Hip Thrust": "barbell",
    "Dumbbell Shoulder Press": "dumbbells",
    "Dumbbell Row": "dumbbells",
    "Dumbbell Curl": "dumbbells",
    "Lateral Raise": "dumbbells",
    "Farmer's Walk": "dumbbells",
    "Bulgarian Split Squat": "dumbbells",
    "Ab Wheel Rollout": "ab_wheel",
}


def _derive_exercise_family(
    movement_pattern: str,
    equipment_type: str,
    is_compound: bool,
) -> str:
    load_mode = "compound" if is_compound else "isolation"

    if equipment_type in ("cable", "machine"):
        equipment_suffix = "guided"
    elif equipment_type in ("pullup_bar", "dips_bar"):
        equipment_suffix = "bodyweight_station"
    elif equipment_type == "resistance_band":
        equipment_suffix = "band"
    else:
        equipment_suffix = equipment_type

    if movement_pattern == "carry":
        return f"carry_{equipment_suffix}"

    return f"{load_mode}_{movement_pattern}_{equipment_suffix}"


def seed_exercises(session: Session) -> int:
    """Insert new exercises and fill secondary_muscle_ids where empty.

    Upsert logic:
    - New exercise (name not found): INSERT with full metadata
    - Existing exercise with secondary_muscle_ids == "[]": UPDATE secondary_muscle_ids only
    - Existing exercise with secondary_muscle_ids already set: SKIP (preserve custom data)

    Returns count of exercises inserted + updated.
    """
    from gym_coach_brain.data.models import MovementPattern

    mg_ids = {mg.name: mg.id for mg in session.query(MuscleGroup).all()}
    mp_ids = {mp.name: mp.id for mp in session.query(MovementPattern).all()}

    touched = 0
    for name, primary_mg, primary_mp, secondary_mgs, is_compound, stretch, equip in _EXERCISES:
        primary_mg_id = mg_ids[primary_mg]
        primary_mp_id = mp_ids[primary_mp]
        secondary_ids = [mg_ids[m] for m in secondary_mgs]
        secondary_json = json.dumps(secondary_ids)

        concrete_item = _EXERCISE_CONCRETE_INVENTORY.get(name)
        requires_concrete = concrete_item is not None and equip != "bodyweight"
        exercise_family = _derive_exercise_family(primary_mp, equip, is_compound)

        existing = session.query(Exercise).filter_by(name=name).first()
        if existing is None:
            session.add(Exercise(
                name=name,
                primary_muscle_id=primary_mg_id,
                movement_pattern_id=primary_mp_id,
                secondary_muscle_ids=secondary_json,
                is_compound=is_compound,
                stretch_mediated=stretch,
                equipment_type=equip,
                exercise_family=exercise_family,
                requires_concrete_inventory=requires_concrete,
                concrete_item_id=concrete_item,
            ))
            touched += 1
        elif existing.secondary_muscle_ids == "[]" and (
            secondary_json != "[]" or
            existing.movement_pattern_id != primary_mp_id or
            existing.primary_muscle_id != primary_mg_id
        ):
            existing.secondary_muscle_ids = secondary_json
            existing.movement_pattern_id = primary_mp_id
            existing.primary_muscle_id = primary_mg_id
            existing.exercise_family = exercise_family
            existing.requires_concrete_inventory = requires_concrete
            existing.concrete_item_id = concrete_item
            touched += 1
        elif existing.exercise_family is None:
            existing.exercise_family = exercise_family
            existing.requires_concrete_inventory = requires_concrete
            existing.concrete_item_id = concrete_item
            touched += 1

    session.flush()
    return touched


def seed_all(session: Session) -> dict[str, int]:
    """Seed all reference data: taxonomy + equipment + exercises. Idempotent.

    ORDER MATTERS: taxonomy → equipment → exercises (exercises depend on taxonomy)
    Returns dict with counts of newly inserted/updated records per category.
    """
    taxonomy_result = seed_taxonomy(session)
    eq_count = seed_equipment(session)
    ex_count = seed_exercises(session)
    return {**taxonomy_result, "equipment": eq_count, "exercises": ex_count}


if __name__ == "__main__":
    from sqlalchemy import create_engine
    from gym_coach_brain.data.models import Base

    if len(sys.argv) < 2:
        print("Usage: python -m gym_coach_brain.data.seed <database_url>", file=sys.stderr)
        sys.exit(1)
    db_url = sys.argv[1]
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        result = seed_all(s)
        s.commit()
    print(f"Seeded: {result}")

"""
PUOS (Per-Unit-Of-Set) volume calculation and validation.

Implements:
- fractional_volume: DB-backed per-exercise contribution (СУЩЕСТВУЮЩАЯ функция)
- FractionalVolume: dataclass для результатов validate_puos
- validate_puos: pure function — PUOS limit enforcement
- accumulate_session_volume: within-session volume aggregation

References:
    Israetel, M. et al. (2019). Scientific Principles of Hypertrophy Training.
    Schoenfeld, B.J. & Grgic, J. (2021). Sports, 9(2), 32. PMC7927075.
"""
import json
from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy.orm import Session

from gym_coach_brain.core.science import ScienceConfig
from gym_coach_brain.data.models import Exercise, MuscleGroup, WorkoutSet
from gym_coach_brain.exceptions import ScienceLimitError

# ─── Constants ────────────────────────────────────────────────────────────────

AGONIST_COEFF: float = 1.0    # Primary muscle: full set contribution
SYNERGIST_COEFF: float = 0.5  # Secondary muscle: half set contribution
PUOS_WARNING_THRESHOLD: int = 9  # Sets: log WARNING if ≥ this value


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class FractionalVolume:
    """Result of a successful PUOS validation for a muscle group.

    Attributes:
        muscle_group_id: PK of the validated MuscleGroup
        accumulated_sets: Planned or accumulated sets for this session
        effective_limit: Actual limit after SMH multiplier (if applicable)
        agonist_coeff: Fractional contribution as primary muscle (always 1.0)
        synergist_coeff: Fractional contribution as synergist (always 0.5)
    """
    muscle_group_id: int
    accumulated_sets: float
    effective_limit: float
    agonist_coeff: float = field(default=AGONIST_COEFF)
    synergist_coeff: float = field(default=SYNERGIST_COEFF)


# ─── Existing function (DO NOT MODIFY) ────────────────────────────────────────

def fractional_volume(exercise_id: int, muscle_group_id: int, session: Session) -> float:
    """Return fractional volume contribution of an exercise for a muscle group.

    Args:
        exercise_id: PK of the Exercise record
        muscle_group_id: PK of the MuscleGroup to check
        session: Active SQLAlchemy session

    Returns:
        1.0 if muscle_group_id is the primary muscle of the exercise
        0.5 if muscle_group_id is a synergist (in secondary_muscle_ids)
        0.0 if muscle_group_id has no meaningful contribution
    """
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        return 0.0
    if exercise.primary_muscle_id == muscle_group_id:
        return 1.0
    secondary_ids = json.loads(exercise.secondary_muscle_ids or "[]")
    if muscle_group_id in secondary_ids:
        return 0.5
    return 0.0


# ─── New functions for Story 4.2 ──────────────────────────────────────────────

def validate_puos(
    muscle_group: MuscleGroup,
    planned_sets: float,
    science: ScienceConfig,
) -> FractionalVolume:
    """Validate planned sets against PUOS limit for a muscle group.

    Pure function (only side effect: loguru WARNING at ≥9 sets).
    Raises ScienceLimitError if planned_sets exceeds effective limit.

    ⚠️ USAGE SCOPE: Call on TOTAL accumulated session volume for a muscle group,
    NOT on per-exercise volume. Use accumulate_session_volume() first to aggregate
    all exercises in the session, then call validate_puos on the result.

    SMH (Stretch-Mediated Hypertrophy) multiplier: exercises that load muscles
    in a stretched position (Romanian deadlift, overhead press, incline curl)
    are better tolerated and allow higher volume per session. If
    muscle_group.stretch_mediated=True, the effective limit is multiplied by
    science.puos.smh_volume_multiplier (e.g., 1.2 → 13.2 sets for 11-set base).

    Args:
        muscle_group: MuscleGroup ORM object with id, name, stretch_mediated fields
        planned_sets: Accumulated sets planned for this muscle group in the session
        science: ScienceConfig with puos.max_sets_per_group and puos.smh_volume_multiplier

    Returns:
        FractionalVolume with accumulated_sets, effective_limit, and coefficients

    Raises:
        ScienceLimitError: If planned_sets > effective_limit

    References:
        [Source: gym-coach-brain/ScienceEvidence.md#PUOS Limits]
        [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
    """
    smh_mult = science.puos.smh_volume_multiplier if muscle_group.stretch_mediated else 1.0
    effective_limit = science.puos.max_sets_per_group * smh_mult

    # Log WARNING when approaching limit (science-informed threshold)
    if planned_sets >= PUOS_WARNING_THRESHOLD:
        logger.warning(
            "PUOS limit approached: {sets}/{limit} sets for {muscle}",
            sets=planned_sets,
            limit=effective_limit,
            muscle=muscle_group.name,
        )

    if planned_sets > effective_limit:
        raise ScienceLimitError(
            f"PUOS limit exceeded for {muscle_group.name}: "
            f"{planned_sets} sets > {effective_limit:.1f} limit"
            + (" (SMH multiplier applied)" if muscle_group.stretch_mediated else "")
        )

    return FractionalVolume(
        muscle_group_id=muscle_group.id,
        accumulated_sets=planned_sets,
        effective_limit=effective_limit,
    )


def accumulate_session_volume(
    session_sets: list[WorkoutSet],
    science: ScienceConfig,
) -> dict[int, float]:
    """Aggregate fractional volume per muscle group across all sets in a session.

    Implements within-session volume tracking using fractional contribution:
    - Primary muscle (agonist): +1.0 per set
    - Secondary muscles (synergists): +0.5 per set each

    Example: bench press (chest primary, triceps/front delt secondary) + dumbbell
    press + cable fly in one session → chest accumulates volume from ALL THREE,
    not independent per-exercise checks. Call validate_puos on the aggregated
    result to enforce PUOS limits.

    ⚠️ REQUIRES: WorkoutSet.exercise relationship must be loaded (eager/joined).
    Use SQLAlchemy selectinload or joinedload when querying WorkoutSets.

    Args:
        session_sets: List of WorkoutSet ORM objects with exercise relationship loaded
        science: ScienceConfig (reserved for future use, e.g., per-exercise overrides)

    Returns:
        dict mapping muscle_group_id (int) → accumulated_volume (float)
        Empty dict if session_sets is empty.

    References:
        [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.2]
        [Source: _bmad-output/planning-artifacts/architecture.md#FR12 fractional volume]
    """
    volume: dict[int, float] = {}

    for workout_set in session_sets:
        exercise = workout_set.exercise
        if exercise is None:
            continue

        # Primary muscle: full contribution
        primary_id = exercise.primary_muscle_id
        volume[primary_id] = volume.get(primary_id, 0.0) + AGONIST_COEFF

        # Secondary muscles: half contribution each
        for secondary_id in exercise.secondary_muscle_id_list:
            if secondary_id != primary_id:
                volume[secondary_id] = volume.get(secondary_id, 0.0) + SYNERGIST_COEFF

    return volume

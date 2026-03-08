"""
ML feature vector builder for RPEModel.

Assembles a 14-dimensional feature vector from the database for a given
(exercise_id, session_id) pair. All values are numeric (float/int).
Cold start fallbacks ensure no None/NaN values.

Cold start defaults:
- historical_rpe: 6.0 (moderate perceived effort — reasonable global median)
- avg_rpe_last_3_sessions_for_exercise: 6.0
- sessions_count_for_exercise: 0
- readiness_score: 5.0 (neutral recovery — midpoint of 1-10 scale)
- days_since_last_session: 0 (first session → no gap)
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import (
    EquipmentType,
    Exercise,
    ReadinessLog,
    WorkoutSession,
    WorkoutSet,
)

# Stable ordering for equipment_type → int mapping
_EQUIPMENT_ORDER: list[str] = sorted(e.value for e in EquipmentType)

# Cold start defaults
_DEFAULT_RPE: float = 6.0
_DEFAULT_READINESS: float = 5.0
_DEFAULT_DAYS_SINCE: int = 0
_DEFAULT_SESSIONS_COUNT: int = 0


@dataclass
class FeatureVector:
    """14-dimensional feature vector for RPEModel input.

    All fields are numeric (float or int). Never None, never NaN.
    """
    exercise_id: int
    movement_pattern_id: int
    primary_muscle_id: int
    is_compound: int                              # bool → 0/1
    stretch_mediated: int                          # bool → 0/1
    equipment_type_int: int                        # EquipmentType ordinal 0-7
    set_number: int
    weight_kg: float
    reps: int
    historical_rpe: float                          # last RPE for this athlete+exercise
    avg_rpe_last_3_sessions_for_exercise: float    # rolling avg RPE, last 3 sessions
    sessions_count_for_exercise: int               # total sessions with this exercise
    readiness_score: float                         # from ReadinessLog.recovery_score
    days_since_last_session: int                   # days since last completed session


def build_feature_vector(
    exercise_id: int,
    session_id: int,
    set_number: int,
    weight_kg: float,
    reps: int,
    session: Session,
    cold_start_rpe: float = _DEFAULT_RPE,
) -> FeatureVector:
    """Build a complete feature vector for a given exercise+session context.

    Args:
        exercise_id: Exercise PK from exercises table
        session_id: Current WorkoutSession PK
        set_number: Set number within the session (1-based)
        weight_kg: Weight to be used in this set
        reps: Planned repetitions
        session: SQLAlchemy Session (caller manages lifecycle)
        cold_start_rpe: Fallback RPE when no history exists (default 6.0)

    Returns:
        FeatureVector with all 14 features. Never raises for missing data.
    """
    # ── Exercise static features ───────────────────────────────────────────────
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise ValueError(f"Exercise {exercise_id} not found in database")

    equipment_type_int = _EQUIPMENT_ORDER.index(exercise.equipment_type.value)

    # ── Historical RPE for this exercise ──────────────────────────────────────
    last_rpe_row = (
        session.execute(
            select(WorkoutSet.rpe)
            .where(
                WorkoutSet.exercise_id == exercise_id,
                WorkoutSet.session_id != session_id,
                WorkoutSet.rpe.is_not(None),
            )
            .order_by(WorkoutSet.id.desc())
            .limit(1)
        )
        .first()
    )
    historical_rpe: float = last_rpe_row[0] if last_rpe_row else cold_start_rpe

    # ── Avg RPE last 3 sessions for this exercise ──────────────────────────────
    # Get last 3 distinct session_ids with RPE data for this exercise
    recent_sessions_with_rpe = (
        session.execute(
            select(WorkoutSet.session_id)
            .where(
                WorkoutSet.exercise_id == exercise_id,
                WorkoutSet.session_id != session_id,
                WorkoutSet.rpe.is_not(None),
            )
            .distinct()
            .order_by(WorkoutSet.session_id.desc())
            .limit(3)
        )
        .scalars()
        .all()
    )

    if recent_sessions_with_rpe:
        avg_rpe_row = session.execute(
            select(func.avg(WorkoutSet.rpe))
            .where(
                WorkoutSet.exercise_id == exercise_id,
                WorkoutSet.session_id.in_(recent_sessions_with_rpe),
                WorkoutSet.rpe.is_not(None),
            )
        ).scalar()
        avg_rpe_last_3 = float(avg_rpe_row) if avg_rpe_row is not None else cold_start_rpe
    else:
        avg_rpe_last_3 = cold_start_rpe

    # ── Sessions count for this exercise ──────────────────────────────────────
    sessions_count = session.execute(
        select(func.count(WorkoutSet.session_id.distinct()))
        .where(
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSet.session_id != session_id,
        )
    ).scalar() or 0

    # ── Readiness score (most recent log entry) ────────────────────────────────
    readiness_row = (
        session.execute(
            select(ReadinessLog.recovery_score)
            .order_by(ReadinessLog.session_date.desc())
            .limit(1)
        )
        .scalar()
    )
    readiness_score: float = float(readiness_row) if readiness_row is not None else _DEFAULT_READINESS

    # ── Days since last session ────────────────────────────────────────────────
    last_session_date_row = (
        session.execute(
            select(WorkoutSession.session_date)
            .where(
                WorkoutSession.status == "completed",
                WorkoutSession.id != session_id,
            )
            .order_by(WorkoutSession.session_date.desc())
            .limit(1)
        )
        .scalar()
    )

    if last_session_date_row:
        try:
            last_dt = datetime.fromisoformat(last_session_date_row)
            # Architecture rule: "НЕ datetime.now() (localtime risk)". 
            # Use utcnow() as defined in "Write: datetime.utcnow().isoformat()" pattern.
            now = datetime.utcnow()
            days_since = max(0, (now - last_dt).days)
        except (ValueError, TypeError):
            days_since = _DEFAULT_DAYS_SINCE
    else:
        days_since = _DEFAULT_DAYS_SINCE

    return FeatureVector(
        exercise_id=exercise_id,
        movement_pattern_id=exercise.movement_pattern_id,
        primary_muscle_id=exercise.primary_muscle_id,
        is_compound=int(exercise.is_compound),
        stretch_mediated=int(exercise.stretch_mediated),
        equipment_type_int=equipment_type_int,
        set_number=set_number,
        weight_kg=float(weight_kg),
        reps=int(reps),
        historical_rpe=historical_rpe,
        avg_rpe_last_3_sessions_for_exercise=avg_rpe_last_3,
        sessions_count_for_exercise=int(sessions_count),
        readiness_score=readiness_score,
        days_since_last_session=days_since,
    )

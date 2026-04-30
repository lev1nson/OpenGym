"""
Adaptation Engine — coordinates ML predictions with deterministic fallback.

Reads RPE predictions from DB (produced by MLWorker), applies confidence
threshold, falls back to Double Progression when ML is unavailable/uncertain.
Detects training plateaus and includes weight rounding.

Architecture:
    - ADR-001: ML Layer Isolation (RPEModelProtocol, no direct torch import)
    - ADR-002: ScienceConfig as parameter (never module-level global)
    - Dependency: api → adaptation → core → data (no reverse deps)

References:
    [Source: _bmad-output/planning-artifacts/architecture.md#Adaptation Engine]
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.5]
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import UserProfile, WorkoutSession
    from gym_coach_brain.core.readiness import RecoverySignal
    from gym_coach_brain.ml.interface import RPEModelProtocol


# ─── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class AdaptationDecision:
    """Structured decision record passed to ExplanationLayer."""
    exercise_name: str
    previous_weight: float
    new_weight: float
    used_ml: bool
    ml_rpe: float | None
    ml_confidence: float | None
    fallback_reason: str | None  # e.g. "confidence below threshold", "no prediction"
    source_label: str = "[ядро]"
    anomaly_flag: bool = False
    core_weight_kg: float | None = None


@dataclass
class AdaptedExercise:
    """Single exercise in the adapted plan."""
    exercise_id: int
    exercise_name: str
    sets: int
    rep_range: tuple[int, int]        # (min, max)
    target_reps: int
    target_weight_kg: float
    explanation: str                   # from ExplanationLayer.explain()
    used_ml: bool


@dataclass
class AdaptationResult:
    """Full adapted workout plan for a session."""
    exercises: list[AdaptedExercise]
    science_version: str               # science.version — traceability
    plateau_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExercisePerformanceSnapshot:
    """Most recent completed performance context for one exercise."""

    current_weight: float
    current_reps: int
    has_completed_history: bool


def rpe_to_weight(
    predicted_rpe: float,
    target_rpe: float,
    core_weight_kg: float,
    science: "ScienceConfig",
    confidence: float | None = None,
) -> float:
    """Convert an RPE prediction into a bounded candidate weight."""
    if core_weight_kg <= 0:
        return 0.0
    adjustment_ratio = science.ml.rpe_weight_sensitivity * _effective_rpe_error(
        predicted_rpe=predicted_rpe,
        target_rpe=target_rpe,
        science=science,
    )
    if confidence is not None:
        adjustment_ratio *= _confidence_correction_scale(confidence, science)
    return max(0.0, core_weight_kg * (1.0 - adjustment_ratio))


# ─── Engine ───────────────────────────────────────────────────────────────────

class AdaptationEngine:
    """Coordinates ML predictions with deterministic fallback.

    Accepts rpe_model via constructor (duck typing). When rpe_model is None
    or returns low-confidence predictions, falls back to Double Progression.
    No direct PyTorch import — uses RPEModelProtocol interface.

    Usage:
        engine = AdaptationEngine(rpe_model=None)  # deterministic only
        engine = AdaptationEngine(rpe_model=some_rpe_model)  # with ML

        result = engine.adapt(session, user_profile, recovery_signal, science, db_session)
    """

    def __init__(self, rpe_model: "RPEModelProtocol | None" = None) -> None:
        self._rpe_model = rpe_model

    def adapt(
        self,
        session: "WorkoutSession",
        user_profile: "UserProfile",
        recovery_signal: "RecoverySignal | None",
        science: "ScienceConfig",
        db_session: "SASession",
    ) -> AdaptationResult:
        """Produce an adapted workout plan from a planned session.

        For each exercise in session.planned_exercises:
          1. Attempt ML RPE prediction (via rpe_predictions table or rpe_model)
          2. If confidence >= science.ml.confidence_threshold: use ML
          3. Otherwise: call calculate_double_progression() (deterministic fallback)
          4. Apply round_to_equipment_increment() on all weights
          5. Generate explanation via ExplanationLayer

        Then check plateau for each exercise across last science.plateau_detection_sessions.

        Args:
            session: WorkoutSession ORM object with planned_exercises JSON
            user_profile: UserProfile ORM object (goal, equipment, etc.)
            recovery_signal: RecoverySignal or None (coefficient 0-1)
            science: ScienceConfig (passed at startup, never a module global)
            db_session: SQLAlchemy Session for DB reads

        Returns:
            AdaptationResult with exercises, science_version, plateau_warnings
        """
        from gym_coach_brain.adaptation.explanation import ExplanationLayer
        from gym_coach_brain.core.methodology import select_methodology
        from gym_coach_brain.core.weight_utils import round_to_equipment_increment
        from gym_coach_brain.data.models import RPEPrediction, Exercise, EquipmentType

        methodology = select_methodology(user_profile, science)
        rep_range = (methodology.rep_range.min, methodology.rep_range.max)

        try:
            planned = json.loads(session.planned_exercises or "[]")
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse planned_exercises for session {id}: {exc}",
                id=session.id,
                exc=exc,
            )
            planned = []
        adapted_exercises: list[AdaptedExercise] = []
        plateau_warnings: list[str] = []

        recovery_coeff = recovery_signal.coefficient if recovery_signal is not None else 1.0

        for planned_ex in planned:
            exercise_id = planned_ex["exercise_id"]
            sets = int(planned_ex.get("sets", 3))
            planned_weight = float(planned_ex.get("target_weight_kg", 0.0))
            requested_target_reps = planned_ex.get("target_reps")

            # Retrieve exercise metadata for equipment type
            exercise = db_session.query(Exercise).filter_by(id=exercise_id).first()
            exercise_name = (
                exercise.name
                if exercise is not None
                else planned_ex.get("exercise_name", f"exercise-{exercise_id}")
            )
            equipment_type = (
                EquipmentType(exercise.equipment_type) if exercise else EquipmentType.barbell
            )
            is_compound = exercise.is_compound if exercise else True
            previous_performance = _get_previous_performance(
                exercise_id=exercise_id,
                current_session=session,
                fallback_weight=planned_weight,
                fallback_reps=rep_range[0],
                rep_range=rep_range,
                db_session=db_session,
            )
            planned_target_reps = _clamp_target_reps(
                requested_target_reps
                if requested_target_reps is not None
                else previous_performance.current_reps,
                rep_range,
            )

            core_weight_kg, core_target_reps, core_fallback_reason = _fallback_recommendation(
                previous_performance=previous_performance,
                planned_weight=planned_weight,
                planned_target_reps=planned_target_reps,
                rep_range=rep_range,
                science=science,
                equipment_type=equipment_type,
                is_compound=is_compound,
                recovery_coeff=1.0,
            )

            # ── ML path ──────────────────────────────────────────────────────
            used_ml = False
            ml_rpe: float | None = None
            ml_confidence: float | None = None
            fallback_reason: str | None = None
            source_label = "[ядро]"
            anomaly_flag = False
            ml_weight_kg: float | None = None
            target_reps = core_target_reps

            # Check rpe_predictions table first (populated by MLWorker async)
            db_prediction = _get_latest_db_prediction(
                session_id=session.id,
                exercise_id=exercise_id,
                db_session=db_session,
            )
            if db_prediction and db_prediction.confidence_score >= science.ml.confidence_threshold:
                ml_rpe = db_prediction.predicted_rpe
                ml_confidence = db_prediction.confidence_score
                raw_ml_weight_kg = rpe_to_weight(
                    predicted_rpe=ml_rpe,
                    target_rpe=_resolve_target_rpe(planned_ex, science),
                    core_weight_kg=core_weight_kg,
                    science=science,
                )
                ml_weight_kg = rpe_to_weight(
                    predicted_rpe=ml_rpe,
                    target_rpe=_resolve_target_rpe(planned_ex, science),
                    core_weight_kg=core_weight_kg,
                    science=science,
                    confidence=ml_confidence,
                )
                delta_percent = _compute_delta_percent(core_weight_kg, raw_ml_weight_kg)
                if delta_percent > science.ml.max_correction_percent:
                    fallback_reason = "ml correction exceeded safety bound"
                    anomaly_flag = True
                    source_label = _format_anomaly_source_label(
                        delta_percent=delta_percent,
                        max_correction_percent=science.ml.max_correction_percent,
                    )
                else:
                    used_ml = True
                    source_label = _format_ai_source_label(
                        ml_weight_kg=ml_weight_kg,
                        core_weight_kg=core_weight_kg,
                        predicted_rpe=ml_rpe,
                        confidence=ml_confidence,
                    )
            elif db_prediction:
                # DB prediction exists but confidence is too low
                ml_confidence = db_prediction.confidence_score
                fallback_reason = f"confidence {ml_confidence:.2f} below threshold {science.ml.confidence_threshold}"
                source_label = _format_low_confidence_source_label(ml_confidence)
                logger.warning(
                    "ML fallback: {reason} for exercise '{ex}'",
                    reason=fallback_reason,
                    ex=exercise_name,
                )
            elif self._rpe_model is not None:
                # Fallback to direct model call (e.g., in-process during session)
                features = _build_features(
                    exercise_id=exercise_id,
                    session_id=session.id,
                    set_number=max(1, sets),
                    current_weight=previous_performance.current_weight,
                    current_reps=planned_target_reps,
                    recovery_signal=recovery_signal,
                    science=science,
                    db_session=db_session,
                )
                rpe_pred, conf = self._rpe_model.predict(features)
                if conf >= science.ml.confidence_threshold:
                    ml_rpe = rpe_pred
                    ml_confidence = conf
                    raw_ml_weight_kg = rpe_to_weight(
                        predicted_rpe=rpe_pred,
                        target_rpe=_resolve_target_rpe(planned_ex, science),
                        core_weight_kg=core_weight_kg,
                        science=science,
                    )
                    ml_weight_kg = rpe_to_weight(
                        predicted_rpe=rpe_pred,
                        target_rpe=_resolve_target_rpe(planned_ex, science),
                        core_weight_kg=core_weight_kg,
                        science=science,
                        confidence=conf,
                    )
                    delta_percent = _compute_delta_percent(core_weight_kg, raw_ml_weight_kg)
                    if delta_percent > science.ml.max_correction_percent:
                        fallback_reason = "ml correction exceeded safety bound"
                        anomaly_flag = True
                        source_label = _format_anomaly_source_label(
                            delta_percent=delta_percent,
                            max_correction_percent=science.ml.max_correction_percent,
                        )
                    else:
                        used_ml = True
                        source_label = _format_ai_source_label(
                            ml_weight_kg=ml_weight_kg,
                            core_weight_kg=core_weight_kg,
                            predicted_rpe=ml_rpe,
                            confidence=ml_confidence,
                        )
                else:
                    ml_confidence = conf
                    fallback_reason = f"confidence {conf:.2f} below threshold {science.ml.confidence_threshold}"
                    source_label = _format_low_confidence_source_label(conf)
                    logger.warning(
                        "ML fallback: {reason} for exercise '{ex}'",
                        reason=fallback_reason,
                        ex=exercise_name,
                    )
            else:
                # No ML available — pure deterministic
                fallback_reason = "no rpe_model provided"
                logger.warning(
                    "ML fallback: {reason} for exercise '{ex}'",
                    reason=fallback_reason,
                    ex=exercise_name,
                )
                source_label = "[ядро]"

            base_weight_after_recovery = core_weight_kg * recovery_coeff
            ml_delta = (ml_weight_kg - core_weight_kg) if used_ml else 0.0
            new_weight = round_to_equipment_increment(
                base_weight_after_recovery + ml_delta,
                equipment_type,
                science,
            )
            if used_ml and ml_rpe is not None:
                target_reps = _target_reps_for_ml(
                    ml_rpe=ml_rpe,
                    previous_performance=previous_performance,
                    new_weight=new_weight,
                    rep_range=rep_range,
                    science=science,
                )
            elif fallback_reason is None:
                fallback_reason = core_fallback_reason

            if db_prediction is not None:
                _update_prediction_record(
                    prediction=db_prediction,
                    core_weight_kg=core_weight_kg,
                    ml_weight_kg=ml_weight_kg if (used_ml or anomaly_flag) else None,
                    anomaly_flag=anomaly_flag,
                    source_label=source_label,
                )
                db_session.flush()

            decision = AdaptationDecision(
                exercise_name=exercise_name,
                previous_weight=previous_performance.current_weight,
                new_weight=new_weight,
                used_ml=used_ml,
                ml_rpe=ml_rpe,
                ml_confidence=ml_confidence,
                fallback_reason=fallback_reason,
                source_label=source_label,
                anomaly_flag=anomaly_flag,
                core_weight_kg=core_weight_kg,
            )
            explanation = ExplanationLayer.explain(decision, science)

            adapted_exercises.append(AdaptedExercise(
                exercise_id=exercise_id,
                exercise_name=exercise_name,
                sets=sets,
                rep_range=rep_range,
                target_reps=target_reps,
                target_weight_kg=new_weight,
                explanation=explanation,
                used_ml=used_ml,
            ))

            # ── Plateau detection ─────────────────────────────────────────────
            if _is_plateau(exercise_id, science.plateau_detection_sessions, db_session):
                n = science.plateau_detection_sessions
                plateau_warnings.append(
                    f"📊 Плато {n} сессий [{exercise_name}] — попробуй другое упражнение или измени диапазон повторений"
                )

        return AdaptationResult(
            exercises=adapted_exercises,
            science_version=science.version,
            plateau_warnings=plateau_warnings,
        )


# ─── Private Helpers ──────────────────────────────────────────────────────────

def _double_progression_recommendation(
    current_weight: float,
    current_reps: int,
    rep_range: tuple[int, int],
    science: "ScienceConfig",
    equipment_type: "EquipmentType",
    is_compound: bool,
    recovery_coeff: float,
) -> tuple[float, int]:
    """Compute next-session weight and reps via Double Progression."""
    from gym_coach_brain.core.progression import calculate_double_progression

    result = calculate_double_progression(
        current_reps=current_reps,
        current_weight=current_weight,
        rep_range=rep_range,
        science=science,
        equipment_type=equipment_type,
        is_compound=is_compound,
    )
    return result.new_weight * recovery_coeff, result.new_reps


def _resolve_target_rpe(planned_exercise: dict, science: "ScienceConfig") -> float:
    target_rpe = planned_exercise.get("target_rpe")
    if target_rpe is not None:
        return float(target_rpe)
    return (science.ml.rpe_easy_threshold + science.ml.rpe_hard_threshold) / 2.0


def _compute_delta_percent(core_weight_kg: float, ml_weight_kg: float) -> float:
    if core_weight_kg <= 0:
        return 0.0
    return abs(ml_weight_kg - core_weight_kg) / core_weight_kg


def _effective_rpe_error(
    predicted_rpe: float,
    target_rpe: float,
    science: "ScienceConfig",
) -> float:
    """Ignore small target misses so ML does not oscillate around steady-state loads."""
    error = predicted_rpe - target_rpe
    deadband = science.ml.rpe_correction_deadband
    if abs(error) <= deadband:
        return 0.0
    return math.copysign(abs(error) - deadband, error)


def _confidence_correction_scale(confidence: float, science: "ScienceConfig") -> float:
    """Scale correction strength smoothly between threshold and full confidence."""
    threshold = science.ml.confidence_threshold
    if confidence <= threshold:
        return 0.0
    if threshold >= 1.0:
        return 1.0
    normalized = min(1.0, max(0.0, (confidence - threshold) / (1.0 - threshold)))
    min_scale = science.ml.min_confidence_correction_scale
    return min_scale + (1.0 - min_scale) * normalized


def _format_ai_source_label(
    ml_weight_kg: float,
    core_weight_kg: float,
    predicted_rpe: float,
    confidence: float,
) -> str:
    adjustment = ml_weight_kg - core_weight_kg
    confidence_percent = round(confidence * 100)
    return (
        f"[AI: {adjustment:+.1f}кг / RPE прогноз: {predicted_rpe:.1f} / "
        f"confidence: {confidence_percent}%]"
    )


def _format_low_confidence_source_label(confidence: float) -> str:
    confidence_percent = round(confidence * 100)
    return f"[ядро: confidence {confidence_percent}% < порога]"


def _format_anomaly_source_label(
    delta_percent: float,
    max_correction_percent: float,
) -> str:
    return (
        f"[AI заблокирован: дельта {round(delta_percent * 100)}% > "
        f"{round(max_correction_percent * 100)}% лимит]"
    )


def _update_prediction_record(
    prediction,
    core_weight_kg: float,
    ml_weight_kg: float | None,
    anomaly_flag: bool,
    source_label: str,
) -> None:
    prediction.core_weight_kg = core_weight_kg
    prediction.ml_weight_kg = ml_weight_kg
    prediction.ml_adjustment_kg = (
        0.0 if ml_weight_kg is None else ml_weight_kg - core_weight_kg
    )
    prediction.anomaly_flag = anomaly_flag
    prediction.source_label = source_label


def _fallback_recommendation(
    previous_performance: ExercisePerformanceSnapshot,
    planned_weight: float,
    planned_target_reps: int,
    rep_range: tuple[int, int],
    science: "ScienceConfig",
    equipment_type: "EquipmentType",
    is_compound: bool,
    recovery_coeff: float,
) -> tuple[float, int, str | None]:
    """Choose deterministic fallback without re-progressing when history is absent."""
    if not previous_performance.has_completed_history:
        return planned_weight, planned_target_reps, "no completed history"

    new_weight, target_reps = _double_progression_recommendation(
        current_weight=previous_performance.current_weight,
        current_reps=previous_performance.current_reps,
        rep_range=rep_range,
        science=science,
        equipment_type=equipment_type,
        is_compound=is_compound,
        recovery_coeff=recovery_coeff,
    )
    return new_weight, target_reps, None


def _build_features(
    exercise_id: int,
    session_id: int,
    set_number: int,
    current_weight: float,
    current_reps: int,
    recovery_signal: "RecoverySignal | None",
    science: "ScienceConfig",
    db_session: "SASession",
) -> dict:
    """Build feature dict for RPEModelProtocol.predict() from real DB context."""
    from gym_coach_brain.data.features import build_feature_vector

    feature_vector = build_feature_vector(
        exercise_id=exercise_id,
        session_id=session_id,
        set_number=set_number,
        weight_kg=current_weight,
        reps=current_reps,
        session=db_session,
    )
    features = vars(feature_vector).copy()
    if recovery_signal is not None:
        features["readiness_score"] = recovery_signal.coefficient
    features["muscle_group_fatigue_estimate"] = _estimate_muscle_group_fatigue(
        exercise_id=exercise_id,
        current_session_id=session_id,
        science=science,
        db_session=db_session,
    )
    return features


def _get_latest_db_prediction(
    session_id: int,
    exercise_id: int,
    db_session: "SASession",
):
    """Return the most recent ML prediction for a session/exercise pair."""
    from gym_coach_brain.data.models import RPEPrediction

    return (
        db_session.query(RPEPrediction)
        .filter_by(session_id=session_id, exercise_id=exercise_id)
        .order_by(RPEPrediction.created_at.desc(), RPEPrediction.id.desc())
        .first()
    )


def _get_previous_performance(
    exercise_id: int,
    current_session: "WorkoutSession",
    fallback_weight: float,
    fallback_reps: int,
    rep_range: tuple[int, int],
    db_session: "SASession",
) -> ExercisePerformanceSnapshot:
    """Load the most recent completed exercise performance for progression logic.

    Ensures the history lookup is strictly limited to sessions that occurred before
    the current session to avoid using "future" data in case of out-of-order logging.
    """
    from sqlalchemy import and_, or_

    from gym_coach_brain.data.models import ReadinessLog, RPEPrediction, WorkoutSession, WorkoutSet

    # Filter for sessions that are completed AND occurred before current session
    latest_session_row = (
        db_session.query(WorkoutSession.id)
        .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
        .filter(
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSession.status == "completed",
            or_(
                WorkoutSession.session_date < current_session.session_date,
                and_(
                    WorkoutSession.session_date == current_session.session_date,
                    WorkoutSession.id < current_session.id,
                ),
            ),
        )
        .order_by(WorkoutSession.session_date.desc(), WorkoutSession.id.desc())
        .first()
    )
    if latest_session_row is None:
        return ExercisePerformanceSnapshot(
            current_weight=fallback_weight,
            current_reps=_clamp_target_reps(fallback_reps, rep_range),
            has_completed_history=False,
        )

    latest_session_id = latest_session_row[0]
    sets = (
        db_session.query(WorkoutSet)
        .filter_by(session_id=latest_session_id, exercise_id=exercise_id)
        .order_by(WorkoutSet.set_number.asc())
        .all()
    )
    if not sets:
        return ExercisePerformanceSnapshot(
            current_weight=fallback_weight,
            current_reps=_clamp_target_reps(fallback_reps, rep_range),
            has_completed_history=False,
        )

    weight_to_sets: dict[float, list] = defaultdict(list)
    for workout_set in sets:
        weight_to_sets[float(workout_set.weight_kg)].append(workout_set)

    # Prefer the repeated working-set load over a one-off top set in pyramid sessions.
    working_weight, working_sets = max(
        weight_to_sets.items(),
        key=lambda item: (len(item[1]), item[0]),
    )
    working_sets = [
        workout_set
        for workout_set in working_sets
        if abs(workout_set.weight_kg - working_weight) <= 1e-9
    ]
    achieved_reps = min(workout_set.reps for workout_set in working_sets)
    prediction = (
        db_session.query(RPEPrediction)
        .filter_by(session_id=latest_session_id, exercise_id=exercise_id)
        .order_by(RPEPrediction.created_at.desc(), RPEPrediction.id.desc())
        .first()
    )
    if prediction is not None and prediction.core_weight_kg is not None:
        working_weight = float(prediction.core_weight_kg)

    previous_session = db_session.get(WorkoutSession, latest_session_id)
    readiness_log = None
    if previous_session is not None and previous_session.session_date:
        readiness_log = (
            db_session.query(ReadinessLog)
            .filter_by(session_date=previous_session.session_date[:10])
            .first()
        )
    recovery_score = (
        float(readiness_log.recovery_score)
        if readiness_log is not None and readiness_log.recovery_score is not None
        else 1.0
    )
    if (
        recovery_score > 0.0
        and not (prediction is not None and prediction.core_weight_kg is not None)
    ):
        working_weight = working_weight / recovery_score
    return ExercisePerformanceSnapshot(
        current_weight=float(working_weight),
        current_reps=_clamp_target_reps(achieved_reps, rep_range),
        has_completed_history=True,
    )


def _target_reps_for_ml(
    ml_rpe: float,
    previous_performance: ExercisePerformanceSnapshot,
    new_weight: float,
    rep_range: tuple[int, int],
    science: "ScienceConfig",
) -> int:
    """Determine target repetitions for the ML adaptation path.

    - If weight increases: reset reps to rep_min (standard Double Progression).
    - If weight stays same but RPE is easy: increment reps (first progression).
    - If weight stays same and RPE is on target: hold current reps.
    """
    if new_weight > previous_performance.current_weight + 1e-9:
        return rep_range[0]

    # If weight is same (or less), we handle the "rep progression" part of Double Progression
    if ml_rpe < science.ml.rpe_easy_threshold:
        return _clamp_target_reps(previous_performance.current_reps + 1, rep_range)

    return _clamp_target_reps(previous_performance.current_reps, rep_range)


def _clamp_target_reps(value: int | float, rep_range: tuple[int, int]) -> int:
    """Clamp target reps into the active methodology range."""
    rep_min, rep_max = rep_range
    return max(rep_min, min(rep_max, int(value)))


def _is_plateau(
    exercise_id: int,
    n_sessions: int,
    db_session: "SASession",
) -> bool:
    """Return True if no weight or volume improvement over the last n_sessions.

    Plateau = most recent session is no better than the oldest session in the
    window. Handles both stagnation (same values) AND regression (values went
    down then back up). Float tolerance of 1e-9 avoids spurious float equality
    failures.

    Performance: uses a subquery to limit DB fetch to only the n relevant sessions
    rather than loading the entire exercise history into memory.

    If fewer than n_sessions of data exist → not enough history → no plateau.
    """
    from sqlalchemy import select

    from gym_coach_brain.data.models import WorkoutSet, WorkoutSession

    # Subquery: IDs of the n most recent completed sessions containing this exercise
    recent_session_ids_stmt = (
        select(WorkoutSession.id)
        .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
        .filter(
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSession.status == "completed",
        )
        .order_by(WorkoutSession.session_date.desc(), WorkoutSession.id.desc())
        .distinct()
        .limit(n_sessions)
    )
    # Using a list of IDs for the .in_() filter for maximum compatibility across dialects
    recent_ids = db_session.execute(recent_session_ids_stmt).scalars().all()

    if len(recent_ids) < n_sessions:
        return False  # Not enough history

    rows = (
        db_session.query(WorkoutSet)
        .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
        .filter(
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSet.session_id.in_(recent_ids),
        )
        .order_by(WorkoutSession.session_date.desc(), WorkoutSession.id.desc())
        .all()
    )

    # Group by session preserving DESC date order (most recent first)
    session_data: dict[int, dict] = defaultdict(lambda: {"weight": 0.0, "volume": 0.0})
    for row in rows:
        sid = row.session_id
        session_data[sid]["weight"] = max(session_data[sid]["weight"], row.weight_kg)
        session_data[sid]["volume"] += (row.weight_kg * row.reps if row.weight_kg > 0 else row.reps)

    # Convert to list preserving the DESC order from query results
    sessions = []
    seen_ids = set()
    for row in rows:
        if row.session_id not in seen_ids:
            sessions.append(session_data[row.session_id])
            seen_ids.add(row.session_id)

    if len(sessions) < n_sessions:
        return False

    # sessions[0] = most recent, sessions[-1] = oldest in the window
    most_recent = sessions[0]
    oldest = sessions[-1]
    weight_grew = most_recent["weight"] > oldest["weight"] + 1e-9
    volume_grew = most_recent["volume"] > oldest["volume"] + 1e-9
    return not weight_grew and not volume_grew


def _estimate_muscle_group_fatigue(
    exercise_id: int,
    current_session_id: int,
    science: "ScienceConfig",
    db_session: "SASession",
) -> float:
    """Estimate recent same-muscle workload as a normalized fatigue proxy.

    Normalization: total sets over lookback sessions / (PUOS limit * lookback sessions).
    """
    from sqlalchemy import func

    from gym_coach_brain.data.models import Exercise, WorkoutSession, WorkoutSet

    exercise = db_session.get(Exercise, exercise_id)
    if exercise is None:
        return 0.0

    recent_session_limit = max(1, science.ml.fatigue_lookback_sessions)
    recent_session_ids = (
        db_session.query(WorkoutSession.id)
        .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
        .join(Exercise, WorkoutSet.exercise_id == Exercise.id)
        .filter(
            WorkoutSession.status == "completed",
            WorkoutSession.id != current_session_id,
            Exercise.primary_muscle_id == exercise.primary_muscle_id,
        )
        .order_by(WorkoutSession.session_date.desc(), WorkoutSession.id.desc())
        .distinct()
        .limit(recent_session_limit)
        .subquery()
    )
    session_ids = db_session.query(recent_session_ids.c.id).all()
    if not session_ids:
        return 0.0

    total_sets = (
        db_session.query(func.count(WorkoutSet.id))
        .join(Exercise, WorkoutSet.exercise_id == Exercise.id)
        .filter(
            WorkoutSet.session_id.in_([row[0] for row in session_ids]),
            Exercise.primary_muscle_id == exercise.primary_muscle_id,
        )
        .scalar()
        or 0
    )
    # Normalize against the cumulative PUOS capacity over the lookback window
    capacity = float(max(1, science.puos.max_sets_per_group * recent_session_limit))
    return min(1.0, float(total_sets) / capacity)

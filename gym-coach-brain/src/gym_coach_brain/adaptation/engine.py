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


@dataclass
class AdaptedExercise:
    """Single exercise in the adapted plan."""
    exercise_id: int
    exercise_name: str
    sets: int
    rep_range: tuple[int, int]        # (min, max)
    target_weight_kg: float
    explanation: str                   # from ExplanationLayer.explain()
    used_ml: bool


@dataclass
class AdaptationResult:
    """Full adapted workout plan for a session."""
    exercises: list[AdaptedExercise]
    science_version: str               # science.version — traceability
    plateau_warnings: list[str] = field(default_factory=list)


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
            exercise_name = planned_ex["exercise_name"]
            sets = planned_ex.get("sets", 3)
            last_weight = planned_ex.get("target_weight_kg", 0.0)

            # Retrieve exercise metadata for equipment type
            exercise = db_session.query(Exercise).filter_by(id=exercise_id).first()
            equipment_type = (
                EquipmentType(exercise.equipment_type) if exercise else EquipmentType.barbell
            )
            is_compound = exercise.is_compound if exercise else True

            # ── ML path ──────────────────────────────────────────────────────
            used_ml = False
            ml_rpe: float | None = None
            ml_confidence: float | None = None
            fallback_reason: str | None = None

            # Check rpe_predictions table first (populated by MLWorker async)
            db_prediction = (
                db_session.query(RPEPrediction)
                .filter_by(session_id=session.id, exercise_id=exercise_id)
                .first()
            )
            if db_prediction and db_prediction.confidence_score >= science.ml.confidence_threshold:
                used_ml = True
                ml_rpe = db_prediction.predicted_rpe
                ml_confidence = db_prediction.confidence_score
                adjusted_weight = _adjust_weight_by_rpe(
                    ml_rpe, last_weight, science, is_compound
                )
                new_weight = round_to_equipment_increment(adjusted_weight * recovery_coeff, equipment_type, science)
            elif db_prediction:
                # DB prediction exists but confidence is too low
                ml_confidence = db_prediction.confidence_score
                fallback_reason = f"confidence {ml_confidence:.2f} below threshold {science.ml.confidence_threshold}"
                logger.warning(
                    "ML fallback: {reason} for exercise '{ex}'",
                    reason=fallback_reason,
                    ex=exercise_name,
                )
                new_weight = _double_progression_weight(
                    last_weight, rep_range, science, equipment_type, is_compound, recovery_coeff
                )
                new_weight = round_to_equipment_increment(new_weight, equipment_type, science)
            elif self._rpe_model is not None:
                # Fallback to direct model call (e.g., in-process during session)
                features = _build_features(exercise_id, last_weight, db_session)
                rpe_pred, conf = self._rpe_model.predict(features)
                if conf >= science.ml.confidence_threshold:
                    used_ml = True
                    ml_rpe = rpe_pred
                    ml_confidence = conf
                    adjusted_weight = _adjust_weight_by_rpe(rpe_pred, last_weight, science, is_compound)
                    new_weight = round_to_equipment_increment(adjusted_weight * recovery_coeff, equipment_type, science)
                else:
                    ml_confidence = conf
                    fallback_reason = f"confidence {conf:.2f} below threshold {science.ml.confidence_threshold}"
                    logger.warning(
                        "ML fallback: {reason} for exercise '{ex}'",
                        reason=fallback_reason,
                        ex=exercise_name,
                    )
                    new_weight = _double_progression_weight(
                        last_weight, rep_range, science, equipment_type, is_compound, recovery_coeff
                    )
                    new_weight = round_to_equipment_increment(new_weight, equipment_type, science)
            else:
                # No ML available — pure deterministic
                fallback_reason = "no rpe_model provided"
                logger.warning(
                    "ML fallback: {reason} for exercise '{ex}'",
                    reason=fallback_reason,
                    ex=exercise_name,
                )
                new_weight = _double_progression_weight(
                    last_weight, rep_range, science, equipment_type, is_compound, recovery_coeff
                )
                new_weight = round_to_equipment_increment(new_weight, equipment_type, science)

            decision = AdaptationDecision(
                exercise_name=exercise_name,
                previous_weight=last_weight,
                new_weight=new_weight,
                used_ml=used_ml,
                ml_rpe=ml_rpe,
                ml_confidence=ml_confidence,
                fallback_reason=fallback_reason,
            )
            explanation = ExplanationLayer.explain(decision, science)

            adapted_exercises.append(AdaptedExercise(
                exercise_id=exercise_id,
                exercise_name=exercise_name,
                sets=sets,
                rep_range=rep_range,
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

def _adjust_weight_by_rpe(
    predicted_rpe: float,
    current_weight: float,
    science: "ScienceConfig",
    is_compound: bool,
) -> float:
    """Adjust weight based on ML-predicted RPE.

    RPE < 7: athlete has capacity → increment weight (Double Progression step)
    RPE 7-8.5: on target → keep weight
    RPE > 8.5: close to failure → hold or decrease by isolation increment
    """
    increment = (
        science.progression.compound_increment_kg if is_compound
        else science.progression.isolation_increment_kg
    )
    if predicted_rpe < 7.0:
        return current_weight + increment
    elif predicted_rpe > 8.5:
        return max(0.0, current_weight - increment)
    return current_weight


def _double_progression_weight(
    last_weight: float,
    rep_range: tuple[int, int],
    science: "ScienceConfig",
    equipment_type: "EquipmentType",
    is_compound: bool,
    recovery_coeff: float,
) -> float:
    """Compute next-session weight via Double Progression then apply recovery scaling."""
    from gym_coach_brain.core.progression import calculate_double_progression
    # Use rep_max as current_reps to trigger weight progression (conservative assumption)
    result = calculate_double_progression(
        current_reps=rep_range[1],
        current_weight=last_weight,
        rep_range=rep_range,
        science=science,
        equipment_type=equipment_type,
        is_compound=is_compound,
    )
    return result.new_weight * recovery_coeff


def _build_features(
    exercise_id: int,
    last_weight: float,
    db_session: "SASession",
) -> dict:
    """Build feature dict for RPEModelProtocol.predict()."""
    return {
        "exercise_id": exercise_id,
        "weight": last_weight,
        "set_number": 1,
        "reps": 0,
        "historical_rpe": 0.0,
        "readiness_score": 1.0,
        "days_since_last_session": 0,
        "muscle_group_fatigue_estimate": 0.0,
    }


def _is_plateau(
    exercise_id: int,
    n_sessions: int,
    db_session: "SASession",
) -> bool:
    """Return True if no weight or volume growth in last n_sessions for exercise_id.

    Plateau = same or decreasing (weight AND volume) across all N sessions.
    If fewer than n_sessions of data exist → no plateau (not enough data).
    """
    from gym_coach_brain.data.models import WorkoutSet, WorkoutSession

    # Get last n_sessions completed sessions containing this exercise
    rows = (
        db_session.query(WorkoutSet)
        .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
        .filter(
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSession.status == "completed",
        )
        .order_by(WorkoutSession.session_date.desc())
        .all()
    )

    # Group by session to compute per-session max_weight and total_volume
    session_data: dict[int, dict] = defaultdict(lambda: {"weight": 0.0, "volume": 0.0})

    for row in rows:
        sid = row.session_id
        session_data[sid]["weight"] = max(session_data[sid]["weight"], row.weight_kg)
        session_data[sid]["volume"] += (row.weight_kg * row.reps if row.weight_kg > 0 else row.reps)

    sessions = list(session_data.values())
    if len(sessions) < n_sessions:
        return False  # Not enough history

    recent = sessions[:n_sessions]
    weights = [s["weight"] for s in recent]
    volumes = [s["volume"] for s in recent]

    # Plateau: no growth in either metric
    return (max(weights) == min(weights)) and (max(volumes) == min(volumes))

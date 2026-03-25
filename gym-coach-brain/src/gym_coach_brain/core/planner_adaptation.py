"""
Pre-planning adaptation signals for gym-coach-brain slot-based planner.

Two-Phase Adaptation Pattern:
  Phase 1: Pre-Planning (readiness-aware slot selection)
  Phase 2: Post-Planning (weight/rep adaptation via adaptation/engine.py)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from gym_coach_brain.core.science import ScienceConfig


class PlannerEventType(str, Enum):
    PAIN_REPORT = "pain_report"
    READINESS_OVERRIDE = "readiness_override"
    SKIPPED_SESSION = "skipped_session"
    PERFORMANCE_FEEDBACK = "performance_feedback"
    PREFERENCE_REQUEST = "preference_request"


@dataclass
class PlannerEvent:
    event_type: PlannerEventType
    timestamp: datetime
    athlete_id: int
    data: dict


@dataclass
class PlanningContext:
    athlete_id: int
    split_label: str
    session_date: date
    recovery_signal_coefficient: float
    skipped_sessions: list[str]
    pain_reported_muscles: list[str]
    detraining_coefficient: float
    suppressed_slots: list[str]
    preference_requests: dict[str, str]


def apply_pre_planning_adaptation(
    base_template: tuple,
    recovery_signal_coefficient: float,
    skipped_sessions: list[str],
    pain_reported_muscles: list[str],
    days_since_last_session: int,
    science: "ScienceConfig",
) -> tuple:
    from gym_coach_brain.core.planner_slots import Slot

    suppressed: list[str] = []

    if recovery_signal_coefficient < 0.7:
        suppressed = _suppress_optional_slots(base_template)

    if pain_reported_muscles:
        suppressed.extend(_suppress_pain_slots(base_template, pain_reported_muscles))

    detraining_coeff = 1.0
    if days_since_last_session > science.planning.detraining_threshold_days:
        detraining_coeff = science.planning.detraining_coefficient

    filtered_slots = tuple(
        slot for slot in base_template
        if slot.slot_id not in suppressed
    )

    return filtered_slots, PlanningContext(
        athlete_id=0,
        split_label="",
        session_date=date.today(),
        recovery_signal_coefficient=recovery_signal_coefficient,
        skipped_sessions=skipped_sessions,
        pain_reported_muscles=pain_reported_muscles,
        detraining_coefficient=detraining_coeff,
        suppressed_slots=suppressed,
        preference_requests={},
    )


def _suppress_optional_slots(slots: tuple) -> list[str]:
    suppressed: list[str] = []
    for slot in slots:
        if not slot.required and slot.role.value in ("accessory",):
            suppressed.append(slot.slot_id)
    return suppressed


def _suppress_pain_slots(slots: tuple, pain_muscles: list[str]) -> list[str]:
    suppressed: list[str] = []
    for slot in slots:
        if any(muscle.lower() in [m.lower() for m in slot.target_muscles] for muscle in pain_muscles):
            if slot.required:
                continue
            suppressed.append(slot.slot_id)
    return suppressed


def get_planning_context(
    athlete_id: int,
    split_label: str,
    session_date: date,
    recovery_signal_coefficient: float,
    db_session: "SASession",
    science: "ScienceConfig",
) -> PlanningContext:
    from gym_coach_brain.data.models import WorkoutSession, ReadinessLog

    skipped_sessions = _get_skipped_sessions(athlete_id, db_session)

    pain_muscles: list[str] = _get_recent_pain_reports(athlete_id, db_session)

    last_session = (
        db_session.query(WorkoutSession)
        .filter(WorkoutSession.status == "completed")
        .order_by(WorkoutSession.session_date.desc())
        .first()
    )

    days_since = 0
    if last_session:
        last_date = date.fromisoformat(last_session.session_date[:10])
        days_since = (session_date - last_date).days

    detraining_coeff = 1.0
    if days_since > science.planning.detraining_threshold_days:
        detraining_coeff = science.planning.detraining_coefficient

    suppressed = []
    if recovery_signal_coefficient < 0.7:
        suppressed = _suppress_optional_slots(())

    return PlanningContext(
        athlete_id=athlete_id,
        split_label=split_label,
        session_date=session_date,
        recovery_signal_coefficient=recovery_signal_coefficient,
        skipped_sessions=skipped_sessions,
        pain_reported_muscles=pain_muscles,
        detraining_coefficient=detraining_coeff,
        suppressed_slots=suppressed,
        preference_requests={},
    )


def _get_skipped_sessions(athlete_id: int, db_session: "SASession") -> list[str]:
    return []


def _get_recent_pain_reports(athlete_id: int, db_session: "SASession") -> list[str]:
    return []


def store_planner_event(event: PlannerEvent, db_session: "SASession") -> None:
    pass


def get_recent_events(
    athlete_id: int,
    db_session: "SASession",
    since_date: date | None = None,
) -> list[PlannerEvent]:
    return []

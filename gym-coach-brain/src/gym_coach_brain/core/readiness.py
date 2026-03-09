"""
Readiness log processing and recovery signal calculation.

Implements FR17: lifestyle coefficients from readiness log entries.
RecoverySignal provides a deterministic coefficient (0.0–1.0) used by
WorkoutPlanner to scale planned training volume.

Formula from ScienceEvidence.md (recovery section):
    coefficient = hrv_component*hrv_weight + sleep_component*sleep_weight
                  + stress_component*stress_weight

References:
    Kiviniemi, A.M. et al. (2007). European Journal of Applied Physiology, 101, 743-751.
    Plews, D.J. et al. (2013). Sports Medicine, 43, 773-781.
    Buchheit, M. (2014). Frontiers in Physiology, 5, 112.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import ReadinessLog

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_RECOVERY_COEFFICIENT: float = 1.0
"""Coefficient used when no readiness log exists for the session."""

# Normalization reference values — fixed per ScienceEvidence.md methodology
SLEEP_OPTIMAL_HOURS: float = 8.0      # 8h = full sleep score (Hirshkowitz 2015)
STRESS_MAX_SCALE: float = 10.0        # 1–10 scale max
STRESS_MIN_SCALE: float = 1.0         # 1–10 scale min
HRV_REFERENCE_MAX: float = 100.0      # Reference max for HRV normalization


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class RecoverySignal:
    """Computed recovery readiness for a training session.

    Attributes:
        coefficient: Recovery coefficient 0.0 (exhausted) – 1.0 (fully recovered).
            Used as a multiplier for planned_volume in WorkoutPlanner.
        sleep_component: Normalized sleep score 0.0–1.0
        stress_component: Normalized stress score 0.0–1.0 (inverted; 1.0 = no stress)
        hrv_component: Normalized HRV score 0.0–1.0, or None if not measured.
            When None, weights are redistributed between sleep and stress.
    """
    coefficient: float
    sleep_component: float
    stress_component: float
    hrv_component: float | None


# ─── Core Functions ───────────────────────────────────────────────────────────

def calculate_recovery_signal(
    readiness_log: "ReadinessLog",
    science: "ScienceConfig",
) -> RecoverySignal:
    """Calculate composite recovery coefficient from readiness log entry.

    Pure function (no side effects). Coefficient is always clamped to [0.0, 1.0].

    Normalization:
    - sleep_hours: min(sleep_hours / 8.0, 1.0)  — 8h = optimal
    - stress_level (1–10): (10 - stress_level) / 9.0  — inverted scale
    - hrv_score: min(hrv_score / 100.0, 1.0)  — 100 = reference max

    When hrv_score is None, hrv_weight is redistributed proportionally
    between sleep_weight and stress_weight.

    Args:
        readiness_log: ReadinessLog ORM object with sleep_hours, stress_level, hrv_score
        science: ScienceConfig with recovery.hrv_weight, sleep_weight, stress_weight

    Returns:
        RecoverySignal with coefficient in [0.0, 1.0]

    References:
        [Source: gym-coach-brain/ScienceEvidence.md#Composite Readiness Formula]
        [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.3]
    """
    # Normalize each component to [0.0, 1.0]
    sleep_component = max(0.0, min(1.0, readiness_log.sleep_hours / SLEEP_OPTIMAL_HOURS))
    stress_component = max(0.0, min(1.0, (STRESS_MAX_SCALE - readiness_log.stress_level) / (
        STRESS_MAX_SCALE - STRESS_MIN_SCALE
    )))  # stress 1→1.0, stress 10→0.0

    rc = science.recovery

    if readiness_log.hrv_score is not None:
        hrv_component: float | None = min(
            readiness_log.hrv_score / HRV_REFERENCE_MAX, 1.0
        )
        raw = (
            hrv_component * rc.hrv_weight
            + sleep_component * rc.sleep_weight
            + stress_component * rc.stress_weight
        )
    else:
        # HRV absent: redistribute hrv_weight proportionally to sleep+stress
        non_hrv_total = rc.sleep_weight + rc.stress_weight
        if non_hrv_total > 0:
            effective_sleep_w = rc.sleep_weight / non_hrv_total
            effective_stress_w = rc.stress_weight / non_hrv_total
        else:
            effective_sleep_w = 0.5
            effective_stress_w = 0.5
        hrv_component = None
        raw = (
            sleep_component * effective_sleep_w
            + stress_component * effective_stress_w
        )

    return RecoverySignal(
        coefficient=max(0.0, min(1.0, raw)),
        sleep_component=sleep_component,
        stress_component=stress_component,
        hrv_component=hrv_component,
    )


def get_recovery_signal_or_default(
    session_date: str,
    db_session: "Session",
    science: "ScienceConfig",
) -> RecoverySignal:
    """Return RecoverySignal for session_date or default (coefficient=1.0) if absent.

    Args:
        session_date: ISO 8601 date string (YYYY-MM-DD or with timestamp) to look up
        db_session: SQLAlchemy Session
        science: ScienceConfig for weight parameters

    Returns:
        RecoverySignal — either computed from log or default with coefficient=1.0
    """
    from gym_coach_brain.data.models import ReadinessLog

    # Normalize to date-only (YYYY-MM-DD) regardless of whether a timestamp was passed
    date_str = session_date[:10]
    log = db_session.query(ReadinessLog).filter_by(session_date=date_str).first()
    if log is None:
        return RecoverySignal(
            coefficient=DEFAULT_RECOVERY_COEFFICIENT,
            sleep_component=1.0,
            stress_component=1.0,
            hrv_component=None,
        )
    return calculate_recovery_signal(log, science)

"""
Coverage Analyzer for gym-coach-brain slot-based planner.

Detects coverage gaps when equipment missing causes weekly volume below MEV.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from gym_coach_brain.core.science import ScienceConfig, WeeklyVolumeLandmark
    from gym_coach_brain.data.models import WorkoutSession


class GapSeverity(str, Enum):
    MINOR = "minor_gap"
    SIGNIFICANT = "significant_gap"
    CRITICAL = "critical_gap"


@dataclass
class CoverageGap:
    muscle_group: str
    severity: GapSeverity
    current_fractional_sets: float
    mev: float
    mv: float
    gap_size: float
    resolution_action: str


@dataclass
class CoverageGapReport:
    gaps: list[CoverageGap]
    total_muscles_tracked: int
    weeks_at_target_pct: float


EQUIPMENT_QUALITY_MULTIPLIER: dict[str, float] = {
    "barbell": 1.0,
    "dumbbell": 0.95,
    "machine": 0.90,
    "cable": 0.95,
    "bodyweight": 0.85,
    "resistance_band": 0.80,
    "pullup_bar": 0.90,
    "dips_bar": 0.90,
}


def fractional_contribution(
    exercise_primary_muscle: str,
    exercise_equipment_type: str,
    slot_role: str,
    weekly_volume_landmarks: dict[str, "WeeklyVolumeLandmark"],
) -> float:
    landmark = weekly_volume_landmarks.get(exercise_primary_muscle)
    if landmark is None:
        return 0.0

    multiplier = EQUIPMENT_QUALITY_MULTIPLIER.get(exercise_equipment_type, 0.8)

    role_fractional = {
        "primary": 1.0,
        "secondary": 0.5,
        "accessory": 0.25,
        "core": 0.1,
        "carry": 0.1,
    }.get(slot_role, 0.5)

    return role_fractional * multiplier


def compute_weekly_fractional_sets(
    sessions: list["WorkoutSession"],
    db_session: "SASession",
    weekly_volume_landmarks: dict[str, "WeeklyVolumeLandmark"],
) -> dict[str, float]:
    from gym_coach_brain.data.models import Exercise, WorkoutSet

    muscle_fractionals: dict[str, float] = {}

    for session in sessions:
        if session.status != "completed":
            continue

        sets = (
            db_session.query(WorkoutSet)
            .filter(WorkoutSet.session_id == session.id)
            .all()
        )

        for ws in sets:
            exercise = db_session.query(Exercise).filter_by(id=ws.exercise_id).first()
            if exercise is None:
                continue

            primary_muscle = exercise.primary_muscle.name if exercise.primary_muscle else ""
            equipment_type = exercise.equipment_type.value if hasattr(exercise.equipment_type, "value") else str(exercise.equipment_type)

            contribution = fractional_contribution(
                primary_muscle,
                equipment_type,
                "primary",
                weekly_volume_landmarks,
            )

            muscle_fractionals[primary_muscle] = muscle_fractionals.get(primary_muscle, 0.0) + contribution

            secondary_ids = exercise.secondary_muscle_id_list
            for sid in secondary_ids:
                from gym_coach_brain.data.models import MuscleGroup
                mg = db_session.query(MuscleGroup).filter_by(id=sid).first()
                if mg:
                    secondary_contrib = fractional_contribution(
                        mg.name,
                        equipment_type,
                        "secondary",
                        weekly_volume_landmarks,
                    )
                    muscle_fractionals[mg.name] = muscle_fractionals.get(mg.name, 0.0) + secondary_contrib

    return muscle_fractionals


def detect_coverage_gaps(
    muscle_fractionals: dict[str, float],
    weekly_volume_landmarks: dict[str, "WeeklyVolumeLandmark"],
) -> list[CoverageGap]:
    gaps: list[CoverageGap] = []

    for muscle, total_fractional in muscle_fractionals.items():
        landmark = weekly_volume_landmarks.get(muscle)
        if landmark is None:
            continue

        mev = landmark.mev
        mv = landmark.mv

        if total_fractional >= mv:
            continue

        gap_size = mv - total_fractional

        if total_fractional >= mev:
            severity = GapSeverity.MINOR
            resolution = "log_warning"
        elif total_fractional >= mv:
            severity = GapSeverity.SIGNIFICANT
            resolution = "activate_optional_slot_or_increase_intensity"
        else:
            severity = GapSeverity.CRITICAL
            resolution = "force_equipment_free_alternative_or_suggest_acquisition"

        gaps.append(CoverageGap(
            muscle_group=muscle,
            severity=severity,
            current_fractional_sets=total_fractional,
            mev=mev,
            mv=mv,
            gap_size=gap_size,
            resolution_action=resolution,
        ))

    return gaps


def generate_coverage_report(
    sessions: list["WorkoutSession"],
    db_session: "SASession",
    science: "ScienceConfig",
) -> CoverageGapReport:
    weekly_landmarks = {
        name: landmark
        for name, landmark in science.weekly_volume_landmarks.__dict__.items()
        if not name.startswith("_")
    }

    muscle_fractionals = compute_weekly_fractional_sets(sessions, db_session, weekly_landmarks)
    gaps = detect_coverage_gaps(muscle_fractionals, weekly_landmarks)

    total_tracked = len([m for m, v in muscle_fractionals.items() if v > 0])
    at_target = sum(1 for m, v in muscle_fractionals.items() if v >= weekly_landmarks.get(m, None) and v > 0)
    at_target_pct = at_target / max(1, total_tracked) if total_tracked > 0 else 0.0

    return CoverageGapReport(
        gaps=gaps,
        total_muscles_tracked=total_tracked,
        weeks_at_target_pct=at_target_pct,
    )


def resolve_coverage_gap(
    gap: CoverageGap,
    optional_slots_available: tuple,
) -> str | None:
    if gap.severity == GapSeverity.MINOR:
        return None

    if gap.severity == GapSeverity.SIGNIFICANT:
        return "activate_optional_support_slot"

    if gap.severity == GapSeverity.CRITICAL:
        return "suggest_equipment_acquisition"

    return None

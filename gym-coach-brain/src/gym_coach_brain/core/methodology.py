"""
Training methodology selection for workout planning.

Implements the pluggable methodology pattern from architecture ADR-002:
selecting a training methodology based on UserProfile.goal maps to
a MethodologySpec from ScienceConfig. Zero hardcoded rep ranges — all
values come from ScienceConfig, so methodology updates require only
updating ScienceEvidence.md.

References:
    Schoenfeld, B.J. & Grgic, J. (2021). PMC7927075.
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.4]
    [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import UserProfile


# ─── Types ────────────────────────────────────────────────────────────────────

class RepRange(NamedTuple):
    """Inclusive rep range for a given methodology."""
    min: int
    max: int


class ProgressionType(str, Enum):
    """Which progression algorithm to use for this methodology."""
    DOUBLE_PROGRESSION = "double_progression"   # default for hypertrophy/endurance
    APRE = "apre"                                # used for strength goal


# ─── Methodology Result ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Methodology:
    """Resolved methodology parameters for a training session.

    All values are derived from ScienceConfig — never hardcoded.
    The frozen dataclass ensures immutability (deterministic per call).

    Attributes:
        name: Methodology name ("strength" | "hypertrophy" | "endurance")
        rep_range: Inclusive rep range (min, max) from ScienceConfig
        progression_type: Which progression algorithm to apply
        frequency_min: Minimum training sessions per muscle group per week
        frequency_max: Maximum training sessions per muscle group per week
    """
    name: str
    rep_range: RepRange
    progression_type: ProgressionType
    frequency_min: int
    frequency_max: int


# ─── Goal → Progression Type Mapping ─────────────────────────────────────────

def get_progression_type(goal: str | None) -> ProgressionType:
    """Return the appropriate progression algorithm for a given goal.

    Strength training uses APRE (auto-regulatory) for near-maximal loads.
    Hypertrophy and endurance use Double Progression (volume-first progression).

    Args:
        goal: User's training goal. Case-insensitive. None → hypertrophy default.

    Returns:
        ProgressionType enum value.
    """
    if goal is not None and goal.lower() == "strength":
        return ProgressionType.APRE
    return ProgressionType.DOUBLE_PROGRESSION


# ─── Core Selector ────────────────────────────────────────────────────────────

def select_methodology(
    user_profile: "UserProfile",
    science: "ScienceConfig",
) -> Methodology:
    """Select and return a training methodology based on the athlete's goal.

    Pure function — no side effects, no DB calls, no randomness.
    Methodology parameters come entirely from ScienceConfig (zero hardcoding).

    Goal → Methodology mapping:
        "strength"            → science.methodologies.strength + APRE
        "hypertrophy" / None  → science.methodologies.hypertrophy + DOUBLE_PROGRESSION
        "endurance"           → science.methodologies.endurance + DOUBLE_PROGRESSION
        <any other value>     → default hypertrophy (safe fallback)

    Matching is case-insensitive: "STRENGTH", "Strength", "strength" all match.

    Args:
        user_profile: UserProfile ORM object with .goal (nullable string)
        science: ScienceConfig instance with .methodologies section

    Returns:
        Methodology with rep_range and progression_type from ScienceConfig.

    References:
        [Source: gym-coach-brain/ScienceEvidence.md#Training Methodologies]
        [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002 ScienceConfig Loading]
    """
    goal = user_profile.goal
    normalized = goal.lower() if goal is not None else None

    # Goal -> (spec_attr, methodology_name) mapping
    # Fallback to hypertrophy for any unknown goal or None
    mapping = {
        "strength": ("strength", "strength"),
        "endurance": ("endurance", "endurance"),
    }

    spec_attr, name = mapping.get(normalized, ("hypertrophy", "hypertrophy"))
    spec = getattr(science.methodologies, spec_attr)

    return Methodology(
        name=name,
        rep_range=RepRange(min=spec.rep_min, max=spec.rep_max),
        progression_type=get_progression_type(goal),
        frequency_min=spec.frequency_per_week_min,
        frequency_max=spec.frequency_per_week_max,
    )

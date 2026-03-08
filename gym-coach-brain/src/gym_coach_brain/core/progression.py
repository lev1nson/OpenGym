"""
Double Progression algorithm.

Implements two-variable progressive overload: reps first, then weight.
All functions are pure — no DB calls, no side effects.

References:
    Schoenfeld, B.J. & Grgic, J. (2021). Sports, 9(2), 32. PMC7927075.
"""
from dataclasses import dataclass, field

from gym_coach_brain.core.science import ScienceConfig
from gym_coach_brain.data.models import EquipmentType


@dataclass
class ProgressionResult:
    """Result of a double progression calculation.

    Attributes:
        new_reps: Target rep count for the next session
        new_weight: Target weight for the next session in kg (0.0 for bodyweight)
        suggest_added_load: True if athlete has topped out bodyweight rep range
            and should consider adding external load (vest, resistance band)
    """

    new_reps: int
    new_weight: float
    suggest_added_load: bool = field(default=False)


def calculate_double_progression(
    current_reps: int,
    current_weight: float,
    rep_range: tuple[int, int],
    science: ScienceConfig,
    equipment_type: EquipmentType = EquipmentType.barbell,
    is_compound: bool = True,
) -> ProgressionResult:
    """Calculate next session reps and weight using Double Progression.

    ⚠️ USAGE SCOPE: Call ONLY when generating the plan for the NEXT session,
    using final data from the previous session stored in the DB.
    Do NOT call this within an active session — use calculate_apre_adjustment()
    from core/apre.py for in-session recommendations.

    Logic:
        - Non-bodyweight: if current_reps < rep_max → increment reps by 1, keep weight.
          If current_reps >= rep_max → increase weight by compound_increment_kg (compound)
          or isolation_increment_kg (isolation), reset reps to rep_min.
        - Bodyweight: progress reps only within rep_range. At rep_max, return suggest_added_load=True
          to signal the athlete should add external load (weight vest, resistance band).

    Args:
        current_reps: Reps achieved in the last session for this exercise
        current_weight: Weight used in the last session in kg (0.0 for bodyweight)
        rep_range: (rep_min, rep_max) target repetition range from current methodology
        science: ScienceConfig with progression.compound_increment_kg and isolation_increment_kg
        equipment_type: Exercise equipment type (determines bodyweight vs weighted branch)
        is_compound: True for compound movements (uses compound_increment_kg),
            False for isolation exercises (uses isolation_increment_kg).
            Matches Exercise.is_compound field from data/models.py.

    Returns:
        ProgressionResult with new_reps, new_weight, and optional suggest_added_load flag.
        Note: new_weight is NOT rounded to equipment step — apply
        round_to_equipment_increment() from core/weight_utils.py before displaying.
    """
    rep_min, rep_max = rep_range

    # ── Bodyweight branch ────────────────────────────────────────────────────
    if equipment_type == EquipmentType.bodyweight:
        if current_reps < rep_max:
            return ProgressionResult(new_reps=current_reps + 1, new_weight=0.0)
        else:
            return ProgressionResult(
                new_reps=rep_max,
                new_weight=0.0,
                suggest_added_load=True,
            )

    # ── Weighted branch ──────────────────────────────────────────────────────
    if current_reps >= rep_max:
        # All sets completed at top of range: advance weight, reset reps
        increment = (
            science.progression.compound_increment_kg
            if is_compound
            else science.progression.isolation_increment_kg
        )
        return ProgressionResult(
            new_reps=rep_min,
            new_weight=max(0.0, current_weight + increment),
        )
    else:
        return ProgressionResult(
            new_reps=current_reps + 1,
            new_weight=current_weight,
        )

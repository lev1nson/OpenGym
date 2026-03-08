"""
APRE (Auto-Regulatory Progressive Resistance Exercise) algorithm.

Implements APRE-6 weight adjustment table from Knight (1979).
All functions are pure — no DB calls, no side effects.

References:
    Knight, K.L. (1979). AJSM, 7(6), 336-337.
    Mann, J.B. et al. (2010). JSCR, 24(7), 1718-1723 (PubMed 20543732).
"""

from gym_coach_brain.core.science import ScienceConfig


def rpe_from_rir(rir: int) -> float:
    """Convert Reps In Reserve to RPE.

    Formula: RPE = 10.0 - RIR
    RIR=0 means performed to failure (RPE=10.0).
    Matches WorkoutSet.rpe computed column convention.

    Args:
        rir: Reps In Reserve (0=to failure, 4=very easy). DB constrains to 0–4,
            but this function defensively clamps output to [6.0, 10.0].

    Returns:
        RPE value clamped to [6.0, 10.0] range.
    """
    return min(10.0, max(6.0, 10.0 - float(rir)))


def calculate_apre_adjustment(
    actual_reps: int,
    target_reps: int,
    current_weight: float,
    science: ScienceConfig,
) -> float:
    """Calculate recommended weight for the next set using APRE-6 protocol.

    ⚠️ USAGE SCOPE: Call ONLY within an active training session, after each
    logged AMRAP set to recommend weight for the athlete's next set.
    Do NOT call this when generating the next session plan — use
    calculate_double_progression() from core/progression.py instead.

    Uses Knight's (1979) original APRE-6 adjustment table (converted to kg):
        ≤ target-2 reps: decrease by apre_6_step_max_kg
        target-1 to target+1: no change (at target)
        target+2 to target+4: increase by apre_6_step_min_kg
        ≥ target+5 reps: increase by apre_6_step_max_kg

    For APRE-6 (target=6): ≤4 / 5-7 / 8-10 / ≥11

    Args:
        actual_reps: Reps performed in the AMRAP set
        target_reps: Target rep count (6 for APRE-6, 3 for APRE-3, etc.)
        current_weight: Current working weight in kg
        science: ScienceConfig with progression.apre_6_step_min_kg and apre_6_step_max_kg

    Returns:
        Recommended weight for next set (pure float, not rounded to equipment step).
        Apply round_to_equipment_increment() from core/weight_utils.py before displaying.
    """
    step_min = science.progression.apre_6_step_min_kg
    step_max = science.progression.apre_6_step_max_kg

    if actual_reps <= target_reps - 2:          # ≤4 for APRE-6
        return max(0.0, current_weight - step_max)
    elif actual_reps <= target_reps + 1:         # 5-7 for APRE-6
        return current_weight
    elif actual_reps <= target_reps + 4:         # 8-10 for APRE-6
        return current_weight + step_min
    else:                                         # ≥11 for APRE-6
        return current_weight + step_max

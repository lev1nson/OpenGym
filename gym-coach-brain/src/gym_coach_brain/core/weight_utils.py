"""
Equipment weight rounding utilities.

All functions are pure — no DB calls, no side effects.
"""
import math

from gym_coach_brain.core.science import ScienceConfig
from gym_coach_brain.data.models import EquipmentType


def round_to_equipment_increment(
    weight_kg: float,
    equipment_type: EquipmentType,
    science: ScienceConfig,
) -> float:
    """Round weight to the nearest physically achievable increment for equipment type.

    Pure function — no side effects, no DB calls.

    Rounding uses standard nearest-step rounding (round half up).
    Equipment-specific increments from science.equipment_increments.

    Args:
        weight_kg: Raw weight in kg to round
        equipment_type: Type of equipment (determines step size)
        science: ScienceConfig with equipment_increments section

    Returns:
        Weight rounded to nearest equipment step in kg.
        - bodyweight: always 0.0
        - resistance_band / pullup_bar / dips_bar: unchanged (no meaningful step)
        - barbell / dumbbell / machine / cable: rounded to nearest step

    Notes:
        Rounding: uses floor(w/step + 0.5)*step for true round-half-up semantics,
        avoiding Python's default banker's rounding (round half to even).
        Floating-point safety: final result rounded to 10 decimal places to
        avoid representation drift (e.g. 82.50000000000001).
    """
    increments = science.equipment_increments

    # ── Special equipment: no rounding ─────────────────────────────────────
    if equipment_type == EquipmentType.bodyweight:
        return 0.0

    if equipment_type in (
        EquipmentType.resistance_band,
        EquipmentType.pullup_bar,
        EquipmentType.dips_bar,
    ):
        return weight_kg

    # ── Step-incremented equipment ──────────────────────────────────────────
    step_map = {
        EquipmentType.barbell: increments.barbell,
        EquipmentType.dumbbell: increments.dumbbell,
        EquipmentType.machine: increments.machine,
        EquipmentType.cable: increments.cable,
    }
    step = step_map.get(equipment_type)
    if step is None or step <= 0:
        return weight_kg

    # Round half up (not banker's rounding): floor(x/step + 0.5) * step
    rounded = math.floor(weight_kg / step + 0.5) * step
    return round(rounded, 10)

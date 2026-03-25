"""
Slot-based prescription logic for gym-coach-brain.

Assigns sets, rep ranges, and progression behavior based on slot role.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gym_coach_brain.core.planner_slots import SlotRole, PrescriptionMode

if TYPE_CHECKING:
    from gym_coach_brain.core.planner_slots import Slot
    from gym_coach_brain.data.models import Exercise, MuscleGroup


@dataclass
class SlotPrescription:
    sets: int
    rep_min: int
    rep_max: int
    prescription_mode: "PrescriptionMode"
    description: str


_DEFAULT_PRESCRIPTIONS: dict["SlotRole", SlotPrescription] = {
    SlotRole.PRIMARY: SlotPrescription(
        sets=3,
        rep_min=6,
        rep_max=10,
        prescription_mode=PrescriptionMode.REPS,
        description="primary compound movement",
    ),
    SlotRole.SECONDARY: SlotPrescription(
        sets=3,
        rep_min=8,
        rep_max=12,
        prescription_mode=PrescriptionMode.REPS,
        description="secondary compound movement",
    ),
    SlotRole.ACCESSORY: SlotPrescription(
        sets=2,
        rep_min=8,
        rep_max=15,
        prescription_mode=PrescriptionMode.REPS,
        description="accessory isolation movement",
    ),
    SlotRole.CARRY: SlotPrescription(
        sets=3,
        rep_min=2,
        rep_max=4,
        prescription_mode=PrescriptionMode.DISTANCE,
        description="carry work bout",
    ),
    SlotRole.CORE: SlotPrescription(
        sets=3,
        rep_min=20,
        rep_max=40,
        prescription_mode=PrescriptionMode.SECONDS,
        description="timed core hold",
    ),
}

_CARRY_SPECIFIC: dict[str, tuple[int, int]] = {
    "Farmer's Walk": (30, 60),
    "Trap Bar Walk": (20, 40),
    "Suitcase Carry": (15, 30),
}

_ARM_ISOLATION: SlotPrescription = SlotPrescription(
    sets=2,
    rep_min=8,
    rep_max=15,
    prescription_mode=PrescriptionMode.REPS,
    description="arm isolation movement",
)

_CLAVES_PRESCRIPTION: SlotPrescription = SlotPrescription(
    sets=2,
    rep_min=10,
    rep_max=20,
    prescription_mode=PrescriptionMode.REPS,
    description="calves isolation",
)


def get_slot_prescription(
    slot: "Slot",
    exercise: "Exercise",
    muscle_group: "MuscleGroup",
    default_sets: int,
    base_rep_range: tuple[int, int],
) -> SlotPrescription:
    if slot.slot_id == "calves_slot":
        return _CLAVES_PRESCRIPTION

    if slot.role == SlotRole.ACCESSORY:
        if _is_arm_isolation(exercise, muscle_group):
            return _ARM_ISOLATION
        return _DEFAULT_PRESCRIPTIONS.get(
            SlotRole.ACCESSORY,
            SlotPrescription(sets=2, rep_min=8, rep_max=15, prescription_mode=PrescriptionMode.REPS, description="accessory"),
        )

    if slot.role == SlotRole.CARRY:
        carry_prescription = _CARRY_SPECIFIC.get(exercise.name)
        if carry_prescription:
            return SlotPrescription(
                sets=3,
                rep_min=carry_prescription[0],
                rep_max=carry_prescription[1],
                prescription_mode=PrescriptionMode.DISTANCE,
                description=f"{exercise.name} carry",
            )
        return SlotPrescription(
            sets=3,
            rep_min=20,
            rep_max=40,
            prescription_mode=PrescriptionMode.SECONDS,
            description=f"{exercise.name} timed hold",
        )

    if slot.role == SlotRole.CORE:
        movement = exercise.movement_pattern.name if exercise.movement_pattern else ""
        if movement == "carry":
            carry_prescription = _CARRY_SPECIFIC.get(exercise.name)
            if carry_prescription:
                return SlotPrescription(
                    sets=3,
                    rep_min=carry_prescription[0],
                    rep_max=carry_prescription[1],
                    prescription_mode=PrescriptionMode.DISTANCE,
                    description=f"{exercise.name} carry",
                )
        return SlotPrescription(
            sets=3,
            rep_min=20,
            rep_max=40,
            prescription_mode=PrescriptionMode.SECONDS,
            description=f"{exercise.name} timed core",
        )

    base = _DEFAULT_PRESCRIPTIONS.get(slot.role)
    if base is None:
        return SlotPrescription(
            sets=max(1, default_sets - 1),
            rep_min=base_rep_range[0],
            rep_max=base_rep_range[1],
            prescription_mode=PrescriptionMode.REPS,
            description="default prescription",
        )

    if slot.role == SlotRole.PRIMARY:
        movement = exercise.movement_pattern.name if exercise.movement_pattern else ""
        if movement in ("squat", "hinge"):
            return SlotPrescription(
                sets=max(3, default_sets),
                rep_min=6,
                rep_max=10,
                prescription_mode=PrescriptionMode.REPS,
                description="lower body primary",
            )
        return SlotPrescription(
            sets=max(3, default_sets),
            rep_min=base_rep_range[0],
            rep_max=min(base_rep_range[1], 12),
            prescription_mode=PrescriptionMode.REPS,
            description="primary movement",
        )

    if slot.role == SlotRole.SECONDARY:
        return SlotPrescription(
            sets=max(2, default_sets - 1),
            rep_min=base_rep_range[0],
            rep_max=min(base_rep_range[1], 15),
            prescription_mode=PrescriptionMode.REPS,
            description="secondary movement",
        )

    return base


def _is_arm_isolation(exercise: "Exercise", muscle_group: "MuscleGroup") -> bool:
    muscle_name = muscle_group.name.lower()
    if muscle_name not in ("biceps", "triceps"):
        return False
    return not exercise.is_compound


def clamp_sets_for_methodology(
    sets: int,
    slot_role: "SlotRole",
    is_compound: bool,
) -> int:
    if slot_role == SlotRole.PRIMARY and is_compound:
        return max(3, min(5, sets))
    if slot_role == SlotRole.SECONDARY:
        return max(2, min(4, sets))
    if slot_role == SlotRole.ACCESSORY:
        return max(2, min(4, sets))
    if slot_role in (SlotRole.CORE, SlotRole.CARRY):
        return max(2, min(4, sets))
    return sets


def get_prescription_mode_for_slot(slot: "Slot") -> "PrescriptionMode":
    return slot.prescription_mode

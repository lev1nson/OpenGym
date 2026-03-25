"""
Slot-based planning system for gym-coach-brain.

Defines training day slots, day templates, and slot builder logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gym_coach_brain.data.models import TrainingSplit


class AnchorPolicy(str, Enum):
    STABLE = "stable"
    SEMI_STABLE = "semi_stable"
    FREE_ROTATION = "free_rotation"


class PrescriptionMode(str, Enum):
    REPS = "reps"
    SECONDS = "seconds"
    DISTANCE = "distance"


class SlotRole(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ACCESSORY = "accessory"
    CARRY = "carry"
    CORE = "core"


@dataclass(frozen=True)
class Slot:
    slot_id: str
    required: bool
    priority: int
    target_regions: tuple[str, ...]
    target_muscles: tuple[str, ...]
    movement_preferences: tuple[str, ...]
    exercise_family_preferences: tuple[str, ...]
    fallback_policy: tuple[str, ...]
    anchor_policy: AnchorPolicy
    role: SlotRole
    prescription_mode: PrescriptionMode = PrescriptionMode.REPS
    max_exercises_for_role: int = 1


@dataclass
class DayTemplate:
    split_label: str
    slots: tuple[Slot, ...]


_UPPER_PRIMARY_PUSH = Slot(
    slot_id="upper_primary_push",
    required=True,
    priority=1,
    target_regions=("upper",),
    target_muscles=("chest", "shoulders", "triceps"),
    movement_preferences=("horizontal_push", "vertical_push"),
    exercise_family_preferences=("compound_horizontal_push_barbell", "compound_horizontal_push_machine", "compound_vertical_push_barbell"),
    fallback_policy=("barbell", "dumbbell", "machine", "bodyweight"),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.PRIMARY,
)

_UPPER_PRIMARY_PULL = Slot(
    slot_id="upper_primary_pull",
    required=True,
    priority=1,
    target_regions=("upper",),
    target_muscles=("back", "biceps", "trapezius"),
    movement_preferences=("horizontal_pull", "vertical_pull"),
    exercise_family_preferences=("compound_vertical_pull_pullup_bar", "compound_vertical_pull_cable", "compound_horizontal_pull_barbell"),
    fallback_policy=("pullup_bar", "cable", "dumbbell", "bodyweight"),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.PRIMARY,
)

_UPPER_SECONDARY = Slot(
    slot_id="upper_secondary_upper",
    required=True,
    priority=2,
    target_regions=("upper",),
    target_muscles=("chest", "back", "shoulders", "triceps", "biceps"),
    movement_preferences=("horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull"),
    exercise_family_preferences=(),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.SECONDARY,
)

_UPPER_OPTIONAL_SUPPORT_1 = Slot(
    slot_id="upper_optional_support_1",
    required=False,
    priority=3,
    target_regions=("upper",),
    target_muscles=("triceps", "biceps", "trapezius"),
    movement_preferences=(),
    exercise_family_preferences=("isolation_arm_flexion", "isolation_arm_extension"),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.FREE_ROTATION,
    role=SlotRole.ACCESSORY,
)

_UPPER_OPTIONAL_SUPPORT_2 = Slot(
    slot_id="upper_optional_support_2",
    required=False,
    priority=4,
    target_regions=("upper",),
    target_muscles=("triceps", "biceps", "trapezius"),
    movement_preferences=(),
    exercise_family_preferences=("isolation_arm_flexion", "isolation_arm_extension"),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.FREE_ROTATION,
    role=SlotRole.ACCESSORY,
)

_LOWER_PRIMARY_KNEE = Slot(
    slot_id="lower_primary_knee",
    required=True,
    priority=1,
    target_regions=("lower",),
    target_muscles=("quadriceps", "glutes"),
    movement_preferences=("squat",),
    exercise_family_preferences=("compound_squat_barbell", "compound_squat_machine"),
    fallback_policy=("barbell", "smith_machine", "machine", "dumbbell", "bodyweight"),
    anchor_policy=AnchorPolicy.STABLE,
    role=SlotRole.PRIMARY,
)

_LOWER_PRIMARY_HINGE = Slot(
    slot_id="lower_primary_hinge",
    required=True,
    priority=1,
    target_regions=("lower",),
    target_muscles=("hamstrings", "glutes", "lower_back"),
    movement_preferences=("hinge",),
    exercise_family_preferences=("compound_hinge_barbell", "compound_hinge_bodyweight"),
    fallback_policy=("barbell", "bodyweight", "cable"),
    anchor_policy=AnchorPolicy.STABLE,
    role=SlotRole.PRIMARY,
)

_LOWER_SECONDARY = Slot(
    slot_id="lower_secondary_lower",
    required=True,
    priority=2,
    target_regions=("lower",),
    target_muscles=("quadriceps", "hamstrings", "glutes", "calves"),
    movement_preferences=("squat", "hinge"),
    exercise_family_preferences=(),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.SECONDARY,
)

_CORE_SLOT = Slot(
    slot_id="core_slot",
    required=True,
    priority=3,
    target_regions=("core",),
    target_muscles=("abs", "lower_back"),
    movement_preferences=("carry",),
    exercise_family_preferences=("carry_bodyweight", "trunk_bracing"),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.FREE_ROTATION,
    role=SlotRole.CORE,
    prescription_mode=PrescriptionMode.SECONDS,
)

_CALVES_SLOT = Slot(
    slot_id="calves_slot",
    required=True,
    priority=4,
    target_regions=("lower",),
    target_muscles=("calves",),
    movement_preferences=("squat",),
    exercise_family_preferences=("isolation_squat_bodyweight"),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.FREE_ROTATION,
    role=SlotRole.ACCESSORY,
)

_PUSH_PRIMARY_HORIZONTAL = Slot(
    slot_id="push_primary_horizontal",
    required=True,
    priority=1,
    target_regions=("upper",),
    target_muscles=("chest", "shoulders", "triceps"),
    movement_preferences=("horizontal_push",),
    exercise_family_preferences=("compound_horizontal_push_barbell", "compound_horizontal_push_machine"),
    fallback_policy=("barbell", "dumbbell", "machine", "bodyweight"),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.PRIMARY,
)

_PUSH_PRIMARY_VERTICAL = Slot(
    slot_id="push_primary_vertical",
    required=True,
    priority=1,
    target_regions=("upper",),
    target_muscles=("shoulders", "triceps", "chest"),
    movement_preferences=("vertical_push",),
    exercise_family_preferences=("compound_vertical_push_barbell", "compound_vertical_push_dumbbell"),
    fallback_policy=("barbell", "dumbbell", "machine", "bodyweight"),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.PRIMARY,
)

_PUSH_SECONDARY = Slot(
    slot_id="push_secondary_push",
    required=True,
    priority=2,
    target_regions=("upper",),
    target_muscles=("chest", "shoulders", "triceps"),
    movement_preferences=("horizontal_push", "vertical_push"),
    exercise_family_preferences=(),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.SECONDARY,
)

_PUSH_OPTIONAL_TRICEPS = Slot(
    slot_id="push_optional_triceps",
    required=False,
    priority=3,
    target_regions=("upper",),
    target_muscles=("triceps",),
    movement_preferences=(),
    exercise_family_preferences=("isolation_arm_extension"),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.FREE_ROTATION,
    role=SlotRole.ACCESSORY,
)

_PULL_PRIMARY_VERTICAL = Slot(
    slot_id="pull_primary_vertical",
    required=True,
    priority=1,
    target_regions=("upper",),
    target_muscles=("back", "biceps", "trapezius"),
    movement_preferences=("vertical_pull",),
    exercise_family_preferences=("compound_vertical_pull_pullup_bar", "compound_vertical_pull_cable"),
    fallback_policy=("pullup_bar", "cable", "bodyweight"),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.PRIMARY,
)

_PULL_PRIMARY_ROW = Slot(
    slot_id="pull_primary_row",
    required=True,
    priority=1,
    target_regions=("upper",),
    target_muscles=("back", "biceps", "trapezius"),
    movement_preferences=("horizontal_pull",),
    exercise_family_preferences=("compound_horizontal_pull_barbell", "compound_horizontal_pull_cable"),
    fallback_policy=("barbell", "cable", "dumbbell", "bodyweight"),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.PRIMARY,
)

_PULL_SECONDARY = Slot(
    slot_id="pull_secondary_pull",
    required=True,
    priority=2,
    target_regions=("upper",),
    target_muscles=("back", "biceps", "trapezius"),
    movement_preferences=("horizontal_pull", "vertical_pull"),
    exercise_family_preferences=(),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.SECONDARY,
)

_PULL_OPTIONAL = Slot(
    slot_id="pull_optional_biceps_or_traps",
    required=False,
    priority=3,
    target_regions=("upper",),
    target_muscles=("biceps", "trapezius"),
    movement_preferences=(),
    exercise_family_preferences=("isolation_arm_flexion", "carry_dumbbell"),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.FREE_ROTATION,
    role=SlotRole.ACCESSORY,
)

_LEGS_PRIMARY_KNEE = Slot(
    slot_id="legs_primary_knee",
    required=True,
    priority=1,
    target_regions=("lower",),
    target_muscles=("quadriceps", "glutes"),
    movement_preferences=("squat",),
    exercise_family_preferences=("compound_squat_barbell", "compound_squat_machine"),
    fallback_policy=("barbell", "smith_machine", "machine", "dumbbell", "bodyweight"),
    anchor_policy=AnchorPolicy.STABLE,
    role=SlotRole.PRIMARY,
)

_LEGS_PRIMARY_HINGE = Slot(
    slot_id="legs_primary_hinge",
    required=True,
    priority=1,
    target_regions=("lower",),
    target_muscles=("hamstrings", "glutes", "lower_back"),
    movement_preferences=("hinge",),
    exercise_family_preferences=("compound_hinge_barbell", "compound_hinge_bodyweight"),
    fallback_policy=("barbell", "bodyweight", "cable"),
    anchor_policy=AnchorPolicy.STABLE,
    role=SlotRole.PRIMARY,
)

_LEGS_SECONDARY = Slot(
    slot_id="legs_secondary_lower",
    required=True,
    priority=2,
    target_regions=("lower",),
    target_muscles=("quadriceps", "hamstrings", "glutes", "calves"),
    movement_preferences=("squat", "hinge"),
    exercise_family_preferences=(),
    fallback_policy=(),
    anchor_policy=AnchorPolicy.SEMI_STABLE,
    role=SlotRole.SECONDARY,
)

_DAY_TEMPLATES: dict[tuple[str, str], DayTemplate] = {
    ("upper_lower", "upper"): DayTemplate(
        split_label="upper",
        slots=(
            _UPPER_PRIMARY_PUSH,
            _UPPER_PRIMARY_PULL,
            _UPPER_SECONDARY,
            _UPPER_OPTIONAL_SUPPORT_1,
            _UPPER_OPTIONAL_SUPPORT_2,
        ),
    ),
    ("upper_lower", "lower"): DayTemplate(
        split_label="lower",
        slots=(
            _LOWER_PRIMARY_KNEE,
            _LOWER_PRIMARY_HINGE,
            _LOWER_SECONDARY,
            _CORE_SLOT,
            _CALVES_SLOT,
        ),
    ),
    ("ppl", "push"): DayTemplate(
        split_label="push",
        slots=(
            _PUSH_PRIMARY_HORIZONTAL,
            _PUSH_PRIMARY_VERTICAL,
            _PUSH_SECONDARY,
            _PUSH_OPTIONAL_TRICEPS,
        ),
    ),
    ("ppl", "pull"): DayTemplate(
        split_label="pull",
        slots=(
            _PULL_PRIMARY_VERTICAL,
            _PULL_PRIMARY_ROW,
            _PULL_SECONDARY,
            _PULL_OPTIONAL,
        ),
    ),
    ("ppl", "legs"): DayTemplate(
        split_label="legs",
        slots=(
            _LEGS_PRIMARY_KNEE,
            _LEGS_PRIMARY_HINGE,
            _LEGS_SECONDARY,
            _CORE_SLOT,
            _CALVES_SLOT,
        ),
    ),
}


def get_day_template(split: "TrainingSplit | str", split_day_label: str) -> DayTemplate | None:
    split_str = split.value if hasattr(split, "value") else str(split)
    key = (split_str, split_day_label)
    return _DAY_TEMPLATES.get(key)


def get_all_slots_for_split(split: "TrainingSplit | str", split_day_label: str) -> tuple[Slot, ...]:
    template = get_day_template(split, split_day_label)
    if template is None:
        return ()
    return template.slots


def filter_required_slots(slots: tuple[Slot, ...]) -> tuple[Slot, ...]:
    return tuple(s for s in slots if s.required)


def filter_optional_slots(slots: tuple[Slot, ...]) -> tuple[Slot, ...]:
    return tuple(s for s in slots if not s.required)


def get_primary_slots(slots: tuple[Slot, ...]) -> tuple[Slot, ...]:
    return tuple(s for s in slots if s.role == SlotRole.PRIMARY)


def get_secondary_slots(slots: tuple[Slot, ...]) -> tuple[Slot, ...]:
    return tuple(s for s in slots if s.role == SlotRole.SECONDARY)


def get_accessory_slots(slots: tuple[Slot, ...]) -> tuple[Slot, ...]:
    return tuple(s for s in slots if s.role == SlotRole.ACCESSORY)


def get_core_and_carry_slots(slots: tuple[Slot, ...]) -> tuple[Slot, ...]:
    return tuple(s for s in slots if s.role in (SlotRole.CORE, SlotRole.CARRY))

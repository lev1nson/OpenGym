"""Concrete equipment inventory parsing and exercise availability rules.

This module keeps two layers intentionally separate:

1. Broad equipment types (`barbell`, `machine`, `cable`, ...)
2. Concrete inventory items (`smith_machine`, `leg_curl_machine`, ...)

The old planner only understood layer 1. The new onboarding flow can accept
specific machines and derive the broad layer for backward compatibility while
using the concrete layer for precise exercise availability checks.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gym_coach_brain.data.models import Exercise, UserProfile


@dataclass(frozen=True)
class InventoryItem:
    """One concrete piece of available gym equipment."""

    id: str
    label: str
    aliases: tuple[str, ...]
    derived_equipment_types: tuple[str, ...] = ()


_INVENTORY_ITEMS: tuple[InventoryItem, ...] = (
    InventoryItem(
        id="barbell",
        label="Barbell",
        aliases=(
            "barbell",
            "olympic barbell",
            "olympic bar",
            "straight barbell",
            "штанга",
            "олимпийская штанга",
            "олимпийский гриф",
            "обычная штанга",
        ),
        derived_equipment_types=("barbell",),
    ),
    InventoryItem(
        id="ez_bar",
        label="EZ Bar",
        aliases=(
            "ez bar",
            "ez-bar",
            "curl bar",
            "biceps bar",
            "штанга на бицепс",
            "ez гриф",
            "изи гриф",
            "кривой гриф",
        ),
    ),
    InventoryItem(
        id="dumbbells",
        label="Dumbbells",
        aliases=("dumbbell", "dumbbells", "гантель", "гантели", "набор гантелей"),
        derived_equipment_types=("dumbbell",),
    ),
    InventoryItem(
        id="adjustable_bench",
        label="Adjustable Bench",
        aliases=("adjustable bench", "incline bench", "flat bench", "скамья", "регулируемая скамья"),
    ),
    InventoryItem(
        id="ab_wheel",
        label="Ab Wheel",
        aliases=("ab wheel", "ab roller", "ролик для пресса"),
    ),
    InventoryItem(
        id="squat_rack",
        label="Squat Rack",
        aliases=("squat rack", "power rack", "rack", "силовая рама", "стойки для приседа"),
    ),
    InventoryItem(
        id="smith_machine",
        label="Smith Machine",
        aliases=("smith machine", "smith", "машина смита", "смит"),
        derived_equipment_types=("machine",),
    ),
    InventoryItem(
        id="chest_press_machine",
        label="Chest Press Machine",
        aliases=(
            "chest press machine",
            "machine chest press",
            "bench press machine",
            "chest press",
            "жим от груди",
            "грудной жим",
        ),
        derived_equipment_types=("machine",),
    ),
    InventoryItem(
        id="shoulder_press_machine",
        label="Shoulder Press Machine",
        aliases=("shoulder press machine", "machine shoulder press", "shoulder press", "жим на плечи"),
        derived_equipment_types=("machine",),
    ),
    InventoryItem(
        id="leg_extension_machine",
        label="Leg Extension Machine",
        aliases=("leg extension machine", "leg extension", "разгибание ног", "разгибатель ног"),
        derived_equipment_types=("machine",),
    ),
    InventoryItem(
        id="leg_curl_machine",
        label="Leg Curl Machine",
        aliases=("leg curl machine", "leg curl", "сгибание ног", "бицепс бедра машина"),
        derived_equipment_types=("machine",),
    ),
    InventoryItem(
        id="leg_press_machine",
        label="Leg Press Machine",
        aliases=("leg press machine", "leg press", "жим ногами"),
        derived_equipment_types=("machine",),
    ),
    InventoryItem(
        id="high_pulley_cable",
        label="High Pulley Cable",
        aliases=(
            "high pulley",
            "lat pulldown",
            "lat pulldown machine",
            "upper pulley",
            "верхний блок",
            "тяга верхнего блока",
            "машина с тягой верхнего блока",
        ),
        derived_equipment_types=("cable",),
    ),
    InventoryItem(
        id="low_pulley_cable",
        label="Low Pulley Cable",
        aliases=("low pulley", "cable row station", "нижний блок", "горизонтальная тяга"),
        derived_equipment_types=("cable",),
    ),
    InventoryItem(
        id="cable_station",
        label="Cable Station",
        aliases=("cable machine", "cable station", "functional trainer", "кроссовер", "блочная рама"),
        derived_equipment_types=("cable",),
    ),
    InventoryItem(
        id="pullup_bar",
        label="Pull-up Bar",
        aliases=("pull-up bar", "pullup bar", "турник"),
        derived_equipment_types=("pullup_bar",),
    ),
    InventoryItem(
        id="dip_bars",
        label="Dip Bars",
        aliases=("dip bars", "dips bar", "брусья"),
        derived_equipment_types=("dips_bar",),
    ),
    InventoryItem(
        id="resistance_bands",
        label="Resistance Bands",
        aliases=("resistance band", "bands", "band", "резинка", "резинки", "эспандер"),
        derived_equipment_types=("resistance_band",),
    ),
    InventoryItem(
        id="bodyweight",
        label="Bodyweight",
        aliases=("bodyweight", "own bodyweight", "собственный вес"),
        derived_equipment_types=("bodyweight",),
    ),
)

SUPPORTED_INVENTORY_IDS: tuple[str, ...] = tuple(item.id for item in _INVENTORY_ITEMS)
_ITEM_BY_ID: dict[str, InventoryItem] = {item.id: item for item in _INVENTORY_ITEMS}

LEGACY_EQUIPMENT_TYPES: tuple[str, ...] = (
    "barbell",
    "dumbbell",
    "machine",
    "cable",
    "bodyweight",
    "resistance_band",
    "pullup_bar",
    "dips_bar",
)
_LEGACY_TYPE_SET = set(LEGACY_EQUIPMENT_TYPES)

_INVENTORY_CAPABILITIES: dict[str, frozenset[str]] = {
    "cable_station": frozenset({"cable_station", "high_pulley_cable", "low_pulley_cable"}),
}

# Concrete availability requirements for seeded exercises.
# Unlisted exercises fall back to the broad equipment type behavior.
EXERCISE_REQUIREMENTS: dict[str, frozenset[str]] = {
    "Bench Press": frozenset({"barbell", "adjustable_bench"}),
    "Incline Dumbbell Press": frozenset({"dumbbells", "adjustable_bench"}),
    "Dumbbell Fly": frozenset({"dumbbells", "adjustable_bench"}),
    "Machine Chest Press": frozenset({"chest_press_machine"}),
    "Machine Shoulder Press": frozenset({"shoulder_press_machine"}),
    "Smith Squat": frozenset({"smith_machine"}),
    "Machine Leg Curl": frozenset({"leg_curl_machine"}),
    "Machine Leg Extension": frozenset({"leg_extension_machine"}),
    "Leg Press": frozenset({"leg_press_machine"}),
    "Lat Pulldown": frozenset({"high_pulley_cable"}),
    "Tricep Pushdown": frozenset({"high_pulley_cable"}),
    "Cable Row": frozenset({"low_pulley_cable"}),
    "Cable Pull-Through": frozenset({"low_pulley_cable"}),
    "Overhead Press": frozenset({"barbell"}),
    "Barbell Row": frozenset({"barbell"}),
    "Barbell Squat": frozenset({"barbell", "squat_rack"}),
    "Romanian Deadlift": frozenset({"barbell"}),
    "Deadlift": frozenset({"barbell"}),
    "Good Morning": frozenset({"barbell"}),
    "Hip Thrust": frozenset({"barbell", "adjustable_bench"}),
    "Dumbbell Shoulder Press": frozenset({"dumbbells"}),
    "Dumbbell Row": frozenset({"dumbbells"}),
    "Dumbbell Curl": frozenset({"dumbbells"}),
    "Lateral Raise": frozenset({"dumbbells"}),
    "Farmer's Walk": frozenset({"dumbbells"}),
    "Bulgarian Split Squat": frozenset({"dumbbells"}),
    "Ab Wheel Rollout": frozenset({"ab_wheel"}),
}

_NORMALIZE_RE = re.compile(r"[\s\-_]+")


def _normalize(text: str) -> str:
    """Lowercase + collapse punctuation/spacing for tolerant alias matching."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("(", " ")
    normalized = normalized.replace(")", " ")
    normalized = normalized.replace(".", " ")
    normalized = normalized.replace(":", " ")
    normalized = normalized.replace(";", " ")
    normalized = normalized.replace("\n", " ")
    return _NORMALIZE_RE.sub(" ", normalized).strip()


def _parse_answer_items(raw_answer: str) -> list[str]:
    """Split input while also supporting free-form equipment descriptions."""
    answer = raw_answer.strip()
    if not answer:
        return []
    if answer.startswith("["):
        payload = json.loads(answer)
        return [str(item).strip() for item in payload if str(item).strip()]
    return [part.strip() for part in re.split(r"[,;\n]+", answer) if part.strip()]


def resolve_equipment_answer(raw_answer: str) -> dict[str, str]:
    """Resolve a free-form onboarding equipment answer.

    Returns JSON-encoded payload for both the broad and concrete layers.
    """
    raw_items = _parse_answer_items(raw_answer)
    normalized_items = [_normalize(item) for item in raw_items]
    normalized_blob = _normalize(" ".join(raw_items)) if raw_items else _normalize(raw_answer)

    inventory_ids: list[str] = []
    derived_types: list[str] = []

    def _add_inventory(item_id: str) -> None:
        if item_id not in inventory_ids:
            inventory_ids.append(item_id)
        for equipment_type in _ITEM_BY_ID[item_id].derived_equipment_types:
            if equipment_type not in derived_types:
                derived_types.append(equipment_type)

    for normalized in normalized_items:
        if normalized in _ITEM_BY_ID:
            _add_inventory(normalized)
        elif normalized in _LEGACY_TYPE_SET and normalized not in derived_types:
            derived_types.append(normalized)

    for item in _INVENTORY_ITEMS:
        for alias in item.aliases:
            alias_normalized = _normalize(alias)
            if alias_normalized and alias_normalized in normalized_blob:
                _add_inventory(item.id)
                break

    if not inventory_ids and not derived_types:
        raise ValueError(
            "Unknown equipment answer. Use broad types or concrete items such as "
            "smith machine, chest press machine, lat pulldown, dumbbells, barbell"
        )

    return {
        "available_equipment": json.dumps(derived_types),
        "available_equipment_inventory": json.dumps(inventory_ids),
    }


def profile_inventory_ids(user_profile: "UserProfile") -> set[str]:
    """Return normalized concrete inventory IDs from the profile."""
    raw = getattr(user_profile, "available_equipment_inventory", None) or "[]"
    return {item for item in json.loads(raw) if item in _ITEM_BY_ID}


def profile_equipment_types(user_profile: "UserProfile") -> set[str]:
    """Return broad equipment types from the profile."""
    raw = getattr(user_profile, "available_equipment", None) or "[]"
    return {item for item in json.loads(raw) if item in _LEGACY_TYPE_SET}


def get_exercise_requirement_ids(exercise_name: str) -> frozenset[str] | None:
    """Return concrete inventory requirements for a seeded exercise, if defined."""
    return EXERCISE_REQUIREMENTS.get(exercise_name)


def _inventory_satisfies_requirements(
    inventory_ids: set[str],
    requirement_ids: frozenset[str],
) -> bool:
    capabilities: set[str] = set()
    for item_id in inventory_ids:
        capabilities.add(item_id)
        capabilities.update(_INVENTORY_CAPABILITIES.get(item_id, ()))
    return requirement_ids.issubset(capabilities)


def exercise_available_for_profile(
    exercise: "Exercise",
    user_profile: "UserProfile",
    *,
    allow_bodyweight_fallback: bool = False,
    allow_unrestricted_if_empty: bool = False,
) -> bool:
    """Check whether an exercise is executable with the athlete's inventory."""
    equipment_type = (
        exercise.equipment_type.value
        if hasattr(exercise.equipment_type, "value")
        else str(exercise.equipment_type)
    )
    inventory_ids = profile_inventory_ids(user_profile)
    equipment_types = profile_equipment_types(user_profile)

    if not inventory_ids and not equipment_types:
        return allow_unrestricted_if_empty

    requirement_ids = get_exercise_requirement_ids(exercise.name)
    if requirement_ids is not None and inventory_ids:
        if _inventory_satisfies_requirements(inventory_ids, requirement_ids):
            requirement_matched = True
        else:
            # Concrete inventory is authoritative when we have explicit requirements.
            return False
    else:
        requirement_matched = requirement_ids is None

    if equipment_type == "bodyweight":
        if requirement_ids is not None and not requirement_matched:
            return False
        return allow_bodyweight_fallback or "bodyweight" in equipment_types or "bodyweight" in inventory_ids

    return equipment_type in equipment_types


def concrete_inventory_labels(inventory_ids: list[str] | set[str]) -> list[str]:
    """Return stable human-readable labels for concrete equipment items."""
    labels: list[str] = []
    for item_id in inventory_ids:
        item = _ITEM_BY_ID.get(item_id)
        if item is not None:
            labels.append(item.label)
    return labels

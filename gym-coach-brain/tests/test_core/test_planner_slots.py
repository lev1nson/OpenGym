"""
Tests for slot-based planner components.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from gym_coach_brain.core.planner import WorkoutPlanner
from gym_coach_brain.core.planner_slots import (
    AnchorPolicy,
    DayTemplate,
    Slot,
    SlotRole,
    PrescriptionMode,
    get_day_template,
    get_all_slots_for_split,
    filter_required_slots,
    filter_optional_slots,
    get_primary_slots,
)
from gym_coach_brain.core.planner_prescription import (
    get_slot_prescription,
    _is_arm_isolation,
)
from gym_coach_brain.core.planner_scoring import (
    EQUIPMENT_QUALITY_MULTIPLIER,
    score_candidate,
    get_anchor_exercise_id_for_slot,
)
from gym_coach_brain.data.models import (
    EquipmentType,
    Exercise,
    MuscleGroup,
    MovementPattern,
    TrainingSplit,
    UserProfile,
    WorkoutSession,
    WorkoutSet,
)


def create_test_muscle_group(
    db_session: Session,
    name: str,
    body_region: str = "upper",
    is_push: bool = False,
    is_pull: bool = False,
) -> MuscleGroup:
    mg = MuscleGroup(name=name, body_region=body_region, is_push=is_push, is_pull=is_pull)
    db_session.add(mg)
    db_session.flush()
    return mg


def create_test_movement_pattern(db_session: Session, name: str = "horizontal_push") -> MovementPattern:
    mp = MovementPattern(name=name, category="push" if "push" in name else "pull" if "pull" in name else "legs")
    db_session.add(mp)
    db_session.flush()
    return mp


def create_test_exercise(
    db_session: Session,
    name: str,
    muscle_group: MuscleGroup,
    movement_pattern: MovementPattern,
    equipment_type: str = "barbell",
    is_compound: bool = True,
    secondary_muscle_ids: list[int] | None = None,
    exercise_family: str | None = None,
    requires_concrete_inventory: bool = False,
    concrete_item_id: str | None = None,
) -> Exercise:
    ex = Exercise(
        name=name,
        primary_muscle_id=muscle_group.id,
        movement_pattern_id=movement_pattern.id,
        equipment_type=equipment_type,
        secondary_muscle_ids=json.dumps(secondary_muscle_ids or []),
        is_compound=is_compound,
        exercise_family=exercise_family,
        requires_concrete_inventory=requires_concrete_inventory,
        concrete_item_id=concrete_item_id,
    )
    db_session.add(ex)
    db_session.flush()
    return ex


def create_test_user_profile(
    db_session: Session,
    training_split: str = "upper_lower",
    equipment: list[str] | None = None,
    inventory: list[str] | None = None,
    goal: str = "hypertrophy",
    bodyweight_kg: float = 80.0,
) -> UserProfile:
    equip = equipment if equipment is not None else ["barbell"]
    profile = UserProfile(
        training_split=training_split,
        available_equipment=json.dumps(equip),
        available_equipment_inventory=json.dumps(inventory or []),
        goal=goal,
        bodyweight_kg=bodyweight_kg,
        experience_level="intermediate",
        training_days_per_week=3,
        initial_weight_coefficients="{}",
    )
    db_session.add(profile)
    db_session.flush()
    return profile


def create_completed_session(
    db_session: Session,
    session_date: date,
    split_day_label: str | None = None,
    exercise: Exercise | None = None,
    weight_kg: float = 80.0,
    reps: int = 8,
) -> WorkoutSession:
    session = WorkoutSession(
        session_date=session_date.isoformat(),
        status="completed",
        split_day_label=split_day_label,
    )
    db_session.add(session)
    db_session.flush()

    if exercise is not None:
        ws = WorkoutSet(
            session_id=session.id,
            exercise_id=exercise.id,
            set_number=1,
            weight_kg=weight_kg,
            reps=reps,
            rpe=7.0,
        )
        db_session.add(ws)
        db_session.flush()

    return session


# ─── Slot Template Tests ───────────────────────────────────────────────────────

class TestSlotTemplates:
    def test_upper_lower_upper_day_has_correct_slots(self):
        template = get_day_template(TrainingSplit.upper_lower, "upper")
        assert template is not None
        assert template.split_label == "upper"
        slot_ids = {s.slot_id for s in template.slots}
        assert "upper_primary_push" in slot_ids
        assert "upper_primary_pull" in slot_ids

    def test_upper_lower_lower_day_has_correct_slots(self):
        template = get_day_template(TrainingSplit.upper_lower, "lower")
        assert template is not None
        assert template.split_label == "lower"
        slot_ids = {s.slot_id for s in template.slots}
        assert "lower_primary_knee" in slot_ids
        assert "lower_primary_hinge" in slot_ids
        assert "core_slot" in slot_ids
        assert "calves_slot" in slot_ids

    def test_ppl_push_day_has_correct_slots(self):
        template = get_day_template(TrainingSplit.ppl, "push")
        assert template is not None
        assert template.split_label == "push"
        slot_ids = {s.slot_id for s in template.slots}
        assert "push_primary_horizontal" in slot_ids
        assert "push_primary_vertical" in slot_ids

    def test_ppl_pull_day_has_correct_slots(self):
        template = get_day_template(TrainingSplit.ppl, "pull")
        assert template is not None
        slot_ids = {s.slot_id for s in template.slots}
        assert "pull_primary_vertical" in slot_ids
        assert "pull_primary_row" in slot_ids

    def test_ppl_legs_day_has_correct_slots(self):
        template = get_day_template(TrainingSplit.ppl, "legs")
        assert template is not None
        slot_ids = {s.slot_id for s in template.slots}
        assert "legs_primary_knee" in slot_ids
        assert "legs_primary_hinge" in slot_ids

    def test_filter_required_slots(self):
        template = get_day_template(TrainingSplit.upper_lower, "upper")
        required = filter_required_slots(template.slots)
        assert all(s.required for s in required)

    def test_filter_optional_slots(self):
        template = get_day_template(TrainingSplit.upper_lower, "upper")
        optional = filter_optional_slots(template.slots)
        assert all(not s.required for s in optional)

    def test_get_primary_slots(self):
        template = get_day_template(TrainingSplit.upper_lower, "lower")
        primaries = get_primary_slots(template.slots)
        assert all(s.role == SlotRole.PRIMARY for s in primaries)


# ─── Slot Prescription Tests ───────────────────────────────────────────────────

class TestSlotPrescription:
    def test_primary_slot_gets_correct_sets(self, db_session, mock_science_config):
        from gym_coach_brain.core.planner_slots import _LOWER_PRIMARY_KNEE

        mp = create_test_movement_pattern(db_session, name="squat")
        mg = create_test_muscle_group(db_session, "quadriceps", body_region="lower")
        ex = create_test_exercise(db_session, "Barbell Squat", mg, mp, "barbell", True)

        prescription = get_slot_prescription(
            slot=_LOWER_PRIMARY_KNEE,
            exercise=ex,
            muscle_group=mg,
            default_sets=3,
            base_rep_range=(6, 12),
        )
        assert prescription.sets >= 3
        assert prescription.rep_min == 6
        assert prescription.rep_max == 10

    def test_calves_slot_prescription(self, db_session, mock_science_config):
        from gym_coach_brain.core.planner_slots import _CALVES_SLOT

        mp = create_test_movement_pattern(db_session, name="squat")
        mg = create_test_muscle_group(db_session, "calves", body_region="lower")
        ex = create_test_exercise(db_session, "Calf Raise", mg, mp, "bodyweight", False)

        prescription = get_slot_prescription(
            slot=_CALVES_SLOT,
            exercise=ex,
            muscle_group=mg,
            default_sets=3,
            base_rep_range=(10, 20),
        )
        assert prescription.rep_min == 10
        assert prescription.rep_max == 20


# ─── Anchor Policy Tests ────────────────────────────────────────────────────────

class TestAnchorPolicy:
    def test_stable_anchor_prefers_same_exercise(self, db_session, mock_science_config):
        from gym_coach_brain.core.planner_slots import _LOWER_PRIMARY_KNEE

        mp = create_test_movement_pattern(db_session, name="squat")
        mg = create_test_muscle_group(db_session, "quadriceps", body_region="lower")
        ex1 = create_test_exercise(db_session, "Barbell Squat", mg, mp, "barbell")
        ex2 = create_test_exercise(db_session, "Bodyweight Squat", mg, mp, "bodyweight")

        create_completed_session(
            db_session, date.today() - timedelta(days=7),
            split_day_label="lower", exercise=ex1, weight_kg=100.0
        )

        anchor_id = get_anchor_exercise_id_for_slot(_LOWER_PRIMARY_KNEE, date.today(), db_session)
        assert anchor_id == ex1.id

    def test_free_rotation_returns_none(self, db_session, mock_science_config):
        from gym_coach_brain.core.planner_slots import _UPPER_OPTIONAL_SUPPORT_1

        anchor_id = get_anchor_exercise_id_for_slot(_UPPER_OPTIONAL_SUPPORT_1, date.today(), db_session)
        assert anchor_id is None


# ─── Slot-Based Planner Tests ─────────────────────────────────────────────────

class TestSlotBasedPlanner:
    def test_generate_slot_based_upper_lower_upper_day(
        self, db_session, mock_science_config
    ):
        mp_h = create_test_movement_pattern(db_session, "horizontal_push")
        mp_v = create_test_movement_pattern(db_session, "horizontal_pull")
        mp_s = create_test_movement_pattern(db_session, "squat")

        mg_chest = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg_back = create_test_muscle_group(db_session, "back", body_region="upper", is_pull=True)
        mg_shoulders = create_test_muscle_group(db_session, "shoulders", body_region="upper", is_push=True)
        mg_traps = create_test_muscle_group(db_session, "trapezius", body_region="upper", is_pull=True)
        mg_triceps = create_test_muscle_group(db_session, "triceps", body_region="upper", is_push=True)
        mg_biceps = create_test_muscle_group(db_session, "biceps", body_region="upper", is_pull=True)

        create_test_exercise(db_session, "Bench Press", mg_chest, mp_h, "barbell")
        create_test_exercise(db_session, "Incline Dumbbell Press", mg_chest, mp_h, "dumbbell")
        create_test_exercise(db_session, "Barbell Row", mg_back, mp_v, "barbell")
        create_test_exercise(db_session, "Overhead Press", mg_shoulders, mp_h, "barbell")

        profile = create_test_user_profile(db_session, training_split="upper_lower", equipment=["barbell", "dumbbell"])

        planner = WorkoutPlanner()
        plan = planner.generate_slot_based(profile, mock_science_config, db_session)

        assert plan.split_day_label == "upper"
        assert len(plan.exercises) > 0
        assert plan.planning_trace is not None

    def test_generate_slot_based_respects_equipment(
        self, db_session, mock_science_config
    ):
        mp_h = create_test_movement_pattern(db_session, "horizontal_push")
        mp_s = create_test_movement_pattern(db_session, "squat")

        mg_chest = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)

        create_test_exercise(db_session, "Bench Press", mg_chest, mp_h, "barbell")
        create_test_exercise(db_session, "Push-up", mg_chest, mp_h, "bodyweight")

        profile_barbell = create_test_user_profile(
            db_session, training_split="upper_lower", equipment=["barbell"]
        )
        profile_bodyweight = create_test_user_profile(
            db_session, training_split="upper_lower", equipment=["bodyweight"]
        )

        planner = WorkoutPlanner()

        plan_barbell = planner.generate_slot_based(profile_barbell, mock_science_config, db_session)
        plan_bodyweight = planner.generate_slot_based(profile_bodyweight, mock_science_config, db_session)

        if plan_barbell.exercises:
            barbell_exercises = {e.exercise_name for e in plan_barbell.exercises}
            assert "Bench Press" in barbell_exercises or "Push-up" in barbell_exercises


# ─── Equipment Fallback Tests ──────────────────────────────────────────────────

class TestEquipmentFallback:
    def test_bodyweight_fallback_when_no_equipment(
        self, db_session, mock_science_config
    ):
        mp_h = create_test_movement_pattern(db_session, "horizontal_push")
        mg_chest = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)

        create_test_exercise(db_session, "Bench Press", mg_chest, mp_h, "barbell")
        create_test_exercise(db_session, "Push-up", mg_chest, mp_h, "bodyweight")

        profile = create_test_user_profile(
            db_session, training_split="full_body", equipment=["bodyweight"]
        )

        planner = WorkoutPlanner()
        plan = planner.generate(profile, mock_science_config, db_session)

        exercise_names = {e.exercise_name for e in plan.exercises}
        assert "Push-up" in exercise_names


# ─── Coverage Model Tests ──────────────────────────────────────────────────────

class TestCoverageModel:
    def test_equipment_quality_multiplier_exists(self):
        assert "barbell" in EQUIPMENT_QUALITY_MULTIPLIER
        assert EQUIPMENT_QUALITY_MULTIPLIER["barbell"] == 1.0
        assert EQUIPMENT_QUALITY_MULTIPLIER["machine"] == 0.90
        assert EQUIPMENT_QUALITY_MULTIPLIER["bodyweight"] == 0.85

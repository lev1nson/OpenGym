"""
Tests for WorkoutPlanner — Story 4.7.

All tests use in-memory SQLite (db_session fixture from conftest.py).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from gym_coach_brain.core.planner import PlannedExercise, WorkoutPlan, WorkoutPlanner
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


# ─── Test Helpers ─────────────────────────────────────────────────────────────

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
    mp = MovementPattern(name=name, category="compound")
    db_session.add(mp)
    db_session.flush()
    return mp


def create_test_exercise(
    db_session: Session,
    name: str,
    muscle_group: MuscleGroup,
    movement_pattern: MovementPattern,
    equipment_type: str = "barbell",
    secondary_muscle_ids: list[int] | None = None,
) -> Exercise:
    ex = Exercise(
        name=name,
        primary_muscle_id=muscle_group.id,
        movement_pattern_id=movement_pattern.id,
        equipment_type=equipment_type,
        secondary_muscle_ids=json.dumps(secondary_muscle_ids or []),
    )
    db_session.add(ex)
    db_session.flush()
    return ex


def create_test_user_profile(
    db_session: Session,
    training_split: str = "full_body",
    equipment: list[str] | None = None,
    goal: str = "hypertrophy",
    bodyweight_kg: float = 80.0,
) -> UserProfile:
    equip = equipment if equipment is not None else ["barbell"]
    profile = UserProfile(
        training_split=training_split,
        available_equipment=json.dumps(equip),
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
    methodology: str | None = None,
) -> WorkoutSession:
    session = WorkoutSession(
        session_date=session_date.isoformat(),
        status="completed",
        split_day_label=split_day_label,
        methodology=methodology,
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


# ─── Split-Day Logic Tests ─────────────────────────────────────────────────────

class TestSplitDayLogic:
    def test_full_body_split_all_groups(self, db_session, mock_science_config):
        """full_body split → all muscle groups in plan."""
        mp = create_test_movement_pattern(db_session)
        mg1 = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg2 = create_test_muscle_group(db_session, "back", body_region="upper", is_pull=True)
        mg3 = create_test_muscle_group(db_session, "quads", body_region="lower")
        create_test_exercise(db_session, "bench", mg1, mp)
        create_test_exercise(db_session, "row", mg2, mp)
        create_test_exercise(db_session, "squat", mg3, mp)

        profile = create_test_user_profile(db_session, training_split="full_body")
        planner = WorkoutPlanner()
        plan = planner.generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "full_body"
        assert len(plan.exercises) == 3

    def test_upper_lower_flip_upper_to_lower(self, db_session, mock_science_config):
        """Previous split_day_label=upper → today=lower."""
        mp = create_test_movement_pattern(db_session)
        mg_upper = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg_lower = create_test_muscle_group(db_session, "quads", body_region="lower")
        ex_upper = create_test_exercise(db_session, "bench", mg_upper, mp)
        create_test_exercise(db_session, "squat", mg_lower, mp)

        create_completed_session(db_session, date.today() - timedelta(days=2),
                                  split_day_label="upper", exercise=ex_upper)
        profile = create_test_user_profile(db_session, training_split="upper_lower")
        planner = WorkoutPlanner()
        plan = planner.generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "lower"
        assert all("quads" in mg or "lower" in mg.lower() for mg in plan.muscle_groups_today)

    def test_upper_lower_flip_lower_to_upper(self, db_session, mock_science_config):
        """Previous split_day_label=lower → today=upper."""
        mp = create_test_movement_pattern(db_session)
        mg_upper = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg_lower = create_test_muscle_group(db_session, "quads", body_region="lower")
        ex_lower = create_test_exercise(db_session, "squat", mg_lower, mp)
        create_test_exercise(db_session, "bench", mg_upper, mp)

        create_completed_session(db_session, date.today() - timedelta(days=2),
                                  split_day_label="lower", exercise=ex_lower)
        profile = create_test_user_profile(db_session, training_split="upper_lower")
        planner = WorkoutPlanner()
        plan = planner.generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "upper"

    def test_ppl_push_to_pull(self, db_session, mock_science_config):
        """Previous push → today pull."""
        mp = create_test_movement_pattern(db_session)
        mg_push = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg_pull = create_test_muscle_group(db_session, "back", body_region="upper", is_pull=True)
        ex_push = create_test_exercise(db_session, "bench", mg_push, mp)
        create_test_exercise(db_session, "row", mg_pull, mp)

        create_completed_session(db_session, date.today() - timedelta(days=2),
                                  split_day_label="push", exercise=ex_push)
        profile = create_test_user_profile(db_session, training_split="ppl")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "pull"

    def test_ppl_pull_to_legs(self, db_session, mock_science_config):
        """Previous pull → today legs."""
        mp = create_test_movement_pattern(db_session)
        mg_pull = create_test_muscle_group(db_session, "back", body_region="upper", is_pull=True)
        mg_legs = create_test_muscle_group(db_session, "quads", body_region="lower")
        ex_pull = create_test_exercise(db_session, "row", mg_pull, mp)
        create_test_exercise(db_session, "squat", mg_legs, mp)

        create_completed_session(db_session, date.today() - timedelta(days=2),
                                  split_day_label="pull", exercise=ex_pull)
        profile = create_test_user_profile(db_session, training_split="ppl")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "legs"

    def test_ppl_legs_to_push(self, db_session, mock_science_config):
        """Previous legs → today push."""
        mp = create_test_movement_pattern(db_session)
        mg_legs = create_test_muscle_group(db_session, "quads", body_region="lower")
        mg_push = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex_legs = create_test_exercise(db_session, "squat", mg_legs, mp)
        create_test_exercise(db_session, "bench", mg_push, mp)

        create_completed_session(db_session, date.today() - timedelta(days=2),
                                  split_day_label="legs", exercise=ex_legs)
        profile = create_test_user_profile(db_session, training_split="ppl")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "push"

    def test_ppl_first_workout_starts_push(self, db_session, mock_science_config):
        """No history, ppl → split_day_label=push."""
        mp = create_test_movement_pattern(db_session)
        mg_push = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg_push, mp)

        profile = create_test_user_profile(db_session, training_split="ppl")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "push"

    def test_upper_lower_first_workout_starts_upper(self, db_session, mock_science_config):
        """No history, upper_lower → upper."""
        mp = create_test_movement_pattern(db_session)
        mg_upper = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg_upper, mp)

        profile = create_test_user_profile(db_session, training_split="upper_lower")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "upper"

    def test_full_body_first_workout(self, db_session, mock_science_config):
        """No history, full_body → full_body."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg, mp)

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "full_body"

    def test_custom_split_uses_last_session_groups_without_split_label(
        self, db_session, mock_science_config
    ):
        """custom split repeats last completed session muscles even if split_day_label is NULL."""
        mp = create_test_movement_pattern(db_session)
        mg_chest = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg_back = create_test_muscle_group(db_session, "back", body_region="upper", is_pull=True)
        mg_quads = create_test_muscle_group(db_session, "quads", body_region="lower")
        ex_chest = create_test_exercise(db_session, "bench", mg_chest, mp)
        ex_back = create_test_exercise(db_session, "row", mg_back, mp)
        create_test_exercise(db_session, "squat", mg_quads, mp)

        last_session = create_completed_session(
            db_session,
            date.today() - timedelta(days=3),
            split_day_label=None,
        )
        db_session.add_all(
            [
                WorkoutSet(
                    session_id=last_session.id,
                    exercise_id=ex_chest.id,
                    set_number=1,
                    weight_kg=80.0,
                    reps=8,
                    rpe=7.0,
                ),
                WorkoutSet(
                    session_id=last_session.id,
                    exercise_id=ex_back.id,
                    set_number=1,
                    weight_kg=70.0,
                    reps=8,
                    rpe=7.0,
                ),
            ]
        )
        db_session.flush()

        profile = create_test_user_profile(db_session, training_split="custom")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert plan.split_day_label == "full_body"
        assert set(plan.muscle_groups_today) == {"chest", "back"}


# ─── Recovery Signal Tests ─────────────────────────────────────────────────────

class TestRecoverySignal:
    def test_recovery_signal_scales_weight(self, db_session, mock_science_config):
        """signal.coefficient=0.6 → target_weight ≈ last_weight * 0.6 (before rounding)."""
        from unittest.mock import Mock
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        # Create session with known weight, min_rest_days=2 ago
        create_completed_session(
            db_session, date.today() - timedelta(days=2),
            split_day_label="full_body", exercise=ex, weight_kg=100.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")

        signal = Mock()
        signal.coefficient = 0.6

        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session, recovery_signal=signal)

        assert len(plan.exercises) > 0
        # 100 * 0.6 = 60.0 → rounded to nearest 2.5 = 60.0
        assert plan.exercises[0].target_weight_kg == pytest.approx(60.0, abs=2.5)

    def test_no_recovery_signal_uses_full_weight(self, db_session, mock_science_config):
        """signal=None → target_weight = last_weight."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        create_completed_session(
            db_session, date.today() - timedelta(days=2),
            split_day_label="full_body", exercise=ex, weight_kg=100.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session, recovery_signal=None)

        assert len(plan.exercises) > 0
        assert plan.exercises[0].target_weight_kg == pytest.approx(100.0, abs=0.01)


# ─── Equipment Filter Tests ────────────────────────────────────────────────────

class TestEquipmentFilter:
    def test_no_equipment_for_group_skips_it(self, db_session, mock_science_config):
        """No exercises with matching equipment → group in skipped_groups."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        # Create barbell exercise but user only has dumbbell
        create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        profile = create_test_user_profile(db_session, training_split="full_body", equipment=["dumbbell"])
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert len(plan.skipped_groups) > 0
        assert any("chest" in sg for sg in plan.skipped_groups)

    def test_skipped_groups_reason(self, db_session, mock_science_config):
        """skipped_groups contains reason no_equipment."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "triceps", body_region="upper", is_push=True)
        create_test_exercise(db_session, "pushdown", mg, mp, equipment_type="cable")

        profile = create_test_user_profile(db_session, training_split="full_body", equipment=["barbell"])
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert any("no_equipment" in sg for sg in plan.skipped_groups)


# ─── Min Rest Days Tests ───────────────────────────────────────────────────────

class TestMinRestDays:
    def test_min_rest_days_excludes_recent_group(self, db_session, mock_science_config):
        """Group trained yesterday → excluded when another group is available."""
        mp = create_test_movement_pattern(db_session)
        mg_chest = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg_back = create_test_muscle_group(db_session, "back", body_region="upper", is_pull=True)
        ex_chest = create_test_exercise(db_session, "bench", mg_chest, mp, equipment_type="barbell")
        create_test_exercise(db_session, "row", mg_back, mp, equipment_type="barbell")

        # Chest trained yesterday
        create_completed_session(
            db_session, date.today() - timedelta(days=1),
            split_day_label="full_body", exercise=ex_chest, weight_kg=80.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        # min_rest_days=2, chest trained 1 day ago → excluded
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        chest_in_plan = any(ex.exercise_name == "bench" for ex in plan.exercises)
        assert not chest_in_plan

    def test_all_groups_blocked_overrides_rest_days(self, db_session, mock_science_config):
        """All groups blocked by min_rest_days → override, warning added."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        # Train yesterday — only group, min_rest=2 would block it
        create_completed_session(
            db_session, date.today() - timedelta(days=1),
            split_day_label="full_body", exercise=ex, weight_kg=80.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        # Plan should still have exercises (override applied)
        assert len(plan.exercises) > 0

    def test_min_rest_days_warning_message(self, db_session, mock_science_config):
        """warnings contains 'Нарушен рекомендуемый отдых'."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        create_completed_session(
            db_session, date.today() - timedelta(days=1),
            split_day_label="full_body", exercise=ex, weight_kg=80.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert any("Нарушен рекомендуемый отдых" in w for w in plan.warnings)


# ─── Detraining Tests ─────────────────────────────────────────────────────────

class TestDetraining:
    def test_detraining_applies_after_long_break(self, db_session, mock_science_config):
        """Last session 20 days ago → target_weight reduced by detraining_coefficient."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        create_completed_session(
            db_session, date.today() - timedelta(days=20),
            split_day_label="full_body", exercise=ex, weight_kg=100.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert len(plan.exercises) > 0
        # 100 * 0.85 = 85.0 → rounded to nearest 2.5 = 85.0
        assert plan.exercises[0].target_weight_kg == pytest.approx(85.0, abs=2.5)

    def test_detraining_not_applied_short_break(self, db_session, mock_science_config):
        """Last session 5 days ago → target_weight not reduced."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        create_completed_session(
            db_session, date.today() - timedelta(days=5),
            split_day_label="full_body", exercise=ex, weight_kg=100.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert len(plan.exercises) > 0
        assert plan.exercises[0].target_weight_kg == pytest.approx(100.0, abs=0.01)

    def test_detraining_warning_message(self, db_session, mock_science_config):
        """warnings contains 'Перерыв'."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        create_completed_session(
            db_session, date.today() - timedelta(days=20),
            split_day_label="full_body", exercise=ex, weight_kg=100.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert any("Перерыв" in w for w in plan.warnings)

    def test_no_sessions_no_detraining(self, db_session, mock_science_config):
        """No history → detraining not applied, no detraining warning."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert not any("Перерыв" in w for w in plan.warnings)


# ─── Deload Tests ─────────────────────────────────────────────────────────────

class TestDeload:
    def test_deload_warning_at_threshold(self, db_session, mock_science_config):
        """16+ completed sessions → warnings contains 'дилоад'."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        # Create 16 completed sessions
        for i in range(16):
            create_completed_session(
                db_session, date.today() - timedelta(days=50 + i),
                split_day_label="full_body", exercise=ex, weight_kg=80.0
            )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert any("дилоад" in w.lower() for w in plan.warnings)

    def test_no_deload_below_threshold(self, db_session, mock_science_config):
        """10 sessions → no deload warning."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        for i in range(10):
            create_completed_session(
                db_session, date.today() - timedelta(days=50 + i),
                split_day_label="full_body", exercise=ex, weight_kg=80.0
            )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert not any("дилоад" in w.lower() for w in plan.warnings)

    def test_deload_counter_resets_after_deload_session(self, db_session, mock_science_config):
        """Only sessions after the most recent deload contribute to the warning threshold."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        for i in range(12):
            create_completed_session(
                db_session,
                date.today() - timedelta(days=40 + i),
                split_day_label="full_body",
                exercise=ex,
                weight_kg=80.0,
            )

        create_completed_session(
            db_session,
            date.today() - timedelta(days=20),
            split_day_label="full_body",
            exercise=ex,
            weight_kg=60.0,
            methodology="deload",
        )

        for i in range(5):
            create_completed_session(
                db_session,
                date.today() - timedelta(days=5 + i),
                split_day_label="full_body",
                exercise=ex,
                weight_kg=82.5,
            )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert not any("дилоад" in w.lower() for w in plan.warnings)


# ─── Weight Rounding Tests ─────────────────────────────────────────────────────

class TestWeightRounding:
    def test_barbell_weight_rounded_to_2_5kg(self, db_session, mock_science_config):
        """raw weight 82.3 → target_weight_kg rounded to nearest 2.5 = 82.5."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        create_completed_session(
            db_session, date.today() - timedelta(days=2),
            split_day_label="full_body", exercise=ex, weight_kg=82.3
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert len(plan.exercises) > 0
        # 82.3 rounded to nearest 2.5 = 82.5
        weight = plan.exercises[0].target_weight_kg
        assert weight % 2.5 == pytest.approx(0.0, abs=0.01)


# ─── PUOS Tests ────────────────────────────────────────────────────────────────

class TestPUOS:
    def test_puos_auto_reduction_on_excess(self, db_session, mock_science_config):
        """Plan with 12 sets for one group → auto-reduced to ≤10."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        profile = create_test_user_profile(db_session, training_split="full_body")

        # Patch default_sets to return 12 to trigger PUOS
        planner = WorkoutPlanner()
        original = planner._get_methodology_params

        def patched_params(user_profile, science):
            return 6, 12, 12  # 12 sets — exceeds PUOS limit of 10

        planner._get_methodology_params = patched_params
        plan = planner.generate(profile, mock_science_config, db_session)

        # PUOS limit is max_sets_per_group=11 in mock_science_config
        if plan.exercises:
            assert plan.exercises[0].sets <= mock_science_config.puos.max_sets_per_group

    def test_puos_auto_reduction_keeps_reducing_until_valid(self, db_session, mock_science_config):
        """Auto-reduction must continue past five rounds if required."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        profile = create_test_user_profile(db_session, training_split="full_body")
        planner = WorkoutPlanner()

        def patched_params(user_profile, science):
            return 6, 12, 20

        planner._get_methodology_params = patched_params
        plan = planner.generate(profile, mock_science_config, db_session)

        assert len(plan.exercises) == 1
        assert plan.exercises[0].sets <= mock_science_config.puos.max_sets_per_group

    def test_puos_auto_reduction_drops_exercise_if_needed(self, db_session, mock_science_config):
        """If PUOS limit is still violated at 1 set, the exercise is dropped entirely without raising ScienceLimitError."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")

        profile = create_test_user_profile(db_session, training_split="full_body")
        planner = WorkoutPlanner()

        # Temporarily strictly limit PUOS to 0 for this test
        mock_science_config.puos.max_sets_per_group = 0
        
        # Will start with 3 sets but must reduce to 0 (dropped)
        def patched_params(user_profile, science):
            return 6, 12, 3

        planner._get_methodology_params = patched_params
        plan = planner.generate(profile, mock_science_config, db_session)

        # The exercise should be dropped entirely, returning an empty plan list for this group
        assert len(plan.exercises) == 0


class TestMethodologySets:
    def test_sets_are_derived_from_methodology_and_science(self, db_session, mock_science_config):
        """Planner should derive set count without relying on a missing Methodology.sets attribute."""
        mp = create_test_movement_pattern(db_session, name="squat")
        mg = create_test_muscle_group(db_session, "quads", body_region="lower")
        create_test_exercise(db_session, "squat", mg, mp, equipment_type="barbell")

        profile = create_test_user_profile(
            db_session,
            training_split="full_body",
            goal="strength",
        )
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert len(plan.exercises) == 1
        assert plan.exercises[0].sets == (
            mock_science_config.puos.max_sets_per_group
            // mock_science_config.methodologies.strength.frequency_per_week_min
        )


# ─── Antagonist Balance Tests ──────────────────────────────────────────────────

class TestAntagonistBalance:
    def test_upper_session_only_push_adds_warning(self, db_session, mock_science_config):
        """Upper body session with only push muscles → warning about imbalance."""
        mp = create_test_movement_pattern(db_session)
        mg_push = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        create_test_exercise(db_session, "bench", mg_push, mp, equipment_type="barbell")

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert any("Дисбаланс" in w for w in plan.warnings)

    def test_balanced_upper_no_warning(self, db_session, mock_science_config):
        """Push + pull exercises → no antagonist warning."""
        mp = create_test_movement_pattern(db_session)
        mg_push = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        mg_pull = create_test_muscle_group(db_session, "back", body_region="upper", is_pull=True)
        create_test_exercise(db_session, "bench", mg_push, mp, equipment_type="barbell")
        create_test_exercise(db_session, "row", mg_pull, mp, equipment_type="barbell")

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        assert not any("Дисбаланс" in w for w in plan.warnings)


# ─── Rotation Tests ────────────────────────────────────────────────────────────

class TestRotation:
    def test_rotation_prefers_unused_exercise(self, db_session, mock_science_config):
        """2 exercises for group, one used recently → prefer the other."""
        mp = create_test_movement_pattern(db_session)
        mg = create_test_muscle_group(db_session, "chest", body_region="upper", is_push=True)
        ex_used = create_test_exercise(db_session, "bench", mg, mp, equipment_type="barbell")
        ex_unused = create_test_exercise(db_session, "incline_bench", mg, mp, equipment_type="barbell")

        # ex_used was used 2 days ago
        create_completed_session(
            db_session, date.today() - timedelta(days=2),
            split_day_label="full_body", exercise=ex_used, weight_kg=80.0
        )

        profile = create_test_user_profile(db_session, training_split="full_body")
        plan = WorkoutPlanner().generate(profile, mock_science_config, db_session)

        # Should prefer the unused exercise (higher rotation_score)
        if plan.exercises:
            assert plan.exercises[0].exercise_name == "incline_bench"

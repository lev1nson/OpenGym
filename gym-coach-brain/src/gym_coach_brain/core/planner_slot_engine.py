"""
Slot-based workout planner engine.

Stateless engine that generates slot-based workout plans using:
- Day templates (slot definitions per split)
- Deterministic candidate scoring
- Role-based prescription
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from gym_coach_brain.core.equipment_inventory import exercise_available_for_profile

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from gym_coach_brain.core.readiness import RecoverySignal
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import Exercise, PlannedExercise, UserProfile, WorkoutSession
    from gym_coach_brain.core.planner import WorkoutPlanner
    from gym_coach_brain.core.planner_slots import Slot


@dataclass
class SlotPlanResult:
    planned_exercises: list
    warnings: list[str]
    planning_trace: list[dict]
    covered_muscles: set[str]


class SlotPlannerEngine:
    def plan(
        self,
        user_profile: "UserProfile",
        science: "ScienceConfig",
        db_session: "SASession",
        recovery_signal: "RecoverySignal | None" = None,
        _today: "date | None" = None,
        forced_split_day_label: str | None = None,
    ) -> SlotPlanResult:
        """Generate workout plan using slot-based architecture."""
        from gym_coach_brain.core.planner import WorkoutPlanner
        from gym_coach_brain.core.planner_slots import (
            get_day_template,
            filter_required_slots,
            filter_optional_slots,
        )
        from gym_coach_brain.core.planner_scoring import (
            get_anchor_exercise_id_for_slot,
            rank_candidates,
            score_candidate,
            ScoredCandidate,
        )
        from gym_coach_brain.core.planner_prescription import get_slot_prescription
        from gym_coach_brain.data.models import Exercise, WorkoutSession

        today = _today if _today is not None else date.today()
        planner = WorkoutPlanner()

        last_session: WorkoutSession | None = (
            db_session.query(WorkoutSession)
            .filter(WorkoutSession.status == "completed")
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )

        if forced_split_day_label is not None:
            split_label = forced_split_day_label
        else:
            split_label, _ = planner._determine_split_day(user_profile, last_session, db_session)

        template = get_day_template(user_profile.training_split, split_label)
        if template is None:
            return SlotPlanResult(
                planned_exercises=[],
                warnings=[f"No slot template for split={user_profile.training_split}, day={split_label}"],
                planning_trace=[],
                covered_muscles=set(),
            )

        all_slots = template.slots
        required_slots = filter_required_slots(all_slots)
        optional_slots = filter_optional_slots(all_slots)

        recovery_coeff = recovery_signal.coefficient if recovery_signal is not None else 1.0

        apply_detraining = False
        if last_session:
            last_date = date.fromisoformat(last_session.session_date[:10])
            days_gap = (today - last_date).days
            if days_gap > science.planning.detraining_threshold_days:
                apply_detraining = True

        rep_min, rep_max, default_sets = planner._get_methodology_params(user_profile, science)
        rep_range = (rep_min, rep_max)

        warnings: list[str] = []
        planning_trace: list[dict] = []
        planned_exercises: list = []
        covered_muscles: set[str] = set()

        for slot in required_slots:
            candidate = self._select_for_slot(
                slot=slot,
                user_profile=user_profile,
                science=science,
                db_session=db_session,
                today=today,
                recovery_coeff=recovery_coeff,
                apply_detraining=apply_detraining,
                default_sets=default_sets,
                rep_range=rep_range,
                planner=planner,
            )

            if candidate is None:
                warnings.append(f"No valid exercise for required slot: {slot.slot_id}")
                continue

            planned_exercises.append(candidate)
            if candidate.primary_muscle_name:
                covered_muscles.add(candidate.primary_muscle_name)

            planning_trace.append({
                "slot_id": slot.slot_id,
                "exercise_id": candidate.exercise_id,
                "exercise_name": candidate.exercise_name,
                "selection_source": "deterministic",
            })

        for slot in optional_slots:
            if self._should_fill_optional_slot(slot, covered_muscles, planned_exercises, science):
                candidate = self._select_for_slot(
                    slot=slot,
                    user_profile=user_profile,
                    science=science,
                    db_session=db_session,
                    today=today,
                    recovery_coeff=recovery_coeff,
                    apply_detraining=apply_detraining,
                    default_sets=default_sets,
                    rep_range=rep_range,
                    planner=planner,
                )

                if candidate is None:
                    continue

                planned_exercises.append(candidate)
                if candidate.primary_muscle_name:
                    covered_muscles.add(candidate.primary_muscle_name)

                planning_trace.append({
                    "slot_id": slot.slot_id,
                    "exercise_id": candidate.exercise_id,
                    "exercise_name": candidate.exercise_name,
                    "selection_source": "deterministic",
                })

        planned_exercises = planner._apply_puos_reduction(
            planned_exercises, [], db_session, science
        )

        return SlotPlanResult(
            planned_exercises=planned_exercises,
            warnings=warnings,
            planning_trace=planning_trace,
            covered_muscles=covered_muscles,
        )

    def _select_for_slot(
        self,
        slot: "Slot",
        user_profile: "UserProfile",
        science: "ScienceConfig",
        db_session: "SASession",
        today: date,
        recovery_coeff: float,
        apply_detraining: bool,
        default_sets: int,
        rep_range: tuple[int, int],
        planner: "WorkoutPlanner",
    ) -> "PlannedExercise | None":
        from gym_coach_brain.core.planner_scoring import (
            get_anchor_exercise_id_for_slot,
            rank_candidates,
            score_candidate,
            ScoredCandidate,
        )
        from gym_coach_brain.core.planner_prescription import get_slot_prescription
        from gym_coach_brain.core.weight_utils import round_to_equipment_increment
        from gym_coach_brain.data.models import Exercise
        from gym_coach_brain.core.planner import PlannedExercise

        candidates = self._enumerate_slot_candidates(slot, user_profile, db_session)
        if not candidates:
            return None

        anchor_exercise_id = get_anchor_exercise_id_for_slot(slot, today, db_session)

        scored: list[ScoredCandidate] = []
        for ex in candidates:
            history_days = self._get_days_since_use(ex.id, today, db_session)
            sc = score_candidate(
                exercise=ex,
                slot=slot,
                user_profile=user_profile,
                today_date=today,
                db_session=db_session,
                science=science,
                history_days_since_use=history_days,
                anchor_exercise_id=anchor_exercise_id,
            )
            scored.append(ScoredCandidate(exercise=ex, slot=slot, score=sc))

        ranked = rank_candidates(scored, today)
        if not ranked:
            return None

        best = ranked[0]
        best_exercise = best.exercise

        primary_mg = best_exercise.primary_muscle
        primary_mg_name = primary_mg.name if primary_mg else ""

        prescription = get_slot_prescription(
            slot=slot,
            exercise=best_exercise,
            muscle_group=primary_mg,
            default_sets=default_sets,
            base_rep_range=rep_range,
        )

        raw_weight = planner._calculate_weight(
            best_exercise, user_profile, science, recovery_coeff,
            apply_detraining, db_session
        )

        rounded_weight = round_to_equipment_increment(
            raw_weight, best_exercise.equipment_type, science
        )

        return PlannedExercise(
            exercise_id=best_exercise.id,
            exercise_name=best_exercise.name,
            sets=prescription.sets,
            rep_range=(prescription.rep_min, prescription.rep_max),
            target_weight_kg=rounded_weight,
            slot_id=slot.slot_id,
            selection_reason="deterministic",
            primary_muscle_name=primary_mg_name,
        )

    def _enumerate_slot_candidates(
        self,
        slot: "Slot",
        user_profile: "UserProfile",
        db_session: "SASession",
    ) -> list["Exercise"]:
        from gym_coach_brain.data.models import Exercise

        all_exercises = db_session.query(Exercise).all()
        candidates: list[Exercise] = []
        for ex in all_exercises:
            if not self._exercise_matches_slot(ex, slot, user_profile, db_session):
                continue
            if exercise_available_for_profile(ex, user_profile, allow_bodyweight_fallback=True):
                candidates.append(ex)
        return candidates

    def _exercise_matches_slot(
        self,
        exercise: "Exercise",
        slot: "Slot",
        user_profile: "UserProfile",
        db_session: "SASession",
    ) -> bool:
        primary_muscle = exercise.primary_muscle
        if primary_muscle is None:
            return False

        if primary_muscle.name not in slot.target_muscles:
            return False

        if slot.movement_preferences:
            movement = exercise.movement_pattern.name if exercise.movement_pattern else ""
            if movement not in slot.movement_preferences:
                return False

        return True

    def _should_fill_optional_slot(
        self,
        slot: "Slot",
        covered_muscles: set[str],
        planned: list,
        science: "ScienceConfig",
    ) -> bool:
        return True

    def _get_days_since_use(
        self,
        exercise_id: int,
        today: date,
        db_session: "SASession",
    ) -> int | None:
        from gym_coach_brain.data.models import WorkoutSession, WorkoutSet

        last_used = (
            db_session.query(WorkoutSession.session_date)
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .filter(
                WorkoutSession.status == "completed",
                WorkoutSet.exercise_id == exercise_id,
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )
        if last_used is None:
            return None
        last_date = date.fromisoformat(last_used[0][:10])
        return (today - last_date).days

"""
WorkoutPlanner — deterministic daily training plan generator.

Implements the science-driven exercise selection, split-day rotation,
detraining detection, recovery signal scaling, PUOS validation,
and antagonist balance checks.

References:
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.7]
    [Source: _bmad-output/planning-artifacts/architecture.md#FR5]
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from loguru import logger

from gym_coach_brain.core.equipment_inventory import exercise_available_for_profile

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from gym_coach_brain.core.readiness import RecoverySignal
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import Exercise, MuscleGroup, UserProfile, WorkoutSession


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class PlannedExercise:
    """One exercise in today's workout plan."""
    exercise_id: int
    exercise_name: str
    sets: int
    rep_range: tuple[int, int]
    target_weight_kg: float


@dataclass
class WorkoutPlan:
    """Complete workout plan for today's session."""
    muscle_groups_today: list[str]
    split_day_label: str
    exercises: list[PlannedExercise]
    skipped_groups: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ─── Split-Day Constants ───────────────────────────────────────────────────────

_PPL_CYCLE: list[str] = ["push", "pull", "legs"]
_UL_CYCLE: list[str] = ["upper", "lower"]
_SUPPORT_OPTIONAL_GROUPS: set[str] = {"trapezius", "biceps", "triceps", "calves", "abs", "lower_back"}
_SUPPORT_COVERAGE_TARGETS: dict[str, float] = {
    "trapezius": 2.5,
    "biceps": 2.5,
    "triceps": 2.5,
    "calves": 2.0,
    "abs": 2.0,
    "lower_back": 2.0,
}
_MAX_SUPPORT_EXERCISES_PER_SESSION: int = 2


# ─── WorkoutPlanner ───────────────────────────────────────────────────────────

class WorkoutPlanner:
    """Generates deterministic daily workout plans from athlete profile and history.

    Composition Root pattern: create one instance per request, pass science + db_session.
    No global state, no singleton.

    Usage:
        planner = WorkoutPlanner()
        plan = planner.generate(user_profile, science, db_session, recovery_signal)
    """

    def generate(
        self,
        user_profile: "UserProfile",
        science: "ScienceConfig",
        db_session: "SASession",
        recovery_signal: "RecoverySignal | None" = None,
        _today: "date | None" = None,
        forced_split_day_label: str | None = None,
    ) -> WorkoutPlan:
        """Generate complete workout plan for today.

        Args:
            user_profile: Athlete profile with training_split, available_equipment, bodyweight_kg
            science: ScienceConfig with PUOS limits, planning thresholds, methodologies
            db_session: Active SQLAlchemy Session (read-only — no commit)
            recovery_signal: Optional readiness signal; if None, coefficient=1.0 is used

        Returns:
            WorkoutPlan with exercises, warnings, and skipped groups.
        """
        from gym_coach_brain.data.models import WorkoutSession

        today = _today if _today is not None else date.today()

        # ── Step 1: Find last completed session ──────────────────────────────
        last_session: WorkoutSession | None = (
            db_session.query(WorkoutSession)
            .filter(WorkoutSession.status == "completed")
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )

        # ── Step 2: Determine split day and muscle groups ────────────────────
        if forced_split_day_label is not None:
            split_label = forced_split_day_label
            muscle_groups = self._determine_muscle_groups_for_label(
                user_profile, split_label, last_session, db_session
            )
        else:
            split_label, muscle_groups = self._determine_split_day(
                user_profile, last_session, db_session
            )

        # ── Step 3: Apply min_rest_days filter ───────────────────────────────
        warnings: list[str] = []
        skipped_groups: list[str] = []

        filtered_groups = self._filter_by_rest_days(
            muscle_groups, today, db_session, science
        )
        if not filtered_groups and muscle_groups:
            # Override: rest days would leave plan empty
            filtered_groups = muscle_groups
            warnings.append(
                "⚠️ Нарушен рекомендуемый отдых — недостаточно времени с последней тренировки"
            )

        # ── Step 4: Check detraining ─────────────────────────────────────────
        apply_detraining = False
        days_gap = 0
        if last_session:
            last_date = date.fromisoformat(last_session.session_date[:10])
            days_gap = (today - last_date).days
            if days_gap > science.planning.detraining_threshold_days:
                apply_detraining = True
                warnings.append(
                    f"⚠️ Перерыв {days_gap} дней — веса снижены для безопасного возврата"
                )

        # ── Step 5: Check deload recommendation ──────────────────────────────
        completed_count = self._count_completed_sessions(db_session)
        if completed_count >= science.planning.deload_trigger_sessions:
            weeks = completed_count // 4  # approximate
            warnings.append(
                f"💤 Рекомендуется дилоад-неделя — {weeks} недель непрерывной нагрузки"
            )

        # ── Step 6: Get methodology (rep range + default sets) ───────────────
        rep_min, rep_max, default_sets = self._get_methodology_params(user_profile, science)
        rep_range = (rep_min, rep_max)

        # ── Step 7: Select exercises and calculate weights ───────────────────
        planned_exercises: list[PlannedExercise] = []
        recovery_coeff = recovery_signal.coefficient if recovery_signal is not None else 1.0
        primary_groups = [mg for mg in filtered_groups if not self._is_optional_support_group(mg)]
        support_groups = [mg for mg in filtered_groups if self._is_optional_support_group(mg)]

        selected: list[tuple["Exercise", "MuscleGroup"]] = []

        for mg in primary_groups:
            stability_bias = split_label in {"lower", "legs"} and mg.body_region == "lower"
            exercise = self._select_exercise(
                mg,
                user_profile,
                today,
                db_session,
                stability_bias=stability_bias,
            )
            if exercise is None:
                skipped_groups.append(f"{mg.name}:no_equipment")
                continue
            selected.append((exercise, mg))

        support_candidates: list[tuple[float, "MuscleGroup"]] = []
        support_volume = self._estimate_fractional_volume(selected, user_profile, science, default_sets, split_label)
        for mg in support_groups:
            current_volume = support_volume.get(mg.id, 0.0)
            target_volume = _SUPPORT_COVERAGE_TARGETS.get(mg.name, 2.0)
            if current_volume >= target_volume:
                continue
            support_candidates.append((current_volume, mg))

        support_exercises_added = 0
        for _, mg in sorted(support_candidates, key=lambda item: (item[0], item[1].name)):
            if support_exercises_added >= _MAX_SUPPORT_EXERCISES_PER_SESSION:
                break
            exercise = self._select_exercise(mg, user_profile, today, db_session)
            if exercise is None:
                skipped_groups.append(f"{mg.name}:no_equipment")
                continue
            selected.append((exercise, mg))
            support_exercises_added += 1
            support_volume = self._estimate_fractional_volume(selected, user_profile, science, default_sets, split_label)

        for exercise, muscle_group in selected:
            sets, rep_range = self._get_exercise_prescription(
                exercise=exercise,
                muscle_group=muscle_group,
                split_label=split_label,
                default_sets=default_sets,
                base_rep_range=rep_range,
            )
            raw_weight = self._calculate_weight(
                exercise, user_profile, science, recovery_coeff,
                apply_detraining, db_session
            )

            from gym_coach_brain.core.weight_utils import round_to_equipment_increment
            rounded_weight = round_to_equipment_increment(
                raw_weight, exercise.equipment_type, science
            )

            planned_exercises.append(
                PlannedExercise(
                    exercise_id=exercise.id,
                    exercise_name=exercise.name,
                    sets=sets,
                    rep_range=rep_range,
                    target_weight_kg=rounded_weight,
                )
            )

        # ── Step 8: PUOS validation and auto-reduction ───────────────────────
        planned_exercises = self._apply_puos_reduction(
            planned_exercises, filtered_groups, db_session, science
        )

        # ── Step 9: Antagonist balance check (upper body only) ───────────────
        is_upper_session = split_label in ("upper", "push", "pull", "full_body")
        if is_upper_session and planned_exercises:
            balance_warning = self._check_antagonist_balance(
                planned_exercises, db_session
            )
            if balance_warning:
                warnings.append(balance_warning)

        skipped_names = {sg.split(":")[0] for sg in skipped_groups}
        return WorkoutPlan(
            muscle_groups_today=[mg.name for mg in filtered_groups if mg.name not in skipped_names],
            split_day_label=split_label,
            exercises=planned_exercises,
            skipped_groups=skipped_groups,
            warnings=warnings,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _determine_split_day(
        self,
        user_profile: "UserProfile",
        last_session: "WorkoutSession | None",
        db_session: "SASession",
    ) -> tuple[str, list["MuscleGroup"]]:
        """Return (today_split_label, muscle_groups_for_today)."""
        from gym_coach_brain.data.models import TrainingSplit

        split = user_profile.training_split
        prev_label = last_session.split_day_label if last_session else None

        # Normalize split to string for comparison
        split_str = split.value if hasattr(split, "value") else str(split)

        if split_str in (TrainingSplit.full_body, TrainingSplit.full_body.value, "full_body"):
            today_label = "full_body"

        elif split_str in (TrainingSplit.upper_lower, TrainingSplit.upper_lower.value, "upper_lower"):
            if not prev_label or prev_label not in ("upper", "lower"):
                today_label = "upper"
            else:
                today_label = "lower" if prev_label == "upper" else "upper"

        elif split_str in (TrainingSplit.ppl, TrainingSplit.ppl.value, "ppl"):
            if not prev_label or prev_label not in _PPL_CYCLE:
                today_label = "push"
            else:
                idx = _PPL_CYCLE.index(prev_label)
                today_label = _PPL_CYCLE[(idx + 1) % len(_PPL_CYCLE)]

        else:  # custom
            today_label = "full_body"

        return today_label, self._determine_muscle_groups_for_label(
            user_profile, today_label, last_session, db_session
        )

    def _determine_muscle_groups_for_label(
        self,
        user_profile: "UserProfile",
        split_label: str,
        last_session: "WorkoutSession | None",
        db_session: "SASession",
    ) -> list["MuscleGroup"]:
        """Return muscle groups for an explicit split label without advancing the cycle."""
        from gym_coach_brain.data.models import MuscleGroup, TrainingSplit

        split = user_profile.training_split
        split_str = split.value if hasattr(split, "value") else str(split)
        all_groups: list[MuscleGroup] = db_session.query(MuscleGroup).all()

        if split_str in (TrainingSplit.full_body, TrainingSplit.full_body.value, "full_body"):
            return all_groups

        if split_str in (TrainingSplit.upper_lower, TrainingSplit.upper_lower.value, "upper_lower"):
            regions = {"upper"} if split_label == "upper" else {"lower", "core"}
            return [group for group in all_groups if group.body_region in regions]

        if split_str in (TrainingSplit.ppl, TrainingSplit.ppl.value, "ppl"):
            if split_label == "push":
                return [
                    group for group in all_groups
                    if group.is_push and group.body_region == "upper"
                ]
            if split_label == "pull":
                return [
                    group for group in all_groups
                    if group.is_pull and group.body_region == "upper"
                ]
            return [group for group in all_groups if group.body_region == "lower"]

        if last_session is not None:
            groups = self._get_last_session_muscle_groups(last_session, db_session)
            if groups:
                return groups

        return all_groups

    def _get_last_session_muscle_groups(
        self, last_session: "WorkoutSession", db_session: "SASession"
    ) -> list["MuscleGroup"]:
        """Get unique primary muscle groups trained in last session."""
        from gym_coach_brain.data.models import Exercise, MuscleGroup, WorkoutSet

        sets = (
            db_session.query(WorkoutSet)
            .filter(WorkoutSet.session_id == last_session.id)
            .all()
        )
        exercise_ids = {ws.exercise_id for ws in sets}
        muscle_ids: set[int] = set()
        for eid in exercise_ids:
            ex = db_session.query(Exercise).filter_by(id=eid).first()
            if ex:
                muscle_ids.add(ex.primary_muscle_id)

        result = []
        for mid in muscle_ids:
            mg = db_session.query(MuscleGroup).filter_by(id=mid).first()
            if mg is not None:
                result.append(mg)
        return result

    def _filter_by_rest_days(
        self,
        groups: list["MuscleGroup"],
        today: date,
        db_session: "SASession",
        science: "ScienceConfig",
    ) -> list["MuscleGroup"]:
        """Exclude muscle groups trained too recently."""
        min_rest = science.planning.min_rest_days_per_muscle_group
        allowed: list["MuscleGroup"] = []

        for mg in groups:
            last_trained = self._get_last_trained_date(mg.id, db_session)
            if last_trained is None:
                allowed.append(mg)
                continue

            days_since = (today - last_trained).days
            if days_since >= min_rest:
                allowed.append(mg)
            else:
                logger.debug(
                    "Excluding {mg} — trained {days}d ago (min rest: {min}d)",
                    mg=mg.name, days=days_since, min=min_rest,
                )
        return allowed

    def _get_last_trained_date(
        self, muscle_group_id: int, db_session: "SASession"
    ) -> date | None:
        """Return date of most recent session where muscle_group_id was a primary muscle."""
        from gym_coach_brain.data.models import Exercise, WorkoutSession, WorkoutSet

        row = (
            db_session.query(WorkoutSession.session_date)
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .join(Exercise, Exercise.id == WorkoutSet.exercise_id)
            .filter(
                WorkoutSession.status == "completed",
                Exercise.primary_muscle_id == muscle_group_id,
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )
        if row is None:
            return None
        date_str = row[0][:10]
        return date.fromisoformat(date_str)

    def _select_exercise(
        self,
        mg: "MuscleGroup",
        user_profile: "UserProfile",
        today_date: date,
        db_session: "SASession",
        *,
        stability_bias: bool = False,
    ) -> "Exercise | None":
        """Select best exercise for muscle group based on equipment and rotation."""
        from gym_coach_brain.data.models import Exercise, WorkoutSession, WorkoutSet

        all_candidates: list[Exercise] = (
            db_session.query(Exercise)
            .filter(Exercise.primary_muscle_id == mg.id)
            .all()
        )

        available_equipment = json.loads(user_profile.available_equipment or "[]")
        inventory = json.loads(user_profile.available_equipment_inventory or "[]")

        if not available_equipment and not inventory:
            candidates = all_candidates
        else:
            direct_candidates = [
                exercise
                for exercise in all_candidates
                if exercise_available_for_profile(
                    exercise,
                    user_profile,
                    allow_bodyweight_fallback=False,
                    allow_unrestricted_if_empty=False,
                )
            ]
            if direct_candidates:
                candidates = direct_candidates
            else:
                # If the inventory cannot train this muscle group directly,
                # use bodyweight options as a balancing fallback.
                candidates = [
                    exercise
                    for exercise in all_candidates
                    if exercise_available_for_profile(
                        exercise,
                        user_profile,
                        allow_bodyweight_fallback=True,
                        allow_unrestricted_if_empty=False,
                    )
                ]

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        if stability_bias:
            stable_choice = self._select_recent_anchor(candidates, today_date, db_session)
            if stable_choice is not None:
                return stable_choice

        # Build rotation scores: higher score = less recently used = preferred
        exercise_last_used: dict[int, int] = {}  # exercise_id → days since last use
        for ex in candidates:
            last_set_row = (
                db_session.query(WorkoutSession.session_date)
                .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
                .filter(
                    WorkoutSession.status == "completed",
                    WorkoutSet.exercise_id == ex.id,
                )
                .order_by(WorkoutSession.session_date.desc())
                .first()
            )
            if last_set_row is None:
                exercise_last_used[ex.id] = 9999  # Never used → highest priority
            else:
                last_date = date.fromisoformat(last_set_row[0][:10])
                exercise_last_used[ex.id] = (today_date - last_date).days

        # Apply equipment preference bonus when user has specific equipment
        # Prefer machine > cable > dumbbell > barbell > bodyweight when available
        equipment_priority = {"machine": 100, "cable": 90, "dumbbell": 80, "barbell": 70, "bodyweight": 60}
        for ex in candidates:
            equip_value = ex.equipment_type.value if hasattr(ex.equipment_type, 'value') else str(ex.equipment_type)
            priority_bonus = equipment_priority.get(equip_value, 0)
            exercise_last_used[ex.id] += priority_bonus

        # Sort: highest days_since first; break ties randomly (seeded by date)
        max_score = max(exercise_last_used.values())
        top_candidates = [
            ex for ex in candidates
            if exercise_last_used[ex.id] == max_score
        ]

        if len(top_candidates) == 1:
            return top_candidates[0]

        # Deterministic random tie-breaking
        rng = random.Random(today_date.isoformat())
        return rng.choice(top_candidates)

    def _select_recent_anchor(
        self,
        candidates: list["Exercise"],
        today_date: date,
        db_session: "SASession",
    ) -> "Exercise | None":
        """Prefer repeating a recent lower-body anchor to preserve progression continuity."""
        from gym_coach_brain.data.models import WorkoutSession, WorkoutSet

        anchor_window_days = 21
        most_recent: tuple[int, "Exercise"] | None = None

        for exercise in candidates:
            last_set_row = (
                db_session.query(WorkoutSession.session_date)
                .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
                .filter(
                    WorkoutSession.status == "completed",
                    WorkoutSet.exercise_id == exercise.id,
                )
                .order_by(WorkoutSession.session_date.desc())
                .first()
            )
            if last_set_row is None:
                continue
            last_date = date.fromisoformat(last_set_row[0][:10])
            days_since = (today_date - last_date).days
            if days_since > anchor_window_days:
                continue
            if most_recent is None or days_since < most_recent[0]:
                most_recent = (days_since, exercise)

        return most_recent[1] if most_recent is not None else None

    def _calculate_weight(
        self,
        exercise: "Exercise",
        user_profile: "UserProfile",
        science: "ScienceConfig",
        recovery_coeff: float,
        apply_detraining: bool,
        db_session: "SASession",
    ) -> float:
        """Compute raw target weight for an exercise before rounding."""
        from gym_coach_brain.data.models import EquipmentType

        if exercise.equipment_type == EquipmentType.bodyweight:
            return 0.0

        # Try last used weight for this exercise
        last_weight = self._get_last_used_weight(exercise.id, db_session)

        if last_weight is not None:
            raw = self._normalize_recent_weight_for_recovery(
                exercise_id=exercise.id,
                last_weight=last_weight,
                db_session=db_session,
            )
        else:
            # New exercise: look up initial weight from profile
            initial_weights = json.loads(user_profile.initial_weight_coefficients or "{}")
            pattern_name = exercise.movement_pattern.name if exercise.movement_pattern else ""
            initial = initial_weights.get(pattern_name, 0.0)

            if initial == 0.0 and pattern_name and user_profile.bodyweight_kg:
                # Fallback: compute from science table
                exp_level = user_profile.experience_level or "beginner"
                table = science.initial_weight_table.get(exp_level, {})
                coeff = table.get(pattern_name, 0.0)
                initial = (user_profile.bodyweight_kg or 0.0) * coeff

            raw = initial

        # Apply detraining coefficient
        if apply_detraining:
            raw *= science.planning.detraining_coefficient

        # Apply recovery signal
        raw *= recovery_coeff

        return max(0.0, raw)

    def _get_last_used_weight(
        self, exercise_id: int, db_session: "SASession"
    ) -> float | None:
        """Return most recent weight used for this exercise across all sessions."""
        from gym_coach_brain.data.models import WorkoutSession, WorkoutSet

        row = (
            db_session.query(WorkoutSet.weight_kg)
            .join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
            .filter(
                WorkoutSession.status == "completed",
                WorkoutSet.exercise_id == exercise_id,
            )
            .order_by(WorkoutSession.session_date.desc(), WorkoutSet.set_number.desc())
            .first()
        )
        return row[0] if row else None

    def _normalize_recent_weight_for_recovery(
        self,
        exercise_id: int,
        last_weight: float,
        db_session: "SASession",
    ) -> float:
        """Undo the previous session's temporary readiness reduction before re-planning.

        A low-readiness day should scale only that session, not permanently ratchet the
        athlete's long-term baseline downward.
        """
        from gym_coach_brain.data.models import (
            RPEPrediction,
            ReadinessLog,
            WorkoutSession,
            WorkoutSet,
        )

        row = (
            db_session.query(WorkoutSession.id, WorkoutSession.session_date)
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .filter(
                WorkoutSession.status == "completed",
                WorkoutSet.exercise_id == exercise_id,
            )
            .order_by(WorkoutSession.session_date.desc(), WorkoutSet.set_number.desc())
            .first()
        )
        if row is None:
            return last_weight

        prediction = (
            db_session.query(RPEPrediction)
            .filter_by(session_id=row[0], exercise_id=exercise_id)
            .order_by(RPEPrediction.created_at.desc(), RPEPrediction.id.desc())
            .first()
        )
        if prediction is not None and prediction.core_weight_kg is not None:
            return float(prediction.core_weight_kg)

        readiness_log = (
            db_session.query(ReadinessLog)
            .filter_by(session_date=row[1][:10])
            .first()
        )
        recovery_score = (
            float(readiness_log.recovery_score)
            if readiness_log is not None and readiness_log.recovery_score is not None
            else 1.0
        )
        if recovery_score <= 0.0:
            return last_weight
        return last_weight / recovery_score

    def _apply_puos_reduction(
        self,
        exercises: list[PlannedExercise],
        muscle_groups: list["MuscleGroup"],
        db_session: "SASession",
        science: "ScienceConfig",
    ) -> list[PlannedExercise]:
        """Validate PUOS and auto-reduce sets if limit exceeded. Returns adjusted list."""
        from gym_coach_brain.core.puos import validate_puos
        from gym_coach_brain.data.models import Exercise, MuscleGroup
        from gym_coach_brain.exceptions import ScienceLimitError

        # Build volume map from planned exercises
        mg_by_id: dict[int, MuscleGroup] = {mg.id: mg for mg in muscle_groups}

        while True:
            volume_map: dict[int, float] = {}
            for pe in exercises:
                ex = db_session.query(Exercise).filter_by(id=pe.exercise_id).first()
                if ex is None:
                    continue
                # Primary muscle
                pid = ex.primary_muscle_id
                volume_map[pid] = volume_map.get(pid, 0.0) + pe.sets * 1.0
                # Secondary muscles
                for sid in json.loads(ex.secondary_muscle_ids or "[]"):
                    volume_map[sid] = volume_map.get(sid, 0.0) + pe.sets * 0.5

            violation_found = False
            for mg_id, volume in volume_map.items():
                mg = mg_by_id.get(mg_id) or db_session.query(MuscleGroup).filter_by(id=mg_id).first()
                if mg is None:
                    continue
                try:
                    validate_puos(mg, volume, science)
                except ScienceLimitError:
                    violation_found = True
                    # Find the exercise contributing most to this muscle group
                    max_contrib = 0.0
                    max_idx = -1
                    for i, pe in enumerate(exercises):
                        ex = db_session.query(Exercise).filter_by(id=pe.exercise_id).first()
                        if ex is None:
                            continue
                        contrib = pe.sets * (
                            1.0 if ex.primary_muscle_id == mg_id
                            else 0.5 if mg_id in json.loads(ex.secondary_muscle_ids or "[]")
                            else 0.0
                        )
                        if contrib > max_contrib:
                            max_contrib = contrib
                            max_idx = i
                    if max_idx >= 0:
                        if exercises[max_idx].sets <= 1:
                            exercises.pop(max_idx)
                        else:
                            exercises[max_idx] = PlannedExercise(
                                exercise_id=exercises[max_idx].exercise_id,
                                exercise_name=exercises[max_idx].exercise_name,
                                sets=exercises[max_idx].sets - 1,
                                rep_range=exercises[max_idx].rep_range,
                                target_weight_kg=exercises[max_idx].target_weight_kg,
                            )
                    else:
                        break  # Stop reduction if we can't find any contributor
                    break  # Re-validate from scratch after reduction

            if not violation_found:
                break

        return exercises

    def _check_antagonist_balance(
        self,
        exercises: list[PlannedExercise],
        db_session: "SASession",
    ) -> str | None:
        """Return warning string if antagonist balance is missing, else None."""
        from gym_coach_brain.data.models import Exercise, MuscleGroup

        if not exercises:
            return None

        exercise_ids = [pe.exercise_id for pe in exercises]
        
        muscles = (
            db_session.query(MuscleGroup)
            .join(Exercise, Exercise.primary_muscle_id == MuscleGroup.id)
            .filter(Exercise.id.in_(exercise_ids))
            .all()
        )

        has_push = any(mg.is_push for mg in muscles)
        has_pull = any(mg.is_pull for mg in muscles)

        if has_push and not has_pull:
            return "⚠️ Дисбаланс: только push упражнения — рекомендуется добавить антагонист"
        if has_pull and not has_push:
            return "⚠️ Дисбаланс: только pull упражнения — рекомендуется добавить антагонист"
        return None

    def _get_methodology_params(
        self,
        user_profile: "UserProfile",
        science: "ScienceConfig",
    ) -> tuple[int, int, int]:
        """Return rep range and a science-derived set count for the active methodology."""
        from gym_coach_brain.core.methodology import select_methodology

        methodology = select_methodology(user_profile, science)
        default_sets = max(
            1,
            science.puos.max_sets_per_group // max(1, methodology.frequency_min),
        )
        return methodology.rep_range.min, methodology.rep_range.max, default_sets

    def _get_exercise_prescription(
        self,
        exercise: "Exercise",
        muscle_group: "MuscleGroup",
        split_label: str,
        default_sets: int,
        base_rep_range: tuple[int, int],
    ) -> tuple[int, tuple[int, int]]:
        """Return exercise-specific set and rep targets.

        The old planner assigned one identical prescription to every exercise.
        This keeps the methodology baseline but scales accessories down and
        avoids treating carries/core work like primary barbell lifts.
        """
        movement_pattern = (
            exercise.movement_pattern.name
            if exercise.movement_pattern is not None
            else ""
        )
        primary_sets = max(1, default_sets - 1)
        accessory_sets = max(1, default_sets - 2)

        if movement_pattern == "carry" or muscle_group.name in {"abs", "calves"}:
            return accessory_sets, (10, 20)

        if not exercise.is_compound:
            return accessory_sets, (8, max(base_rep_range[1], 15))

        if not self._is_optional_support_group(muscle_group):
            if split_label == "lower" and movement_pattern in {"squat", "hinge"}:
                return primary_sets, (6, min(base_rep_range[1], 10))
            return primary_sets, base_rep_range

        return accessory_sets, (8, max(base_rep_range[1], 15))

    def _is_optional_support_group(self, muscle_group: "MuscleGroup") -> bool:
        """Return whether a muscle group can be omitted when compounds already cover it."""
        return muscle_group.name in _SUPPORT_OPTIONAL_GROUPS

    def _estimate_fractional_volume(
        self,
        selected: list[tuple["Exercise", "MuscleGroup"]],
        user_profile: "UserProfile",
        science: "ScienceConfig",
        default_sets: int,
        split_label: str,
    ) -> dict[int, float]:
        """Estimate fractional volume generated by the current selection."""
        volume_map: dict[int, float] = {}
        for exercise, muscle_group in selected:
            sets, _ = self._get_exercise_prescription(
                exercise=exercise,
                muscle_group=muscle_group,
                split_label=split_label,
                default_sets=default_sets,
                base_rep_range=self._get_methodology_params(user_profile, science)[:2],
            )
            volume_map[exercise.primary_muscle_id] = volume_map.get(exercise.primary_muscle_id, 0.0) + sets
            for secondary_id in json.loads(exercise.secondary_muscle_ids or "[]"):
                volume_map[secondary_id] = volume_map.get(secondary_id, 0.0) + sets * 0.5
        return volume_map

    def _count_completed_sessions(self, db_session: "SASession") -> int:
        """Count completed sessions since the most recent completed deload, if any."""
        from gym_coach_brain.data.models import WorkoutSession

        last_deload = (
            db_session.query(WorkoutSession.session_date)
            .filter(
                WorkoutSession.status == "completed",
                WorkoutSession.methodology == "deload",
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )

        query = db_session.query(WorkoutSession).filter(WorkoutSession.status == "completed")
        if last_deload is not None:
            query = query.filter(WorkoutSession.session_date > last_deload[0])

        return query.count()

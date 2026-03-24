"""
Simulation CLI entrypoint for E2E system validation.

Drives a synthetic N-month athlete training history through the real production
pipeline (planner → ML worker → adaptation engine) without mocks or parallel
business logic.

Usage:
    python -m gym_coach_brain.simulation.run --months=6 --sessions-per-week=3
    python -m gym_coach_brain.simulation.run --months=6 --sessions-per-week=3 --seed=42
"""
from __future__ import annotations

import argparse
import json
import random
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gym_coach_brain.adaptation.engine import AdaptationEngine
from gym_coach_brain.core.planner import WorkoutPlanner
from gym_coach_brain.core.readiness import calculate_recovery_signal
from gym_coach_brain.core.science import load_science_config
from gym_coach_brain.data.models import (
    Base,
    RPEPrediction,
    ReadinessLog,
    UserProfile,
    WorkoutSession,
    WorkoutSet,
)
from gym_coach_brain.data.queue import enqueue_fine_tune, enqueue_predict
from gym_coach_brain.data.seed import seed_all
from gym_coach_brain.ml.model import RPEModel
from gym_coach_brain.ml.worker import MLWorker
from gym_coach_brain.simulation.synthetic_athlete import (
    SyntheticAthlete,
    get_simulation_scenario,
)

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig


# ─── Simulation constants ──────────────────────────────────────────────────────

_FINE_TUNE_EVERY: int = 10      # Enqueue fine-tune after every N completed sessions
_COLD_START_SESSIONS: int = 5   # First N sessions stay on deterministic core
_ANOMALY_START: int = 25        # Begin fault injection at this session index
_ANOMALY_LENGTH: int = 2        # Inject anomaly model for this many consecutive sessions


# ─── Fault-injection model ────────────────────────────────────────────────────

class _AnomalyInjectModel:
    """Returns extreme low-RPE predictions to deliberately breach the correction limit.

    Predicted RPE=1.0 with high confidence → large delta from target RPE (~7.75)
    → delta_percent > max_correction_percent (0.15) → anomaly_flag=True.

    Safe to inject: save() is a no-op, no checkpoint is overwritten.
    """

    def predict(self, features: dict) -> tuple[float, float]:
        """Return (rpe=1.0, confidence=0.99) — triggers anomaly on any weight."""
        return 1.0, 0.99

    def fine_tune(self, training_samples: list[dict], **kwargs) -> None:
        """No-op: anomaly model is not trained."""

    def save(self, path: Path) -> None:
        """No-op: anomaly model has no weights to persist."""

    def load(self, path: Path) -> None:
        """No-op: anomaly model ignores checkpoint files."""


# ─── Metrics collector ────────────────────────────────────────────────────────

class SimulationMetrics:
    """Collects per-session metrics for report generation."""

    def __init__(self) -> None:
        self.session_records: list[dict] = []   # {idx, date, ai, anomaly, core, total}
        self.weight_records: list[dict] = []    # {idx, date, weights: {name: kg}}
        self.rpe_errors: list[dict] = []        # {idx, error}
        self.anomaly_events: list[dict] = []    # {idx, date, type, details}

    def record_session(
        self,
        idx: int,
        sim_date: date,
        source_labels: list[str],
        weights: dict[str, float],
        split_label: str,
        target_rpe: float,
        exercise_names: list[str],
        anomaly_flags: list[bool] | None = None,
        exercise_dimensions: dict[str, dict[str, str]] | None = None,
    ) -> None:
        ai = sum(1 for lbl in source_labels if lbl.startswith("[AI:"))
        # Use explicit anomaly_flag from DB (authoritative) when available; fall back to
        # label string matching only for callers that don't have the flag list.
        if anomaly_flags is not None:
            anomaly = sum(anomaly_flags)
        else:
            anomaly = sum(1 for lbl in source_labels if "заблокирован" in lbl)
        core = len(source_labels) - ai - anomaly
        self.session_records.append({
            "idx": idx,
            "date": sim_date.isoformat(),
            "ai": ai,
            "anomaly": anomaly,
            "core": core,
            "total": len(source_labels),
            "split_label": split_label,
            "target_rpe": target_rpe,
            "exercise_names": list(exercise_names),
        })
        self.weight_records.append({
            "idx": idx,
            "date": sim_date.isoformat(),
            "weights": dict(weights),
            "exercise_dimensions": dict(exercise_dimensions or {}),
        })

    def record_rpe(self, idx: int, predicted: float | None, actual: float) -> None:
        if predicted is not None:
            self.rpe_errors.append({"idx": idx, "error": abs(predicted - actual)})

    def record_anomaly_event(
        self, idx: int, sim_date: date, type_: str, details: str
    ) -> None:
        self.anomaly_events.append({
            "idx": idx,
            "date": sim_date.isoformat(),
            "type": type_,
            "details": details,
        })

    def mae_for_window(self, start: int, end: int) -> float | None:
        """Compute MAE over session indices [start, end)."""
        errors = [r["error"] for r in self.rpe_errors if start <= r["idx"] < end]
        return sum(errors) / len(errors) if errors else None

    def ai_usage_rate_after(self, start_session: int) -> float:
        """Fraction of exercise decisions that used ML correction after start_session."""
        records = [r for r in self.session_records if r["idx"] >= start_session]
        total = sum(r["total"] for r in records)
        ai = sum(r["ai"] for r in records)
        return ai / max(1, total)

    def weight_history_by_exercise(self) -> dict[str, list[dict[str, object]]]:
        """Return per-exercise ordered weight history across recorded sessions."""
        history: dict[str, list[dict[str, object]]] = defaultdict(list)
        for record in self.weight_records:
            for exercise_name, weight in record["weights"].items():
                history[exercise_name].append({
                    "idx": record["idx"],
                    "date": record["date"],
                    "weight": weight,
                })
        return dict(history)

    def weight_history_by_dimension(self, dimension: str) -> dict[str, list[dict[str, object]]]:
        """Return per-dimension aggregated weight history across sessions.

        Aggregates multiple exercises in the same dimension within one session via mean weight.
        Supported dimensions: movement_pattern, primary_muscle, equipment_type,
        exercise_cluster, exercise_family.
        """
        if dimension == "exercise":
            return self.weight_history_by_exercise()

        history: dict[str, list[dict[str, object]]] = defaultdict(list)
        for record in self.weight_records:
            exercise_dimensions = record.get("exercise_dimensions", {})
            bucketed_weights: dict[str, list[float]] = defaultdict(list)
            for exercise_name, weight in record["weights"].items():
                metadata = exercise_dimensions.get(exercise_name, {})
                dimension_key = metadata.get(dimension)
                if not dimension_key:
                    continue
                bucketed_weights[dimension_key].append(float(weight))

            for dimension_key, weights in bucketed_weights.items():
                history[dimension_key].append({
                    "idx": record["idx"],
                    "date": record["date"],
                    "weight": sum(weights) / len(weights),
                })

        return dict(history)

    def _transition_counts(
        self,
        weights: list[float],
        *,
        hold_tolerance_kg: float,
    ) -> dict[str, float]:
        increases = 0
        holds = 0
        decreases = 0
        for prev, current in zip(weights, weights[1:]):
            delta = current - prev
            if abs(delta) <= hold_tolerance_kg:
                holds += 1
            elif delta > 0:
                increases += 1
            else:
                decreases += 1
        total_transitions = increases + holds + decreases
        return {
            "increases": increases,
            "holds": holds,
            "decreases": decreases,
            "total_transitions": total_transitions,
            "decrease_ratio": decreases / total_transitions if total_transitions else 0.0,
        }

    def _dimension_exercise_histories(
        self,
        dimension: str,
    ) -> dict[str, dict[str, list[dict[str, object]]]]:
        """Return histories grouped as dimension -> exercise -> entries.

        Dimension health should aggregate exercise-level trajectories, not raw kg means
        across unrelated exercises. This avoids false degradation signals when a
        dimension mixes weighted and bodyweight movements.
        """
        grouped: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(dict)
        exercise_history = self.weight_history_by_exercise()
        exercise_to_dimension: dict[str, str] = {}

        for record in self.weight_records:
            exercise_dimensions = record.get("exercise_dimensions", {})
            for exercise_name, metadata in exercise_dimensions.items():
                dimension_key = metadata.get(dimension)
                if dimension_key:
                    exercise_to_dimension[exercise_name] = dimension_key

        for exercise_name, entries in exercise_history.items():
            dimension_key = exercise_to_dimension.get(exercise_name)
            if dimension_key:
                grouped[dimension_key][exercise_name] = entries

        return dict(grouped)

    def _direction_summary_for_history(
        self,
        history: dict[str, list[dict[str, object]]],
        hold_tolerance_kg: float = 0.25,
    ) -> dict[str, float]:
        increases = 0
        holds = 0
        decreases = 0
        tracked_entities = 0

        for entries in history.values():
            weights = [float(entry["weight"]) for entry in entries]
            if len(weights) < 2 or max(weights) <= hold_tolerance_kg:
                continue
            tracked_entities += 1
            for prev, current in zip(weights, weights[1:]):
                delta = current - prev
                if abs(delta) <= hold_tolerance_kg:
                    holds += 1
                elif delta > 0:
                    increases += 1
                else:
                    decreases += 1

        total_transitions = increases + holds + decreases
        decrease_ratio = decreases / total_transitions if total_transitions else 0.0
        return {
            "tracked_entities": tracked_entities,
            "increases": increases,
            "holds": holds,
            "decreases": decreases,
            "total_transitions": total_transitions,
            "decrease_ratio": decrease_ratio,
        }

    def load_direction_summary(self, hold_tolerance_kg: float = 0.25) -> dict[str, float]:
        """Summarize increase/hold/decrease transitions across weighted exercises."""
        summary = self._direction_summary_for_history(
            self.weight_history_by_exercise(),
            hold_tolerance_kg=hold_tolerance_kg,
        )
        summary["weighted_exercises"] = summary["tracked_entities"]
        return summary

    def dimension_load_direction_summary(
        self,
        dimension: str,
        hold_tolerance_kg: float = 0.25,
    ) -> dict[str, float]:
        """Summarize increase/hold/decrease transitions for a non-exercise dimension."""
        grouped_history = self._dimension_exercise_histories(dimension)
        tracked_dimensions = 0
        increases = 0
        holds = 0
        decreases = 0

        for exercise_histories in grouped_history.values():
            dimension_has_signal = False
            for entries in exercise_histories.values():
                weights = [float(entry["weight"]) for entry in entries]
                if len(weights) < 2 or max(weights) <= hold_tolerance_kg:
                    continue
                dimension_has_signal = True
                counts = self._transition_counts(weights, hold_tolerance_kg=hold_tolerance_kg)
                increases += int(counts["increases"])
                holds += int(counts["holds"])
                decreases += int(counts["decreases"])
            if dimension_has_signal:
                tracked_dimensions += 1

        total_transitions = increases + holds + decreases
        return {
            "tracked_entities": tracked_dimensions,
            "tracked_dimensions": tracked_dimensions,
            "increases": increases,
            "holds": holds,
            "decreases": decreases,
            "total_transitions": total_transitions,
            "decrease_ratio": decreases / total_transitions if total_transitions else 0.0,
        }

    def degradation_flags(
        self,
        *,
        hold_tolerance_kg: float = 0.25,
        min_observations: int = 3,
        moderate_drop_ratio: float = 0.15,
        severe_drop_ratio: float = 0.30,
        decrease_ratio_threshold: float = 0.60,
    ) -> list[dict[str, object]]:
        """Return weighted exercises that show sustained downward load drift."""
        return self.dimension_degradation_flags(
            "exercise",
            hold_tolerance_kg=hold_tolerance_kg,
            min_observations=min_observations,
            moderate_drop_ratio=moderate_drop_ratio,
            severe_drop_ratio=severe_drop_ratio,
            decrease_ratio_threshold=decrease_ratio_threshold,
        )

    def dimension_degradation_flags(
        self,
        dimension: str,
        *,
        hold_tolerance_kg: float = 0.25,
        min_observations: int = 3,
        moderate_drop_ratio: float = 0.15,
        severe_drop_ratio: float = 0.30,
        decrease_ratio_threshold: float = 0.60,
        min_flagged_member_ratio: float = 0.50,
        min_flagged_members: int = 2,
        min_systemic_member_exercises: int = 2,
    ) -> list[dict[str, object]]:
        """Return broad dimension-level entities that show sustained downward load drift.

        Non-exercise dimensions are meant to capture class-level bias, not a single
        degraded movement masquerading as a systemic issue. Singleton buckets remain
        visible at exercise level and are excluded from dimension flags until the
        dimension has enough weighted members to represent a reusable class.
        """
        if dimension == "exercise":
            history = self.weight_history_by_exercise()
            flagged: list[dict[str, object]] = []

            for entity_name, entries in history.items():
                weights = [float(entry["weight"]) for entry in entries]
                if len(weights) < min_observations or max(weights) <= hold_tolerance_kg:
                    continue

                counts = self._transition_counts(weights, hold_tolerance_kg=hold_tolerance_kg)
                first_weight = weights[0]
                last_weight = weights[-1]
                peak_weight = max(weights)
                drop_from_start = (
                    (first_weight - last_weight) / first_weight
                    if first_weight > hold_tolerance_kg
                    else 0.0
                )
                drop_from_peak = (
                    (peak_weight - last_weight) / peak_weight
                    if peak_weight > hold_tolerance_kg
                    else 0.0
                )

                if counts["decrease_ratio"] < decrease_ratio_threshold or drop_from_peak < moderate_drop_ratio:
                    continue

                severity = "high" if (
                    drop_from_peak >= severe_drop_ratio and drop_from_start >= moderate_drop_ratio
                ) else "medium"
                flagged.append({
                    "entity": entity_name,
                    "observations": len(weights),
                    "first_weight": first_weight,
                    "last_weight": last_weight,
                    "peak_weight": peak_weight,
                    "increases": counts["increases"],
                    "holds": counts["holds"],
                    "decreases": counts["decreases"],
                    "decrease_ratio": counts["decrease_ratio"],
                    "drop_from_start": drop_from_start,
                    "drop_from_peak": drop_from_peak,
                    "severity": severity,
                })

            return sorted(
                flagged,
                key=lambda item: (
                    0 if item["severity"] == "high" else 1,
                    -float(item["drop_from_peak"]),
                    -float(item["decrease_ratio"]),
                    str(item["entity"]),
                ),
            )

        flagged: list[dict[str, object]] = []
        grouped_history = self._dimension_exercise_histories(dimension)
        exercise_flags = self.degradation_flags(
            hold_tolerance_kg=hold_tolerance_kg,
            min_observations=min_observations,
            moderate_drop_ratio=moderate_drop_ratio,
            severe_drop_ratio=severe_drop_ratio,
            decrease_ratio_threshold=decrease_ratio_threshold,
        )
        exercise_flag_map = {str(flag["entity"]): flag for flag in exercise_flags}

        for entity_name, exercise_histories in grouped_history.items():
            member_exercises = 0
            increases = 0
            holds = 0
            decreases = 0
            flagged_members: list[dict[str, object]] = []

            for exercise_name, entries in exercise_histories.items():
                weights = [float(entry["weight"]) for entry in entries]
                if len(weights) < min_observations or max(weights) <= hold_tolerance_kg:
                    continue
                member_exercises += 1
                counts = self._transition_counts(weights, hold_tolerance_kg=hold_tolerance_kg)
                increases += int(counts["increases"])
                holds += int(counts["holds"])
                decreases += int(counts["decreases"])
                if exercise_name in exercise_flag_map:
                    flagged_members.append(exercise_flag_map[exercise_name])

            total_transitions = increases + holds + decreases
            if member_exercises == 0 or total_transitions == 0:
                continue
            if member_exercises < min_systemic_member_exercises:
                continue

            decrease_ratio = decreases / total_transitions
            flagged_member_count = len(flagged_members)
            flagged_member_ratio = flagged_member_count / member_exercises
            systemic_flag = (
                flagged_member_count >= min_flagged_members
                or flagged_member_ratio >= min_flagged_member_ratio
            )

            if not flagged_members or not systemic_flag or decrease_ratio < decrease_ratio_threshold:
                continue

            worst_member = max(
                flagged_members,
                key=lambda item: (
                    0 if item["severity"] == "high" else 1,
                    -float(item["drop_from_peak"]),
                    -float(item["decrease_ratio"]),
                ),
            )
            severity = "high" if any(flag["severity"] == "high" for flag in flagged_members) else "medium"
            flagged.append({
                "entity": entity_name,
                "member_exercises": member_exercises,
                "flagged_member_exercises": flagged_member_count,
                "flagged_member_ratio": flagged_member_ratio,
                "increases": increases,
                "holds": holds,
                "decreases": decreases,
                "decrease_ratio": decrease_ratio,
                "worst_member": worst_member["entity"],
                "worst_drop_from_peak": worst_member["drop_from_peak"],
                "severity": severity,
            })

        return sorted(
            flagged,
            key=lambda item: (
                0 if item["severity"] == "high" else 1,
                -float(item["worst_drop_from_peak"]),
                -float(item["decrease_ratio"]),
                str(item["entity"]),
            ),
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_session_dates(
    total_sessions: int,
    sessions_per_week: int,
    base_date: date,
) -> list[date]:
    """Generate evenly-spaced session dates at training frequency."""
    days_gap = max(1, 7 // max(1, sessions_per_week))
    dates: list[date] = []
    current = base_date
    for _ in range(total_sessions):
        dates.append(current)
        current += timedelta(days=days_gap)
    return dates


def _derive_exercise_cluster(exercise_row: "Exercise") -> str:
    """Map an exercise to a reusable logic cluster for system-level health checks."""
    movement_pattern = (
        exercise_row.movement_pattern.name
        if exercise_row.movement_pattern is not None
        else "unknown"
    )
    equipment_type = exercise_row.equipment_type.value
    is_compound = bool(exercise_row.is_compound)

    if movement_pattern == "carry":
        return "weighted_carry" if equipment_type != "bodyweight" else "bodyweight_carry"

    if equipment_type == "bodyweight":
        if movement_pattern in {"horizontal_push", "vertical_push"}:
            return "bodyweight_push"
        if movement_pattern in {"horizontal_pull", "vertical_pull"}:
            return "bodyweight_pull"
        if movement_pattern in {"squat", "hinge"}:
            return "bodyweight_lower"
        return "bodyweight_other"

    if is_compound:
        if movement_pattern in {"horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull"}:
            return "weighted_compound_upper"
        if movement_pattern in {"squat", "hinge"}:
            return "weighted_compound_lower"
    else:
        if movement_pattern in {"horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull"}:
            return "weighted_isolation_upper"
        if movement_pattern in {"squat", "hinge"}:
            return "weighted_isolation_lower"

    return "weighted_other" if equipment_type != "bodyweight" else "bodyweight_other"


def _derive_exercise_family(exercise_row: "Exercise") -> str:
    """Map an exercise to a narrower reusable family than the cluster-level grouping."""
    movement_pattern = (
        exercise_row.movement_pattern.name
        if exercise_row.movement_pattern is not None
        else "unknown"
    )
    equipment_type = exercise_row.equipment_type.value
    load_mode = "compound" if bool(exercise_row.is_compound) else "isolation"

    if equipment_type in {"cable", "machine"}:
        equipment_family = "guided"
    elif equipment_type in {"pullup_bar", "dips_bar"}:
        equipment_family = "bodyweight_station"
    elif equipment_type == "resistance_band":
        equipment_family = "band"
    else:
        equipment_family = equipment_type

    if movement_pattern == "carry":
        return f"carry_{equipment_family}"

    return f"{load_mode}_{movement_pattern}_{equipment_family}"


def _plan_to_json(plan: object, *, target_rpe: float) -> str:
    """Serialize WorkoutPlan exercises to JSON for WorkoutSession.planned_exercises."""
    return json.dumps([
        {
            "exercise_id": pe.exercise_id,       # type: ignore[attr-defined]
            "exercise_name": pe.exercise_name,   # type: ignore[attr-defined]
            "sets": pe.sets,                     # type: ignore[attr-defined]
            "target_weight_kg": pe.target_weight_kg,  # type: ignore[attr-defined]
            "target_reps": (pe.rep_range[0] + pe.rep_range[1]) // 2,  # type: ignore[attr-defined]
            "target_rpe": target_rpe,
        }
        for pe in plan.exercises  # type: ignore[attr-defined]
    ])


def _append_dimension_health_section(
    lines: list[str],
    *,
    title: str,
    entity_label: str,
    summary: dict[str, float],
    flags: list[dict[str, object]],
) -> None:
    lines += [
        "",
        f"## {title}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Tracked {entity_label} groups | {int(summary['tracked_dimensions'])} |",
        f"| Increase transitions | {int(summary['increases'])} |",
        f"| Hold transitions | {int(summary['holds'])} |",
        f"| Decrease transitions | {int(summary['decreases'])} |",
        f"| Decrease ratio | {summary['decrease_ratio'] * 100:.1f}% |",
        f"| Flagged {entity_label} groups | {len(flags)} |",
        "",
        f"## {title} Flags",
        "",
    ]

    if flags:
        lines += [
            f"| Severity | {entity_label.title()} | Exercises | Flagged | Flagged % | Inc | Hold | Dec | Decrease ratio | Worst member | Worst drop |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for flag in flags:
            lines.append(
                "| {severity} | {entity} | {member_exercises} | {flagged_member_exercises} | "
                "{flagged_member_ratio:.0%} | {increases} | {holds} | {decreases} | {decrease_ratio:.0%} | "
                "{worst_member} | {worst_drop_from_peak:.0%} |".format(**flag)
            )
    else:
        lines.append(f"No {entity_label} flags detected.")


# ─── Core simulation runner ───────────────────────────────────────────────────

def run_simulation(
    months: int = 6,
    sessions_per_week: int = 3,
    seed: int = 42,
    output_path: Path | None = None,
    model_dir: Path | None = None,
    science: "ScienceConfig | None" = None,
    engine=None,
    scenario_name: str = "ppl_hypertrophy_gym",
    user_profile_overrides: dict | None = None,
) -> SimulationMetrics:
    """Run the full E2E simulation and return collected metrics.

    Args:
        months: Simulation duration in months.
        sessions_per_week: Training sessions per week.
        seed: RNG seed for reproducibility.
        output_path: Where to write simulation-report.md (default: _bmad-output/simulation-report.md).
        model_dir: Directory for ML checkpoints (temp dir if None).
        science: Pre-loaded ScienceConfig (loads from ScienceEvidence.md if None).
        engine: SQLAlchemy engine (creates in-memory SQLite if None).
        scenario_name: Registered scenario profile + mesocycle wave.
        user_profile_overrides: Optional UserProfile field overrides for scenario customization.
    """
    # ── Seed RNGs for determinism ──────────────────────────────────────────────
    import torch  # lazy import to keep module importable without PyTorch installed in CI
    rng = random.Random(seed)
    torch.manual_seed(seed)

    scenario = get_simulation_scenario(scenario_name)

    # ── Science config ─────────────────────────────────────────────────────────
    if science is None:
        science = load_science_config()

    # ── Database ───────────────────────────────────────────────────────────────
    own_engine = engine is None
    if own_engine:
        engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # ── Seed reference data ────────────────────────────────────────────────────
    with Session(engine) as db:
        seed_all(db)
        db.commit()

    # ── Create synthetic athlete profile ───────────────────────────────────────
    with Session(engine) as db:
        profile_kwargs = SyntheticAthlete.create_user_profile_data(
            scenario_name=scenario_name,
            training_days_per_week=sessions_per_week,
            overrides=user_profile_overrides,
        )
        user_profile = UserProfile(**profile_kwargs)
        db.add(user_profile)
        db.commit()
        db.refresh(user_profile)
        user_profile_id: int = user_profile.id

    # ── Setup model and worker ─────────────────────────────────────────────────
    _tmp_dir = None
    if model_dir is None:
        _tmp_dir = tempfile.TemporaryDirectory()
        model_dir = Path(_tmp_dir.name)

    real_model = RPEModel()
    worker = MLWorker(
        engine=engine,
        model=real_model,
        science_config=science,
        model_dir=model_dir,
        fine_tune_threshold=_FINE_TUNE_EVERY,
    )

    # Save initial checkpoint so rollback always has a prior version
    (model_dir / "model_v1.pt").parent.mkdir(parents=True, exist_ok=True)
    real_model.save(model_dir / "model_v1.pt")

    # ── Simulation objects ─────────────────────────────────────────────────────
    athlete = SyntheticAthlete(
        rng,
        scenario=scenario,
        sessions_per_week=sessions_per_week,
    )
    planner = WorkoutPlanner()
    adaptation_engine = AdaptationEngine(rpe_model=None)  # uses DB-mediated predictions
    metrics = SimulationMetrics()
    anomaly_model = _AnomalyInjectModel()

    total_sessions = months * 4 * sessions_per_week  # ~4 weeks/month
    base_date = date(2025, 9, 1)
    session_dates = _build_session_dates(total_sessions, sessions_per_week, base_date)
    completed_session_ids: list[int] = []

    logger.info(
        "Simulation start: {months}mo × {spw}×/week = {total} sessions, seed={seed}",
        months=months, spw=sessions_per_week, total=total_sessions, seed=seed,
    )

    for session_idx, sim_date in enumerate(session_dates):
        signals = athlete.generate_session_signals(session_idx)
        is_anomaly_session = _ANOMALY_START <= session_idx < _ANOMALY_START + _ANOMALY_LENGTH
        session_target_rpe = (
            max(signals.target_rpe, 7.5)
            if is_anomaly_session
            else signals.target_rpe
        )

        # Build simulated workout datetime (19:00 ± offset)
        raw_minute = 0 + signals.workout_minute_offset
        workout_hour = 19 + (raw_minute // 60)
        workout_minute = raw_minute % 60
        workout_hour = max(0, min(23, workout_hour))
        sim_datetime = datetime(
            sim_date.year, sim_date.month, sim_date.day,
            workout_hour, workout_minute, 0,
            tzinfo=timezone.utc,
        )

        # ── Phase 1: Plan and persist session ─────────────────────────────────
        session_id: int | None = None
        recovery_signal = None

        with Session(engine) as db:
            # ReadinessLog for today
            stress_level = athlete.generate_stress_level(signals.sleep_hours)
            readiness_log = ReadinessLog(
                session_date=sim_date.isoformat(),
                sleep_hours=signals.sleep_hours,
                stress_level=stress_level,
                hrv_score=None,
                recovery_score=1.0,
            )
            db.add(readiness_log)
            db.flush()

            recovery_signal = calculate_recovery_signal(readiness_log, science)
            readiness_log.recovery_score = recovery_signal.coefficient

            # Load profile for planner (needs training_split, equipment, etc.)
            user_profile = db.get(UserProfile, user_profile_id)

            # Generate workout plan (real planner with sim date clock seam)
            try:
                plan = planner.generate(
                    user_profile, science, db, recovery_signal, _today=sim_date
                )
            except Exception as exc:
                logger.warning(
                    "Planner error at session {idx}: {exc}", idx=session_idx, exc=exc
                )
                db.rollback()
                continue

            if not plan.exercises:
                logger.debug(
                    "No exercises planned at session {idx} — skipping", idx=session_idx
                )
                db.rollback()
                continue

            # Persist WorkoutSession
            session_row = WorkoutSession(
                session_date=sim_datetime.isoformat(),
                status="active",
                planned_exercises=_plan_to_json(plan, target_rpe=session_target_rpe),
                split_day_label=plan.split_day_label,
                sleep_hours=signals.sleep_hours,
                pre_readiness=signals.pre_readiness,
                is_deload=signals.is_deload,
            )
            db.add(session_row)
            db.flush()
            session_id = session_row.id

            # Enqueue PREDICT only after cold-start window (AC 8: first N sessions = core)
            if session_idx >= _COLD_START_SESSIONS:
                enqueue_predict(session_id, db_session=db)
            db.commit()

        if session_id is None:
            continue

        # ── Phase 2: ML PREDICT job (skipped during cold-start) ───────────────
        is_cold_start = session_idx < _COLD_START_SESSIONS
        if not is_cold_start:
            # Inject anomaly model for fault-injection window (AC 8)
            if is_anomaly_session:
                worker.model = anomaly_model
                metrics.record_anomaly_event(
                    session_idx, sim_date,
                    "fault_injection",
                    f"session_idx={session_idx}: anomaly model injected (RPE=1.0)",
                )

            worker.simulation_clock = sim_datetime
            worker.poll_once()

            # Restore real model after anomaly window
            if is_anomaly_session:
                worker.model = real_model

        # ── Phase 3: Adapt, create sets, complete session ─────────────────────
        source_labels: list[str] = []
        anomaly_flags: list[bool] = []
        exercise_weights: dict[str, float] = {}
        exercise_names: list[str] = []
        exercise_dimensions: dict[str, dict[str, str]] = {}

        with Session(engine) as db:
            from gym_coach_brain.data.models import Exercise

            session_row = db.get(WorkoutSession, session_id)
            user_profile = db.get(UserProfile, user_profile_id)

            # Read RPEPredictions for source_label tracking and MAE computation
            predictions = list(
                db.execute(
                    select(RPEPrediction).where(RPEPrediction.session_id == session_id)
                ).scalars().all()
            )
            pred_by_exercise: dict[int, RPEPrediction] = {
                p.exercise_id: p for p in predictions
            }

            # Record anomaly prediction events
            for pred in predictions:
                if pred.anomaly_flag:
                    metrics.record_anomaly_event(
                        session_idx, sim_date,
                        "anomaly_prediction",
                        f"exercise_id={pred.exercise_id} "
                        f"delta={pred.ml_adjustment_kg:.2f}kg "
                        f"source={pred.source_label}",
                    )

            # Adapt plan using DB predictions
            try:
                adaptation = adaptation_engine.adapt(
                    session_row, user_profile, recovery_signal, science, db
                )
            except Exception as exc:
                logger.warning(
                    "Adaptation error at session {idx}: {exc}", idx=session_idx, exc=exc
                )
                db.rollback()
                continue

            # Create WorkoutSet rows with synthetic actual RPE (AC 2, 5)
            for adapted_ex in adaptation.exercises:
                exercise_weights[adapted_ex.exercise_name] = adapted_ex.target_weight_kg
                exercise_names.append(adapted_ex.exercise_name)
                exercise_row = db.get(Exercise, adapted_ex.exercise_id)
                if exercise_row is not None:
                    exercise_dimensions[adapted_ex.exercise_name] = {
                        "movement_pattern": (
                            exercise_row.movement_pattern.name
                            if exercise_row.movement_pattern is not None
                            else "unknown"
                        ),
                        "primary_muscle": (
                            exercise_row.primary_muscle.name
                            if exercise_row.primary_muscle is not None
                            else "unknown"
                        ),
                        "equipment_type": exercise_row.equipment_type.value,
                        "exercise_cluster": _derive_exercise_cluster(exercise_row),
                        "exercise_family": _derive_exercise_family(exercise_row),
                    }

                # Source label from DB prediction (authoritative after adaptation update)
                pred = pred_by_exercise.get(adapted_ex.exercise_id)
                label = pred.source_label if pred and pred.source_label else "[ядро]"
                source_labels.append(label)
                anomaly_flags.append(bool(pred.anomaly_flag) if pred else False)

                # Generate synthetic actual RPE outcomes for each set
                target_rpe = session_target_rpe
                for set_num in range(1, adapted_ex.sets + 1):
                    actual_rpe = athlete.generate_set_rpe(target_rpe, session_idx)
                    actual_rir = max(0, min(4, round(10.0 - actual_rpe)))
                    db.add(WorkoutSet(
                        session_id=session_id,
                        exercise_id=adapted_ex.exercise_id,
                        set_number=set_num,
                        weight_kg=adapted_ex.target_weight_kg,
                        reps=adapted_ex.target_reps,
                        rpe=actual_rpe,
                        rir=actual_rir,
                    ))
                    # Record RPE error vs model prediction for MAE tracking
                    pred_rpe = pred.predicted_rpe if pred else None
                    metrics.record_rpe(session_idx, pred_rpe, actual_rpe)

            # Mark session completed
            session_row.status = "completed"
            session_row.post_feeling = signals.post_feeling
            session_row.is_deload = signals.is_deload
            db.commit()

        completed_session_ids.append(session_id)
        metrics.record_session(
            session_idx,
            sim_date,
            source_labels,
            exercise_weights,
            plan.split_day_label,
            session_target_rpe,
            exercise_names,
            anomaly_flags,
            exercise_dimensions,
        )

        logger.debug(
            "Session {idx} ({date}) complete: {n_ex} exercises, split={split}",
            idx=session_idx,
            date=sim_date.isoformat(),
            n_ex=len(exercise_weights),
            split=plan.split_day_label if "plan" in dir() else "?",
        )

        # ── Fine-tune every N sessions (AC 5) ─────────────────────────────────
        if (session_idx + 1) % _FINE_TUNE_EVERY == 0:
            eligible_ids = completed_session_ids[-_FINE_TUNE_EVERY:]
            try:
                enqueue_fine_tune(eligible_ids, engine=engine)
                worker.simulation_clock = sim_datetime
                worker.poll_once()
                logger.info(
                    "Fine-tune dispatched after session {idx} with {n} eligible sessions",
                    idx=session_idx, n=len(eligible_ids),
                )
            except (ValueError, Exception) as exc:
                logger.warning(
                    "Fine-tune skipped at session {idx}: {exc}", idx=session_idx, exc=exc
                )

    # ── Write report ───────────────────────────────────────────────────────────
    if output_path is None:
        output_path = Path("_bmad-output/simulation-report.md")
    _write_report(metrics, output_path, months, sessions_per_week, seed, scenario_name)

    if _tmp_dir is not None:
        _tmp_dir.cleanup()

    logger.info(
        "Simulation complete: {n} sessions recorded, report → {path}",
        n=len(metrics.session_records), path=output_path,
    )
    return metrics


# ─── Report generator ─────────────────────────────────────────────────────────

def _write_report(
    metrics: SimulationMetrics,
    output_path: Path,
    months: int,
    sessions_per_week: int,
    seed: int,
    scenario_name: str,
) -> None:
    """Write markdown simulation report to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_sessions = len(metrics.session_records)
    total_exercises = sum(r["total"] for r in metrics.session_records)
    total_ai = sum(r["ai"] for r in metrics.session_records)
    total_anomaly = sum(r["anomaly"] for r in metrics.session_records)
    total_core = sum(r["core"] for r in metrics.session_records)
    split_counts: dict[str, int] = defaultdict(int)
    target_rpe_counts: dict[str, int] = defaultdict(int)
    exercise_coverage: dict[str, int] = defaultdict(int)

    for record in metrics.session_records:
        split_counts[str(record["split_label"])] += 1
        target_rpe_counts[f'{record["target_rpe"]:.1f}'] += 1
        for exercise_name in record["exercise_names"]:
            exercise_coverage[exercise_name] += 1

    def pct(n: int) -> str:
        return f"{n / max(1, total_exercises) * 100:.1f}%"

    mae_early = metrics.mae_for_window(0, 10)
    mae_late = metrics.mae_for_window(50, total_sessions)
    load_summary = metrics.load_direction_summary()
    degradation_flags = metrics.degradation_flags()
    pattern_summary = metrics.dimension_load_direction_summary("movement_pattern")
    pattern_flags = metrics.dimension_degradation_flags("movement_pattern")
    muscle_summary = metrics.dimension_load_direction_summary("primary_muscle")
    muscle_flags = metrics.dimension_degradation_flags("primary_muscle")
    equipment_summary = metrics.dimension_load_direction_summary("equipment_type")
    equipment_flags = metrics.dimension_degradation_flags("equipment_type")
    cluster_summary = metrics.dimension_load_direction_summary("exercise_cluster")
    cluster_flags = metrics.dimension_degradation_flags("exercise_cluster")
    family_summary = metrics.dimension_load_direction_summary("exercise_family")
    family_flags = metrics.dimension_degradation_flags("exercise_family")

    lines: list[str] = [
        "# OpenGym Simulation Report",
        "",
        f"**Parameters:** {months} months, {sessions_per_week}×/week, seed={seed}",
        f"**Scenario:** {scenario_name}",
        f"**Total sessions simulated:** {total_sessions}",
        f"**Total exercise decisions:** {total_exercises}",
        "",
        "## Source Label Distribution",
        "",
        "| Category | Decisions | Percentage |",
        "|---|---|---|",
        f"| AI (ML correction applied) | {total_ai} | {pct(total_ai)} |",
        f"| Anomaly (ML blocked) | {total_anomaly} | {pct(total_anomaly)} |",
        f"| Core (deterministic fallback) | {total_core} | {pct(total_core)} |",
        "",
        "## RPE Model MAE Trend",
        "",
        "| Window | MAE |",
        "|---|---|",
    ]

    window = 10
    for start in range(0, total_sessions, window):
        end = min(start + window, total_sessions)
        mae = metrics.mae_for_window(start, end)
        lines.append(f"| Sessions {start + 1}–{end} | {f'{mae:.3f}' if mae is not None else 'N/A'} |")

    lines += [
        "",
        f"**MAE sessions 1–10:** {f'{mae_early:.3f}' if mae_early is not None else 'N/A'}",
        f"**MAE sessions 51+:** {f'{mae_late:.3f}' if mae_late is not None else 'N/A'}",
        "",
        "## Split Rotation Coverage",
        "",
        "| Split | Sessions |",
        "|---|---|",
    ]

    for split_label, count in sorted(split_counts.items()):
        lines.append(f"| {split_label} | {count} |")

    lines += [
        "",
        "## Intensity Wave Coverage",
        "",
        "| Target RPE | Sessions |",
        "|---|---|",
    ]

    for target_rpe, count in sorted(target_rpe_counts.items()):
        lines.append(f"| {target_rpe} | {count} |")

    lines += [
        "",
        "## Exercise Coverage",
        "",
        "| Exercise | Sessions Present |",
        "|---|---|",
    ]

    for exercise_name, count in sorted(exercise_coverage.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {exercise_name} | {count} |")

    lines += [
        "",
        "## Simulation Health",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Weighted exercises tracked | {int(load_summary['weighted_exercises'])} |",
        f"| Increase transitions | {int(load_summary['increases'])} |",
        f"| Hold transitions | {int(load_summary['holds'])} |",
        f"| Decrease transitions | {int(load_summary['decreases'])} |",
        f"| Decrease ratio | {load_summary['decrease_ratio'] * 100:.1f}% |",
        f"| Exercises flagged for degradation | {len(degradation_flags)} |",
        "",
        "## Degradation Flags",
        "",
    ]

    if degradation_flags:
        lines += [
            "| Severity | Exercise | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for flag in degradation_flags:
            lines.append(
                "| {severity} | {entity} | {observations} | {increases} | {holds} | "
                "{decreases} | {first_weight:.1f} | {last_weight:.1f} | "
                "{peak_weight:.1f} | {drop_from_peak:.0%} |".format(**flag)
            )
    else:
        lines.append("No weighted degradation flags detected.")

    _append_dimension_health_section(
        lines,
        title="Movement Pattern Health",
        entity_label="movement pattern",
        summary=pattern_summary,
        flags=pattern_flags,
    )
    _append_dimension_health_section(
        lines,
        title="Primary Muscle Health",
        entity_label="primary muscle",
        summary=muscle_summary,
        flags=muscle_flags,
    )
    _append_dimension_health_section(
        lines,
        title="Equipment Type Health",
        entity_label="equipment type",
        summary=equipment_summary,
        flags=equipment_flags,
    )
    _append_dimension_health_section(
        lines,
        title="Exercise Cluster Health",
        entity_label="exercise cluster",
        summary=cluster_summary,
        flags=cluster_flags,
    )
    _append_dimension_health_section(
        lines,
        title="Exercise Family Health",
        entity_label="exercise family",
        summary=family_summary,
        flags=family_flags,
    )

    lines += [
        "",
        "## Weight Progression (Sample Exercises)",
        "",
    ]

    # Collect up to 6 exercise names seen across sessions for a broader sample.
    seen_exercises: list[str] = []
    for wr in metrics.weight_records:
        for name in wr["weights"]:
            if name not in seen_exercises:
                seen_exercises.append(name)
        if len(seen_exercises) >= 6:
            break

    for ex_name in seen_exercises[:6]:
        lines += [f"### {ex_name}", "", "| Session | Date | Weight (kg) |", "|---|---|---|"]
        for wr in metrics.weight_records:
            if ex_name in wr["weights"]:
                lines.append(
                    f"| {wr['idx'] + 1} | {wr['date']} | {wr['weights'][ex_name]:.1f} |"
                )
        lines.append("")

    lines += ["## Anomaly and Rollback Events", ""]
    if metrics.anomaly_events:
        lines += ["| Session | Date | Type | Details |", "|---|---|---|---|"]
        for ev in metrics.anomaly_events:
            lines.append(
                f"| {ev['idx'] + 1} | {ev['date']} | {ev['type']} | {ev['details']} |"
            )
    else:
        lines.append("No anomaly events recorded.")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─── CLI entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    """CLI entrypoint: parse arguments and run simulation."""
    parser = argparse.ArgumentParser(
        description="Run E2E simulation of synthetic athlete training history",
        add_help=False,
    )
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--sessions-per-week", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", type=str, default="ppl_hypertrophy_gym")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS)
    args = parser.parse_args()

    run_simulation(
        months=args.months,
        sessions_per_week=args.sessions_per_week,
        seed=args.seed,
        output_path=Path(args.output) if args.output else None,
        scenario_name=args.scenario,
    )


if __name__ == "__main__":
    main()

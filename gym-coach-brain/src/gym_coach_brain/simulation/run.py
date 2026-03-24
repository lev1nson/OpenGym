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
from gym_coach_brain.simulation.synthetic_athlete import SyntheticAthlete

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
        anomaly_flags: list[bool] | None = None,
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
        })
        self.weight_records.append({
            "idx": idx,
            "date": sim_date.isoformat(),
            "weights": dict(weights),
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


def _plan_to_json(plan: object) -> str:
    """Serialize WorkoutPlan exercises to JSON for WorkoutSession.planned_exercises."""
    return json.dumps([
        {
            "exercise_id": pe.exercise_id,       # type: ignore[attr-defined]
            "exercise_name": pe.exercise_name,   # type: ignore[attr-defined]
            "sets": pe.sets,                     # type: ignore[attr-defined]
            "target_weight_kg": pe.target_weight_kg,  # type: ignore[attr-defined]
            "target_reps": (pe.rep_range[0] + pe.rep_range[1]) // 2,  # type: ignore[attr-defined]
        }
        for pe in plan.exercises  # type: ignore[attr-defined]
    ])


# ─── Core simulation runner ───────────────────────────────────────────────────

def run_simulation(
    months: int = 6,
    sessions_per_week: int = 3,
    seed: int = 42,
    output_path: Path | None = None,
    model_dir: Path | None = None,
    science: "ScienceConfig | None" = None,
    engine=None,
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
    """
    # ── Seed RNGs for determinism ──────────────────────────────────────────────
    import torch  # lazy import to keep module importable without PyTorch installed in CI
    rng = random.Random(seed)
    torch.manual_seed(seed)

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
        profile_kwargs = SyntheticAthlete.create_user_profile_data()
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
    athlete = SyntheticAthlete(rng)
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
                recovery_score=max(0.0, min(1.0, signals.sleep_hours / 8.0)),
            )
            db.add(readiness_log)
            db.flush()

            recovery_signal = calculate_recovery_signal(readiness_log, science)

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
                planned_exercises=_plan_to_json(plan),
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
            is_anomaly_session = _ANOMALY_START <= session_idx < _ANOMALY_START + _ANOMALY_LENGTH
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

        with Session(engine) as db:
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

                # Source label from DB prediction (authoritative after adaptation update)
                pred = pred_by_exercise.get(adapted_ex.exercise_id)
                label = pred.source_label if pred and pred.source_label else "[ядро]"
                source_labels.append(label)
                anomaly_flags.append(bool(pred.anomaly_flag) if pred else False)

                # Generate synthetic actual RPE outcomes for each set
                target_rpe = 7.5  # nominal training intensity target
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
        metrics.record_session(session_idx, sim_date, source_labels, exercise_weights, anomaly_flags)

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
    _write_report(metrics, output_path, months, sessions_per_week, seed)

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
) -> None:
    """Write markdown simulation report to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_sessions = len(metrics.session_records)
    total_exercises = sum(r["total"] for r in metrics.session_records)
    total_ai = sum(r["ai"] for r in metrics.session_records)
    total_anomaly = sum(r["anomaly"] for r in metrics.session_records)
    total_core = sum(r["core"] for r in metrics.session_records)

    def pct(n: int) -> str:
        return f"{n / max(1, total_exercises) * 100:.1f}%"

    mae_early = metrics.mae_for_window(0, 10)
    mae_late = metrics.mae_for_window(50, total_sessions)

    lines: list[str] = [
        "# OpenGym Simulation Report",
        "",
        f"**Parameters:** {months} months, {sessions_per_week}×/week, seed={seed}",
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
        "## Weight Progression (Sample Exercises)",
        "",
    ]

    # Collect up to 3 exercise names seen across sessions
    seen_exercises: list[str] = []
    for wr in metrics.weight_records:
        for name in wr["weights"]:
            if name not in seen_exercises:
                seen_exercises.append(name)
        if len(seen_exercises) >= 3:
            break

    for ex_name in seen_exercises[:3]:
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
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS)
    args = parser.parse_args()

    run_simulation(
        months=args.months,
        sessions_per_week=args.sessions_per_week,
        seed=args.seed,
        output_path=Path(args.output) if args.output else None,
    )


if __name__ == "__main__":
    main()

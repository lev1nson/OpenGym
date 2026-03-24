"""
MLWorker — polling daemon for ML job queue processing.

Process isolation contract:
    API  → writes ml_jobs (PREDICT / FINE_TUNE)
    Worker → reads ml_jobs, writes rpe_predictions
    Adaptation → reads rpe_predictions

No shared memory with the API process. All IPC is DB-mediated.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger
from sqlalchemy import select

from gym_coach_brain.data.models import MLJob, RPEPrediction, WorkoutSession, WorkoutSet
from gym_coach_brain.data.queue import get_pending_jobs, update_job_status
from gym_coach_brain.data.session import get_session
from gym_coach_brain.data.features import build_feature_vector, estimate_muscle_group_fatigue
from gym_coach_brain.ml.constants import (
    DEFAULT_FINE_TUNE_THRESHOLD,
    MODEL_DIR,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session as OrmSession

    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.ml.interface import RPEModelProtocol


class ModelVersionNotFoundError(FileNotFoundError):
    """Raised when a requested model checkpoint version does not exist on disk."""


def _discover_canonical_versions(model_dir: Path) -> list[int]:
    """Return sorted list of canonical version numbers from model_vN.pt files.

    Ignores .backup.pt and .anomaly.pt suffix variants.
    """
    versions: list[int] = []
    for path in model_dir.glob("model_v*.pt"):
        match = re.fullmatch(r"model_v(\d+)\.pt", path.name)
        if match:
            versions.append(int(match.group(1)))
    return sorted(versions)


def _safe_copy(src: Path, dst: Path) -> None:
    """Copy src to dst atomically on the same filesystem via temp file + os.replace()."""
    tmp = dst.with_suffix(".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


class MLWorker:
    """Polling daemon for the ML job queue.

    Designed for process isolation: run as a separate process from the API.
    Communicates with the API exclusively via the database (ml_jobs table for
    input, rpe_predictions table for output).

    Dependency injection enables testing without real PyTorch:
        engine      — SQLAlchemy Engine (in-memory SQLite for tests)
        model       — any RPEModelProtocol implementation (mock in tests)
        science_config — ScienceConfig (use mock_science_config fixture in tests)

    Usage:
        worker = MLWorker(engine=engine, model=model, science_config=science)
        worker.poll_once()   # single cycle (tests)
        worker.run()         # infinite loop (production)
    """

    def __init__(
        self,
        engine: "Engine",
        model: "RPEModelProtocol",
        science_config: "ScienceConfig",
        *,
        poll_interval: int = 60,
        fine_tune_threshold: int | None = None,
        model_dir: Path | None = None,
        initial_model_version: int = 1,
        simulation_clock: "datetime | None" = None,
    ) -> None:
        self._engine = engine
        self._model = model
        self._science = science_config
        self._poll_interval = poll_interval
        self._fine_tune_threshold = (
            fine_tune_threshold
            if fine_tune_threshold is not None
            else DEFAULT_FINE_TUNE_THRESHOLD
        )
        self._model_dir = Path(model_dir) if model_dir is not None else Path(MODEL_DIR)

        # In-memory state for current process run
        self.consecutive_anomalies: int = 0
        self._current_model_version: int = initial_model_version
        self._reported_processing_incidents: set[int] = set()
        # Simulation clock seam: when set, used as "now" in feature building
        # instead of datetime.now(). Set per-session in simulation context.
        self.simulation_clock: "datetime | None" = simulation_clock

    # ─── Model access (public for simulation fault injection) ─────────────────

    @property
    def model(self) -> "RPEModelProtocol":
        """Active model instance. Writable for simulation fault injection."""
        return self._model

    @model.setter
    def model(self, value: "RPEModelProtocol") -> None:
        self._model = value

    # ─── Versioning surface ───────────────────────────────────────────────────

    def load_model_version(self, version: int) -> None:
        """Load model_v{version}.pt into the model and update internal version tracking.

        Raises ModelVersionNotFoundError if the canonical file does not exist.
        Structured log context: model_version, checkpoint_path.
        """
        path = self._model_dir / f"model_v{version}.pt"
        if not path.exists():
            raise ModelVersionNotFoundError(
                f"model_v{version}.pt not found in {self._model_dir}"
            )
        self._model.load(path)
        self._current_model_version = version
        logger.bind(
            model_version=f"model_v{version}",
            checkpoint_path=str(path),
        ).info("Loaded model checkpoint model_v{version}.pt", version=version)

    # ─── Public API ───────────────────────────────────────────────────────────

    def poll_once(self) -> None:
        """Process one batch of pending jobs. Core polling unit; safe to call in tests.

        Fetches all pending jobs ordered PREDICT-first (priority enforced by
        data.queue.get_pending_jobs), then processes each sequentially.
        """
        self._log_processing_incidents()
        jobs = get_pending_jobs(self._engine)
        for job in jobs:
            # Extract scalar attributes now — objects become detached after session close
            self._process_job(
                job_id=job.id,
                job_type=job.job_type,
                session_id=job.session_id,
                session_ids=job.session_ids,
            )

    def run(self, sleep_fn: Callable[[float], None] | None = None) -> None:
        """Infinite polling loop for production use.

        Args:
            sleep_fn: Injectable sleep for tests (avoids real time.sleep).
        """
        if sleep_fn is None:
            sleep_fn = time.sleep

        logger.info(
            "MLWorker starting: poll_interval={interval}s, "
            "fine_tune_threshold={threshold}, model_dir={model_dir}",
            interval=self._poll_interval,
            threshold=self._fine_tune_threshold,
            model_dir=self._model_dir,
        )
        while True:
            try:
                self.poll_once()
            except Exception as exc:
                logger.error("Unexpected error in polling loop: {exc}", exc=exc)
            sleep_fn(self._poll_interval)

    # ─── Job Dispatch ─────────────────────────────────────────────────────────

    def _process_job(
        self,
        job_id: int,
        job_type: str,
        session_id: int | None,
        session_ids: str,
    ) -> None:
        """Dispatch one job through the pending → processing → done|failed lifecycle."""
        bound = logger.bind(
            job_id=job_id,
            job_type=job_type,
            session_ids=session_ids,
            status="processing",
        )

        try:
            update_job_status(job_id, "processing", self._engine)
        except Exception as exc:
            bound.error("Failed to mark job as processing; skipping: {exc}", exc=exc)
            return

        try:
            with get_session(self._engine) as db:
                if job_type == "PREDICT":
                    self._execute_predict(job_id, session_id, session_ids, db)
                elif job_type == "FINE_TUNE":
                    self._execute_fine_tune(job_id, session_ids, db)
                else:
                    raise ValueError(f"Unknown job_type: {job_type!r}")
            update_job_status(job_id, "done", self._engine)
            bound.bind(status="done").info("Job completed")

        except Exception as exc:
            bound.bind(status="failed").error("Job failed: {exc}", exc=exc)
            try:
                update_job_status(job_id, "failed", self._engine)
            except Exception:
                pass  # Log already captured above; daemon must not crash

    def _log_processing_incidents(self) -> None:
        """Report stuck processing jobs as operational incidents without mutating them."""
        with get_session(self._engine) as db:
            processing_jobs = list(
                db.execute(
                    select(MLJob).where(MLJob.status == "processing")
                ).scalars().all()
            )

        for job in processing_jobs:
            if job.id in self._reported_processing_incidents:
                continue
            logger.bind(
                job_id=job.id,
                job_type=job.job_type,
                session_ids=job.session_ids,
                status=job.status,
            ).error(
                "Operational incident: job remains in processing state; "
                "leaving row unchanged for manual investigation"
            )
            self._reported_processing_incidents.add(job.id)

    # ─── PREDICT Execution ────────────────────────────────────────────────────

    def _execute_predict(
        self,
        job_id: int,
        session_id: int | None,
        session_ids: str,
        db: "OrmSession",
    ) -> None:
        """Build features, call model.predict(), persist RPEPrediction rows."""
        if session_id is None:
            raise ValueError(f"PREDICT job {job_id} has no session_id")

        workout_session = db.get(WorkoutSession, session_id)
        if workout_session is None:
            raise ValueError(f"WorkoutSession {session_id} not found")

        try:
            planned = json.loads(workout_session.planned_exercises or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Cannot parse planned_exercises for session {session_id}: {exc}"
            ) from exc

        if not planned:
            raise ValueError(f"WorkoutSession {session_id} has no planned exercises")

        model_version_str = f"model_v{self._current_model_version}"
        confidence_threshold = self._science.ml.confidence_threshold
        # Collect (anomaly_flag, exercise_id) tuples for counter update AFTER commit
        written_flags: list[tuple[bool, int]] = []

        for planned_ex in planned:
            try:
                exercise_id = int(planned_ex["exercise_id"])
                weight_kg = float(planned_ex.get("target_weight_kg", 0.0))
                # Story spec: standardize on set_number=1 for planned-exercise predictions
                reps = int(planned_ex.get("target_reps") or 8)
                feature_vector = build_feature_vector(
                    exercise_id=exercise_id,
                    session_id=session_id,
                    set_number=1,
                    weight_kg=weight_kg,
                    reps=reps,
                    session=db,
                    _now=self.simulation_clock,
                )
                features = vars(feature_vector).copy()
                features["muscle_group_fatigue_estimate"] = (
                    estimate_muscle_group_fatigue(
                        exercise_id=exercise_id,
                        current_session_id=session_id,
                        science=self._science,
                        db_session=db,
                    )
                )

                predicted_rpe, confidence = self._model.predict(features)
                core_weight_kg = weight_kg
                anomaly_flag = False
                ml_weight_kg: float | None = None
                ml_adjustment_kg = 0.0
                source_label = _format_low_confidence_source_label(confidence)

                if confidence >= confidence_threshold:
                    target_rpe = _resolve_target_rpe(planned_ex, self._science)
                    raw_ml_weight_kg = _rpe_to_weight(
                        predicted_rpe=predicted_rpe,
                        target_rpe=target_rpe,
                        core_weight_kg=core_weight_kg,
                        science=self._science,
                    )
                    ml_weight_kg = _rpe_to_weight(
                        predicted_rpe=predicted_rpe,
                        target_rpe=target_rpe,
                        core_weight_kg=core_weight_kg,
                        science=self._science,
                        confidence=confidence,
                    )
                    delta_percent = _compute_delta_percent(core_weight_kg, raw_ml_weight_kg)
                    anomaly_flag = (
                        delta_percent > self._science.ml.max_correction_percent
                    )
                    if anomaly_flag:
                        source_label = _format_anomaly_source_label(
                            delta_percent=delta_percent,
                            max_correction_percent=self._science.ml.max_correction_percent,
                        )
                    else:
                        source_label = _format_ai_source_label(
                            ml_weight_kg=ml_weight_kg,
                            core_weight_kg=core_weight_kg,
                            predicted_rpe=predicted_rpe,
                            confidence=confidence,
                        )
                        ml_adjustment_kg = ml_weight_kg - core_weight_kg

                prediction = RPEPrediction(
                    session_id=session_id,
                    exercise_id=exercise_id,
                    predicted_rpe=float(predicted_rpe),
                    confidence_score=float(confidence),
                    model_version=model_version_str,
                    anomaly_flag=anomaly_flag,
                    source_label=source_label,
                    core_weight_kg=core_weight_kg,
                    ml_weight_kg=ml_weight_kg,
                    ml_adjustment_kg=ml_adjustment_kg,
                )
                db.add(prediction)

                bound = logger.bind(
                    job_id=job_id,
                    job_type="PREDICT",
                    session_ids=session_ids,
                    exercise_id=exercise_id,
                    status="anomaly" if anomaly_flag else "predicted",
                )
                if confidence < confidence_threshold:
                    bound.warning(
                        "Low-confidence prediction: rpe={rpe:.1f}, "
                        "confidence={conf:.2f} < threshold={thresh}",
                        rpe=predicted_rpe,
                        conf=confidence,
                        thresh=confidence_threshold,
                    )
                elif anomaly_flag:
                    bound.error(
                        "Prediction exceeds bounded-correction limit: "
                        "rpe={rpe:.1f}, confidence={conf:.2f}",
                        rpe=predicted_rpe,
                        conf=confidence,
                    )
                else:
                    bound.info(
                        "Prediction written: rpe={rpe:.1f}, confidence={conf:.2f}",
                        rpe=predicted_rpe,
                        conf=confidence,
                    )

                written_flags.append((anomaly_flag, exercise_id))
            except Exception as exc:
                raise ValueError(
                    "Failed to process planned exercise for "
                    f"session {session_id}: {exc}"
                ) from exc

        if not written_flags:
            raise ValueError(
                f"PREDICT job {job_id} produced no persisted predictions"
            )

        # Persist all predictions before any anomaly counter / rollback decision (AC 10)
        db.commit()

        # Update anomaly counter based on persisted prediction state (AC 8, AC 9)
        for anomaly_flag, exercise_id in written_flags:
            self._update_anomaly_counter(
                anomaly_flag=anomaly_flag,
                exercise_id=exercise_id,
                model_version=model_version_str,
                job_id=job_id,
                session_ids=session_ids,
            )

    # ─── FINE_TUNE Execution ──────────────────────────────────────────────────

    def _execute_fine_tune(
        self,
        job_id: int,
        session_ids: str,
        db: "OrmSession",
    ) -> None:
        """Check threshold, build training data, fine-tune model, save checkpoint."""
        try:
            all_session_ids: list[int] = json.loads(session_ids)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid session_ids JSON for FINE_TUNE job {job_id}: {exc}"
            ) from exc

        bound = logger.bind(
            job_id=job_id,
            job_type="FINE_TUNE",
            session_ids=session_ids,
            status="threshold_check",
        )

        # Count eligible sessions: post_feeling IS NOT NULL and is_deload=False (AC 3)
        eligible_ids: list[int] = list(
            db.execute(
                select(WorkoutSession.id).where(
                    WorkoutSession.id.in_(all_session_ids),
                    WorkoutSession.post_feeling.isnot(None),
                    WorkoutSession.is_deload.is_(False),
                )
            ).scalars().all()
        )

        if len(eligible_ids) < self._fine_tune_threshold:
            bound.bind(status="skipped").info(
                "Fine-tune skipped: {count} eligible sessions < threshold={threshold}",
                count=len(eligible_ids),
                threshold=self._fine_tune_threshold,
            )
            return

        training_samples = self._load_training_samples(eligible_ids, db)

        if not training_samples:
            bound.bind(status="skipped").warning(
                "Fine-tune skipped: no usable training samples from {count} eligible sessions",
                count=len(eligible_ids),
            )
            return

        # Discover versions from filesystem — no in-memory counter shortcuts (AC 1)
        versions = _discover_canonical_versions(self._model_dir)

        # Backup current canonical before fine-tuning mutates weights (AC 2)
        if versions:
            cur_version = max(versions)
            cur_path = self._model_dir / f"model_v{cur_version}.pt"
            if cur_path.exists():
                backup_path = self._model_dir / f"model_v{cur_version}.backup.pt"
                _safe_copy(cur_path, backup_path)
                bound.bind(
                    model_version=f"model_v{cur_version}",
                    checkpoint_path=str(backup_path),
                ).info(
                    "Backed up model_v{v}.pt → model_v{v}.backup.pt before fine-tuning",
                    v=cur_version,
                )

        self._model.fine_tune(training_samples)

        # Compute next version from filesystem (AC 1) — no cached "current + 1"
        next_version = (max(versions) if versions else 0) + 1
        save_path = self._model_dir / f"model_v{next_version}.pt"
        self._model.save(save_path)
        self._current_model_version = next_version

        bound.bind(
            status="done",
            model_version=f"model_v{next_version}",
            checkpoint_path=str(save_path),
        ).info(
            "Fine-tune completed: {count} samples, saved model_v{version}.pt",
            count=len(training_samples),
            version=next_version,
        )

    def _load_training_samples(
        self,
        session_ids: list[int],
        db: "OrmSession",
    ) -> list[dict]:
        """Assemble feature dicts with ``target_rpe`` for fine-tuning.

        Returns only sets that have a recorded RPE value.
        """
        samples: list[dict] = []
        for session_id in session_ids:
            sets = list(
                db.execute(
                    select(WorkoutSet).where(
                        WorkoutSet.session_id == session_id,
                        WorkoutSet.rpe.isnot(None),
                    )
                ).scalars().all()
            )
            for ws in sets:
                try:
                    fv = build_feature_vector(
                        exercise_id=ws.exercise_id,
                        session_id=session_id,
                        set_number=ws.set_number,
                        weight_kg=ws.weight_kg,
                        reps=ws.reps,
                        session=db,
                        _now=self.simulation_clock,
                    )
                    features = vars(fv).copy()
                    features["muscle_group_fatigue_estimate"] = estimate_muscle_group_fatigue(
                        exercise_id=ws.exercise_id,
                        current_session_id=session_id,
                        science=self._science,
                        db_session=db,
                    )
                    features["target_rpe"] = float(ws.rpe)
                    samples.append(features)
                except Exception as exc:
                    logger.warning(
                        "Skipping set {set_id} for training (session {sid}): {exc}",
                        set_id=ws.id,
                        sid=session_id,
                        exc=exc,
                    )
        return samples

    # ─── Anomaly Counter and Rollback ─────────────────────────────────────────

    def _update_anomaly_counter(
        self,
        anomaly_flag: bool,
        exercise_id: int,
        model_version: str,
        job_id: int,
        session_ids: str,
    ) -> None:
        """Update the consecutive anomaly counter and trigger rollback at threshold."""
        if anomaly_flag:
            self.consecutive_anomalies += 1
            if self.consecutive_anomalies >= self._science.ml.anomaly_rollback_threshold:
                logger.bind(
                    job_id=job_id,
                    job_type="PREDICT",
                    session_ids=session_ids,
                    model_version=model_version,
                    consecutive_anomalies=self.consecutive_anomalies,
                    exercise_id=exercise_id,
                    status="rollback_trigger",
                ).error(
                    "Anomaly threshold reached ({n}); triggering model rollback "
                    "from {version} for exercise_id={ex}",
                    n=self.consecutive_anomalies,
                    version=model_version,
                    ex=exercise_id,
                )
                self._try_rollback(exercise_id=exercise_id)
                self.consecutive_anomalies = 0
        else:
            self.consecutive_anomalies = 0

    def _try_rollback(self, exercise_id: int) -> None:
        """Attempt to load the previous model version. Non-blocking on failure.

        On rollback: renames current canonical to .anomaly.pt for post-mortem (AC 8),
        then loads the highest previous model_v{n}.pt via load_model_version() (AC 6).
        Structured log context: model_version, from_version, to_version,
        checkpoint_path, reason.
        """
        versions = _discover_canonical_versions(self._model_dir)
        prior_versions = [v for v in versions if v < self._current_model_version]
        target_version = max(prior_versions) if prior_versions else 0
        bound = logger.bind(
            job_id=0,
            job_type="PREDICT",
            session_ids="[]",
            model_version=f"model_v{self._current_model_version}",
            from_version=f"model_v{self._current_model_version}",
            to_version=f"model_v{target_version}",
            consecutive_anomalies=self.consecutive_anomalies,
            exercise_id=exercise_id,
            reason="anomaly_threshold_exceeded",
        )

        if target_version < 1:
            bound.critical(
                "Rollback requested but no previous model version exists "
                "(current: model_v{current}); continuing on current model",
                current=self._current_model_version,
            )
            return

        # Rename current canonical to .anomaly.pt for post-mortem preservation (AC 8)
        current_canonical = self._model_dir / f"model_v{self._current_model_version}.pt"
        if current_canonical.exists():
            anomaly_path = self._model_dir / f"model_v{self._current_model_version}.anomaly.pt"
            try:
                os.replace(current_canonical, anomaly_path)
                bound.bind(checkpoint_path=str(anomaly_path)).warning(
                    "Renamed model_v{n}.pt → model_v{n}.anomaly.pt for post-mortem",
                    n=self._current_model_version,
                )
            except OSError as exc:
                bound.bind(checkpoint_path=str(current_canonical)).warning(
                    "Could not rename model_v{n}.pt to .anomaly.pt: {exc}",
                    n=self._current_model_version,
                    exc=exc,
                )

        # Load previous version via versioning surface (AC 6)
        try:
            self.load_model_version(target_version)
            bound.bind(
                model_version=f"model_v{target_version}",
                checkpoint_path=str(self._model_dir / f"model_v{target_version}.pt"),
                status="rollback_success",
            ).error(
                "Model rolled back to model_v{version} due to consecutive anomalies",
                version=target_version,
            )
        except (ModelVersionNotFoundError, FileNotFoundError):
            bound.bind(status="rollback_failed").critical(
                "Rollback target model_v{version}.pt not found; "
                "continuing on current model",
                version=target_version,
            )


def _resolve_target_rpe(planned_exercise: dict, science: "ScienceConfig") -> float:
    target_rpe = planned_exercise.get("target_rpe")
    if target_rpe is not None:
        return float(target_rpe)
    return (science.ml.rpe_easy_threshold + science.ml.rpe_hard_threshold) / 2.0


def _rpe_to_weight(
    predicted_rpe: float,
    target_rpe: float,
    core_weight_kg: float,
    science: "ScienceConfig",
    confidence: float | None = None,
) -> float:
    if core_weight_kg <= 0:
        return 0.0
    adjustment_ratio = science.ml.rpe_weight_sensitivity * _effective_rpe_error(
        predicted_rpe=predicted_rpe,
        target_rpe=target_rpe,
        science=science,
    )
    if confidence is not None:
        adjustment_ratio *= _confidence_correction_scale(confidence, science)
    return max(0.0, core_weight_kg * (1.0 - adjustment_ratio))


def _compute_delta_percent(core_weight_kg: float, ml_weight_kg: float) -> float:
    if core_weight_kg <= 0:
        return 0.0
    return abs(ml_weight_kg - core_weight_kg) / core_weight_kg


def _effective_rpe_error(
    predicted_rpe: float,
    target_rpe: float,
    science: "ScienceConfig",
) -> float:
    """Ignore small target misses so worker predictions do not oscillate around steady state."""
    error = predicted_rpe - target_rpe
    deadband = science.ml.rpe_correction_deadband
    if abs(error) <= deadband:
        return 0.0
    return math.copysign(abs(error) - deadband, error)


def _confidence_correction_scale(confidence: float, science: "ScienceConfig") -> float:
    """Scale correction strength smoothly between threshold and full confidence."""
    threshold = science.ml.confidence_threshold
    if confidence <= threshold:
        return 0.0
    if threshold >= 1.0:
        return 1.0
    normalized = min(1.0, max(0.0, (confidence - threshold) / (1.0 - threshold)))
    min_scale = science.ml.min_confidence_correction_scale
    return min_scale + (1.0 - min_scale) * normalized


def _format_ai_source_label(
    ml_weight_kg: float,
    core_weight_kg: float,
    predicted_rpe: float,
    confidence: float,
) -> str:
    adjustment = ml_weight_kg - core_weight_kg
    confidence_percent = round(confidence * 100)
    return (
        f"[AI: {adjustment:+.1f}кг / RPE прогноз: {predicted_rpe:.1f} / "
        f"confidence: {confidence_percent}%]"
    )


def _format_low_confidence_source_label(confidence: float) -> str:
    confidence_percent = round(confidence * 100)
    return f"[ядро: confidence {confidence_percent}% < порога]"


def _format_anomaly_source_label(
    delta_percent: float,
    max_correction_percent: float,
) -> str:
    return (
        f"[AI заблокирован: дельта {round(delta_percent * 100)}% > "
        f"{round(max_correction_percent * 100)}% лимит]"
    )

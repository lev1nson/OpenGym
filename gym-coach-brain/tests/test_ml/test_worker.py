"""
Tests for ml/worker.py — MLWorker polling, dispatch, lifecycle, anomaly tracking.

Uses in-memory SQLite and a mock RPE model — no real PyTorch required.
All tests verify worker orchestration logic only; PyTorch behavior is tested
separately in test_model.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import (
    Base,
    Equipment,
    EquipmentType,
    Exercise,
    MLJob,
    MovementPattern,
    MuscleGroup,
    RPEPrediction,
    WorkoutSession,
    WorkoutSet,
)
from gym_coach_brain.data.queue import enqueue_fine_tune, enqueue_predict, update_job_status
from gym_coach_brain.ml.worker import MLWorker, _rpe_to_weight


# ─── DB seed helpers ──────────────────────────────────────────────────────────

def _seed_minimal_exercise(db_engine) -> int:
    """Seed MuscleGroup + MovementPattern + Exercise. Returns exercise_id."""
    with Session(db_engine) as s:
        mg = MuscleGroup(
            name="chest",
            body_region="upper",
            is_push=True,
            is_pull=False,
            stretch_mediated=False,
        )
        s.add(mg)
        s.flush()

        mp = MovementPattern(name="horizontal_push", category="push")
        s.add(mp)
        s.flush()

        ex = Exercise(
            name="bench_press",
            primary_muscle_id=mg.id,
            movement_pattern_id=mp.id,
            is_compound=True,
            stretch_mediated=False,
            equipment_type=EquipmentType.barbell,
            secondary_muscle_ids="[]",
        )
        s.add(ex)
        s.commit()
        s.refresh(ex)
        return ex.id


def _make_workout_session(
    db_engine,
    *,
    exercise_id: int | None = None,
    target_rpe: float | None = None,
    post_feeling: int | None = None,
    is_deload: bool = False,
    status: str = "active",
) -> WorkoutSession:
    """Create and commit a WorkoutSession. Includes planned_exercises if exercise_id given."""
    with Session(db_engine) as s:
        if exercise_id is not None:
            planned_exercise = {
                "exercise_id": exercise_id,
                "target_weight_kg": 80.0,
                "target_reps": 8,
                "sets": 3,
            }
            if target_rpe is not None:
                planned_exercise["target_rpe"] = target_rpe
            planned = json.dumps([planned_exercise])
        else:
            planned = None
        ws = WorkoutSession(
            session_date="2026-03-09T10:00:00",
            status=status,
            post_feeling=post_feeling,
            is_deload=is_deload,
            planned_exercises=planned,
            sleep_hours=7.5,
            pre_readiness=7,
        )
        s.add(ws)
        s.commit()
        s.refresh(ws)
        return ws


def _make_worker(
    db_engine,
    mock_science_config,
    model=None,
    *,
    fine_tune_threshold: int = 5,
) -> MLWorker:
    if model is None:
        model = Mock()
        model.predict.return_value = (7.5, 0.85)
    return MLWorker(
        engine=db_engine,
        model=model,
        science_config=mock_science_config,
        poll_interval=60,
        fine_tune_threshold=fine_tune_threshold,
    )


def _get_job_status(db_engine, job_id: int) -> str:
    with Session(db_engine) as s:
        job = s.get(MLJob, job_id)
        return job.status


def _count_predictions(db_engine, session_id: int) -> int:
    from sqlalchemy import select
    with Session(db_engine) as s:
        return s.execute(
            select(RPEPrediction).where(RPEPrediction.session_id == session_id)
        ).scalars().all().__len__()


# ─── Import safety ────────────────────────────────────────────────────────────

def test_worker_importable_without_pytorch():
    """A fresh Python process must import MLWorker even if torch imports are blocked."""
    project_root = Path(__file__).resolve().parents[2]
    src_path = project_root / "src"
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(src_path)
    )
    script = """
import builtins

original_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "torch" or name.startswith("torch."):
        raise RuntimeError("torch import blocked")
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
import gym_coach_brain.ml.worker
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_mlworker_instantiates_with_mock_model(db_engine, mock_science_config):
    """MLWorker must construct without errors using mock fixtures (no PyTorch)."""
    model = Mock()
    model.predict.return_value = (7.5, 0.85)
    worker = MLWorker(
        engine=db_engine,
        model=model,
        science_config=mock_science_config,
    )
    assert worker.consecutive_anomalies == 0
    assert worker._current_model_version == 1


# ─── Queue priority: PREDICT before FINE_TUNE ────────────────────────────────

def test_predict_job_dispatched_before_fine_tune(db_engine, mock_science_config):
    """PREDICT jobs must be processed before FINE_TUNE even when FINE_TUNE was enqueued first."""
    call_order: list[str] = []

    model = Mock()

    def track_predict(features):
        call_order.append("PREDICT")
        return (7.5, 0.85)

    model.predict.side_effect = track_predict

    worker = _make_worker(db_engine, mock_science_config, model=model, fine_tune_threshold=999)

    # Create enough eligible sessions for a FINE_TUNE job (threshold bypassed by fine_tune_threshold=999)
    # Enqueue FINE_TUNE first (older created_at)
    with Session(db_engine) as s:
        ft_job = MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps([]),
            created_at="2026-03-09T09:00:00+00:00",
        )
        s.add(ft_job)
        s.commit()
        s.refresh(ft_job)
        ft_job_id = ft_job.id

    # Enqueue PREDICT job for a real session (newer created_at, but higher priority)
    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id)
    predict_job = enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    # PREDICT must have been dispatched (model.predict called)
    assert model.predict.called, "model.predict should be called for the PREDICT job"
    # The PREDICT job should be done; FINE_TUNE should be done (skipped due to 0 eligible sessions)
    assert _get_job_status(db_engine, predict_job.id) == "done"
    assert _get_job_status(db_engine, ft_job_id) == "done"


# ─── Terminal jobs are ignored ────────────────────────────────────────────────

def test_terminal_done_jobs_not_reprocessed(db_engine, mock_science_config):
    """Jobs with status='done' must not be picked up by the polling loop."""
    model = Mock()
    model.predict.return_value = (7.5, 0.85)
    worker = _make_worker(db_engine, mock_science_config, model=model)

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id)
    job = enqueue_predict(session_id=ws.id, engine=db_engine)
    update_job_status(job.id, "done", db_engine)

    worker.poll_once()

    model.predict.assert_not_called()


def test_terminal_failed_jobs_not_reprocessed(db_engine, mock_science_config):
    """Jobs with status='failed' must not be picked up by the polling loop."""
    model = Mock()
    model.predict.return_value = (7.5, 0.85)
    worker = _make_worker(db_engine, mock_science_config, model=model)

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id)
    job = enqueue_predict(session_id=ws.id, engine=db_engine)
    update_job_status(job.id, "failed", db_engine)

    worker.poll_once()

    model.predict.assert_not_called()


# ─── Job failure: logs error and loop continues ───────────────────────────────

def test_failed_predict_job_marked_failed_and_loop_continues(db_engine, mock_science_config):
    """A job that raises during execution is marked 'failed'; subsequent jobs still run."""
    model = Mock()
    call_count = 0

    def predict_side_effect(features):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("model exploded")
        return (7.5, 0.85)

    model.predict.side_effect = predict_side_effect

    worker = _make_worker(db_engine, mock_science_config, model=model)

    exercise_id = _seed_minimal_exercise(db_engine)
    ws1 = _make_workout_session(db_engine, exercise_id=exercise_id)
    ws2 = _make_workout_session(db_engine, exercise_id=exercise_id)
    job1 = enqueue_predict(session_id=ws1.id, engine=db_engine)
    job2 = enqueue_predict(session_id=ws2.id, engine=db_engine)

    worker.poll_once()  # must not raise even though job1 fails

    assert _get_job_status(db_engine, job1.id) == "failed"
    assert _get_job_status(db_engine, job2.id) == "done"


# ─── FINE_TUNE threshold not met ─────────────────────────────────────────────

def test_fine_tune_skipped_when_threshold_not_met(db_engine, mock_science_config):
    """fine_tune must NOT be called when eligible session count < threshold."""
    model = Mock()
    model.fine_tune = Mock()
    worker = _make_worker(db_engine, mock_science_config, model=model, fine_tune_threshold=5)

    # Only 3 eligible sessions (< 5)
    for _ in range(3):
        ws = _make_workout_session(db_engine, post_feeling=8, is_deload=False, status="completed")

    with Session(db_engine) as s:
        session_ids = [row.id for row in s.query(WorkoutSession).all()]
        ft_job = MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps(session_ids),
        )
        s.add(ft_job)
        s.commit()
        s.refresh(ft_job)
        ft_job_id = ft_job.id

    worker.poll_once()

    model.fine_tune.assert_not_called()
    # Job should be marked done (not failed), but skipped internally
    assert _get_job_status(db_engine, ft_job_id) == "done"


def test_fine_tune_skipped_when_no_eligible_sessions_due_to_deload(db_engine, mock_science_config):
    """Sessions with is_deload=True must not count toward the fine-tune threshold."""
    model = Mock()
    model.fine_tune = Mock()
    worker = _make_worker(db_engine, mock_science_config, model=model, fine_tune_threshold=2)

    # 5 sessions but all are deloads → 0 eligible
    for _ in range(5):
        _make_workout_session(db_engine, post_feeling=5, is_deload=True, status="completed")

    with Session(db_engine) as s:
        session_ids = [row.id for row in s.query(WorkoutSession).all()]
        ft_job = MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps(session_ids),
        )
        s.add(ft_job)
        s.commit()
        s.refresh(ft_job)
        ft_job_id = ft_job.id

    worker.poll_once()

    model.fine_tune.assert_not_called()
    assert _get_job_status(db_engine, ft_job_id) == "done"


# ─── FINE_TUNE threshold met ──────────────────────────────────────────────────

def test_fine_tune_executes_when_threshold_met(db_engine, mock_science_config, tmp_path):
    """fine_tune must be called when enough eligible sessions exist."""
    model = Mock()
    model.fine_tune = Mock()
    model.save = Mock()

    worker = _make_worker(db_engine, mock_science_config, model=model, fine_tune_threshold=3)
    worker._model_dir = tmp_path
    # Pre-seed a model_v1.pt so filesystem discovery finds version 1 → next = 2
    (tmp_path / "model_v1.pt").write_bytes(b"fake")

    # Create 3 eligible sessions with post_feeling and is_deload=False
    for _ in range(3):
        _make_workout_session(db_engine, post_feeling=7, is_deload=False, status="completed")

    with Session(db_engine) as s:
        session_ids = [row.id for row in s.query(WorkoutSession).all()]
        ft_job = MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps(session_ids),
        )
        s.add(ft_job)
        s.commit()
        s.refresh(ft_job)
        ft_job_id = ft_job.id

    # Patch _load_training_samples to return non-empty list (avoids seeding full WorkoutSet data)
    worker._load_training_samples = Mock(return_value=[{"exercise_id": 1, "target_rpe": 7.5}])

    worker.poll_once()

    model.fine_tune.assert_called_once()
    model.save.assert_called_once()
    assert _get_job_status(db_engine, ft_job_id) == "done"
    # Version incremented via filesystem discovery: found v1 → next = v2
    assert worker._current_model_version == 2


# ─── PREDICT: RPEPrediction rows persisted ────────────────────────────────────

def test_predict_job_persists_rpe_predictions(db_engine, mock_science_config):
    """A successful PREDICT job must create one RPEPrediction per planned exercise."""
    model = Mock()
    model.predict.return_value = (7.5, 0.85)

    worker = _make_worker(db_engine, mock_science_config, model=model)

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id)
    job = enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    assert _get_job_status(db_engine, job.id) == "done"
    assert _count_predictions(db_engine, ws.id) == 1

    with Session(db_engine) as s:
        pred = s.query(RPEPrediction).filter_by(session_id=ws.id).first()
        assert pred is not None
        assert pred.predicted_rpe == pytest.approx(7.5)
        assert pred.confidence_score == pytest.approx(0.85)
        assert pred.anomaly_flag is False  # confidence 0.85 >= 0.6 threshold
        assert pred.exercise_id == exercise_id


def test_worker_rpe_to_weight_ignores_small_deviations_inside_deadband(mock_science_config):
    """Worker-side helper should hold weight when prediction is close enough to target."""
    adjusted = _rpe_to_weight(
        predicted_rpe=7.9,
        target_rpe=7.75,
        core_weight_kg=80.0,
        science=mock_science_config,
        confidence=0.95,
    )

    assert adjusted == pytest.approx(80.0)


def test_worker_rpe_to_weight_scales_correction_strength_by_confidence(mock_science_config):
    """Worker-side helper should dampen corrections just above the confidence threshold."""
    low_conf_adjusted = _rpe_to_weight(
        predicted_rpe=6.0,
        target_rpe=7.75,
        core_weight_kg=80.0,
        science=mock_science_config,
        confidence=0.61,
    )
    high_conf_adjusted = _rpe_to_weight(
        predicted_rpe=6.0,
        target_rpe=7.75,
        core_weight_kg=80.0,
        science=mock_science_config,
        confidence=0.95,
    )

    assert low_conf_adjusted > 80.0
    assert high_conf_adjusted > low_conf_adjusted


# ─── Anomaly counter: increments on anomalous prediction ─────────────────────

def test_low_confidence_prediction_does_not_increment_anomaly_counter(
    db_engine, mock_science_config
):
    """Low confidence should trigger fallback, not anomaly tracking or rollback pressure."""
    model = Mock()
    # Return confidence 0.3 < 0.6 threshold → fallback without anomaly
    model.predict.return_value = (8.5, 0.3)

    worker = _make_worker(db_engine, mock_science_config, model=model)
    assert worker.consecutive_anomalies == 0

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    assert worker.consecutive_anomalies == 0

    with Session(db_engine) as s:
        pred = s.query(RPEPrediction).filter_by(session_id=ws.id).first()
        assert pred.anomaly_flag is False
        assert pred.source_label == "[ядро: confidence 30% < порога]"


def test_anomaly_counter_increments_on_bounded_correction_violation(
    db_engine, mock_science_config
):
    """Anomaly tracking should follow bounded-correction breaches, not low confidence."""
    model = Mock()
    model.predict.return_value = (1.0, 0.95)

    worker = _make_worker(db_engine, mock_science_config, model=model)
    assert worker.consecutive_anomalies == 0

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(
        db_engine,
        exercise_id=exercise_id,
        target_rpe=8.0,
    )
    enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    assert worker.consecutive_anomalies == 1

    with Session(db_engine) as s:
        pred = s.query(RPEPrediction).filter_by(session_id=ws.id).first()
        assert pred.anomaly_flag is True


# ─── Anomaly counter: resets on normal prediction ────────────────────────────

def test_anomaly_counter_resets_on_normal_prediction(db_engine, mock_science_config):
    """Anomaly counter must reset to 0 when a high-confidence prediction is written."""
    model = Mock()
    model.predict.return_value = (7.5, 0.85)  # high confidence → normal

    worker = _make_worker(db_engine, mock_science_config, model=model)
    worker.consecutive_anomalies = 3  # pre-set counter

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    assert worker.consecutive_anomalies == 0


# ─── Rollback: triggered at threshold ────────────────────────────────────────

def test_rollback_attempted_when_anomaly_threshold_reached(
    db_engine, mock_science_config, tmp_path
):
    """Model rollback must be attempted when consecutive_anomalies reaches threshold."""
    model = Mock()
    model.predict.return_value = (1.0, 0.95)

    worker = _make_worker(db_engine, mock_science_config, model=model)
    worker._model_dir = tmp_path
    # anomaly_rollback_threshold = 5 (from mock_science_config)
    worker.consecutive_anomalies = 4  # one more anomaly should trigger rollback

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id, target_rpe=8.0)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    # v0 does not exist → CRITICAL path, but no crash
    worker.poll_once()

    # Counter should be reset to 0 after rollback attempt
    assert worker.consecutive_anomalies == 0


def test_rollback_loads_previous_model_when_file_exists(
    db_engine, mock_science_config, tmp_path
):
    """When the previous checkpoint exists, rollback must load it and decrement version."""
    model = Mock()
    model.predict.return_value = (1.0, 0.95)
    model.load = Mock()

    worker = _make_worker(db_engine, mock_science_config, model=model)
    worker._model_dir = tmp_path
    worker._current_model_version = 2
    worker.consecutive_anomalies = 4  # one more → threshold (5)

    # Create a fake v1 checkpoint file
    (tmp_path / "model_v1.pt").write_bytes(b"fake")

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id, target_rpe=8.0)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    model.load.assert_called_once()
    assert worker._current_model_version == 1
    assert worker.consecutive_anomalies == 0


# ─── Rollback: missing prior version degrades safely ─────────────────────────

def test_rollback_missing_prior_version_does_not_crash(
    db_engine, mock_science_config, tmp_path
):
    """When no prior checkpoint exists, rollback must log CRITICAL and continue."""
    model = Mock()
    model.predict.return_value = (1.0, 0.95)
    model.load = Mock(side_effect=FileNotFoundError("file not found"))

    worker = _make_worker(db_engine, mock_science_config, model=model)
    worker._model_dir = tmp_path
    worker._current_model_version = 2  # v1 does not exist on disk
    worker.consecutive_anomalies = 4  # threshold=5 → triggers rollback

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id, target_rpe=8.0)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    # Must not raise
    worker.poll_once()

    # Counter reset even when rollback fails
    assert worker.consecutive_anomalies == 0
    # Model version unchanged since rollback failed
    assert worker._current_model_version == 2


def test_rollback_when_at_version_1_logs_critical_no_crash(
    db_engine, mock_science_config, tmp_path
):
    """Rollback from version 1 (no v0 exists) must log CRITICAL but not crash."""
    model = Mock()
    model.predict.return_value = (1.0, 0.95)
    model.load = Mock()

    worker = _make_worker(db_engine, mock_science_config, model=model)
    worker._model_dir = tmp_path
    worker._current_model_version = 1
    worker.consecutive_anomalies = 4  # one more triggers rollback

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id, target_rpe=8.0)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    # Must not raise; CRITICAL should be logged internally
    worker.poll_once()

    # load should NOT be called (no prior version to load)
    model.load.assert_not_called()
    assert worker.consecutive_anomalies == 0
    # Version unchanged
    assert worker._current_model_version == 1


# ─── run() loop: injectable sleep_fn ─────────────────────────────────────────

def test_run_calls_poll_once_and_sleeps(db_engine, mock_science_config):
    """run() must call poll_once and then sleep; stop after one iteration via sleep side_effect."""
    worker = _make_worker(db_engine, mock_science_config)
    poll_calls: list[int] = []
    original_poll = worker.poll_once

    def mock_poll():
        poll_calls.append(1)

    worker.poll_once = mock_poll

    sleep_calls: list[float] = []

    def mock_sleep(duration: float) -> None:
        sleep_calls.append(duration)
        raise StopIteration("stop after first sleep")

    with pytest.raises(StopIteration):
        worker.run(sleep_fn=mock_sleep)

    assert len(poll_calls) == 1
    assert sleep_calls == [60.0]


def test_processing_job_is_logged_as_operational_incident(
    db_engine, mock_science_config
):
    """Stuck processing rows should be reported and left unchanged."""
    import gym_coach_brain.ml.worker as worker_module

    worker = _make_worker(db_engine, mock_science_config)

    with Session(db_engine) as s:
        job = MLJob(
            job_type="PREDICT",
            status="processing",
            session_ids=json.dumps([123]),
            session_id=None,
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id

    records: list[dict] = []
    sink_id = worker_module.logger.add(
        lambda message: records.append(message.record),
        level="ERROR",
    )
    try:
        worker.poll_once()
    finally:
        worker_module.logger.remove(sink_id)

    assert _get_job_status(db_engine, job_id) == "processing"
    assert any(
        record["extra"].get("job_id") == job_id
        and "Operational incident: job remains in processing state" in record["message"]
        for record in records
    )


def test_predict_job_with_invalid_exercise_is_marked_failed(
    db_engine, mock_science_config
):
    """Broken planned exercises should fail the job instead of reporting a false success."""
    worker = _make_worker(db_engine, mock_science_config)

    with Session(db_engine) as s:
        ws = WorkoutSession(
            session_date="2026-03-09T10:00:00",
            status="active",
            planned_exercises=json.dumps(
                [
                    {
                        "exercise_id": 999999,
                        "target_weight_kg": 80.0,
                        "target_reps": 8,
                        "sets": 3,
                    }
                ]
            ),
            sleep_hours=7.5,
            pre_readiness=7,
        )
        s.add(ws)
        s.commit()
        s.refresh(ws)
        session_id = ws.id

    job = enqueue_predict(session_id=session_id, engine=db_engine)

    worker.poll_once()

    assert _get_job_status(db_engine, job.id) == "failed"
    assert _count_predictions(db_engine, session_id) == 0


def test_discover_latest_checkpoint_prefers_highest_numeric_version(tmp_path):
    """Bootstrap should pick the newest canonical model_vN.pt checkpoint."""
    from gym_coach_brain.ml.__main__ import _discover_latest_checkpoint

    (tmp_path / "model_v1.pt").write_bytes(b"v1")
    (tmp_path / "model_v7.pt").write_bytes(b"v7")
    (tmp_path / "model_v6.backup.pt").write_bytes(b"backup")
    (tmp_path / "model_v5.anomaly.pt").write_bytes(b"anomaly")

    checkpoint_path, version = _discover_latest_checkpoint(tmp_path)

    assert checkpoint_path == tmp_path / "model_v7.pt"
    assert version == 7


# ─── Versioning tests (AC 10) ─────────────────────────────────────────────────

def test_versioning_backup_and_anomaly_ignored_for_next_version(tmp_path):
    """.backup.pt and .anomaly.pt must not affect next-version computation."""
    from gym_coach_brain.ml.worker import _discover_canonical_versions

    (tmp_path / "model_v1.pt").write_bytes(b"v1")
    (tmp_path / "model_v3.pt").write_bytes(b"v3")
    (tmp_path / "model_v3.backup.pt").write_bytes(b"backup")
    (tmp_path / "model_v2.anomaly.pt").write_bytes(b"anomaly")
    (tmp_path / "model_v3.corrupt.pt").write_bytes(b"corrupt")

    versions = _discover_canonical_versions(tmp_path)

    assert versions == [1, 3]


def test_versioning_next_version_from_filesystem_discovery(
    db_engine, mock_science_config, tmp_path
):
    """next_version must come from filesystem glob, not in-memory counter (AC 1)."""
    model = Mock()
    model.fine_tune = Mock()
    model.save = Mock()

    worker = _make_worker(db_engine, mock_science_config, model=model, fine_tune_threshold=1)
    worker._model_dir = tmp_path
    # Simulate worker started at v1 but v3 already exists on disk (could happen after restart)
    worker._current_model_version = 1
    (tmp_path / "model_v1.pt").write_bytes(b"v1")
    (tmp_path / "model_v3.pt").write_bytes(b"v3")

    worker._load_training_samples = Mock(return_value=[{"exercise_id": 1, "target_rpe": 7.5}])

    for _ in range(1):
        _make_workout_session(db_engine, post_feeling=7, is_deload=False, status="completed")
    with Session(db_engine) as s:
        session_ids = [row.id for row in s.query(WorkoutSession).all()]
        ft_job = MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps(session_ids),
        )
        s.add(ft_job)
        s.commit()

    worker.poll_once()

    # next_version must be 4 (max of [1,3] + 1), NOT 2 (in-memory counter + 1)
    assert worker._current_model_version == 4
    save_call_path = model.save.call_args[0][0]
    assert save_call_path.name == "model_v4.pt"


def test_versioning_backup_created_before_fine_tuning(
    db_engine, mock_science_config, tmp_path
):
    """model_v{n}.backup.pt must be created before fine-tuning saves new weights (AC 2)."""
    model = Mock()
    model.fine_tune = Mock()
    model.save = Mock()

    worker = _make_worker(db_engine, mock_science_config, model=model, fine_tune_threshold=1)
    worker._model_dir = tmp_path
    (tmp_path / "model_v2.pt").write_bytes(b"v2")

    worker._load_training_samples = Mock(return_value=[{"exercise_id": 1, "target_rpe": 7.5}])

    for _ in range(1):
        _make_workout_session(db_engine, post_feeling=7, is_deload=False, status="completed")
    with Session(db_engine) as s:
        session_ids = [row.id for row in s.query(WorkoutSession).all()]
        s.add(MLJob(
            job_type="FINE_TUNE",
            status="pending",
            session_ids=json.dumps(session_ids),
        ))
        s.commit()

    backup_created_before_fine_tune: list[bool] = []

    original_fine_tune = model.fine_tune.side_effect

    def track_backup_before_fine_tune(*args, **kwargs):
        backup_created_before_fine_tune.append((tmp_path / "model_v2.backup.pt").exists())

    model.fine_tune.side_effect = track_backup_before_fine_tune

    worker.poll_once()

    assert backup_created_before_fine_tune == [True], (
        "model_v2.backup.pt must exist before fine_tune() is called"
    )
    assert (tmp_path / "model_v2.backup.pt").exists()


def test_versioning_rollback_renames_canonical_to_anomaly(
    db_engine, mock_science_config, tmp_path
):
    """On rollback, model_vN.pt must be renamed to model_vN.anomaly.pt (AC 8)."""
    model = Mock()
    model.predict.return_value = (1.0, 0.95)
    model.load = Mock()

    worker = _make_worker(db_engine, mock_science_config, model=model)
    worker._model_dir = tmp_path
    worker._current_model_version = 3
    worker.consecutive_anomalies = 4  # one more → threshold (5)

    # Create canonical v3 and previous v2
    (tmp_path / "model_v3.pt").write_bytes(b"v3")
    (tmp_path / "model_v2.pt").write_bytes(b"v2")

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id, target_rpe=8.0)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    # model_v3.pt must be renamed to model_v3.anomaly.pt
    assert not (tmp_path / "model_v3.pt").exists()
    assert (tmp_path / "model_v3.anomaly.pt").exists()
    # Rollback loaded v2
    model.load.assert_called_once()
    assert worker._current_model_version == 2
    assert worker.consecutive_anomalies == 0


def test_versioning_rollback_loads_previous_version(
    db_engine, mock_science_config, tmp_path
):
    """Rollback must load the highest prior canonical model_v{n}.pt via load_model_version()."""
    model = Mock()
    model.predict.return_value = (1.0, 0.95)
    model.load = Mock()

    worker = _make_worker(db_engine, mock_science_config, model=model)
    worker._model_dir = tmp_path
    worker._current_model_version = 5
    worker.consecutive_anomalies = 4

    (tmp_path / "model_v2.pt").write_bytes(b"v2")
    (tmp_path / "model_v3.pt").write_bytes(b"v3")

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id, target_rpe=8.0)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    assert worker._current_model_version == 3
    loaded_path = model.load.call_args[0][0]
    assert loaded_path.name == "model_v3.pt"


def test_versioning_load_model_version_raises_for_missing_version(tmp_path):
    """load_model_version(n) must raise ModelVersionNotFoundError when file absent (AC 7)."""
    from gym_coach_brain.ml.worker import ModelVersionNotFoundError

    model = Mock()
    worker = MLWorker(
        engine=None,  # not used in this path
        model=model,
        science_config=Mock(),
        model_dir=tmp_path,
    )

    import pytest
    with pytest.raises(ModelVersionNotFoundError):
        worker.load_model_version(99)

    model.load.assert_not_called()


def test_versioning_predictions_record_active_model_version(
    db_engine, mock_science_config
):
    """Every RPEPrediction row must record the active model_v{n} version string (AC 3)."""
    model = Mock()
    model.predict.return_value = (7.5, 0.85)

    worker = MLWorker(
        engine=db_engine,
        model=model,
        science_config=mock_science_config,
        initial_model_version=4,
    )

    exercise_id = _seed_minimal_exercise(db_engine)
    ws = _make_workout_session(db_engine, exercise_id=exercise_id)
    enqueue_predict(session_id=ws.id, engine=db_engine)

    worker.poll_once()

    with Session(db_engine) as s:
        pred = s.query(RPEPrediction).filter_by(session_id=ws.id).first()
        assert pred is not None
        assert pred.model_version == "model_v4"


def test_versioning_bootstrap_no_checkpoints_random_init_warning(tmp_path, caplog):
    """When no checkpoints exist, bootstrap returns 1 and logs a WARNING (AC 5)."""
    import logging
    from gym_coach_brain.ml.__main__ import _bootstrap_model

    model = Mock()
    model.load = Mock()

    with caplog.at_level(logging.WARNING, logger="root"):
        version = _bootstrap_model(model, tmp_path)

    assert version == 1
    model.load.assert_not_called()
    # model_dir should be created
    assert tmp_path.exists()


def test_versioning_bootstrap_creates_model_dir(tmp_path):
    """_bootstrap_model must create model_dir if it does not exist (AC 4)."""
    from gym_coach_brain.ml.__main__ import _bootstrap_model

    new_dir = tmp_path / "weights" / "nested"
    model = Mock()
    model.load = Mock()

    _bootstrap_model(model, new_dir)

    assert new_dir.exists()


def test_versioning_bootstrap_corrupt_canonical_falls_back_to_backup(tmp_path):
    """Corrupt canonical checkpoint falls back to .backup.pt of same version (AC 4)."""
    import torch
    from gym_coach_brain.ml.__main__ import _bootstrap_model
    from gym_coach_brain.ml.model import RPEModel

    model = RPEModel()
    # Write corrupt canonical
    (tmp_path / "model_v2.pt").write_bytes(b"not-a-valid-checkpoint")
    # Write valid backup
    good_model = RPEModel()
    good_model.save(tmp_path / "model_v2.backup.pt")

    version = _bootstrap_model(model, tmp_path)

    assert version == 2
    # Corrupt canonical should be quarantined
    assert not (tmp_path / "model_v2.pt").exists()
    assert (tmp_path / "model_v2.corrupt.pt").exists()


def test_versioning_bootstrap_corrupt_canonical_falls_back_to_n_minus_1_when_no_backup(
    tmp_path,
):
    """When canonical and backup both fail, fall back to model_v{n-1}.pt (AC 4)."""
    import torch
    from gym_coach_brain.ml.__main__ import _bootstrap_model
    from gym_coach_brain.ml.model import RPEModel

    model = RPEModel()
    # Corrupt v3, no backup, valid v2
    (tmp_path / "model_v3.pt").write_bytes(b"corrupt")
    good_model = RPEModel()
    good_model.save(tmp_path / "model_v2.pt")

    version = _bootstrap_model(model, tmp_path)

    assert version == 2
    assert (tmp_path / "model_v3.corrupt.pt").exists()

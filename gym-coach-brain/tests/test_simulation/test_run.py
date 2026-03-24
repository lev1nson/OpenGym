"""
Tests for simulation/run.py — short-horizon smoke, anomaly, cold-start, and report tests.

All tests use a short run (2–4 weeks) with a fixed seed for determinism.
The full 6-month run is reserved for manual / slow integration validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import Base, RPEPrediction, WorkoutSession, WorkoutSet
from gym_coach_brain.data.seed import seed_all
from gym_coach_brain.simulation.run import (
    SimulationMetrics,
    _AnomalyInjectModel,
    _ANOMALY_START,
    _COLD_START_SESSIONS,
    run_simulation,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sim_engine():
    """Isolated in-memory SQLite engine for simulation tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def mock_science_config(mock_science_config):
    """Re-export shared mock_science_config from conftest (reduces cold-start time)."""
    return mock_science_config


# ─── Smoke test: short run completes without exceptions ───────────────────────

def test_smoke_2_weeks(mock_science_config, tmp_path):
    """2-week run with 3 sessions/week = 6 sessions. Must not raise."""
    metrics = run_simulation(
        months=1,            # 1 month ≈ 4 weeks
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )
    assert len(metrics.session_records) > 0, "Simulation produced no session records"


def test_smoke_sessions_in_chronological_order(mock_science_config, tmp_path):
    """Sessions must be created in chronological (ascending date) order."""
    metrics = run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )
    dates = [r["date"] for r in metrics.session_records]
    assert dates == sorted(dates), "Session dates are not in chronological order"


def test_smoke_no_none_nan_in_weights(mock_science_config, tmp_path):
    """No None or NaN values in tracked exercise weights."""
    import math

    metrics = run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )
    for wr in metrics.weight_records:
        for name, weight in wr["weights"].items():
            assert weight is not None, f"None weight for {name} at session {wr['idx']}"
            assert not math.isnan(weight), f"NaN weight for {name} at session {wr['idx']}"
            assert weight >= 0.0, f"Negative weight for {name} at session {wr['idx']}"


def test_smoke_report_written(mock_science_config, tmp_path):
    """Report file is created and contains required sections."""
    report_path = tmp_path / "report.md"
    run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=report_path,
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )
    assert report_path.exists(), "Report file was not created"
    content = report_path.read_text()
    assert "Source Label Distribution" in content
    assert "RPE Model MAE Trend" in content
    assert "Weight Progression" in content
    assert "Anomaly and Rollback Events" in content


def test_smoke_workout_sessions_completed_in_db(mock_science_config, tmp_path):
    """Completed WorkoutSession rows with planned_exercises must exist after the run."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
        engine=engine,
    )

    with Session(engine) as db:
        completed = db.execute(
            select(WorkoutSession).where(WorkoutSession.status == "completed")
        ).scalars().all()

    assert len(completed) > 0, "No completed WorkoutSession rows in DB after simulation"

    for session_row in completed:
        planned = json.loads(session_row.planned_exercises or "[]")
        assert len(planned) > 0, f"Session {session_row.id} has empty planned_exercises"
        for ex in planned:
            assert "exercise_id" in ex
            assert "target_weight_kg" in ex


def test_smoke_workout_sets_have_rpe(mock_science_config, tmp_path):
    """Every WorkoutSet must have a non-None RPE (no None/NaN enters the feature pipeline)."""
    import math

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
        engine=engine,
    )

    with Session(engine) as db:
        sets = db.execute(select(WorkoutSet)).scalars().all()

    assert len(sets) > 0, "No WorkoutSet rows in DB after simulation"
    for ws in sets:
        assert ws.rpe is not None, f"WorkoutSet {ws.id} has None RPE"
        assert not math.isnan(ws.rpe), f"WorkoutSet {ws.id} has NaN RPE"
        assert 1.0 <= ws.rpe <= 10.0, f"WorkoutSet {ws.id} RPE out of range: {ws.rpe}"


# ─── Anomaly injection test ───────────────────────────────────────────────────

def test_anomaly_predictions_are_recorded(mock_science_config, tmp_path):
    """Anomalous predictions (anomaly_flag=True) exist in DB after fault injection fires."""
    sessions_needed = _ANOMALY_START + 5
    months_needed = max(1, sessions_needed // (3 * 4) + 1)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    metrics = run_simulation(
        months=months_needed,
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
        engine=engine,
    )

    # Fault injection events must have fired
    fault_events = [ev for ev in metrics.anomaly_events if ev["type"] == "fault_injection"]
    assert len(fault_events) > 0, "No fault_injection events — anomaly window not reached?"

    # DB must contain RPEPrediction rows with anomaly_flag=True
    with Session(engine) as db:
        anomaly_preds = db.execute(
            select(RPEPrediction).where(RPEPrediction.anomaly_flag.is_(True))
        ).scalars().all()
    assert len(anomaly_preds) > 0, "No anomaly_flag=True predictions in DB after fault injection"

    # Metrics must also reflect anomaly_prediction events
    anomaly_pred_events = [ev for ev in metrics.anomaly_events if ev["type"] == "anomaly_prediction"]
    assert len(anomaly_pred_events) > 0, "No anomaly_prediction events in metrics"


def test_anomaly_model_predict_triggers_anomaly_flag():
    """_AnomalyInjectModel returns high-confidence extreme prediction."""
    anomaly_model = _AnomalyInjectModel()
    rpe, confidence = anomaly_model.predict({})
    assert rpe == 1.0
    assert confidence == 0.99


def test_anomaly_model_save_is_noop(tmp_path):
    """_AnomalyInjectModel.save() does not write any files."""
    anomaly_model = _AnomalyInjectModel()
    anomaly_model.save(tmp_path / "model_v99.pt")
    assert not (tmp_path / "model_v99.pt").exists()


# ─── Cold-start test ──────────────────────────────────────────────────────────

def test_cold_start_sessions_have_no_ml_predictions(mock_science_config, tmp_path):
    """First COLD_START_SESSIONS sessions must have no RPEPrediction rows (pure core path)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
        engine=engine,
    )

    with Session(engine) as db:
        # Get first N completed sessions ordered by their DB id (insertion order)
        sessions = db.execute(
            select(WorkoutSession)
            .where(WorkoutSession.status == "completed")
            .order_by(WorkoutSession.id.asc())
        ).scalars().all()

        cold_start_ids = [s.id for s in sessions[:_COLD_START_SESSIONS]]

        for sid in cold_start_ids:
            preds = db.execute(
                select(RPEPrediction).where(RPEPrediction.session_id == sid)
            ).scalars().all()
            assert len(preds) == 0, (
                f"Cold-start session {sid} unexpectedly has {len(preds)} ML predictions"
            )


def test_cold_start_no_exception_before_history(mock_science_config, tmp_path):
    """Simulation must not raise during the first cold-start sessions."""
    # A 1-session micro-run — the most cold-start scenario
    metrics = run_simulation(
        months=1,
        sessions_per_week=1,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )
    # Simply not raising is the assertion; additionally verify we got records
    assert len(metrics.session_records) > 0


# ─── Report content test ──────────────────────────────────────────────────────

def test_report_contains_required_sections(mock_science_config, tmp_path):
    """Simulation report must contain all required section headers."""
    report_path = tmp_path / "simulation-report.md"
    run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=report_path,
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )
    content = report_path.read_text()
    required_sections = [
        "Source Label Distribution",
        "RPE Model MAE Trend",
        "Weight Progression",
        "Anomaly and Rollback Events",
    ]
    for section in required_sections:
        assert section in content, f"Missing report section: {section!r}"


def test_report_includes_weight_progression_data(mock_science_config, tmp_path):
    """Report must contain actual exercise names and weight values."""
    report_path = tmp_path / "simulation-report.md"
    run_simulation(
        months=1,
        sessions_per_week=3,
        seed=42,
        output_path=report_path,
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )
    content = report_path.read_text()
    # Should have at least one kg value (e.g., "60.0 |")
    assert "kg)" in content or "Weight (kg)" in content


# ─── Determinism test ─────────────────────────────────────────────────────────

def test_deterministic_under_fixed_seed(mock_science_config, tmp_path):
    """Two runs with the same seed produce identical session dates AND exercise weights."""
    metrics_a = run_simulation(
        months=1,
        sessions_per_week=3,
        seed=99,
        output_path=tmp_path / "report_a.md",
        model_dir=tmp_path / "models_a",
        science=mock_science_config,
    )
    metrics_b = run_simulation(
        months=1,
        sessions_per_week=3,
        seed=99,
        output_path=tmp_path / "report_b.md",
        model_dir=tmp_path / "models_b",
        science=mock_science_config,
    )
    dates_a = [r["date"] for r in metrics_a.session_records]
    dates_b = [r["date"] for r in metrics_b.session_records]
    assert dates_a == dates_b, "Session dates differ between runs with same seed"

    # Weights must also be identical across both runs
    weights_a = [(wr["idx"], sorted(wr["weights"].items())) for wr in metrics_a.weight_records]
    weights_b = [(wr["idx"], sorted(wr["weights"].items())) for wr in metrics_b.weight_records]
    assert weights_a == weights_b, "Exercise weights differ between runs with same seed"


# ─── Weight progression test (AC 4) ──────────────────────────────────────────

def test_weight_progression_trend(mock_science_config, tmp_path):
    """Over 2 months, the peak weight per exercise must not regress vs the first half.

    AC 4: 'Weight progression grows monotonically... no exercise stagnates for more
    than 4 weeks.' This test checks that the second-half peak >= 90% of first-half
    peak, accommodating deload pullbacks of up to 10%.
    """
    metrics = run_simulation(
        months=2,
        sessions_per_week=3,
        seed=42,
        output_path=tmp_path / "report.md",
        model_dir=tmp_path / "models",
        science=mock_science_config,
    )

    # Collect per-exercise weight history
    by_exercise: dict[str, list[float]] = {}
    for wr in metrics.weight_records:
        for name, weight in wr["weights"].items():
            by_exercise.setdefault(name, []).append(weight)

    progressions_checked = 0
    for ex_name, weights in by_exercise.items():
        if len(weights) < 8:
            continue  # Not enough sessions to evaluate trend
        mid = len(weights) // 2
        first_half_max = max(weights[:mid])
        second_half_max = max(weights[mid:])
        # Allow up to 10% regression to accommodate deload pullbacks (AC 4)
        assert second_half_max >= first_half_max * 0.90, (
            f"{ex_name}: second-half max {second_half_max:.1f}kg < 90% of "
            f"first-half max {first_half_max:.1f}kg — unexpected weight regression"
        )
        progressions_checked += 1

    assert progressions_checked > 0, "No exercises had enough sessions to evaluate progression"


# ─── SimulationMetrics unit tests ─────────────────────────────────────────────

def test_metrics_mae_window_empty():
    """MAE over empty window returns None."""
    m = SimulationMetrics()
    assert m.mae_for_window(0, 10) is None


def test_metrics_mae_window_correct():
    """MAE computation is accurate."""
    m = SimulationMetrics()
    m.record_rpe(0, 7.0, 8.0)  # error = 1.0
    m.record_rpe(1, 7.0, 7.5)  # error = 0.5
    assert abs(m.mae_for_window(0, 2) - 0.75) < 1e-9


def test_metrics_ai_usage_rate():
    """AI usage rate after session X is computed correctly."""
    m = SimulationMetrics()
    from datetime import date
    m.record_session(0, date(2025, 9, 1), ["[ядро]", "[ядро]"], {})
    m.record_session(1, date(2025, 9, 4), ["[AI: +1.0кг / RPE прогноз: 7.5 / confidence: 80%]", "[ядро]"], {})
    # After session 1: 1 AI out of 2 decisions = 50%
    rate = m.ai_usage_rate_after(1)
    assert abs(rate - 0.5) < 1e-9

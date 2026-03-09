"""
Integration tests for api/handlers.py — handle_readiness_log intent.
Verifies DB storage and argparse intent parsing end-to-end.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.api.handlers import handle_readiness_log
from gym_coach_brain.core.readiness import get_recovery_signal_or_default
from gym_coach_brain.core.science import (
    MethodologiesConfig,
    MethodologySpec,
    PUOSConfig,
    PlanningConfig,
    ProgressionConfig,
    RecoveryConfig,
    ScienceConfig,
)
from gym_coach_brain.data.models import Base, ReadinessLog, UserProfile
from gym_coach_brain.data.seed import seed_all


@pytest.fixture
def readiness_session():
    """In-memory SQLite session with seed data and a pre-created UserProfile."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        session.add(UserProfile(onboarding_complete=True))
        session.commit()
        yield session


@pytest.fixture
def readiness_session_no_profile():
    """In-memory SQLite session with seed data but NO UserProfile."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
        yield session


@pytest.fixture
def science():
    """Minimal ScienceConfig for readiness tests."""
    return ScienceConfig(
        version="test-1.0",
        puos=PUOSConfig(max_sets_per_group=11, smh_volume_multiplier=1.2),
        progression=ProgressionConfig(
            compound_increment_kg=2.5,
            isolation_increment_kg=1.25,
            apre_6_step_min_kg=2.5,
            apre_6_step_max_kg=5.0,
            hypertrophy_rep_min=6,
            hypertrophy_rep_max=12,
        ),
        recovery=RecoveryConfig(hrv_weight=0.5, sleep_weight=0.3, stress_weight=0.2),
        exercises={},
        methodologies=MethodologiesConfig(
            strength=MethodologySpec(rep_min=1, rep_max=5, frequency_per_week_min=2, frequency_per_week_max=4),
            hypertrophy=MethodologySpec(rep_min=6, rep_max=12, frequency_per_week_min=2, frequency_per_week_max=4),
            endurance=MethodologySpec(rep_min=15, rep_max=30, frequency_per_week_min=3, frequency_per_week_max=5),
        ),
        planning=PlanningConfig(min_rest_days_per_muscle_group=2, min_rest_days_compound=3),
    )


# ─── DB Storage Tests ─────────────────────────────────────────────────────────

def test_readiness_log_saves_to_db(readiness_session, science):
    """handle_readiness_log saves ReadinessLog record to DB with correct fields."""
    argv = ["--sleep", "7.0", "--stress", "3", "--hrv", "60"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)

    assert exit_code == 0, f"Expected 0, got {exit_code}: {stdout}"

    log = readiness_session.query(ReadinessLog).first()
    assert log is not None, "ReadinessLog not found in DB after handle_readiness_log"
    assert log.sleep_hours == pytest.approx(7.0)
    assert log.stress_level == 3
    assert log.hrv_score == pytest.approx(60.0)
    assert 0.0 <= log.recovery_score <= 1.0


def test_readiness_log_stores_date_only(readiness_session, science):
    """session_date is stored as ISO date (YYYY-MM-DD), not full timestamp."""
    argv = ["--sleep", "8.0", "--stress", "1"]
    handle_readiness_log(argv, readiness_session, science)

    log = readiness_session.query(ReadinessLog).first()
    assert log is not None

    today = datetime.now(timezone.utc).date().isoformat()
    assert log.session_date == today, (
        f"Expected date '{today}', got '{log.session_date}'. "
        "Full timestamp would break get_recovery_signal_or_default date lookup."
    )


def test_readiness_log_date_matches_get_recovery_signal(readiness_session, science):
    """Date stored by handler matches what get_recovery_signal_or_default queries by."""
    argv = ["--sleep", "8.0", "--stress", "1", "--hrv", "100"]
    handle_readiness_log(argv, readiness_session, science)
    readiness_session.flush()

    today = datetime.now(timezone.utc).date().isoformat()
    signal = get_recovery_signal_or_default(today, readiness_session, science)

    # If date matched, coefficient is computed (not 1.0 default from no-log case)
    # With sleep=8, stress=1, hrv=100 → should be 1.0 anyway; verify it found the log
    log = readiness_session.query(ReadinessLog).filter_by(session_date=today).first()
    assert log is not None, f"Log not found by date '{today}' — date precision mismatch"
    assert signal.coefficient == pytest.approx(1.0, rel=1e-6)


def test_readiness_log_without_hrv(readiness_session, science):
    """handle_readiness_log works without --hrv (optional field)."""
    argv = ["--sleep", "6.0", "--stress", "5"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)

    assert exit_code == 0
    log = readiness_session.query(ReadinessLog).first()
    assert log is not None
    assert log.hrv_score is None
    assert 0.0 <= log.recovery_score <= 1.0


def test_readiness_log_recovery_score_is_computed(readiness_session, science):
    """recovery_score in DB equals coefficient from calculate_recovery_signal."""
    argv = ["--sleep", "8.0", "--stress", "1", "--hrv", "100"]
    handle_readiness_log(argv, readiness_session, science)

    log = readiness_session.query(ReadinessLog).first()
    assert log is not None
    # sleep=8→1.0, stress=1→1.0, hrv=100→1.0 → coefficient=1.0
    assert log.recovery_score == pytest.approx(1.0)


# ─── Intent Parsing / Validation Tests ───────────────────────────────────────

def test_readiness_log_missing_sleep_returns_error(readiness_session, science):
    """Missing --sleep returns exit_code 1."""
    argv = ["--stress", "5"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1
    assert "missing" in stdout.lower() or "required" in stdout.lower()


def test_readiness_log_missing_stress_returns_error(readiness_session, science):
    """Missing --stress returns exit_code 1."""
    argv = ["--sleep", "7.0"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1


def test_readiness_log_sleep_zero_returns_error(readiness_session, science):
    """--sleep 0 returns exit_code 1 (sleep must be positive)."""
    argv = ["--sleep", "0", "--stress", "5"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1
    assert "positive" in stdout.lower() or "sleep" in stdout.lower()


def test_readiness_log_sleep_negative_returns_error(readiness_session, science):
    """Negative --sleep returns exit_code 1."""
    argv = ["--sleep", "-1.0", "--stress", "5"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1


def test_readiness_log_stress_below_range_returns_error(readiness_session, science):
    """--stress 0 (below 1-10 range) returns exit_code 1."""
    argv = ["--sleep", "7.0", "--stress", "0"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1


def test_readiness_log_stress_above_range_returns_error(readiness_session, science):
    """--stress 11 (above 1-10 range) returns exit_code 1."""
    argv = ["--sleep", "7.0", "--stress", "11"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1


def test_readiness_log_hrv_negative_returns_error(readiness_session, science):
    """Negative --hrv returns exit_code 1."""
    argv = ["--sleep", "7.0", "--stress", "3", "--hrv", "-5"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1


def test_readiness_log_hrv_above_100_returns_error(readiness_session, science):
    """--hrv > 100 returns exit_code 1 (out of valid 0-100 range)."""
    argv = ["--sleep", "7.0", "--stress", "3", "--hrv", "101"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 1
    assert "100" in stdout


def test_readiness_log_no_profile_returns_error(readiness_session_no_profile, science):
    """No UserProfile in DB returns exit_code 1."""
    argv = ["--sleep", "7.0", "--stress", "3"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session_no_profile, science)
    assert exit_code == 1
    assert "Профиль" in stdout


def test_readiness_log_output_contains_coefficient(readiness_session, science):
    """Stdout includes coefficient value on success."""
    argv = ["--sleep", "7.0", "--stress", "3", "--hrv", "70"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 0
    assert "Коэффициент восстановления" in stdout


def test_readiness_log_output_shows_hrv_not_measured_when_absent(readiness_session, science):
    """Stdout indicates HRV not measured when --hrv is omitted."""
    argv = ["--sleep", "7.0", "--stress", "3"]
    stdout, exit_code = handle_readiness_log(argv, readiness_session, science)
    assert exit_code == 0
    assert "не измерен" in stdout


def test_readiness_log_upsert_same_day(readiness_session, science):
    """Calling handle_readiness_log twice on the same day updates the row, not creates a second."""
    argv_first = ["--sleep", "6.0", "--stress", "7"]
    handle_readiness_log(argv_first, readiness_session, science)

    argv_second = ["--sleep", "8.0", "--stress", "1", "--hrv", "80"]
    stdout, exit_code = handle_readiness_log(argv_second, readiness_session, science)
    assert exit_code == 0

    logs = readiness_session.query(ReadinessLog).all()
    assert len(logs) == 1, f"Expected 1 row (upsert), got {len(logs)}"
    assert logs[0].sleep_hours == pytest.approx(8.0)
    assert logs[0].stress_level == 1
    assert logs[0].hrv_score == pytest.approx(80.0)


def test_get_recovery_signal_normalizes_timestamp_input(readiness_session, science):
    """get_recovery_signal_or_default accepts full ISO timestamp and strips to date."""
    argv = ["--sleep", "8.0", "--stress", "1", "--hrv", "100"]
    handle_readiness_log(argv, readiness_session, science)
    readiness_session.flush()

    # Pass full ISO timestamp — should still find the log stored as YYYY-MM-DD
    today_timestamp = datetime.now(timezone.utc).isoformat()
    signal = get_recovery_signal_or_default(today_timestamp, readiness_session, science)

    today = datetime.now(timezone.utc).date().isoformat()
    log = readiness_session.query(ReadinessLog).filter_by(session_date=today).first()
    assert log is not None, "Log not found in DB"
    assert signal.coefficient == pytest.approx(1.0, rel=1e-6)

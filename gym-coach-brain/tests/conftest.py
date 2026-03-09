"""
Shared pytest fixtures for gym-coach-brain tests.

Fixtures:
    db_engine: in-memory SQLite engine with schema (no seed data)
    db_session: in-memory SQLite session with schema (for unit tests)
    mock_science_config: minimal ScienceConfig for testing (no real file I/O)
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from unittest.mock import Mock

from gym_coach_brain.data.models import Base
from gym_coach_brain.core.science import (
    ScienceConfig,
    PUOSConfig,
    ProgressionConfig,
    RecoveryConfig,
    MethodologySpec,
    MethodologiesConfig,
    PlanningConfig,
    MLConfig,
    SummaryConfig,
)


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with full schema. No seed data. No real file."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """In-memory SQLite session with schema. Use as context manager in tests.

    Usage:
        def test_something(db_session):
            db_session.add(obj)
            db_session.commit()
    """
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def mock_rpe_model():
    """Mock RPEModelProtocol for unit tests — no PyTorch required.

    Returns (predicted_rpe=7.5, confidence_score=0.85) — confident prediction
    above the default threshold of 0.6.
    """
    model = Mock()
    model.predict.return_value = (7.5, 0.85)
    return model


@pytest.fixture
def mock_science_config() -> ScienceConfig:
    """Minimal valid ScienceConfig for unit tests. No file I/O.

    Uses test-representative values (not placeholder zeros):
    - max_sets_per_group=11 — PUOS limit from science evidence
    - recovery weights sum to 1.0 (required by model_validator)
    """
    return ScienceConfig(
        version="test-1.0",
        puos=PUOSConfig(
            max_sets_per_group=11,
            smh_volume_multiplier=1.2,
        ),
        progression=ProgressionConfig(
            compound_increment_kg=2.5,
            isolation_increment_kg=1.25,
            apre_6_step_min_kg=2.5,
            apre_6_step_max_kg=5.0,
            hypertrophy_rep_min=6,
            hypertrophy_rep_max=12,
        ),
        recovery=RecoveryConfig(
            hrv_weight=0.5,
            sleep_weight=0.3,
            stress_weight=0.2,
        ),
        exercises={},
        methodologies=MethodologiesConfig(
            strength=MethodologySpec(
                rep_min=1, rep_max=5,
                frequency_per_week_min=2, frequency_per_week_max=4,
            ),
            hypertrophy=MethodologySpec(
                rep_min=6, rep_max=12,
                frequency_per_week_min=2, frequency_per_week_max=4,
            ),
            endurance=MethodologySpec(
                rep_min=15, rep_max=30,
                frequency_per_week_min=3, frequency_per_week_max=5,
            ),
        ),
        planning=PlanningConfig(
            min_rest_days_per_muscle_group=2,
            min_rest_days_compound=3,
            detraining_threshold_days=14,
            detraining_coefficient=0.85,
            deload_trigger_sessions=16,
        ),
        ml=MLConfig(
            confidence_threshold=0.6,
            rpe_easy_threshold=7.0,
            rpe_hard_threshold=8.5,
            fatigue_lookback_sessions=3,
            max_correction_percent=0.15,
            anomaly_rollback_threshold=5,
            rpe_weight_sensitivity=0.025,
        ),
        plateau_detection_sessions=3,
        summary=SummaryConfig(rpe_easy_threshold=7.0, rpe_fatigue_threshold=8.0),
    )

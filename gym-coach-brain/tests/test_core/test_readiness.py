"""Tests for core/readiness.py — RecoverySignal calculation."""
import pytest

from gym_coach_brain.core.readiness import (
    DEFAULT_RECOVERY_COEFFICIENT,
    RecoverySignal,
    calculate_recovery_signal,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

from dataclasses import dataclass as _dc


@_dc
class _FakeReadinessLog:
    """Minimal duck-type of ReadinessLog for pure function tests (no DB/ORM)."""
    sleep_hours: float
    stress_level: int
    hrv_score: float | None
    recovery_score: float = 0.0


def make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=None):
    """Create a ReadinessLog-compatible object without DB — pure function tests."""
    return _FakeReadinessLog(
        sleep_hours=sleep_hours,
        stress_level=stress_level,
        hrv_score=hrv_score,
    )


# ─── DEFAULT_RECOVERY_COEFFICIENT ──────────────────────────────────────────────

def test_default_recovery_coefficient_is_one():
    """Default coefficient for absent log = 1.0."""
    assert DEFAULT_RECOVERY_COEFFICIENT == pytest.approx(1.0)


# ─── Normalization edge cases ─────────────────────────────────────────────────

def test_sleep_8h_gives_full_component(mock_science_config):
    """8 hours sleep → sleep_component = 1.0."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.sleep_component == pytest.approx(1.0)


def test_sleep_4h_gives_half_component(mock_science_config):
    """4 hours sleep → sleep_component = 0.5."""
    log = make_readiness_log(sleep_hours=4.0, stress_level=1, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.sleep_component == pytest.approx(0.5)


def test_sleep_16h_capped_at_one(mock_science_config):
    """Sleep > 8h is capped at 1.0 (no bonus for oversleep)."""
    log = make_readiness_log(sleep_hours=16.0, stress_level=1, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.sleep_component == pytest.approx(1.0)


def test_stress_1_gives_full_component(mock_science_config):
    """Stress level 1 (no stress) → stress_component = 1.0."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.stress_component == pytest.approx(1.0)


def test_stress_10_gives_zero_component(mock_science_config):
    """Stress level 10 (max stress) → stress_component = 0.0."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=10, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.stress_component == pytest.approx(0.0)


def test_stress_5_gives_half_component(mock_science_config):
    """Stress level 5 → approximately 5/9 component."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=5, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    # (10-5)/9 = 5/9 ≈ 0.556
    assert signal.stress_component == pytest.approx(5.0 / 9.0)


# ─── HRV handling ─────────────────────────────────────────────────────────────

def test_hrv_100_gives_full_component(mock_science_config):
    """HRV = 100 → hrv_component = 1.0."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=100.0)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.hrv_component == pytest.approx(1.0)


def test_hrv_50_gives_half_component(mock_science_config):
    """HRV = 50 → hrv_component = 0.5."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=50.0)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.hrv_component == pytest.approx(0.5)


def test_hrv_0_gives_zero_component(mock_science_config):
    """HRV = 0 → hrv_component = 0.0."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=5, hrv_score=0.0)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.hrv_component == pytest.approx(0.0)


def test_hrv_none_sets_component_to_none(mock_science_config):
    """HRV absent → hrv_component is None."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.hrv_component is None


# ─── Coefficient boundary enforcement ─────────────────────────────────────────

def test_optimal_inputs_give_coefficient_one(mock_science_config):
    """Optimal inputs (8h sleep, stress=1, HRV=100) → coefficient = 1.0."""
    log = make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=100.0)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.coefficient == pytest.approx(1.0)


def test_worst_inputs_with_hrv_give_coefficient_zero(mock_science_config):
    """Worst case with HRV (0h sleep, stress=10, HRV=0) → coefficient = 0.0."""
    log = make_readiness_log(sleep_hours=0.0, stress_level=10, hrv_score=0.0)
    signal = calculate_recovery_signal(log, mock_science_config)
    assert signal.coefficient == pytest.approx(0.0)


def test_coefficient_always_in_range_0_to_1(mock_science_config):
    """Coefficient is always clamped to [0.0, 1.0]."""
    test_cases = [
        (0.0, 10, 0.0),
        (8.0, 1, 100.0),
        (6.0, 5, 60.0),
        (3.0, 8, None),
    ]
    for sleep, stress, hrv in test_cases:
        log = make_readiness_log(sleep_hours=sleep, stress_level=stress, hrv_score=hrv)
        signal = calculate_recovery_signal(log, mock_science_config)
        assert 0.0 <= signal.coefficient <= 1.0, (
            f"Coefficient out of range for sleep={sleep}, stress={stress}, hrv={hrv}: "
            f"{signal.coefficient}"
        )


# ─── HRV weight redistribution when absent ────────────────────────────────────

def test_no_hrv_uses_redistributed_weights(mock_science_config):
    """Without HRV, weights redistribute proportionally between sleep+stress.

    mock_science_config: hrv_weight=0.5, sleep_weight=0.3, stress_weight=0.2
    Non-HRV total: 0.3 + 0.2 = 0.5
    Effective sleep_weight: 0.3/0.5 = 0.6
    Effective stress_weight: 0.2/0.5 = 0.4
    """
    log = make_readiness_log(sleep_hours=8.0, stress_level=1, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    # sleep=1.0 * 0.6 + stress=1.0 * 0.4 = 1.0
    assert signal.coefficient == pytest.approx(1.0)


def test_no_hrv_partial_recovery(mock_science_config):
    """Without HRV, partial inputs produce deterministic result."""
    # sleep=6h → 0.75; stress=5 → 5/9 ≈ 0.556
    # effective_sleep_w=0.6, effective_stress_w=0.4
    # coefficient = 0.75*0.6 + 0.556*0.4 ≈ 0.672
    log = make_readiness_log(sleep_hours=6.0, stress_level=5, hrv_score=None)
    signal = calculate_recovery_signal(log, mock_science_config)
    expected = 0.75 * 0.6 + (5.0 / 9.0) * 0.4
    assert signal.coefficient == pytest.approx(expected, rel=1e-6)

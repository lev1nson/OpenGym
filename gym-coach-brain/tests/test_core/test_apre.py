"""Tests for core/apre.py — APRE-6 weight adjustment algorithm."""
import pytest

from gym_coach_brain.core.apre import calculate_apre_adjustment, rpe_from_rir
from gym_coach_brain.core.science import ScienceConfig


@pytest.fixture
def science(mock_science_config):
    """Use conftest mock_science_config (has real ProgressionConfig)."""
    return mock_science_config


# ── rpe_from_rir ─────────────────────────────────────────────────────────────

def test_rpe_from_rir_zero():
    """RIR=0 (to failure) → RPE=10.0."""
    assert rpe_from_rir(0) == pytest.approx(10.0)


def test_rpe_from_rir_four():
    assert rpe_from_rir(4) == pytest.approx(6.0)


def test_rpe_from_rir_two():
    assert rpe_from_rir(2) == pytest.approx(8.0)


# ── calculate_apre_adjustment — Knight (1979) table ──────────────────────────

TARGET = 6  # APRE-6 target
WEIGHT = 80.0


def test_apre_4_or_fewer_reps_decreases_by_step_max(science):
    """≤4 reps → decrease by apre_6_step_max_kg (5.0 kg)."""
    result = calculate_apre_adjustment(4, TARGET, WEIGHT, science)
    assert result == pytest.approx(WEIGHT - science.progression.apre_6_step_max_kg)


def test_apre_3_reps_also_decreases(science):
    result = calculate_apre_adjustment(3, TARGET, WEIGHT, science)
    assert result == pytest.approx(WEIGHT - science.progression.apre_6_step_max_kg)


def test_apre_5_to_7_reps_no_change(science):
    """5-7 reps (target ± 1) → no weight change."""
    for reps in (5, 6, 7):
        result = calculate_apre_adjustment(reps, TARGET, WEIGHT, science)
        assert result == pytest.approx(WEIGHT), f"Expected no change at {reps} reps"


def test_apre_8_to_10_reps_increases_by_step_min(science):
    """8-10 reps → increase by apre_6_step_min_kg (2.5 kg)."""
    for reps in (8, 9, 10):
        result = calculate_apre_adjustment(reps, TARGET, WEIGHT, science)
        assert result == pytest.approx(WEIGHT + science.progression.apre_6_step_min_kg)


def test_apre_11_or_more_reps_increases_by_step_max(science):
    """≥11 reps → increase by apre_6_step_max_kg (5.0 kg)."""
    for reps in (11, 12, 15):
        result = calculate_apre_adjustment(reps, TARGET, WEIGHT, science)
        assert result == pytest.approx(WEIGHT + science.progression.apre_6_step_max_kg)


def test_apre_is_pure_no_mutation(science):
    """Function must not mutate any of its arguments."""
    original_weight = 100.0
    _ = calculate_apre_adjustment(6, TARGET, original_weight, science)
    assert original_weight == 100.0


# ── Negative weight clamp ─────────────────────────────────────────────────────

def test_apre_weight_never_negative(science):
    """When very low starting weight and poor performance, result must be >= 0.0."""
    result = calculate_apre_adjustment(1, TARGET, 2.0, science)
    assert result >= 0.0


# ── rpe_from_rir clamping (Low priority) ─────────────────────────────────────

def test_rpe_from_rir_clamped_at_min(science):
    """RIR > 4 (outside DB constraint but defensively handled) → clamp to 6.0 minimum."""
    assert rpe_from_rir(5) == pytest.approx(6.0)
    assert rpe_from_rir(10) == pytest.approx(6.0)

"""Tests for core/progression.py — Double Progression algorithm."""
import pytest

from gym_coach_brain.core.progression import ProgressionResult, calculate_double_progression
from gym_coach_brain.data.models import EquipmentType


REP_RANGE = (6, 12)   # hypertrophy default
WEIGHT = 60.0


# ── Non-bodyweight: rep increment ────────────────────────────────────────────

def test_double_progression_below_max_increments_reps(mock_science_config):
    result = calculate_double_progression(8, WEIGHT, REP_RANGE, mock_science_config)
    assert result.new_reps == 9
    assert result.new_weight == pytest.approx(WEIGHT)
    assert result.suggest_added_load is False


def test_double_progression_at_max_advances_weight(mock_science_config):
    """At rep_max → weight increases, reps reset to rep_min."""
    result = calculate_double_progression(12, WEIGHT, REP_RANGE, mock_science_config)
    assert result.new_reps == REP_RANGE[0]  # reset to rep_min
    assert result.new_weight == pytest.approx(
        WEIGHT + mock_science_config.progression.compound_increment_kg
    )


def test_double_progression_just_below_max(mock_science_config):
    result = calculate_double_progression(11, WEIGHT, REP_RANGE, mock_science_config)
    assert result.new_reps == 12
    assert result.new_weight == pytest.approx(WEIGHT)


# ── Bodyweight branch ─────────────────────────────────────────────────────────

def test_double_progression_bodyweight_increments_reps(mock_science_config):
    result = calculate_double_progression(
        8, 0.0, REP_RANGE, mock_science_config, EquipmentType.bodyweight
    )
    assert result.new_reps == 9
    assert result.new_weight == pytest.approx(0.0)
    assert result.suggest_added_load is False


def test_double_progression_bodyweight_at_max_suggests_load(mock_science_config):
    """At bodyweight rep_max → suggest_added_load=True, reps stay at max."""
    result = calculate_double_progression(
        12, 0.0, REP_RANGE, mock_science_config, EquipmentType.bodyweight
    )
    assert result.new_reps == REP_RANGE[1]  # stays at max
    assert result.new_weight == pytest.approx(0.0)
    assert result.suggest_added_load is True


def test_double_progression_bodyweight_just_below_max_no_load_signal(mock_science_config):
    result = calculate_double_progression(
        11, 0.0, REP_RANGE, mock_science_config, EquipmentType.bodyweight
    )
    assert result.suggest_added_load is False


def test_double_progression_result_is_dataclass():
    """ProgressionResult is a proper dataclass."""
    r = ProgressionResult(new_reps=8, new_weight=80.0)
    assert r.suggest_added_load is False


# ── is_compound flag: isolation_increment_kg ─────────────────────────────────

def test_double_progression_isolation_uses_isolation_increment(mock_science_config):
    """is_compound=False at rep_max → use isolation_increment_kg (1.25), not compound (2.5)."""
    result = calculate_double_progression(12, WEIGHT, REP_RANGE, mock_science_config, is_compound=False)
    assert result.new_reps == REP_RANGE[0]
    assert result.new_weight == pytest.approx(
        WEIGHT + mock_science_config.progression.isolation_increment_kg
    )


def test_double_progression_compound_uses_compound_increment(mock_science_config):
    """is_compound=True (default) at rep_max → use compound_increment_kg (2.5)."""
    result = calculate_double_progression(12, WEIGHT, REP_RANGE, mock_science_config, is_compound=True)
    assert result.new_reps == REP_RANGE[0]
    assert result.new_weight == pytest.approx(
        WEIGHT + mock_science_config.progression.compound_increment_kg
    )


# ── Negative weight clamps ────────────────────────────────────────────────────

def test_double_progression_weight_never_negative(mock_science_config):
    """If somehow weight + increment would go negative, clamp to 0.0."""
    result = calculate_double_progression(12, 0.0, REP_RANGE, mock_science_config)
    assert result.new_weight >= 0.0

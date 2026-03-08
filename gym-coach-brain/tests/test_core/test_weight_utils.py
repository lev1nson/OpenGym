"""Tests for core/weight_utils.py — equipment weight rounding."""
import pytest

from gym_coach_brain.core.weight_utils import round_to_equipment_increment
from gym_coach_brain.data.models import EquipmentType


# ── Barbell (step=2.5) ────────────────────────────────────────────────────────

def test_barbell_rounds_up(mock_science_config):
    """82.3 kg barbell → 82.5 kg (nearest 2.5 step)."""
    result = round_to_equipment_increment(82.3, EquipmentType.barbell, mock_science_config)
    assert result == pytest.approx(82.5)


def test_barbell_rounds_down(mock_science_config):
    """81.1 kg barbell → 80.0 kg (nearest 2.5 step)."""
    result = round_to_equipment_increment(81.1, EquipmentType.barbell, mock_science_config)
    assert result == pytest.approx(80.0)


def test_barbell_already_on_step(mock_science_config):
    result = round_to_equipment_increment(80.0, EquipmentType.barbell, mock_science_config)
    assert result == pytest.approx(80.0)


def test_barbell_midpoint_rounds_up(mock_science_config):
    """81.25 kg at midpoint between 80.0 and 82.5 → 82.5 (round half up, not banker's)."""
    result = round_to_equipment_increment(81.25, EquipmentType.barbell, mock_science_config)
    assert result == pytest.approx(82.5)


# ── Machine (step=5.0) ────────────────────────────────────────────────────────

def test_machine_rounds_to_step(mock_science_config):
    """67.3 kg machine → 65.0 kg (nearest 5.0 step)."""
    result = round_to_equipment_increment(67.3, EquipmentType.machine, mock_science_config)
    assert result == pytest.approx(65.0)


# ── Cable (step=2.5) ──────────────────────────────────────────────────────────

def test_cable_rounds_to_nearest_step(mock_science_config):
    """53.8 kg cable → 55.0 kg (round-half-up, step=2.5).

    Decision (2026-03-08): 53.8 / 2.5 = 21.52 → floor(21.52 + 0.5) = floor(22.02) = 22
    → 22 * 2.5 = 55.0. This is the correct round-half-up result.

    The epic spec listed 52.5, which would require floor() (floor(21.52)=21 → 52.5).
    But floor() contradicts barbell(82.3→82.5): 82.3/2.5=32.92→floor→32→80.0 (wrong).
    Conclusion: 52.5 in epic spec was an error. Using round-half-up consistently gives 55.0.
    """
    result = round_to_equipment_increment(53.8, EquipmentType.cable, mock_science_config)
    assert result == pytest.approx(55.0)


# ── Dumbbell (step=1.0) ───────────────────────────────────────────────────────

def test_dumbbell_rounds_to_step(mock_science_config):
    result = round_to_equipment_increment(14.3, EquipmentType.dumbbell, mock_science_config)
    assert result == pytest.approx(14.0)


def test_dumbbell_rounds_up(mock_science_config):
    result = round_to_equipment_increment(14.6, EquipmentType.dumbbell, mock_science_config)
    assert result == pytest.approx(15.0)


# ── Bodyweight → 0.0 ─────────────────────────────────────────────────────────

def test_bodyweight_always_returns_zero(mock_science_config):
    result = round_to_equipment_increment(999.9, EquipmentType.bodyweight, mock_science_config)
    assert result == pytest.approx(0.0)


def test_bodyweight_zero_input_returns_zero(mock_science_config):
    result = round_to_equipment_increment(0.0, EquipmentType.bodyweight, mock_science_config)
    assert result == pytest.approx(0.0)


# ── No rounding equipment ─────────────────────────────────────────────────────

def test_resistance_band_unchanged(mock_science_config):
    result = round_to_equipment_increment(15.7, EquipmentType.resistance_band, mock_science_config)
    assert result == pytest.approx(15.7)


def test_pullup_bar_unchanged(mock_science_config):
    result = round_to_equipment_increment(10.3, EquipmentType.pullup_bar, mock_science_config)
    assert result == pytest.approx(10.3)


def test_dips_bar_unchanged(mock_science_config):
    result = round_to_equipment_increment(5.5, EquipmentType.dips_bar, mock_science_config)
    assert result == pytest.approx(5.5)

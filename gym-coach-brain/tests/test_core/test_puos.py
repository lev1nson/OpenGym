"""Tests for core/puos.py — PUOS validator and fractional volume accumulation."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from gym_coach_brain.core.puos import (
    AGONIST_COEFF,
    PUOS_WARNING_THRESHOLD,
    SYNERGIST_COEFF,
    FractionalVolume,
    HistoricalVolumeSummary,
    accumulate_session_volume,
    aggregate_historical_volume,
    fractional_volume,
    validate_puos,
)
from gym_coach_brain.data.models import Exercise, MovementPattern, MuscleGroup, WorkoutSet
from gym_coach_brain.exceptions import ScienceLimitError


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_muscle_group(
    muscle_id: int,
    name: str = "chest",
    stretch_mediated: bool = False,
) -> SimpleNamespace:
    """Create a simple object mimicking MuscleGroup — no DB required."""
    return SimpleNamespace(id=muscle_id, name=name, stretch_mediated=stretch_mediated)


def make_exercise(
    exercise_id: int,
    primary_muscle_id: int,
    secondary_ids: list[int] = None,
) -> SimpleNamespace:
    """Create a simple object mimicking Exercise — no DB required."""
    return SimpleNamespace(
        id=exercise_id,
        primary_muscle_id=primary_muscle_id,
        secondary_muscle_id_list=secondary_ids or [],
    )


def make_workout_set(exercise: SimpleNamespace) -> SimpleNamespace:
    """Create a simple object mimicking WorkoutSet with pre-loaded exercise."""
    return SimpleNamespace(exercise=exercise)


def make_workout_session(
    session_date: str,
    status: str,
    exercise_sets: list[SimpleNamespace],
) -> SimpleNamespace:
    """Create a simple object mimicking WorkoutSession with historical sets."""
    return SimpleNamespace(session_date=session_date, status=status, sets=exercise_sets)


# ─── validate_puos: basic cases ───────────────────────────────────────────────

def test_validate_puos_within_limit_returns_fractional_volume(mock_science_config):
    """Under limit: returns FractionalVolume with correct values."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    result = validate_puos(muscle, 8.0, mock_science_config)
    assert isinstance(result, FractionalVolume)
    assert result.muscle_group_id == 1
    assert result.accumulated_sets == pytest.approx(8.0)
    assert result.effective_limit == pytest.approx(11.0)  # no SMH multiplier


def test_validate_puos_exceeds_limit_raises_science_limit_error(mock_science_config):
    """Over limit: raises ScienceLimitError."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    with pytest.raises(ScienceLimitError, match="PUOS limit exceeded"):
        validate_puos(muscle, 12.0, mock_science_config)  # 12 > 11


def test_validate_puos_exact_limit_is_allowed(mock_science_config):
    """Exactly at limit: no error raised."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    result = validate_puos(muscle, 11.0, mock_science_config)
    assert result.accumulated_sets == pytest.approx(11.0)


# ─── validate_puos: FractionalVolume coefficients ─────────────────────────────

def test_fractional_volume_agonist_coeff_is_1_0(mock_science_config):
    """FractionalVolume always has agonist_coeff=1.0."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    result = validate_puos(muscle, 5.0, mock_science_config)
    assert result.agonist_coeff == pytest.approx(AGONIST_COEFF)
    assert result.agonist_coeff == pytest.approx(1.0)


def test_fractional_volume_synergist_coeff_is_0_5(mock_science_config):
    """FractionalVolume always has synergist_coeff=0.5."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    result = validate_puos(muscle, 5.0, mock_science_config)
    assert result.synergist_coeff == pytest.approx(SYNERGIST_COEFF)
    assert result.synergist_coeff == pytest.approx(0.5)


# ─── validate_puos: SMH multiplier ────────────────────────────────────────────

def test_validate_puos_smh_multiplier_expands_limit(mock_science_config):
    """stretch_mediated=True: effective limit = max_sets * smh_volume_multiplier."""
    # mock_science_config: max_sets_per_group=11, smh_volume_multiplier=1.2
    # effective_limit = 11 * 1.2 = 13.2
    muscle = make_muscle_group(2, "hamstrings", stretch_mediated=True)
    result = validate_puos(muscle, 13.0, mock_science_config)  # 13 <= 13.2
    assert result.effective_limit == pytest.approx(11 * 1.2)


def test_validate_puos_smh_allows_volume_above_base_limit(mock_science_config):
    """SMH muscle can have >11 sets without error."""
    muscle = make_muscle_group(2, "hamstrings", stretch_mediated=True)
    # 12 sets: would fail without SMH (12 > 11), but passes with multiplier (12 <= 13.2)
    result = validate_puos(muscle, 12.0, mock_science_config)
    assert result.accumulated_sets == pytest.approx(12.0)


def test_validate_puos_smh_still_blocks_over_multiplied_limit(mock_science_config):
    """SMH muscle: still blocked if exceeds multiplied limit (>13.2)."""
    muscle = make_muscle_group(2, "hamstrings", stretch_mediated=True)
    with pytest.raises(ScienceLimitError):
        validate_puos(muscle, 14.0, mock_science_config)  # 14 > 13.2


def test_validate_puos_non_smh_uses_base_limit_only(mock_science_config):
    """Non-SMH muscle: multiplier = 1.0, uses base max_sets_per_group."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    result = validate_puos(muscle, 11.0, mock_science_config)
    assert result.effective_limit == pytest.approx(11.0)  # 11 * 1.0


# ─── validate_puos: WARNING logging ───────────────────────────────────────────

def test_validate_puos_logs_warning_at_threshold(mock_science_config):
    """≥9 sets: WARNING is logged via loguru."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    with patch("gym_coach_brain.core.puos.logger") as mock_logger:
        validate_puos(muscle, 9.0, mock_science_config)
        mock_logger.warning.assert_called_once()


def test_validate_puos_no_warning_below_threshold(mock_science_config):
    """<9 sets: no WARNING logged."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    with patch("gym_coach_brain.core.puos.logger") as mock_logger:
        validate_puos(muscle, 8.0, mock_science_config)
        mock_logger.warning.assert_not_called()


# ─── accumulate_session_volume ─────────────────────────────────────────────────

def test_accumulate_session_volume_single_primary(mock_science_config):
    """One set of bench press: chest gets 1.0."""
    chest_id, tricep_id = 1, 2
    bench = make_exercise(1, primary_muscle_id=chest_id, secondary_ids=[tricep_id])
    ws = make_workout_set(bench)

    result = accumulate_session_volume([ws], mock_science_config)
    assert result[chest_id] == pytest.approx(1.0)
    assert result[tricep_id] == pytest.approx(0.5)


def test_accumulate_session_volume_two_exercises_same_primary(mock_science_config):
    """Two chest exercises: volumes are summed, not independent."""
    chest_id = 1
    bench = make_exercise(1, primary_muscle_id=chest_id)
    dbell_press = make_exercise(2, primary_muscle_id=chest_id)
    sets = [make_workout_set(bench), make_workout_set(dbell_press)]

    result = accumulate_session_volume(sets, mock_science_config)
    assert result[chest_id] == pytest.approx(2.0)  # 1.0 + 1.0 (not independent checks)


def test_accumulate_session_volume_three_chest_exercises(mock_science_config):
    """Bench + dumbbell press + cable fly → chest gets 3.0."""
    chest_id = 1
    bench = make_exercise(1, primary_muscle_id=chest_id)
    dbell = make_exercise(2, primary_muscle_id=chest_id)
    fly = make_exercise(3, primary_muscle_id=chest_id)
    sets = [make_workout_set(bench), make_workout_set(dbell), make_workout_set(fly)]

    result = accumulate_session_volume(sets, mock_science_config)
    assert result[chest_id] == pytest.approx(3.0)


def test_accumulate_session_volume_synergist_half_contribution(mock_science_config):
    """Synergist muscle gets 0.5 per set."""
    chest_id, tricep_id = 1, 2
    bench = make_exercise(1, primary_muscle_id=chest_id, secondary_ids=[tricep_id])
    # 2 sets of bench press
    sets = [make_workout_set(bench), make_workout_set(bench)]

    result = accumulate_session_volume(sets, mock_science_config)
    assert result[chest_id] == pytest.approx(2.0)    # 2 × 1.0
    assert result[tricep_id] == pytest.approx(1.0)   # 2 × 0.5


def test_accumulate_session_volume_empty_returns_empty_dict(mock_science_config):
    """Empty session → empty dict."""
    result = accumulate_session_volume([], mock_science_config)
    assert result == {}


def test_accumulate_session_volume_multiple_secondaries(mock_science_config):
    """Exercise with multiple synergists: each gets 0.5."""
    chest_id, tricep_id, front_delt_id = 1, 2, 3
    bench = make_exercise(
        1, primary_muscle_id=chest_id, secondary_ids=[tricep_id, front_delt_id]
    )
    result = accumulate_session_volume([make_workout_set(bench)], mock_science_config)
    assert result[chest_id] == pytest.approx(1.0)
    assert result[tricep_id] == pytest.approx(0.5)
    assert result[front_delt_id] == pytest.approx(0.5)


def test_accumulate_session_volume_primary_secondary_collision(mock_science_config):
    """If primary is accidentally in secondary list, it only counts once (1.0)."""
    chest_id = 1
    # Buggy exercise definition: chest is both primary and secondary
    bench = make_exercise(1, primary_muscle_id=chest_id, secondary_ids=[chest_id])
    result = accumulate_session_volume([make_workout_set(bench)], mock_science_config)
    
    assert result[chest_id] == pytest.approx(1.0)  # Agonist coeff only, no double counting


# ─── Integration: accumulate + validate ───────────────────────────────────────

def test_puos_validate_on_accumulated_volume(mock_science_config):
    """Accumulated volume of 12 sets for chest → ScienceLimitError."""
    chest_id = 1
    chest_ex = make_exercise(1, primary_muscle_id=chest_id)
    # 12 sets total (each WorkoutSet = 1 set)
    sets = [make_workout_set(chest_ex) for _ in range(12)]

    volume = accumulate_session_volume(sets, mock_science_config)
    muscle = make_muscle_group(chest_id, "chest", stretch_mediated=False)

    with pytest.raises(ScienceLimitError):
        validate_puos(muscle, volume[chest_id], mock_science_config)


def test_puos_validate_within_limit_on_accumulated_volume(mock_science_config):
    """Accumulated volume of 11 sets for chest → no error."""
    chest_id = 1
    chest_ex = make_exercise(1, primary_muscle_id=chest_id)
    sets = [make_workout_set(chest_ex) for _ in range(11)]

    volume = accumulate_session_volume(sets, mock_science_config)
    muscle = make_muscle_group(chest_id, "chest", stretch_mediated=False)

    result = validate_puos(muscle, volume[chest_id], mock_science_config)
    assert result.accumulated_sets == pytest.approx(11.0)


def test_aggregate_historical_volume_filters_period_and_flags_overloads(
    mock_science_config,
):
    chest = make_muscle_group(1, "chest", stretch_mediated=False)
    muscles_by_id = {1: chest}
    bench = make_exercise(1, primary_muscle_id=1)

    in_range = make_workout_session(
        "2026-03-20",
        "completed",
        [make_workout_set(bench) for _ in range(2)],
    )
    overload = make_workout_session(
        "2026-03-23",
        "completed",
        [make_workout_set(bench) for _ in range(12)],
    )
    old = make_workout_session(
        "2026-02-20",
        "completed",
        [make_workout_set(bench) for _ in range(5)],
    )
    active = make_workout_session(
        "2026-03-22",
        "active",
        [make_workout_set(bench) for _ in range(7)],
    )

    result = aggregate_historical_volume(
        [in_range, overload, old, active],
        muscles_by_id,
        mock_science_config,
        start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 24),
    )

    assert isinstance(result, HistoricalVolumeSummary)
    assert result.included_session_count == 2
    assert result.total_sets_by_muscle_id[1] == pytest.approx(14.0)
    assert result.overloaded_muscle_ids == {1}


# ─── Legacy: fractional_volume (DB-backed) ─────────────────────────────────────

def test_fractional_volume_primary_muscle(db_session):
    """Primary muscle returns 1.0."""
    # Seed minimal data
    mp = MovementPattern(name="push_horizontal", category="push")
    db_session.add(mp)
    db_session.flush()

    mg = MuscleGroup(name="chest_test", body_region="upper", is_push=True, is_pull=False)
    db_session.add(mg)
    db_session.flush()

    ex = Exercise(
        name="bench_press_test",
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        equipment_type="barbell",
        secondary_muscle_ids="[]",
    )
    db_session.add(ex)
    db_session.flush()

    result = fractional_volume(ex.id, mg.id, db_session)
    assert result == pytest.approx(1.0)


def test_fractional_volume_nonexistent_exercise_returns_zero(db_session):
    """Non-existent exercise_id → 0.0."""
    result = fractional_volume(99999, 1, db_session)
    assert result == pytest.approx(0.0)

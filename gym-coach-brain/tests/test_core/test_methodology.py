"""Tests for core/methodology.py — methodology selection."""
import pytest

from gym_coach_brain.core.methodology import (
    Methodology,
    ProgressionType,
    RepRange,
    get_progression_type,
    select_methodology,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_user_profile(goal=None, experience_level="intermediate"):
    """Create UserProfile without DB session (ORM instance, not persisted)."""
    from gym_coach_brain.data.models import UserProfile
    return UserProfile(goal=goal, experience_level=experience_level)


# ─── ProgressionType mapping ──────────────────────────────────────────────────

def test_strength_goal_uses_apre():
    assert get_progression_type("strength") == ProgressionType.APRE

def test_hypertrophy_goal_uses_double_progression():
    assert get_progression_type("hypertrophy") == ProgressionType.DOUBLE_PROGRESSION

def test_endurance_goal_uses_double_progression():
    assert get_progression_type("endurance") == ProgressionType.DOUBLE_PROGRESSION

def test_none_goal_uses_double_progression():
    assert get_progression_type(None) == ProgressionType.DOUBLE_PROGRESSION

def test_unknown_goal_uses_double_progression():
    assert get_progression_type("powerlifting") == ProgressionType.DOUBLE_PROGRESSION


# ─── Methodology selection ────────────────────────────────────────────────────

def test_strength_goal_selects_strength_methodology(mock_science_config):
    profile = make_user_profile(goal="strength")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "strength"
    assert m.rep_range == RepRange(min=1, max=5)
    assert m.progression_type == ProgressionType.APRE
    assert m.frequency_min == 2
    assert m.frequency_max == 4


def test_hypertrophy_goal_selects_hypertrophy_methodology(mock_science_config):
    profile = make_user_profile(goal="hypertrophy")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"
    assert m.rep_range == RepRange(min=6, max=12)
    assert m.progression_type == ProgressionType.DOUBLE_PROGRESSION
    assert m.frequency_min == 2
    assert m.frequency_max == 4


def test_endurance_goal_selects_endurance_methodology(mock_science_config):
    profile = make_user_profile(goal="endurance")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "endurance"
    assert m.rep_range == RepRange(min=15, max=30)
    assert m.progression_type == ProgressionType.DOUBLE_PROGRESSION
    assert m.frequency_min == 3
    assert m.frequency_max == 5


def test_none_goal_defaults_to_hypertrophy(mock_science_config):
    profile = make_user_profile(goal=None)
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"
    assert m.progression_type == ProgressionType.DOUBLE_PROGRESSION


def test_unknown_goal_defaults_to_hypertrophy(mock_science_config):
    profile = make_user_profile(goal="powerlifting")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"


# ─── Case insensitivity ───────────────────────────────────────────────────────

def test_strength_goal_case_insensitive_upper(mock_science_config):
    profile = make_user_profile(goal="STRENGTH")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "strength"
    assert m.progression_type == ProgressionType.APRE


def test_strength_goal_case_insensitive_mixed(mock_science_config):
    profile = make_user_profile(goal="Strength")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "strength"


def test_hypertrophy_goal_case_insensitive(mock_science_config):
    profile = make_user_profile(goal="HYPERTROPHY")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"


def test_endurance_goal_case_insensitive(mock_science_config):
    profile = make_user_profile(goal="ENDURANCE")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "endurance"


# ─── Determinism ─────────────────────────────────────────────────────────────

def test_same_profile_returns_identical_methodology(mock_science_config):
    """Same input → same output (no randomness)."""
    profile = make_user_profile(goal="strength")
    m1 = select_methodology(profile, mock_science_config)
    m2 = select_methodology(profile, mock_science_config)
    assert m1 == m2


@pytest.mark.parametrize("goal,spec_attr", [
    ("strength", "strength"),
    ("hypertrophy", "hypertrophy"),
    ("endurance", "endurance"),
])
def test_methodology_from_science_config_not_hardcoded(mock_science_config, goal, spec_attr):
    """Rep ranges and frequencies must come from ScienceConfig, not hardcoded values.

    We verify for all methodologies that returned values match mock_science_config.
    """
    profile = make_user_profile(goal=goal)
    m = select_methodology(profile, mock_science_config)
    spec = getattr(mock_science_config.methodologies, spec_attr)
    assert m.rep_range.min == spec.rep_min
    assert m.rep_range.max == spec.rep_max
    assert m.frequency_min == spec.frequency_per_week_min
    assert m.frequency_max == spec.frequency_per_week_max

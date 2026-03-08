from pathlib import Path

import pytest

from gym_coach_brain.core.science import (
    MethodologiesConfig,
    MethodologySpec,
    PlanningConfig,
    PUOSConfig,
    ScienceConfig,
    load_science_config,
)
from gym_coach_brain.exceptions import ConfigError

# Path to the actual skeleton file created by Story 1.2
SCIENCE_PATH = Path(__file__).parent.parent.parent / "ScienceEvidence.md"


@pytest.fixture
def science_config() -> ScienceConfig:
    """Load real ScienceEvidence.md skeleton (placeholder values)."""
    return load_science_config(SCIENCE_PATH)


# ── Happy path ────────────────────────────────────────────────────────────────


def test_load_science_config_parses_skeleton(science_config):
    """ScienceConfig parses placeholder skeleton without ValidationError."""
    assert isinstance(science_config, ScienceConfig)


def test_version_is_production_string(science_config):
    assert science_config.version == "1.0.0"


def test_puos_config_types(science_config):
    assert isinstance(science_config.puos.max_sets_per_group, int)
    assert isinstance(science_config.puos.smh_volume_multiplier, float)


def test_progression_config_types(science_config):
    assert isinstance(science_config.progression.compound_increment_kg, float)
    assert isinstance(science_config.progression.hypertrophy_rep_min, int)
    assert isinstance(science_config.progression.hypertrophy_rep_max, int)


def test_recovery_config_types(science_config):
    assert isinstance(science_config.recovery.hrv_weight, float)
    assert isinstance(science_config.recovery.sleep_weight, float)
    assert isinstance(science_config.recovery.stress_weight, float)


def test_exercises_is_empty_dict(science_config):
    """exercises is empty dict in skeleton — populated in Epic 2."""
    assert science_config.exercises == {}


def test_exercise_overrides_validation(tmp_path):
    """ExerciseConfig correctly validates nested overrides."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text(
        '---\n'
        'version: "1.0.0"\n'
        'puos:\n'
        '  max_sets_per_group: 10\n'
        '  smh_volume_multiplier: 1.2\n'
        'progression:\n'
        '  compound_increment_kg: 2.5\n'
        '  isolation_increment_kg: 1.25\n'
        '  apre_6_step_min_kg: 2.5\n'
        '  apre_6_step_max_kg: 5.0\n'
        '  hypertrophy_rep_min: 6\n'
        '  hypertrophy_rep_max: 12\n'
        'recovery:\n'
        '  hrv_weight: 0.5\n'
        '  sleep_weight: 0.3\n'
        '  stress_weight: 0.2\n'
        'exercises:\n'
        '  deadlift:\n'
        '    smh_eligible: "not_a_bool"\n'
        'methodologies:\n'
        '  strength: {rep_min: 1, rep_max: 5, frequency_per_week_min: 2, frequency_per_week_max: 4}\n'
        '  hypertrophy: {rep_min: 6, rep_max: 12, frequency_per_week_min: 2, frequency_per_week_max: 4}\n'
        '  endurance: {rep_min: 15, rep_max: 30, frequency_per_week_min: 3, frequency_per_week_max: 5}\n'
        'planning:\n'
        '  min_rest_days_per_muscle_group: 2\n'
        '  min_rest_days_compound: 3\n'
        '---\n# body'
    )
    with pytest.raises(ConfigError, match="failed validation"):
        load_science_config(bad)


def test_methodologies_all_present(science_config):
    assert hasattr(science_config.methodologies, "strength")
    assert hasattr(science_config.methodologies, "hypertrophy")
    assert hasattr(science_config.methodologies, "endurance")


def test_methodology_spec_types(science_config):
    spec = science_config.methodologies.strength
    assert isinstance(spec.rep_min, int)
    assert isinstance(spec.rep_max, int)
    assert isinstance(spec.frequency_per_week_min, int)
    assert isinstance(spec.frequency_per_week_max, int)


def test_planning_config_types(science_config):
    assert isinstance(science_config.planning.min_rest_days_per_muscle_group, int)
    assert isinstance(science_config.planning.min_rest_days_compound, int)


def test_equipment_increments_present(science_config):
    """Verify equipment_increments field exists and is correctly typed."""
    inc = science_config.equipment_increments
    assert isinstance(inc.barbell, float)
    assert isinstance(inc.dumbbell, float)
    assert isinstance(inc.machine, float)
    assert isinstance(inc.cable, float)
    assert inc.barbell == 2.5
    assert inc.machine == 5.0


def test_load_science_config_accepts_explicit_path():
    """load_science_config accepts explicit Path parameter."""
    config = load_science_config(SCIENCE_PATH)
    assert isinstance(config, ScienceConfig)


# ── Failure modes ─────────────────────────────────────────────────────────────


def test_load_science_config_missing_file_raises():
    """Missing ScienceEvidence.md raises ConfigError."""
    with pytest.raises(ConfigError, match="not found"):
        load_science_config(Path("/nonexistent/ScienceEvidence.md"))


def test_load_science_config_no_frontmatter_raises(tmp_path):
    """File without --- frontmatter delimiters raises ConfigError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text("# No frontmatter here\nJust plain markdown.")
    with pytest.raises(ConfigError, match="No valid YAML frontmatter"):
        load_science_config(bad)


def test_load_science_config_malformed_yaml_raises(tmp_path):
    """File with invalid YAML raises ConfigError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text("---\nversion: [unclosed\n---\n# body")
    with pytest.raises(ConfigError, match="Malformed YAML"):
        load_science_config(bad)


def test_load_science_config_missing_required_key_raises(tmp_path):
    """YAML frontmatter missing a required top-level key raises ConfigError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text('---\nversion: "0.0.0"\n---\n# body')
    with pytest.raises(ConfigError, match="failed validation"):
        load_science_config(bad)


def test_load_science_config_negative_value_raises(tmp_path):
    """Negative numeric values (e.g., max_sets_per_group: -1) raise ValueError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text(
        '---\n'
        'version: "0.0.0"\n'
        'puos:\n'
        '  max_sets_per_group: -1\n'
        '  smh_volume_multiplier: 0.0\n'
        'progression:\n'
        '  compound_increment_kg: 0.0\n'
        '  isolation_increment_kg: 0.0\n'
        '  apre_6_step_min_kg: 0.0\n'
        '  apre_6_step_max_kg: 0.0\n'
        '  hypertrophy_rep_min: 0\n'
        '  hypertrophy_rep_max: 0\n'
        'recovery:\n'
        '  hrv_weight: 0.0\n'
        '  sleep_weight: 0.0\n'
        '  stress_weight: 0.0\n'
        'exercises: {}\n'
        'methodologies:\n'
        '  strength: {rep_min: 0, rep_max: 0, frequency_per_week_min: 0, frequency_per_week_max: 0}\n'
        '  hypertrophy: {rep_min: 0, rep_max: 0, frequency_per_week_min: 0, frequency_per_week_max: 0}\n'
        '  endurance: {rep_min: 0, rep_max: 0, frequency_per_week_min: 0, frequency_per_week_max: 0}\n'
        'planning:\n'
        '  min_rest_days_per_muscle_group: 0\n'
        '  min_rest_days_compound: 0\n'
        '---\n# body'
    )
    with pytest.raises(ConfigError, match="failed validation"):
        load_science_config(bad)


def test_load_science_config_type_mismatch_raises(tmp_path):
    """String value for int field raises ConfigError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text(
        '---\n'
        'version: "0.0.0"\n'
        'puos:\n'
        '  max_sets_per_group: "not_an_int"\n'
        '  smh_volume_multiplier: 0.0\n'
        'progression:\n'
        '  compound_increment_kg: 0.0\n'
        '  isolation_increment_kg: 0.0\n'
        '  apre_6_step_min_kg: 0.0\n'
        '  apre_6_step_max_kg: 0.0\n'
        '  hypertrophy_rep_min: 0\n'
        '  hypertrophy_rep_max: 0\n'
        'recovery:\n'
        '  hrv_weight: 0.0\n'
        '  sleep_weight: 0.0\n'
        '  stress_weight: 0.0\n'
        'exercises: {}\n'
        'methodologies:\n'
        '  strength: {rep_min: 0, rep_max: 0, frequency_per_week_min: 0, frequency_per_week_max: 0}\n'
        '  hypertrophy: {rep_min: 0, rep_max: 0, frequency_per_week_min: 0, frequency_per_week_max: 0}\n'
        '  endurance: {rep_min: 0, rep_max: 0, frequency_per_week_min: 0, frequency_per_week_max: 0}\n'
        'planning:\n'
        '  min_rest_days_per_muscle_group: 0\n'
        '  min_rest_days_compound: 0\n'
        '---\n# body'
    )
    with pytest.raises(ConfigError, match="failed validation"):
        load_science_config(bad)


def test_load_science_config_invalid_recovery_weights_raises(tmp_path):
    """Recovery weights not summing to 1.0 raise ConfigError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text(
        '---\n'
        'version: "1.0.0"\n'
        'puos:\n'
        '  max_sets_per_group: 10\n'
        '  smh_volume_multiplier: 1.2\n'
        'progression:\n'
        '  compound_increment_kg: 2.5\n'
        '  isolation_increment_kg: 1.25\n'
        '  apre_6_step_min_kg: 2.5\n'
        '  apre_6_step_max_kg: 5.0\n'
        '  hypertrophy_rep_min: 6\n'
        '  hypertrophy_rep_max: 12\n'
        'recovery:\n'
        '  hrv_weight: 0.4\n'
        '  sleep_weight: 0.3\n'
        '  stress_weight: 0.2\n'
        'exercises: {}\n'
        'methodologies:\n'
        '  strength: {rep_min: 1, rep_max: 5, frequency_per_week_min: 2, frequency_per_week_max: 4}\n'
        '  hypertrophy: {rep_min: 6, rep_max: 12, frequency_per_week_min: 2, frequency_per_week_max: 4}\n'
        '  endurance: {rep_min: 15, rep_max: 30, frequency_per_week_min: 3, frequency_per_week_max: 5}\n'
        'planning:\n'
        '  min_rest_days_per_muscle_group: 2\n'
        '  min_rest_days_compound: 3\n'
        '---\n# body'
    )
    with pytest.raises(ConfigError, match="failed validation"):
        load_science_config(bad)


# ── mock_science_config fixture tests ─────────────────────────────────────────


def test_mock_science_config_fixture(mock_science_config):
    """Verifies mock_science_config fixture is valid and injectable."""
    assert isinstance(mock_science_config, ScienceConfig)
    assert mock_science_config.version == "test-1.0"
    assert mock_science_config.puos.max_sets_per_group == 11


def test_science_config_is_injectable(mock_science_config):
    """ScienceConfig is passed as parameter — not a singleton."""
    def some_function(science: ScienceConfig) -> int:
        return science.puos.max_sets_per_group
    assert some_function(mock_science_config) == 11

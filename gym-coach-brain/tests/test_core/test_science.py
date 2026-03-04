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
    with pytest.raises(ValueError, match="failed validation"):
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


def test_load_science_config_accepts_explicit_path():
    """load_science_config accepts explicit Path parameter."""
    config = load_science_config(SCIENCE_PATH)
    assert isinstance(config, ScienceConfig)


# ── Failure modes ─────────────────────────────────────────────────────────────


def test_load_science_config_missing_file_raises():
    """Missing ScienceEvidence.md raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        load_science_config(Path("/nonexistent/ScienceEvidence.md"))


def test_load_science_config_no_frontmatter_raises(tmp_path):
    """File without --- frontmatter delimiters raises ValueError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text("# No frontmatter here\nJust plain markdown.")
    with pytest.raises(ValueError, match="No valid YAML frontmatter"):
        load_science_config(bad)


def test_load_science_config_malformed_yaml_raises(tmp_path):
    """File with invalid YAML raises ValueError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text("---\nversion: [unclosed\n---\n# body")
    with pytest.raises(ValueError, match="Malformed YAML"):
        load_science_config(bad)


def test_load_science_config_missing_required_key_raises(tmp_path):
    """YAML frontmatter missing a required top-level key raises ValueError."""
    bad = tmp_path / "ScienceEvidence.md"
    bad.write_text('---\nversion: "0.0.0"\n---\n# body')
    with pytest.raises(ValueError, match="failed validation"):
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
    with pytest.raises(ValueError, match="failed validation"):
        load_science_config(bad)


def test_load_science_config_type_mismatch_raises(tmp_path):
    """String value for int field raises ValueError."""
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
    with pytest.raises(ValueError, match="failed validation"):
        load_science_config(bad)


def test_load_science_config_invalid_recovery_weights_raises(tmp_path):
    """Recovery weights not summing to 1.0 raise ValueError."""
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
    with pytest.raises(ValueError, match="failed validation"):
        load_science_config(bad)

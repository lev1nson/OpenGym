import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from gym_coach_brain.exceptions import ConfigError


class PUOSConfig(BaseModel):
    """Per-Unique-Output-per-Session volume limits.

    max_sets_per_group: PUOS session limit (~10–11 sets; Israetel/Schoenfeld).
    smh_volume_multiplier: SMH volume multiplier (evidence-informed heuristic,
        Israetel 1.2–1.3; stored as ≥0 to allow placeholder 0.0 in skeleton).
    """

    max_sets_per_group: int = Field(ge=0)
    smh_volume_multiplier: float = Field(ge=0.0)


class ProgressionConfig(BaseModel):
    """Weight progression and rep-range parameters.

    Increment fields: Knight (1979) APRE-6 base steps; compound/isolation deltas.
    Rep range: Schoenfeld & Grgic (2021) hypertrophy bracket (6–12).
    All fields ≥0 to allow placeholder 0/0.0 values in skeleton.
    """

    compound_increment_kg: float = Field(ge=0.0)
    isolation_increment_kg: float = Field(ge=0.0)
    apre_6_step_min_kg: float = Field(ge=0.0)
    apre_6_step_max_kg: float = Field(ge=0.0)
    hypertrophy_rep_min: int = Field(ge=0)
    hypertrophy_rep_max: int = Field(ge=0)


class RecoveryConfig(BaseModel):
    """Composite readiness formula weights: hrv + sleep + stress = 1.0.

    Weights are evidence-informed heuristics (Kiviniemi 2007, PMC).
    Sum must equal exactly 1.0 (enforced by model_validator).
    """

    hrv_weight: float = Field(ge=0.0)
    sleep_weight: float = Field(ge=0.0)
    stress_weight: float = Field(ge=0.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "RecoveryConfig":
        total = self.hrv_weight + self.sleep_weight + self.stress_weight
        if abs(total - 1.0) > 1e-9:
            raise ConfigError(
                f"Recovery weights must sum to 1.0, got {total:.4f} "
                f"(hrv={self.hrv_weight}, sleep={self.sleep_weight}, "
                f"stress={self.stress_weight})"
            )
        return self


class MethodologySpec(BaseModel):
    """Rep ranges and training frequency for a single methodology.

    Source: Schoenfeld & Grgic (2021, PMC7927075).
    All fields ≥0 to allow placeholder 0 values in skeleton.
    """

    rep_min: int = Field(ge=0)
    rep_max: int = Field(ge=0)
    frequency_per_week_min: int = Field(ge=0)
    frequency_per_week_max: int = Field(ge=0)


class MethodologiesConfig(BaseModel):
    """Training methodologies: strength, hypertrophy, endurance."""

    strength: MethodologySpec
    hypertrophy: MethodologySpec
    endurance: MethodologySpec


class PlanningConfig(BaseModel):
    """Minimum rest days between same-muscle-group sessions.

    min_rest_days_per_muscle_group: isolation exercises (48h = 2 days;
        PMC6015912, Monteiro 2018; PMC6719818, De Salles 2010).
    min_rest_days_compound: multi-joint movements (72h = 3 days).
    detraining_threshold_days: days of absence after which detraining coefficient is applied.
        Evidence: Mujika & Padilla (2000). 2 weeks = measurable strength loss onset.
    detraining_coefficient: weight multiplier after long break (e.g. 0.85 = 15% reduction).
        Evidence: conservative return protocol to prevent injury on reactivation.
    deload_trigger_sessions: completed sessions in a mesocycle before recommending deload.
        Evidence: Israetel — 3-4 week mesocycles (12-16 sessions at 3-4/week).
    All fields ≥0 to allow placeholder 0 values in skeleton.
    """

    min_rest_days_per_muscle_group: int = Field(ge=0)
    min_rest_days_compound: int = Field(ge=0)
    detraining_threshold_days: int = Field(default=14, ge=1)
    detraining_coefficient: float = Field(default=0.85, ge=0.0, le=1.0)
    deload_trigger_sessions: int = Field(default=16, ge=1)


class MLConfig(BaseModel):
    """ML thresholds for Adaptation Engine.

    confidence_threshold: MC Dropout confidence score below which the
        Adaptation Engine falls back to Double Progression instead of using
        the ML RPE prediction. Architecture ADR-001.
    rpe_easy_threshold: RPE below this value means athlete has spare capacity
        → increment weight (Double Progression step). Default: 7.0.
    rpe_hard_threshold: RPE above this value means athlete is near failure
        → hold or reduce weight. Default: 8.5.
    fatigue_lookback_sessions: Number of recent same-muscle completed sessions
        used to estimate fatigue for ML feature generation.
    max_correction_percent: Maximum relative delta between deterministic core
        weight and ML-adjusted weight before the correction is blocked.
    anomaly_rollback_threshold: Number of consecutive anomalies that should
        trigger model rollback logic in later stories.
    rpe_weight_sensitivity: Fractional weight adjustment applied per RPE point
        between predicted and target RPE.
    """

    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    rpe_easy_threshold: float = Field(default=7.0, ge=1.0, le=10.0)
    rpe_hard_threshold: float = Field(default=8.5, ge=1.0, le=10.0)
    fatigue_lookback_sessions: int = Field(default=3, ge=1)
    max_correction_percent: float = Field(default=0.15, ge=0.0, le=1.0)
    anomaly_rollback_threshold: int = Field(default=5, ge=1)
    rpe_weight_sensitivity: float = Field(default=0.025, ge=0.0)


class SummaryConfig(BaseModel):
    """RPE thresholds for post-workout fatigue assessment.

    rpe_easy_threshold: avg RPE below this → session classified as "easy"
    rpe_fatigue_threshold: avg RPE at or above this → "fatigued" classification

    Based on: Borg RPE scale application to resistance training feedback.
    RPE 7 = 3 RIR (3 reps in reserve) — comfortable working zone.
    RPE 8 = 2 RIR — approaching challenging territory.
    """

    rpe_easy_threshold: float = Field(default=7.0, ge=0.0, le=10.0)
    rpe_fatigue_threshold: float = Field(default=8.0, ge=0.0, le=10.0)


class ExerciseConfig(BaseModel):
    """Exercise-specific overrides.

    smh_eligible: Whether the exercise is eligible for the SMH volume multiplier.
        Defaults to True as most exercises are SMH-eligible in the RP system.
    """

    smh_eligible: bool = True


class EquipmentIncrementsConfig(BaseModel):
    """Equipment weight increment steps for rounding.

    Each value defines the minimum meaningful weight step for that equipment type.
    Used by core/weight_utils.py to round target weights to physically achievable values.

    Defaults match standard gym plate availability.
    """

    barbell: float = Field(default=2.5, gt=0.0)
    dumbbell: float = Field(default=1.0, gt=0.0)
    machine: float = Field(default=5.0, gt=0.0)
    cable: float = Field(default=2.5, gt=0.0)


CANONICAL_MUSCLE_GROUP_NAMES = (
    "chest",
    "back",
    "shoulders",
    "trapezius",
    "biceps",
    "triceps",
    "quadriceps",
    "hamstrings",
    "glutes",
    "calves",
    "abs",
    "lower_back",
)


class WeeklyVolumeLandmark(BaseModel):
    """Weekly volume landmarks for one canonical muscle group.

    Values follow the repo's MV / MEV / MAV / MRV convention:
    - MV: maintenance volume
    - MEV: minimum effective volume
    - MAV: maximum adaptive volume range
    - MRV: maximum recoverable volume
    """

    mv: float = Field(ge=0.0)
    mev: float = Field(ge=0.0)
    mav_min: float = Field(ge=0.0)
    mav_max: float = Field(ge=0.0)
    mrv: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_order(self) -> "WeeklyVolumeLandmark":
        if not self.mv <= self.mev <= self.mav_min <= self.mav_max <= self.mrv:
            raise ConfigError(
                "Weekly volume landmarks must satisfy "
                "mv <= mev <= mav_min <= mav_max <= mrv, "
                f"got mv={self.mv}, mev={self.mev}, mav_min={self.mav_min}, "
                f"mav_max={self.mav_max}, mrv={self.mrv}"
            )
        return self

    def status_for(self, average_weekly_sets: float) -> str:
        """Classify average weekly volume against MEV/MRV bounds."""
        if average_weekly_sets < self.mev:
            return "below_range"
        if average_weekly_sets > self.mrv:
            return "above_range"
        return "in_range"


class WeeklyVolumeLandmarksConfig(BaseModel):
    """Typed weekly landmarks keyed by canonical seeded muscle names."""

    chest: WeeklyVolumeLandmark
    back: WeeklyVolumeLandmark
    shoulders: WeeklyVolumeLandmark
    trapezius: WeeklyVolumeLandmark
    biceps: WeeklyVolumeLandmark
    triceps: WeeklyVolumeLandmark
    quadriceps: WeeklyVolumeLandmark
    hamstrings: WeeklyVolumeLandmark
    glutes: WeeklyVolumeLandmark
    calves: WeeklyVolumeLandmark
    abs: WeeklyVolumeLandmark
    lower_back: WeeklyVolumeLandmark

    def as_dict(self) -> dict[str, WeeklyVolumeLandmark]:
        return {
            muscle_name: getattr(self, muscle_name)
            for muscle_name in CANONICAL_MUSCLE_GROUP_NAMES
        }


class ScienceConfig(BaseModel):
    """Root model for ScienceEvidence.md YAML frontmatter.

    Loaded ONCE per process at startup (Composition Root pattern).
    Pass as parameter — never store as module-level singleton.
    """

    version: str
    puos: PUOSConfig
    progression: ProgressionConfig
    recovery: RecoveryConfig
    exercises: dict[str, ExerciseConfig]
    methodologies: MethodologiesConfig
    planning: PlanningConfig
    equipment_increments: EquipmentIncrementsConfig = Field(default_factory=EquipmentIncrementsConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    plateau_detection_sessions: int = Field(default=3, ge=1)
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    weekly_volume_landmarks: WeeklyVolumeLandmarksConfig
    initial_weight_table: dict[str, dict[str, float]] = {}


_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _find_default_path() -> Path:
    """Find ScienceEvidence.md by walking up from this file's location.

    More robust than counting parent.parent.parent levels — works regardless
    of install layout as long as ScienceEvidence.md is in a parent directory.
    """
    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "ScienceEvidence.md"
        if candidate.exists():
            return candidate
        current = current.parent
    raise ConfigError(
        f"ScienceEvidence.md not found in any parent directory of {Path(__file__)}"
    )


def load_science_config(path: Path | None = None) -> ScienceConfig:
    """Load and validate ScienceEvidence.md YAML frontmatter into ScienceConfig.

    Called ONCE per process at startup (Composition Root pattern).
    Pass the returned ScienceConfig as a parameter to all internal functions —
    do NOT create a module-level global singleton.

    Args:
        path: Path to ScienceEvidence.md. Defaults to auto-discovery by
              walking up from this file's location.

    Returns:
        Validated ScienceConfig instance.

    Raises:
        ConfigError: If file not found, YAML frontmatter is missing or malformed,
                    or data fails Pydantic validation.
    """
    if path is None:
        path = _find_default_path()

    if not path.exists():
        raise ConfigError(f"ScienceEvidence.md not found at {path}")

    raw = path.read_text(encoding="utf-8").lstrip("\ufeff")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise ConfigError(
            f"No valid YAML frontmatter in {path}. "
            "File must begin with a '---' block containing YAML."
        )

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML frontmatter in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(
            f"YAML frontmatter in {path} must be a mapping, got {type(data).__name__}"
        )

    try:
        return ScienceConfig(**data)
    except Exception as exc:
        raise ConfigError(
            f"ScienceEvidence.md at {path} failed validation: {exc}"
        ) from exc

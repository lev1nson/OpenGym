"""
Synthetic athlete signal generator for E2E simulation.

Provides statistically realistic per-session training signals from a seeded
RNG so simulation runs are deterministic under a fixed seed.

Signal distributions (per AC 2):
  - sleep_hours:     N(7, 1) clamped to [4, 10]
  - pre_readiness:   correlated with sleep; P(readiness=2 | sleep < 6) = 0.6
  - post_feeling:    stochastic with mild bias toward 5
  - workout_minute:  deterministic evening pattern 19:00 ± U(-30, 30)
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass


@dataclass
class SessionSignals:
    """Pre/post workout signals for one synthetic session."""

    sleep_hours: float          # clamped to [4, 10]
    pre_readiness: int          # 2 / 5 / 9
    post_feeling: int           # 2 / 5 / 9
    workout_minute_offset: int  # -30 to +30 relative to 19:00
    is_deload: bool
    target_rpe: float           # weekly intensity wave target
    intensity_label: str        # light / moderate / heavy / deload


@dataclass(frozen=True)
class SimulationScenario:
    """Profile + mesocycle parameters for a simulation scenario."""

    name: str
    goal: str
    experience_level: str
    training_split: str
    bodyweight_kg: float
    available_equipment: tuple[str, ...]
    initial_weight_coefficients: dict[str, float]
    weekly_target_rpes: tuple[float, ...]
    deload_interval: int


_SIMULATION_SCENARIOS: dict[str, SimulationScenario] = {
    "ppl_hypertrophy_gym": SimulationScenario(
        name="ppl_hypertrophy_gym",
        goal="hypertrophy",
        experience_level="intermediate",
        training_split="ppl",
        bodyweight_kg=80.0,
        available_equipment=("barbell", "dumbbell", "cable", "pullup_bar", "dips_bar", "bodyweight"),
        initial_weight_coefficients={
            "horizontal_push": 60.0,
            "vertical_push": 40.0,
            "horizontal_pull": 50.0,
            "vertical_pull": 0.0,
            "squat": 80.0,
            "hinge": 70.0,
            "carry": 0.0,
        },
        weekly_target_rpes=(7.0, 7.5, 8.0, 6.5),
        deload_interval=16,
    ),
    "upper_lower_strength_gym": SimulationScenario(
        name="upper_lower_strength_gym",
        goal="strength",
        experience_level="advanced",
        training_split="upper_lower",
        bodyweight_kg=90.0,
        available_equipment=("barbell", "dumbbell", "cable", "pullup_bar", "dips_bar", "machine", "bodyweight"),
        initial_weight_coefficients={
            "horizontal_push": 85.0,
            "vertical_push": 55.0,
            "horizontal_pull": 75.0,
            "vertical_pull": 10.0,
            "squat": 115.0,
            "hinge": 125.0,
            "carry": 25.0,
        },
        weekly_target_rpes=(7.5, 8.0, 8.5, 6.5),
        deload_interval=20,
    ),
    "full_body_beginner_home": SimulationScenario(
        name="full_body_beginner_home",
        goal="hypertrophy",
        experience_level="beginner",
        training_split="full_body",
        bodyweight_kg=70.0,
        available_equipment=("dumbbell", "resistance_band", "pullup_bar", "bodyweight"),
        initial_weight_coefficients={
            "horizontal_push": 22.0,
            "vertical_push": 14.0,
            "horizontal_pull": 18.0,
            "vertical_pull": 0.0,
            "squat": 30.0,
            "hinge": 26.0,
            "carry": 0.0,
        },
        weekly_target_rpes=(6.5, 7.0, 7.5, 6.0),
        deload_interval=12,
    ),
}


def get_simulation_scenario(name: str) -> SimulationScenario:
    """Return a registered simulation scenario by name."""
    try:
        return _SIMULATION_SCENARIOS[name]
    except KeyError as exc:
        known = ", ".join(sorted(_SIMULATION_SCENARIOS))
        raise ValueError(f"Unknown simulation scenario {name!r}. Known: {known}") from exc


class SyntheticAthlete:
    """Generates synthetic athlete signals for simulation replay.

    All randomness is produced by the injected RNG for determinism under
    a fixed seed.
    """

    BASE_HOUR: int = 19  # Evening base workout hour (19:00)
    def __init__(
        self,
        rng: random.Random,
        *,
        scenario: SimulationScenario,
        sessions_per_week: int,
    ) -> None:
        self._rng = rng
        self._scenario = scenario
        self._sessions_per_week = max(1, sessions_per_week)

    @classmethod
    def create_user_profile_data(
        cls,
        *,
        scenario_name: str = "ppl_hypertrophy_gym",
        training_days_per_week: int = 3,
        overrides: dict | None = None,
    ) -> dict:
        """Return constructor kwargs for a configurable athlete profile."""
        scenario = get_simulation_scenario(scenario_name)
        profile = {
            "age": 30,
            "goal": scenario.goal,
            "experience_level": scenario.experience_level,
            "bodyweight_kg": scenario.bodyweight_kg,
            "training_split": scenario.training_split,
            "training_days_per_week": max(3, min(6, training_days_per_week)),
            "onboarding_complete": True,
            "available_equipment": json.dumps(list(scenario.available_equipment)),
            "initial_weight_coefficients": json.dumps(scenario.initial_weight_coefficients),
        }
        if overrides:
            profile.update(overrides)
        return profile

    def generate_session_signals(self, session_index: int) -> SessionSignals:
        """Generate signals for one training session.

        Args:
            session_index: Zero-based session counter within the simulation.

        Returns:
            SessionSignals with sleep, readiness, post-feeling, timing, deload flag.
        """
        week_index = session_index // self._sessions_per_week
        target_rpe = self._scenario.weekly_target_rpes[
            week_index % len(self._scenario.weekly_target_rpes)
        ]
        if target_rpe <= 6.5:
            intensity_label = "light"
        elif target_rpe >= 8.0:
            intensity_label = "heavy"
        else:
            intensity_label = "moderate"

        # ── Sleep: N(7, 1) clamped to [4, 10] ──────────────────────────────
        sleep_hours = self._rng.gauss(7.0, 1.0)
        sleep_hours = max(4.0, min(10.0, sleep_hours))

        # ── Pre-readiness: correlated with sleep (AC 2) ─────────────────────
        if sleep_hours < 6.0:
            # P(readiness=2) = 0.6 when sleep-deprived
            r = self._rng.random()
            if r < 0.60:
                pre_readiness = 2
            elif r < 0.85:
                pre_readiness = 5
            else:
                pre_readiness = 9
        else:
            # Normal distribution weighted toward 5
            r = self._rng.random()
            if r < 0.15:
                pre_readiness = 2
            elif r < 0.75:
                pre_readiness = 5
            else:
                pre_readiness = 9

        # ── Post feeling: mild bias toward 5 (AC 2) ─────────────────────────
        r = self._rng.random()
        if intensity_label == "heavy":
            if r < 0.25:
                post_feeling = 2
            elif r < 0.80:
                post_feeling = 5
            else:
                post_feeling = 9
        elif intensity_label == "light":
            if r < 0.10:
                post_feeling = 2
            elif r < 0.60:
                post_feeling = 5
            else:
                post_feeling = 9
        elif r < 0.15:
            post_feeling = 2
        elif r < 0.80:
            post_feeling = 5
        else:
            post_feeling = 9

        # ── Workout time: 19:00 ± U(-30, 30) min (AC 2) ─────────────────────
        workout_minute_offset = self._rng.randint(-30, 30)

        # ── Deload: every DELOAD_INTERVAL sessions ───────────────────────────
        is_deload = (
            session_index > 0
            and session_index % self._scenario.deload_interval == 0
        )
        if is_deload:
            target_rpe = min(target_rpe, 6.0)
            intensity_label = "deload"

        return SessionSignals(
            sleep_hours=round(sleep_hours, 1),
            pre_readiness=pre_readiness,
            post_feeling=post_feeling,
            workout_minute_offset=workout_minute_offset,
            is_deload=is_deload,
            target_rpe=target_rpe,
            intensity_label=intensity_label,
        )

    def generate_set_rpe(self, target_rpe: float, session_index: int) -> float:
        """Generate a realistic actual RPE for a completed set.

        Adds Gaussian noise around the target RPE, with a very slight trend
        toward higher effort over the simulation (progressive overload realism).

        Args:
            target_rpe: Model-predicted target RPE for this set.
            session_index: Zero-based session counter (used for trend).

        Returns:
            Actual RPE in [1.0, 10.0] rounded to nearest 0.5.
        """
        trend = session_index * 0.005  # Mild progressive overload trend
        noise = self._rng.gauss(0.0, 0.5)
        rpe = max(1.0, min(10.0, target_rpe + trend + noise))
        return round(rpe * 2) / 2  # Round to nearest 0.5

    def generate_stress_level(self, sleep_hours: float) -> int:
        """Generate a correlated stress level (1-10) from sleep quality.

        Lower sleep → higher stress probability.
        """
        if sleep_hours < 6.0:
            base_stress = 7
        elif sleep_hours < 7.0:
            base_stress = 5
        else:
            base_stress = 3
        noise = self._rng.randint(-1, 1)
        return max(1, min(10, base_stress + noise))

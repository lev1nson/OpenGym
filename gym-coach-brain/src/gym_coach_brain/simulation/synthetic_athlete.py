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


class SyntheticAthlete:
    """Generates synthetic athlete signals for simulation replay.

    All randomness is produced by the injected RNG for determinism under
    a fixed seed.
    """

    BASE_HOUR: int = 19  # Evening base workout hour (19:00)
    DELOAD_INTERVAL: int = 16  # Sessions between deloads

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    @classmethod
    def create_user_profile_data(cls) -> dict:
        """Return constructor kwargs for a realistic intermediate UserProfile.

        Uses PPL split with gym equipment for maximum exercise variety.
        Initial weights reflect a 80 kg intermediate male athlete.
        """
        return {
            "age": 30,
            "goal": "hypertrophy",
            "experience_level": "intermediate",
            "bodyweight_kg": 80.0,
            "training_split": "ppl",
            "training_days_per_week": 3,
            "onboarding_complete": True,
            "available_equipment": (
                '["barbell", "dumbbell", "cable", "pullup_bar", "dips_bar", "bodyweight"]'
            ),
            "initial_weight_coefficients": (
                '{"horizontal_push": 60.0, "vertical_push": 40.0, '
                '"horizontal_pull": 50.0, "vertical_pull": 0.0, '
                '"squat": 80.0, "hinge": 70.0, "carry": 0.0}'
            ),
        }

    def generate_session_signals(self, session_index: int) -> SessionSignals:
        """Generate signals for one training session.

        Args:
            session_index: Zero-based session counter within the simulation.

        Returns:
            SessionSignals with sleep, readiness, post-feeling, timing, deload flag.
        """
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
        if r < 0.15:
            post_feeling = 2
        elif r < 0.80:
            post_feeling = 5
        else:
            post_feeling = 9

        # ── Workout time: 19:00 ± U(-30, 30) min (AC 2) ─────────────────────
        workout_minute_offset = self._rng.randint(-30, 30)

        # ── Deload: every DELOAD_INTERVAL sessions ───────────────────────────
        is_deload = session_index > 0 and (session_index % self.DELOAD_INTERVAL == 0)

        return SessionSignals(
            sleep_hours=round(sleep_hours, 1),
            pre_readiness=pre_readiness,
            post_feeling=post_feeling,
            workout_minute_offset=workout_minute_offset,
            is_deload=is_deload,
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

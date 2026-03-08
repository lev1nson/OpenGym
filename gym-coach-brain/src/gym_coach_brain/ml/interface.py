"""
RPEModelProtocol — duck typing interface for RPE prediction model.

Defines the contract between AdaptationEngine (Epic 4, deterministic core)
and RPEModel (Epic 5, PyTorch ML). AdaptationEngine accepts any object
satisfying this Protocol — no direct PyTorch import in Epic 4.

Architecture: ADR-001 (ML Layer Isolation).

References:
    [Source: _bmad-output/planning-artifacts/architecture.md#ADR-001]
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.5]
"""
from __future__ import annotations

from typing import Protocol


class RPEModelProtocol(Protocol):
    """Protocol for RPE prediction model.

    Any object with a `predict` method satisfying this signature can be
    passed to AdaptationEngine — enables testing without PyTorch.
    """

    def predict(self, features: dict) -> tuple[float, float]:
        """Predict RPE and confidence for a given set of training features.

        Args:
            features: Dict with keys matching ML feature spec:
                exercise_id, set_number, weight, reps, historical_rpe,
                readiness_score, days_since_last_session,
                muscle_group_fatigue_estimate

        Returns:
            (predicted_rpe, confidence_score): RPE in [1.0, 10.0],
            confidence in [0.0, 1.0] (MC Dropout uncertainty).
        """
        ...

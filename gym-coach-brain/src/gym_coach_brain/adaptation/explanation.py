"""
Explanation Layer — generates human-readable justifications for adaptation decisions.

Every weight change is accompanied by a reference to science.version for
full traceability (Architecture ADR-002: ScienceConfig versioning).

References:
    [Source: _bmad-output/planning-artifacts/architecture.md#Explanation Layer]
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.5]
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gym_coach_brain.adaptation.engine import AdaptationDecision
    from gym_coach_brain.core.science import ScienceConfig


class ExplanationLayer:
    """Generates human-readable justifications for adaptation decisions.

    All explanations include a reference to ScienceConfig.version for
    full traceability of every load decision.

    Usage (static — no instantiation needed):
        explanation = ExplanationLayer.explain(decision, science)
    """

    @staticmethod
    def explain(decision: "AdaptationDecision", science: "ScienceConfig") -> str:
        """Generate a justification string for a single adaptation decision.

        Format:
            "{exercise}: {prev}кг → {new}кг ({reason}, ScienceEvidence v{version})"

        Reason variants:
            ML path:        "ML RPE 7.5, уверенность 0.85"
            Fallback:       "Double Progression"
            No ML:          "Double Progression (нет ML-модели)"
            Low confidence: "Double Progression (уверенность 0.45 ниже порога 0.60)"

        Args:
            decision: AdaptationDecision with weight change and ML metadata
            science: ScienceConfig for science.version reference

        Returns:
            Human-readable explanation string
        """
        version = science.version

        if decision.used_ml and decision.ml_rpe is not None:
            conf_str = f"{decision.ml_confidence:.2f}" if decision.ml_confidence is not None else "?"
            reason = f"ML RPE {decision.ml_rpe:.1f}, уверенность {conf_str}"
        elif (
            decision.fallback_reason
            and "confidence" in decision.fallback_reason
            and decision.ml_confidence is not None
        ):
            threshold = getattr(science.ml, "confidence_threshold", 0.6)
            reason = f"Double Progression (уверенность {decision.ml_confidence:.2f} ниже порога {threshold:.2f})"
        elif decision.fallback_reason and "no rpe_model" in decision.fallback_reason:
            reason = "Double Progression (нет ML-модели)"
        else:
            reason = "Double Progression"

        return (
            f"{decision.exercise_name}: {decision.previous_weight:.1f}кг → "
            f"{decision.new_weight:.1f}кг ({reason}, ScienceEvidence v{version})"
        )

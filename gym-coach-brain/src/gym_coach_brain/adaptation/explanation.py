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
            "{source_label} {exercise}: {prev}кг → {new}кг (ScienceEvidence v{version})"

        Args:
            decision: AdaptationDecision with weight change and ML metadata
            science: ScienceConfig for science.version reference

        Returns:
            Human-readable explanation string
        """
        return (
            f"{decision.source_label} {decision.exercise_name}: "
            f"{decision.previous_weight:.1f}кг → {decision.new_weight:.1f}кг "
            f"(ScienceEvidence v{science.version})"
        )

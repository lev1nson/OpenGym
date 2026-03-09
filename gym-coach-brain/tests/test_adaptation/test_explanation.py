"""
Tests for ExplanationLayer — human-readable adaptation justifications.

Tests pass AdaptationDecision directly to ExplanationLayer.explain()
without requiring a real DB session or full engine execution.
"""
import pytest

from gym_coach_brain.adaptation.engine import AdaptationDecision
from gym_coach_brain.adaptation.explanation import ExplanationLayer


def _make_decision(
    *,
    exercise_name: str = "Bench Press",
    previous_weight: float = 80.0,
    new_weight: float = 82.5,
    used_ml: bool = False,
    ml_rpe: float | None = None,
    ml_confidence: float | None = None,
    fallback_reason: str | None = None,
    source_label: str = "[ядро]",
) -> AdaptationDecision:
    return AdaptationDecision(
        exercise_name=exercise_name,
        previous_weight=previous_weight,
        new_weight=new_weight,
        used_ml=used_ml,
        ml_rpe=ml_rpe,
        ml_confidence=ml_confidence,
        fallback_reason=fallback_reason,
        source_label=source_label,
    )


def test_explanation_includes_science_version(mock_science_config):
    """Explanation string must contain science.version."""
    decision = _make_decision(fallback_reason="no rpe_model provided")
    explanation = ExplanationLayer.explain(decision, mock_science_config)

    assert mock_science_config.version in explanation


def test_explanation_ml_path_includes_rpe_and_confidence(mock_science_config):
    """ML path explanation must include the source label and science version."""
    decision = _make_decision(
        used_ml=True,
        ml_rpe=7.5,
        ml_confidence=0.85,
        source_label="[AI: +2.5кг / RPE прогноз: 7.5 / confidence: 85%]",
    )
    explanation = ExplanationLayer.explain(decision, mock_science_config)

    assert "[AI:" in explanation
    assert "7.5" in explanation
    assert "85%" in explanation


def test_explanation_fallback_path_mentions_double_progression(mock_science_config):
    """Fallback path explanation must carry the core source label."""
    decision = _make_decision(fallback_reason="no rpe_model provided", source_label="[ядро]")
    explanation = ExplanationLayer.explain(decision, mock_science_config)

    assert explanation.startswith("[ядро] ")


def test_explanation_shows_weight_change(mock_science_config):
    """Explanation must show both previous and new weight values."""
    decision = _make_decision(
        previous_weight=80.0,
        new_weight=82.5,
        fallback_reason="no rpe_model provided",
    )
    explanation = ExplanationLayer.explain(decision, mock_science_config)

    assert "80.0" in explanation
    assert "82.5" in explanation


def test_explanation_low_confidence_mentions_threshold(mock_science_config):
    """Low confidence fallback must keep the low-confidence source label."""
    decision = _make_decision(
        used_ml=False,
        ml_confidence=0.3,
        fallback_reason="confidence 0.30 below threshold 0.6",
        source_label="[ядро: confidence 30% < порога]",
    )
    explanation = ExplanationLayer.explain(decision, mock_science_config)

    assert "[ядро: confidence 30% < порога]" in explanation


def test_explanation_no_ml_model_mentions_no_model(mock_science_config):
    """No-model fallback uses the plain core source label."""
    decision = _make_decision(fallback_reason="no rpe_model provided", source_label="[ядро]")
    explanation = ExplanationLayer.explain(decision, mock_science_config)

    assert explanation.startswith("[ядро] ")


def test_explanation_format_exercise_name(mock_science_config):
    """Explanation must include source label before the exercise name."""
    decision = _make_decision(
        exercise_name="Squat",
        fallback_reason="no rpe_model provided",
    )
    explanation = ExplanationLayer.explain(decision, mock_science_config)

    assert explanation.startswith("[ядро] Squat:")

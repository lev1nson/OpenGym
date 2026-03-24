"""
Tests for the PyTorch RPE model and EWC helper.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gym_coach_brain.ml.constants import FEATURE_DIM
from gym_coach_brain.ml.ewc import EWC
from gym_coach_brain.ml.model import FEATURE_FIELD_ORDER, RPEModel


def _feature_payload() -> dict[str, float]:
    return {
        "exercise_id": 1,
        "movement_pattern_id": 2,
        "primary_muscle_id": 3,
        "is_compound": 1,
        "stretch_mediated": 0,
        "equipment_type_int": 0,
        "set_number": 3,
        "weight_kg": 80.0,
        "reps": 8,
        "historical_rpe": 7.5,
        "avg_rpe_last_3_sessions_for_exercise": 7.3,
        "sessions_count_for_exercise": 4,
        "readiness_score": 0.82,
        "days_since_last_session": 2,
        "sleep_hours": 7.5,
        "pre_readiness": 6,
        "workout_hour_sin": 0.5,
        "workout_hour_cos": 0.8660254,
        "muscle_group_fatigue_estimate": 0.2,
    }


def test_rpe_model_forward_shape():
    model = RPEModel()
    output = model._forward(model._features_to_tensor(_feature_payload()))

    assert tuple(output.shape) == (1,)


def test_rpe_model_forward_returns_floats():
    model = RPEModel()
    predicted_rpe, confidence = model.forward(_feature_payload())

    assert isinstance(predicted_rpe, float)
    assert isinstance(confidence, float)


def test_rpe_model_mc_dropout_variance():
    model = RPEModel(dropout_p=0.5)
    import torch

    tensor = model._features_to_tensor(_feature_payload())
    network = model.network
    network.train()
    with torch.no_grad():
        samples = [float(model._forward(tensor).item()) for _ in range(20)]

    assert torch.tensor(samples, dtype=torch.float32).std(unbiased=False).item() > 0.0


def test_rpe_model_low_confidence_on_high_variance():
    baseline_model = RPEModel(dropout_p=0.3)
    high_variance_model = RPEModel(dropout_p=0.95)
    _, baseline_confidence = baseline_model.forward(_feature_payload())
    _, confidence = high_variance_model.forward(_feature_payload())

    assert confidence < baseline_confidence


def test_rpe_model_feature_dim():
    model = RPEModel()

    assert model.feature_dim == FEATURE_DIM
    assert len(FEATURE_FIELD_ORDER) == FEATURE_DIM
    assert model._features_to_tensor(_feature_payload()).shape == (1, FEATURE_DIM)


def test_rpe_model_save_and_load(tmp_path: Path):
    model = RPEModel()
    path = tmp_path / "model_v1.pt"

    model.save(path)
    reloaded = RPEModel()
    reloaded.load(path)

    assert path.exists()


def test_rpe_model_fine_tune_stays_in_plausible_range():
    model = RPEModel()
    before_rpe, before_confidence = model.predict(_feature_payload())

    assert 5.5 <= before_rpe <= 8.5
    assert before_confidence >= 0.8

    training_samples = []
    for i in range(200):
        sample = _feature_payload()
        sample["weight_kg"] = 60.0 + (i % 10) * 2.5
        sample["reps"] = 6 + (i % 5)
        sample["historical_rpe"] = 7.0 + (i % 4) * 0.5
        sample["avg_rpe_last_3_sessions_for_exercise"] = 7.0 + (i % 4) * 0.4
        sample["sessions_count_for_exercise"] = 1 + (i % 12)
        sample["days_since_last_session"] = 1 + (i % 4)
        sample["sleep_hours"] = 6.0 + (i % 5) * 0.4
        sample["pre_readiness"] = [2, 5, 9][i % 3]
        sample["target_rpe"] = 7.0 + (i % 5) * 0.25
        training_samples.append(sample)

    model.fine_tune(training_samples)
    after_rpe, after_confidence = model.predict(_feature_payload())

    assert 6.5 <= after_rpe <= 8.5
    assert after_confidence >= 0.6


def test_ewc_penalty_zero_at_init():
    ewc = EWC(RPEModel())
    penalty = ewc.penalty(ewc._model)

    assert penalty.item() == pytest.approx(0.0)


def test_ewc_penalty_nonzero_after_update():
    model = RPEModel()
    ewc = EWC(model)
    dataset = [_feature_payload(), {**_feature_payload(), "weight_kg": 82.5, "reps": 9}]
    ewc.update_fisher(dataset)

    for parameter in model.network.parameters():
        parameter.data.add_(0.1)
        break

    penalty = ewc.penalty(model)

    assert penalty.item() > 0.0

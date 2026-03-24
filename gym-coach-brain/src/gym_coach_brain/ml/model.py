"""
RPEModel — PyTorch MLP with MC Dropout uncertainty estimation.
"""
from __future__ import annotations

import os
from pathlib import Path

from gym_coach_brain.ml.constants import FEATURE_DIM, MC_DROPOUT_PASSES
from gym_coach_brain.ml.interface import RPEModelProtocol

FEATURE_FIELD_ORDER = [
    "exercise_id",
    "movement_pattern_id",
    "primary_muscle_id",
    "is_compound",
    "stretch_mediated",
    "equipment_type_int",
    "set_number",
    "weight_kg",
    "reps",
    "historical_rpe",
    "avg_rpe_last_3_sessions_for_exercise",
    "sessions_count_for_exercise",
    "readiness_score",
    "days_since_last_session",
    "sleep_hours",
    "pre_readiness",
    "workout_hour_sin",
    "workout_hour_cos",
    "muscle_group_fatigue_estimate",
]

_FEATURE_SCALES = {
    "exercise_id": 64.0,
    "movement_pattern_id": 16.0,
    "primary_muscle_id": 16.0,
    "is_compound": 1.0,
    "stretch_mediated": 1.0,
    "equipment_type_int": 8.0,
    "set_number": 10.0,
    "weight_kg": 200.0,
    "reps": 30.0,
    "historical_rpe": 10.0,
    "avg_rpe_last_3_sessions_for_exercise": 10.0,
    "sessions_count_for_exercise": 50.0,
    "readiness_score": 10.0,
    "days_since_last_session": 30.0,
    "sleep_hours": 12.0,
    "pre_readiness": 10.0,
    "workout_hour_sin": 1.0,
    "workout_hour_cos": 1.0,
    "muscle_group_fatigue_estimate": 1.0,
}


class RPEModel(RPEModelProtocol):
    """PyTorch MLP for RPE prediction with MC Dropout inference."""

    def __init__(
        self,
        feature_dim: int = FEATURE_DIM,
        hidden_dims: list[int] | None = None,
        dropout_p: float = 0.3,
    ) -> None:
        if hidden_dims is None:
            hidden_dims = [64, 32]
        self._feature_dim = feature_dim
        self._hidden_dims = list(hidden_dims)
        self._dropout_p = dropout_p
        self._network = None

    def _build_network(self):
        import torch.nn as nn

        layers: list[nn.Module] = []
        in_dim = self._feature_dim
        for hidden_dim in self._hidden_dims:
            layers.extend(
                [nn.Linear(in_dim, hidden_dim), nn.ReLU(), nn.Dropout(p=self._dropout_p)]
            )
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, 1))
        network = nn.Sequential(*layers)

        # Bias the untrained model toward a plausible mid-effort RPE instead of
        # letting raw feature magnitudes push predictions into clamp extremes.
        output_layer = network[-1]
        nn.init.normal_(output_layer.weight, mean=0.0, std=0.01)
        nn.init.constant_(output_layer.bias, 7.0)
        return network

    def _get_network(self):
        if self._network is None:
            self._network = self._build_network()
        return self._network

    def _forward(self, x):
        return self._get_network()(x).squeeze(-1)

    def _features_to_tensor(self, features: dict):
        import torch

        values = [
            float(features.get(field_name, 0.0)) / _FEATURE_SCALES[field_name]
            for field_name in FEATURE_FIELD_ORDER
        ]
        if len(values) != self._feature_dim:
            raise ValueError(
                f"Expected {self._feature_dim} features, got {len(values)}"
            )
        return torch.tensor(values, dtype=torch.float32).unsqueeze(0)

    def forward(self, features: dict) -> tuple[float, float]:
        import torch

        network = self._get_network()
        x = self._features_to_tensor(features)
        was_training = network.training
        network.train()
        with torch.no_grad():
            samples = [float(self._forward(x).item()) for _ in range(MC_DROPOUT_PASSES)]
        if not was_training:
            network.eval()

        mean_rpe = sum(samples) / len(samples)
        std_rpe = float(torch.tensor(samples, dtype=torch.float32).std(unbiased=False).item())
        confidence = max(0.0, min(1.0, 1.0 / (1.0 + std_rpe)))
        mean_rpe = max(1.0, min(10.0, float(mean_rpe)))
        return mean_rpe, confidence

    def predict(self, features: dict) -> tuple[float, float]:
        return self.forward(features)

    def save(self, path: Path) -> None:
        import torch

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        torch.save(self._get_network().state_dict(), tmp_path)
        os.replace(tmp_path, path)

    def load(self, path: Path) -> None:
        import torch

        state_dict = torch.load(path, map_location="cpu", weights_only=True)
        self._get_network().load_state_dict(state_dict)

    def fine_tune(
        self,
        training_samples: list[dict],
        epochs: int = 10,
        lr: float = 0.001,
    ) -> None:
        """Fine-tune the model on new training samples with EWC regularization.

        Each sample must contain all feature keys plus ``target_rpe`` (float).
        Samples without ``target_rpe`` are skipped silently.
        No-op when training_samples is empty.
        """
        import torch
        import torch.nn as nn
        import torch.optim as optim

        from gym_coach_brain.ml.ewc import EWC

        if not training_samples:
            return

        network = self._get_network()
        ewc = EWC(self, lambda_=100.0)
        ewc.update_fisher(training_samples)

        optimizer = optim.Adam(network.parameters(), lr=lr / 2)
        criterion = nn.MSELoss()

        network.train()
        for _ in range(epochs):
            for sample in training_samples:
                if "target_rpe" not in sample:
                    continue
                x = self._features_to_tensor(sample)
                target = torch.tensor([float(sample["target_rpe"])], dtype=torch.float32)
                optimizer.zero_grad()
                out = self._forward(x)
                loss = criterion(out, target) + ewc.penalty(self)
                loss.backward()
                nn.utils.clip_grad_norm_(network.parameters(), max_norm=1.0)
                optimizer.step()

    @property
    def network(self):
        return self._get_network()

    @property
    def feature_dim(self) -> int:
        return self._feature_dim

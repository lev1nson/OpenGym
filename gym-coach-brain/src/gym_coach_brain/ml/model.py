"""
RPEModel — PyTorch MLP with MC Dropout uncertainty estimation.
"""
from __future__ import annotations

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
        return nn.Sequential(*layers)

    def _get_network(self):
        if self._network is None:
            self._network = self._build_network()
        return self._network

    def _forward(self, x):
        return self._get_network()(x).squeeze(-1)

    def _features_to_tensor(self, features: dict):
        import torch

        values = [float(features.get(field_name, 0.0)) for field_name in FEATURE_FIELD_ORDER]
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
        confidence = max(0.0, min(1.0, 1.0 - std_rpe))
        mean_rpe = max(1.0, min(10.0, float(mean_rpe)))
        return mean_rpe, confidence

    def predict(self, features: dict) -> tuple[float, float]:
        return self.forward(features)

    def save(self, path: Path) -> None:
        import torch

        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self._get_network().state_dict(), path)

    def load(self, path: Path) -> None:
        import torch

        state_dict = torch.load(path, map_location="cpu")
        self._get_network().load_state_dict(state_dict)

    @property
    def network(self):
        return self._get_network()

    @property
    def feature_dim(self) -> int:
        return self._feature_dim

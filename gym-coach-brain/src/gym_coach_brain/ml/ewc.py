"""
Elastic Weight Consolidation regularizer for incremental fine-tuning.
"""
from __future__ import annotations


class EWC:
    """Small EWC helper storing Fisher diagonals and parameter snapshots."""

    def __init__(self, model, lambda_: float = 100.0) -> None:
        self._model = model
        self._lambda = lambda_
        self._fisher: dict[str, object] = {}
        self._params_star: dict[str, object] = {}

    def update_fisher(self, dataset: list[dict]) -> None:
        import torch

        network = self._model.network
        network.train()
        self._params_star = {
            name: parameter.detach().clone()
            for name, parameter in network.named_parameters()
            if parameter.requires_grad
        }
        fisher = {
            name: torch.zeros_like(parameter)
            for name, parameter in network.named_parameters()
            if parameter.requires_grad
        }
        if not dataset:
            self._fisher = fisher
            return

        for features in dataset:
            network.zero_grad()
            output = self._model._forward(self._model._features_to_tensor(features))
            loss = -output.mean()
            loss.backward()
            for name, parameter in network.named_parameters():
                if parameter.requires_grad and parameter.grad is not None:
                    fisher[name] += parameter.grad.detach() ** 2

        sample_count = max(1, len(dataset))
        self._fisher = {name: values / sample_count for name, values in fisher.items()}

    def penalty(self, model):
        import torch

        if not self._fisher or not self._params_star:
            return torch.tensor(0.0)

        penalties = []
        for name, parameter in model.network.named_parameters():
            if name not in self._fisher:
                continue
            penalties.append((self._fisher[name] * (parameter - self._params_star[name]) ** 2).sum())
        return sum(penalties) * self._lambda

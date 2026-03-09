# Story 5.2: RPEModel — PyTorch MLP + MC Dropout + EWC

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to implement the RPE prediction model with uncertainty estimation and catastrophic forgetting prevention,
So that the system can personalize training loads while protecting previously learned patterns.

## Acceptance Criteria

1. **Given** ML Data Layer из Story 5.1 готов и `data/validate_features` проходит (Story 2.4)
   **When** агент реализует `ml/model.py` и `ml/ewc.py`
   **Then** `class RPEModel` реализует: `forward(features) -> (predicted_rpe, confidence_score)` через MC Dropout (N=20 passes)

2. `confidence_score < 0.6` → fallback флаг для Adaptation Engine

3. `import torch` ТОЛЬКО внутри методов `RPEModel`, не на уровне модуля

4. `class EWC` реализует Fisher Information Matrix расчёт (~50 LOC) без внешних зависимостей

5. `model_v{n}.pt` сохраняется в `MODEL_DIR` после каждого fine-tuning, `model_v{n}.backup.pt` создаётся перед обучением (механизм save/load — в этой истории)

6. Feature vector включает `exercise_id` как категориальную фичу. Полный состав: 14 базовых фичей из Story 2.4 + 4 новых из Contract v3 §11 (`sleep_hours`, `pre_readiness`, `workout_hour_sin`, `workout_hour_cos`) + `muscle_group_fatigue_estimate` от AdaptationEngine = **19 фичей total**

7. `workout_hour_sin = sin(2π * hour / 24)` и `workout_hour_cos = cos(2π * hour / 24)` вычисляются из `session.session_date` (WorkoutSession) — циклическое кодирование

8. `RPEModel` принимает уже готовый feature payload из канонического builder `data.features`, а не собирает признаки самостоятельно

9. `AdaptationEngine` расширяется bounded correction логикой (вызывается при наличии prediction):
   - вычисляет `core_weight_kg` детерминированным ядром
   - конвертирует `predicted_rpe` в `ml_weight_kg` через `rpe_to_weight(predicted_rpe, target_rpe, core_weight_kg, science)`:
     `ml_weight_kg = core_weight_kg * (1 - science.ml.rpe_weight_sensitivity * (predicted_rpe - target_rpe))`
     где `rpe_weight_sensitivity` из `ScienceConfig.ml` (default: 0.025), `target_rpe` из плана упражнения (default: midpoint of easy/hard thresholds)
   - вычисляет `delta_percent = abs(ml_weight_kg - core_weight_kg) / core_weight_kg`
   - если `delta_percent > science.ml.max_correction_percent` → `anomaly_flag=True`, `final_weight=core_weight_kg`
   - если `confidence < science.ml.confidence_threshold` → fallback, `anomaly_flag=False`, `final_weight=core_weight_kg`
   - иначе → `final_weight=ml_weight_kg`, `anomaly_flag=False`
   - итоговый `final_weight` округляется через `round_to_equipment_increment`
   - обновляет RPEPrediction запись: `core_weight_kg`, `ml_weight_kg`, `ml_adjustment_kg`, `anomaly_flag`, `source_label`

10. `ExplanationLayer` дополняется `source_label` в каждом объяснении:
    - ML применён: `"[AI: +2.5кг / RPE прогноз: 7.2 / confidence: 81%]"`
    - Fallback (низкий confidence): `"[ядро: confidence 43% < порога]"`
    - Аномалия: `"[AI заблокирован: дельта 18% > 15% лимит]"`
    - Нет prediction: `"[ядро]"`

11. `pytest tests/test_ml/test_model.py` проходит: forward pass, MC Dropout variance, EWC weight regularization, корректная размерность feature vector (19)

12. `pytest tests/test_adaptation/test_engine.py` расширяется bounded correction сценариями:
    - delta в пределах нормы → ML-коррекция применена, `source_label` содержит `"[AI:"`, `anomaly_flag=False`
    - delta превышает лимит → `final_weight=core_weight`, `anomaly_flag=True`, `source_label` содержит `"заблокирован"`
    - низкий confidence → fallback, `source_label` содержит `"[ядро:"`, `anomaly_flag=False`
    - нет prediction → `source_label == "[ядро]"`

13. `ScienceConfig.ml` расширяется полями: `max_correction_percent: float` (default 0.15), `anomaly_rollback_threshold: int` (default 5), `rpe_weight_sensitivity: float` (default 0.025) — все не hardcoded

## Tasks / Subtasks

- [x] Task 1: Extend MLConfig in science.py + ScienceEvidence.md (AC: #9, #13)
  - [x] Add `max_correction_percent: float = Field(default=0.15, ge=0.0, le=1.0)` to `MLConfig`
  - [x] Add `anomaly_rollback_threshold: int = Field(default=5, ge=1)` to `MLConfig`
  - [x] Add `rpe_weight_sensitivity: float = Field(default=0.025, ge=0.0)` to `MLConfig`
  - [x] Add `ml:` section to `ScienceEvidence.md` YAML frontmatter (see Dev Notes for exact content)
  - [x] Update `tests/conftest.py` `mock_science_config` — MLConfig now has new fields with defaults, no change required UNLESS tests explicitly test ML config (they don't; defaults cover it)

- [x] Task 2: Extend FeatureVector with 4 new fields (AC: #6, #7)
  - [x] Add `sleep_hours: float` to `FeatureVector` dataclass (after `days_since_last_session`)
  - [x] Add `pre_readiness: int` to `FeatureVector` dataclass
  - [x] Add `workout_hour_sin: float` to `FeatureVector` dataclass
  - [x] Add `workout_hour_cos: float` to `FeatureVector` dataclass
  - [x] Update `build_feature_vector()` to look up `WorkoutSession` by `session_id` and extract these fields
  - [x] Add cold start fallbacks: `sleep_hours=7.5`, `pre_readiness=5`, `workout_hour_sin=0.0`, `workout_hour_cos=1.0` (noon: hour=12 → sin=0, cos=-1, but for cold start use hour=12)
  - [x] Update `docs/ml-feature-spec.md` to document the 4 new features
  - [x] Verify existing tests in `tests/test_data/test_features.py` still pass (cold start fallbacks must populate new fields without None/NaN)

- [x] Task 3: Create ml/constants.py (AC: architecture)
  - [x] `CONFIDENCE_THRESHOLD: float = 0.6`
  - [x] `DEFAULT_FINE_TUNE_THRESHOLD: int = 5`
  - [x] `MC_DROPOUT_PASSES: int = 20`
  - [x] `FEATURE_DIM: int = 19`  (14 base + 4 new + 1 fatigue)
  - [x] `MODEL_DIR: Path` — configurable path for model weights (see Dev Notes)

- [x] Task 4: Create ml/model.py (AC: #1, #2, #3, #5, #8)
  - [x] `class RPEModel` inheriting `RPEModelProtocol`
  - [x] `__init__(self, feature_dim: int = FEATURE_DIM, hidden_dims: list[int] = [64, 32], dropout_p: float = 0.3)`
  - [x] `_build_network()` — construct `nn.Sequential` with layers + dropout internally (lazy import torch)
  - [x] `forward(self, x: "torch.Tensor") -> "torch.Tensor"` — standard forward pass (NOT MC Dropout)
  - [x] `predict(self, features: dict) -> tuple[float, float]` — MC Dropout inference
    - [x] Dict → ordered float list (via `_features_to_tensor()`) → tensor
    - [x] N=20 passes with model in training mode (dropout active) BUT `torch.no_grad()`
    - [x] Returns `(mean_rpe, confidence_score)` where `confidence = max(0.0, 1.0 - std(passes))`
  - [x] `_features_to_tensor(self, features: dict) -> "torch.Tensor"` — dict → tensor in canonical FeatureVector field order
  - [x] `save(self, path: "Path") -> None` — `torch.save(self.state_dict(), path)`
  - [x] `load(self, path: "Path") -> None` — `self.load_state_dict(torch.load(path, map_location="cpu"))`
  - [x] ALL `import torch` / `import torch.nn` INSIDE methods, NEVER at module level

- [x] Task 5: Create ml/ewc.py (AC: #4)
  - [x] `class EWC` (~50 LOC, no external ML dependencies)
  - [x] `__init__(self, model: "RPEModel", lambda_: float = 100.0)`
  - [x] `update_fisher(self, dataset: list[dict]) -> None` — compute Fisher Information Matrix from data batch
  - [x] `penalty(self, model: "RPEModel") -> "torch.Tensor"` — return EWC regularization loss
  - [x] ALL `import torch` INSIDE methods

- [x] Task 6: Create tests/test_ml/__init__.py and tests/test_ml/test_model.py (AC: #11)
  - [x] `tests/test_ml/__init__.py` — empty package init
  - [x] `test_rpe_model_forward_shape` — RPEModel forward output has shape [1] (single RPE value)
  - [x] `test_rpe_model_predict_returns_floats` — predict() returns (float, float) tuple
  - [x] `test_rpe_model_mc_dropout_variance` — N=20 passes produce non-zero variance (model in train mode)
  - [x] `test_rpe_model_low_confidence_on_high_variance` — constructed high-variance case → confidence < 0.6
  - [x] `test_rpe_model_feature_dim` — verify model accepts 19-dim input
  - [x] `test_ewc_penalty_zero_at_init` — before update_fisher, penalty returns a tensor
  - [x] `test_ewc_penalty_nonzero_after_update` — after update_fisher on data, penalty > 0 when params change

- [x] Task 7: Extend AdaptationEngine with bounded correction (AC: #9)
  - [x] Add `source_label: str` field to `AdaptationDecision` dataclass (non-optional, default `"[ядро]"`)
  - [x] Add `anomaly_flag: bool` field to `AdaptationDecision` (default `False`)
  - [x] Add `core_weight_kg: float | None` field to `AdaptationDecision`
  - [x] Add standalone function `rpe_to_weight(predicted_rpe, target_rpe, core_weight_kg, science) -> float`
  - [x] Modify ML path in `adapt()` (when `db_prediction` exists AND `confidence >= threshold`):
    - [x] Compute `core_weight_kg` via `_fallback_recommendation()` (deterministic core weight BEFORE recovery_coeff)
    - [x] Compute `ml_weight_kg = rpe_to_weight(predicted_rpe, target_rpe, core_weight_kg, science)`
    - [x] Compute `delta_percent = abs(ml_weight_kg - core_weight_kg) / core_weight_kg` if `core_weight_kg > 0` else `0.0`
    - [x] If `delta_percent > science.ml.max_correction_percent` → `anomaly=True`, `final_weight=core_weight_kg`, `source_label` = anomaly format
    - [x] Else → `anomaly=False`, `final_weight=ml_weight_kg`, `source_label` = AI format
    - [x] Apply `recovery_coeff` to `final_weight`
    - [x] Round via `round_to_equipment_increment`
    - [x] Update RPEPrediction DB record: write `core_weight_kg`, `ml_weight_kg`, `ml_adjustment_kg`, `anomaly_flag`, `source_label`
  - [x] Fallback paths: set `source_label = "[ядро]"` (no prediction) or `"[ядро: confidence X% < порога]"` (low confidence)
  - [x] Pass `source_label` to `AdaptationDecision`

- [x] Task 8: Extend ExplanationLayer to include source_label (AC: #10)
  - [x] Update `ExplanationLayer.explain()` to include `source_label` from `AdaptationDecision` in the explanation string
  - [x] New format: `"{source_label} {exercise}: {prev}кг → {new}кг (ScienceEvidence v{version})"`
  - [x] Ensure all existing tests in `test_explanation.py` still pass (update assertions)

- [x] Task 9: Add bounded correction tests to test_engine.py (AC: #12)
  - [x] `test_bounded_correction_within_limit` — prediction with small delta → ML applied, source_label contains `"[AI:"`, anomaly_flag=False on RPEPrediction
  - [x] `test_bounded_correction_exceeds_limit` — prediction with large delta > 15% → core weight used, anomaly_flag=True, source_label contains `"заблокирован"`
  - [x] `test_bounded_correction_low_confidence` — prediction with confidence < 0.6 → fallback, source_label contains `"[ядро:"`, anomaly_flag=False
  - [x] `test_bounded_correction_no_prediction` — no RPEPrediction in DB → source_label == `"[ядро]"`

- [x] Task 10: Final validation
  - [x] `cd gym-coach-brain && uv run pytest` — ALL tests pass (existing 354 + new)
  - [x] `cd gym-coach-brain && python -m gym_coach_brain.data.validate_features` — exit 0
  - [x] No `import torch` at module level in any file outside `ml/model.py` and `ml/ewc.py` methods

## Dev Notes

### Current State After Story 5.1 — What Exists

**ml/ directory (currently minimal):**
```
src/gym_coach_brain/ml/
├── __init__.py       ← exists (empty)
└── interface.py      ← exists (RPEModelProtocol)
```
Missing: `model.py`, `ewc.py`, `constants.py`, `worker.py`, `__main__.py`

**data/models.py — RPEPrediction already has the fields you need to write:**
```python
class RPEPrediction(Base):
    id, session_id, exercise_id
    predicted_rpe: Float    # written by ML Worker (Story 5.3)
    confidence_score: Float # written by ML Worker
    model_version: String   # written by ML Worker
    core_weight_kg: Float   # ← AdaptationEngine writes this (Story 5.2)
    ml_weight_kg: Float     # ← AdaptationEngine writes this (Story 5.2)
    ml_adjustment_kg: Float # ← AdaptationEngine writes this (story 5.2)
    anomaly_flag: Boolean   # ← AdaptationEngine writes this (Story 5.2)
    source_label: String    # ← AdaptationEngine writes this (Story 5.2)
    created_at: String
```

**data/models.py — WorkoutSession has the new fields you need for FeatureVector:**
```python
class WorkoutSession(Base):
    session_date: String  # ISO 8601 UTC — USE THIS for workout_hour encoding
    sleep_hours: Float    # nullable — from pre-workout buttons
    pre_readiness: Integer # nullable — from pre-workout buttons
    post_feeling: Integer # nullable — post-workout
    is_deload: Boolean    # non-nullable, default False
```
Note: Field is `session_date` NOT `started_at`. Use `session_date` for hour extraction.

**core/science.py — MLConfig currently has:**
```python
class MLConfig(BaseModel):
    confidence_threshold: float = Field(default=0.6, ...)
    rpe_easy_threshold: float = Field(default=7.0, ...)
    rpe_hard_threshold: float = Field(default=8.5, ...)
    fatigue_lookback_sessions: int = Field(default=3, ...)
    # MISSING: max_correction_percent, anomaly_rollback_threshold, rpe_weight_sensitivity
```

**adaptation/engine.py — AdaptationDecision currently:**
```python
@dataclass
class AdaptationDecision:
    exercise_name: str
    previous_weight: float
    new_weight: float
    used_ml: bool
    ml_rpe: float | None
    ml_confidence: float | None
    fallback_reason: str | None
    # MISSING: source_label, anomaly_flag, core_weight_kg
```

**adaptation/explanation.py — ExplanationLayer.explain() current format:**
```
"{exercise}: {prev}кг → {new}кг ({reason}, ScienceEvidence v{version})"
```
Needs source_label incorporated.

**Current test baseline: 354 tests PASS.**

### Task 1: ScienceEvidence.md ml section to add

Add to `gym-coach-brain/ScienceEvidence.md` YAML frontmatter (after the `planning:` section):

```yaml
ml:
  confidence_threshold: 0.6        # float — MC Dropout confidence below which fallback triggers
  rpe_easy_threshold: 7.0          # float — RPE below this = spare capacity
  rpe_hard_threshold: 8.5          # float — RPE above this = near failure
  fatigue_lookback_sessions: 3     # int — recent sessions for fatigue estimate
  max_correction_percent: 0.15     # float — max ML delta as fraction of core weight (±15%)
  anomaly_rollback_threshold: 5    # int — consecutive anomalies before model rollback
  rpe_weight_sensitivity: 0.025    # float — weight change per RPE unit (~2.5% per RPE unit)
```

This ensures `ScienceConfig.ml` is fully populated from config, not hardcoded defaults.

### Task 2: FeatureVector Extension Implementation

```python
# In data/features.py — add 4 new fields to FeatureVector dataclass:
@dataclass
class FeatureVector:
    # ... existing 14 fields ...
    days_since_last_session: int
    # NEW Contract v3 §11 fields:
    sleep_hours: float              # from WorkoutSession.sleep_hours; fallback: 7.5
    pre_readiness: int              # from WorkoutSession.pre_readiness; fallback: 5
    workout_hour_sin: float         # sin(2π * hour / 24) from session_date; fallback: 0.0
    workout_hour_cos: float         # cos(2π * hour / 24) from session_date; fallback: 1.0
```

**build_feature_vector() extension — add at the end before return:**
```python
# ── Workout session check-in features (Contract v3 §11) ───────────────────────
from gym_coach_brain.data.models import WorkoutSession as WSModel
workout_session = session.get(WSModel, session_id)
if workout_session and workout_session.sleep_hours is not None:
    fv_sleep_hours = float(workout_session.sleep_hours)
else:
    fv_sleep_hours = 7.5  # cold start: average sleep

if workout_session and workout_session.pre_readiness is not None:
    fv_pre_readiness = int(workout_session.pre_readiness)
else:
    fv_pre_readiness = 5  # cold start: neutral readiness

# Cyclic time encoding from session_date
import math as _math
hour = 12  # cold start default: noon
if workout_session and workout_session.session_date:
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(workout_session.session_date)
        hour = dt.hour + dt.minute / 60.0
    except (ValueError, AttributeError):
        hour = 12
fv_sin = _math.sin(2 * _math.pi * hour / 24)
fv_cos = _math.cos(2 * _math.pi * hour / 24)
```

**Cold start fallbacks for new fields:**
- `sleep_hours` → `7.5` (average sleep, Contract v3 §10: 7–8h button = 7.5)
- `pre_readiness` → `5` (neutral readiness)
- `workout_hour_sin` → `0.0` (hour=12: sin(π) = 0)
- `workout_hour_cos` → `-1.0` (hour=12: cos(π) = -1)

Note: Use `0.0` and `-1.0` are the ACTUAL values for hour=12. Don't use arbitrary "0.0/1.0".

**test_features.py cold start test update** — must assert new fields are not None/NaN. The test `test_cold_start` needs updating to assert these fields too (or it will fail because FeatureVector now has 18 fields but the test only checks 14).

### Task 3: ml/constants.py Implementation

```python
"""
ML module constants — single source of truth for ML thresholds.

Import from here in ml/worker.py and ml/model.py.
Do NOT import from science.py in ml/ module (science is passed as parameter).
"""
from pathlib import Path

CONFIDENCE_THRESHOLD: float = 0.6       # MC Dropout confidence below which fallback triggers
DEFAULT_FINE_TUNE_THRESHOLD: int = 5    # sessions needed before FINE_TUNE job is enqueued
MC_DROPOUT_PASSES: int = 20             # number of forward passes for MC Dropout uncertainty
FEATURE_DIM: int = 19                   # 14 base + 4 new (sleep/readiness/time) + 1 fatigue

# Model weights storage directory (relative to package; override via env var in production)
_DEFAULT_MODEL_DIR = Path(__file__).parent.parent.parent.parent / "model_weights"
MODEL_DIR: Path = Path(__file__).parent.parent.parent.parent / "model_weights"
```

### Task 4: ml/model.py Implementation Guide

**Critical architecture rule: `import torch` ONLY inside methods, NEVER at module level.**

```python
"""
RPEModel — PyTorch MLP with MC Dropout uncertainty estimation.

Architecture: 2-layer MLP with dropout. MC Dropout provides confidence estimates
through N=20 forward passes with dropout active during inference.

Lazy torch import: all torch operations are inside methods to allow importing
this module in the main process without loading PyTorch.

References:
    [Source: _bmad-output/planning-artifacts/architecture.md#ML Architecture]
    [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Story 5.2]
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch
    import torch.nn as nn

from gym_coach_brain.ml.constants import CONFIDENCE_THRESHOLD, MC_DROPOUT_PASSES, FEATURE_DIM


# Canonical feature order — must match FeatureVector field declaration order
# Used by _features_to_tensor() for deterministic dict → tensor conversion
FEATURE_FIELD_ORDER = [
    "exercise_id", "movement_pattern_id", "primary_muscle_id",
    "is_compound", "stretch_mediated", "equipment_type_int",
    "set_number", "weight_kg", "reps",
    "historical_rpe", "avg_rpe_last_3_sessions_for_exercise",
    "sessions_count_for_exercise", "readiness_score", "days_since_last_session",
    # New Contract v3 §11 fields:
    "sleep_hours", "pre_readiness", "workout_hour_sin", "workout_hour_cos",
    # Added by AdaptationEngine._build_features():
    "muscle_group_fatigue_estimate",
]
# len(FEATURE_FIELD_ORDER) == FEATURE_DIM == 19


class RPEModel:
    """PyTorch MLP for RPE prediction with MC Dropout uncertainty estimation.

    Usage:
        model = RPEModel()                   # fresh model, random weights
        model.load(path)                     # load from file
        rpe, conf = model.predict(features)  # inference
    """

    def __init__(
        self,
        feature_dim: int = FEATURE_DIM,
        hidden_dims: list[int] | None = None,
        dropout_p: float = 0.3,
    ) -> None:
        if hidden_dims is None:
            hidden_dims = [64, 32]
        self._feature_dim = feature_dim
        self._hidden_dims = hidden_dims
        self._dropout_p = dropout_p
        self._network = None  # lazy init — avoids torch import at module level

    def _get_network(self) -> "nn.Module":
        """Lazily initialize PyTorch network on first use."""
        import torch
        import torch.nn as nn
        if self._network is None:
            layers: list[nn.Module] = []
            in_dim = self._feature_dim
            for h in self._hidden_dims:
                layers.extend([nn.Linear(in_dim, h), nn.ReLU(), nn.Dropout(p=self._dropout_p)])
                in_dim = h
            layers.append(nn.Linear(in_dim, 1))  # output: single RPE value
            self._network = nn.Sequential(*layers)
        return self._network

    def _features_to_tensor(self, features: dict) -> "torch.Tensor":
        """Convert feature dict to ordered float tensor."""
        import torch
        values = [float(features.get(key, 0.0)) for key in FEATURE_FIELD_ORDER]
        return torch.tensor(values, dtype=torch.float32).unsqueeze(0)  # shape: [1, feature_dim]

    def predict(self, features: dict) -> tuple[float, float]:
        """MC Dropout inference: N=20 passes → (mean_rpe, confidence_score).

        Model is kept in .train() mode to keep dropout active during inference.
        Returns:
            (predicted_rpe, confidence_score) — confidence = max(0, 1 - std(passes))
        """
        import torch
        net = self._get_network()
        net.train()  # keep dropout active for MC Dropout
        x = self._features_to_tensor(features)
        with torch.no_grad():
            passes = [net(x).item() for _ in range(MC_DROPOUT_PASSES)]
        mean_rpe = float(sum(passes) / len(passes))
        std_rpe = float(torch.tensor(passes).std().item())
        # Confidence: low variance = high confidence; clamp to [0, 1]
        confidence = max(0.0, min(1.0, 1.0 - std_rpe))
        # Clamp RPE to physiological range [1, 10]
        mean_rpe = max(1.0, min(10.0, mean_rpe))
        return mean_rpe, confidence

    def save(self, path: Path) -> None:
        """Save model weights to .pt file."""
        import torch
        net = self._get_network()
        torch.save(net.state_dict(), path)

    def load(self, path: Path) -> None:
        """Load model weights from .pt file."""
        import torch
        net = self._get_network()
        state_dict = torch.load(path, map_location="cpu")
        net.load_state_dict(state_dict)

    @property
    def network(self) -> "nn.Module":
        """Access underlying nn.Module (needed for EWC Fisher calculation)."""
        return self._get_network()

    @property
    def feature_dim(self) -> int:
        return self._feature_dim
```

### Task 5: ml/ewc.py Implementation Guide (~50 LOC)

```python
"""
EWC (Elastic Weight Consolidation) — catastrophic forgetting prevention.

Custom ~50 LOC implementation. No external ML dependencies beyond PyTorch.
Computes Fisher Information Matrix after fine-tuning to protect important weights.

References:
    Kirkpatrick et al. (2017) "Overcoming catastrophic forgetting in neural networks"
    [Source: _bmad-output/planning-artifacts/architecture.md#EWC: Custom Implementation]
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch
    import torch.nn as nn


class EWC:
    """Elastic Weight Consolidation regularizer for incremental fine-tuning.

    Usage:
        ewc = EWC(model, lambda_=100.0)
        ewc.update_fisher(training_data)    # after each fine-tuning
        loss = criterion(pred, target) + ewc.penalty(model)  # training loop
    """

    def __init__(self, model: "RPEModel", lambda_: float = 100.0) -> None:
        self._model = model
        self._lambda = lambda_
        self._fisher: dict = {}       # param_name → Fisher diagonal
        self._params_star: dict = {}  # param_name → optimal param values

    def update_fisher(self, dataset: list[dict]) -> None:
        """Compute Fisher Information Matrix diagonal from dataset.

        Fisher diagonal ≈ mean squared gradient per parameter.

        Args:
            dataset: list of feature dicts (same format as RPEModel.predict input)
        """
        import torch
        net = self._model.network
        net.train()
        self._params_star = {
            n: p.clone().detach()
            for n, p in net.named_parameters()
            if p.requires_grad
        }
        fisher = {n: torch.zeros_like(p) for n, p in net.named_parameters() if p.requires_grad}
        if not dataset:
            self._fisher = fisher
            return

        for features in dataset:
            net.zero_grad()
            x = self._model._features_to_tensor(features)
            output = net(x)
            # Use output as log-probability proxy: loss = -output (maximize RPE prediction)
            loss = -output.mean()
            loss.backward()
            for n, p in net.named_parameters():
                if p.requires_grad and p.grad is not None:
                    fisher[n] += p.grad.detach() ** 2

        n_samples = max(1, len(dataset))
        self._fisher = {n: f / n_samples for n, f in fisher.items()}

    def penalty(self, model: "RPEModel") -> "torch.Tensor":
        """Compute EWC regularization penalty.

        Penalizes deviation from optimal parameters, weighted by Fisher Information.
        Higher Fisher = parameter was more important = larger penalty for change.

        Returns:
            Scalar tensor — add to task loss during fine-tuning.
        """
        import torch
        if not self._fisher:
            return torch.tensor(0.0)

        loss = torch.tensor(0.0)
        net = model.network
        for n, p in net.named_parameters():
            if n in self._fisher and n in self._params_star:
                loss += (self._fisher[n] * (p - self._params_star[n]) ** 2).sum()
        return self._lambda * loss
```

### Task 7: AdaptationEngine Bounded Correction Implementation

**Updated AdaptationDecision dataclass:**
```python
@dataclass
class AdaptationDecision:
    exercise_name: str
    previous_weight: float
    new_weight: float
    used_ml: bool
    ml_rpe: float | None
    ml_confidence: float | None
    fallback_reason: str | None
    # Story 5.2 additions:
    source_label: str = "[ядро]"    # debug transparency label
    anomaly_flag: bool = False       # True if ML delta exceeded max_correction_percent
    core_weight_kg: float | None = None  # deterministic core weight (before ML)
```

**New standalone function to add to engine.py:**
```python
def rpe_to_weight(
    predicted_rpe: float,
    target_rpe: float,
    core_weight_kg: float,
    science: "ScienceConfig",
) -> float:
    """Convert predicted RPE to target weight kg via bounded sensitivity formula.

    Formula: ml_weight = core_weight * (1 - sensitivity * (predicted_rpe - target_rpe))

    If predicted_rpe < target_rpe → weight increases (athlete has capacity).
    If predicted_rpe > target_rpe → weight decreases (athlete near failure).
    The correction is THEN bounded by max_correction_percent in AdaptationEngine.

    Args:
        predicted_rpe: RPE predicted by ML model
        target_rpe: Target RPE for this exercise from plan
        core_weight_kg: Weight computed by deterministic core (before ML adjustment)
        science: ScienceConfig for rpe_weight_sensitivity

    Returns:
        Suggested weight in kg (before bounding/rounding).
    """
    delta_rpe = predicted_rpe - target_rpe
    return core_weight_kg * (1.0 - science.ml.rpe_weight_sensitivity * delta_rpe)
```

**Updated ML path in adapt() when db_prediction exists AND confidence >= threshold:**
```python
if db_prediction and db_prediction.confidence_score >= science.ml.confidence_threshold:
    used_ml = True
    ml_rpe = db_prediction.predicted_rpe
    ml_confidence = db_prediction.confidence_score

    # Compute deterministic core weight for bounded correction reference
    if previous_performance.has_completed_history:
        core_w, _ = _double_progression_recommendation(
            current_weight=previous_performance.current_weight,
            current_reps=previous_performance.current_reps,
            rep_range=rep_range,
            science=science,
            equipment_type=equipment_type,
            is_compound=is_compound,
            recovery_coeff=1.0,  # apply recovery AFTER bounding, not here
        )
    else:
        core_w = planned_weight  # no history → use planned weight as core reference

    # target_rpe: from planned exercise or midpoint of easy/hard thresholds
    target_rpe = float(planned_ex.get(
        "target_rpe",
        (science.ml.rpe_easy_threshold + science.ml.rpe_hard_threshold) / 2.0
    ))

    ml_w = rpe_to_weight(ml_rpe, target_rpe, core_w, science)

    # Bounded correction check (Contract v2 §6)
    delta_percent = abs(ml_w - core_w) / core_w if core_w > 0 else 0.0
    if delta_percent > science.ml.max_correction_percent:
        # Anomaly: delta exceeds limit → use core weight
        anomaly = True
        final_raw = core_w
        pct_str = f"{delta_percent * 100:.0f}"
        lim_str = f"{science.ml.max_correction_percent * 100:.0f}"
        source_label = f"[AI заблокирован: дельта {pct_str}% > {lim_str}% лимит]"
    else:
        # ML correction within bounds
        anomaly = False
        final_raw = ml_w
        delta_kg = ml_w - core_w
        sign_str = f"+{delta_kg:.1f}" if delta_kg >= 0 else f"{delta_kg:.1f}"
        conf_pct = int(ml_confidence * 100)
        source_label = f"[AI: {sign_str}кг / RPE прогноз: {ml_rpe:.1f} / confidence: {conf_pct}%]"

    new_weight = round_to_equipment_increment(
        final_raw * recovery_coeff, equipment_type, science
    )
    target_reps = _target_reps_for_ml(
        ml_rpe=ml_rpe,
        previous_performance=previous_performance,
        new_weight=new_weight,
        rep_range=rep_range,
        science=science,
    )
    ml_adjustment_kg = new_weight - core_w  # applied delta (0.0 if anomaly)

    # Update RPEPrediction record with bounded correction results
    db_prediction.core_weight_kg = core_w
    db_prediction.ml_weight_kg = float(ml_w)
    db_prediction.ml_adjustment_kg = float(ml_adjustment_kg) if not anomaly else 0.0
    db_prediction.anomaly_flag = anomaly
    db_prediction.source_label = source_label
    db_session.flush()  # write to DB within the existing session
```

**Fallback paths source_label (low confidence):**
```python
elif db_prediction:
    # confidence too low
    ml_confidence = db_prediction.confidence_score
    conf_pct = int(ml_confidence * 100)
    threshold_pct = int(science.ml.confidence_threshold * 100)
    source_label = f"[ядро: confidence {conf_pct}% < порога]"
    fallback_reason = f"confidence {ml_confidence:.2f} below threshold"
    # ... existing fallback logic ...
    db_prediction.source_label = source_label
    db_prediction.anomaly_flag = False
    db_session.flush()
```

**No prediction path:**
```python
else:
    source_label = "[ядро]"
    fallback_reason = "no rpe_model provided"
    # ... existing logic ...
```

### Task 8: ExplanationLayer Update

**New explain() format:**
```python
@staticmethod
def explain(decision: "AdaptationDecision", science: "ScienceConfig") -> str:
    version = science.version
    source_label = getattr(decision, "source_label", "[ядро]")
    return (
        f"{source_label} {decision.exercise_name}: "
        f"{decision.previous_weight:.1f}кг → {decision.new_weight:.1f}кг "
        f"(ScienceEvidence v{version})"
    )
```

This simplifies the explanation: the source_label already encodes the reason, so no separate reason string needed in the main text.

**Existing test_explanation.py must be updated** — the explanation format changed. Update assertions to match new format.

### Task 6: test_model.py Implementation Guide

```python
"""
Tests for ml/model.py — RPEModel (PyTorch MLP + MC Dropout) and ml/ewc.py (EWC).

These tests REQUIRE PyTorch to be installed (unlike test_worker.py which mocks it).
Run via: uv run pytest tests/test_ml/test_model.py -v
"""
import pytest
import math

# Mark entire module as requiring torch
pytestmark = pytest.mark.skipif(
    not _has_torch(), reason="PyTorch not installed"
)

def _has_torch() -> bool:
    try:
        import torch
        return True
    except ImportError:
        return False


@pytest.fixture
def model():
    from gym_coach_brain.ml.model import RPEModel
    return RPEModel(feature_dim=19, hidden_dims=[32, 16])


@pytest.fixture
def sample_features():
    """Valid 19-dim feature dict matching FEATURE_FIELD_ORDER."""
    from gym_coach_brain.ml.model import FEATURE_FIELD_ORDER
    return {key: 1.0 for key in FEATURE_FIELD_ORDER}  # all ones — valid input


def test_rpe_model_predict_returns_floats(model, sample_features):
    """predict() returns (float, float) tuple — both values are Python floats."""
    rpe, conf = model.predict(sample_features)
    assert isinstance(rpe, float)
    assert isinstance(conf, float)


def test_rpe_model_rpe_in_physiological_range(model, sample_features):
    """Predicted RPE is clamped to [1, 10]."""
    rpe, conf = model.predict(sample_features)
    assert 1.0 <= rpe <= 10.0


def test_rpe_model_confidence_in_unit_interval(model, sample_features):
    """Confidence score is in [0, 1]."""
    rpe, conf = model.predict(sample_features)
    assert 0.0 <= conf <= 1.0


def test_rpe_model_feature_dim(model, sample_features):
    """Model accepts 19-dim feature input without error."""
    # If this passes, feature dimensionality is correct
    assert model.feature_dim == 19
    rpe, conf = model.predict(sample_features)  # must not raise


def test_rpe_model_mc_dropout_variance(model, sample_features):
    """MC Dropout N=20 passes produce non-zero variance on random-init model."""
    # Run predict twice — should return slightly different values (dropout is stochastic)
    results = [model.predict(sample_features)[0] for _ in range(5)]
    # With dropout active, at least some variation is expected
    std_val = (sum((r - sum(results)/len(results))**2 for r in results) / len(results)) ** 0.5
    # Not all identical (would indicate dropout is disabled)
    assert not all(abs(r - results[0]) < 1e-9 for r in results), \
        "All predict() calls returned identical values — is dropout active?"


def test_ewc_penalty_is_tensor(model, sample_features):
    """EWC.penalty() returns a tensor (not None or scalar)."""
    import torch
    from gym_coach_brain.ml.ewc import EWC
    ewc = EWC(model)
    penalty = ewc.penalty(model)
    assert isinstance(penalty, torch.Tensor)


def test_ewc_penalty_nonzero_after_weight_change(model, sample_features):
    """After update_fisher, changing weights increases EWC penalty."""
    import torch
    from gym_coach_brain.ml.ewc import EWC
    ewc = EWC(model, lambda_=1000.0)
    ewc.update_fisher([sample_features, sample_features])  # compute Fisher

    penalty_before = ewc.penalty(model).item()

    # Perturb model weights significantly
    net = model.network
    with torch.no_grad():
        for p in net.parameters():
            p.add_(torch.ones_like(p) * 5.0)  # large perturbation

    penalty_after = ewc.penalty(model).item()
    assert penalty_after > penalty_before, \
        f"EWC penalty should increase after weight change: {penalty_before} → {penalty_after}"
```

### Task 9: test_engine.py Bounded Correction Tests

```python
# Add these tests to tests/test_adaptation/test_engine.py

def _make_rpe_prediction(db_session, session_id, exercise_id, predicted_rpe, confidence):
    """Helper: insert RPEPrediction for bounded correction tests."""
    from gym_coach_brain.data.models import RPEPrediction
    pred = RPEPrediction(
        session_id=session_id,
        exercise_id=exercise_id,
        predicted_rpe=predicted_rpe,
        confidence_score=confidence,
        model_version="test-v1",
    )
    db_session.add(pred)
    db_session.flush()
    return pred


def test_bounded_correction_within_limit(db_session, mock_science_config):
    """ML delta ≤ 15% of core weight → ML correction applied, source_label has [AI:."""
    # Setup: exercise with performance history, prediction with small RPE deviation
    exercise = _make_exercise(db_session)
    session = WorkoutSession(session_date="2026-03-09T10:00:00", status="active")
    db_session.add(session)
    db_session.flush()

    # Previous completed session: 100kg × 8 reps
    prev_session = WorkoutSession(session_date="2026-03-07T10:00:00", status="completed")
    db_session.add(prev_session)
    db_session.flush()
    prev_set = WorkoutSet(session_id=prev_session.id, exercise_id=exercise.id,
                          set_number=1, weight_kg=100.0, reps=8)
    db_session.add(prev_set)

    # Prediction: RPE=7.5 with 85% confidence — small correction, within 15% limit
    pred = _make_rpe_prediction(db_session, session.id, exercise.id,
                                predicted_rpe=7.5, confidence=0.85)
    db_session.commit()

    planned = json.dumps([{"exercise_id": exercise.id, "sets": 3,
                           "target_weight_kg": 100.0, "target_reps": 8}])
    session.planned_exercises = planned
    db_session.flush()

    user_profile = _make_user_profile()
    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user_profile, None, mock_science_config, db_session)

    assert len(result.exercises) == 1
    adapted = result.exercises[0]
    assert adapted.used_ml is True
    # source_label should start with [AI:
    db_session.refresh(pred)
    assert pred.source_label is not None
    assert "[AI:" in pred.source_label
    assert pred.anomaly_flag is False


def test_bounded_correction_exceeds_limit(db_session, mock_science_config):
    """ML delta > 15% of core weight → anomaly: core weight used, anomaly_flag=True."""
    exercise = _make_exercise(db_session)
    session = WorkoutSession(session_date="2026-03-09T10:00:00", status="active")
    db_session.add(session)
    db_session.flush()

    prev_session = WorkoutSession(session_date="2026-03-07T10:00:00", status="completed")
    db_session.add(prev_session)
    db_session.flush()
    prev_set = WorkoutSet(session_id=prev_session.id, exercise_id=exercise.id,
                          set_number=1, weight_kg=100.0, reps=8)
    db_session.add(prev_set)

    # Prediction: RPE=1.0 (extreme) → very large positive weight delta > 15%
    pred = _make_rpe_prediction(db_session, session.id, exercise.id,
                                predicted_rpe=1.0, confidence=0.9)
    db_session.commit()

    planned = json.dumps([{"exercise_id": exercise.id, "sets": 3,
                           "target_weight_kg": 100.0, "target_reps": 8}])
    session.planned_exercises = planned
    db_session.flush()

    user_profile = _make_user_profile()
    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user_profile, None, mock_science_config, db_session)

    db_session.refresh(pred)
    assert pred.anomaly_flag is True
    assert pred.source_label is not None
    assert "заблокирован" in pred.source_label


def test_bounded_correction_low_confidence(db_session, mock_science_config):
    """Confidence < 0.6 → fallback, source_label contains [ядро:, anomaly_flag=False."""
    exercise = _make_exercise(db_session)
    session = WorkoutSession(session_date="2026-03-09T10:00:00", status="active")
    db_session.add(session)
    db_session.flush()

    # Prediction with low confidence
    pred = _make_rpe_prediction(db_session, session.id, exercise.id,
                                predicted_rpe=7.5, confidence=0.3)
    db_session.commit()

    planned = json.dumps([{"exercise_id": exercise.id, "sets": 3,
                           "target_weight_kg": 80.0, "target_reps": 8}])
    session.planned_exercises = planned
    db_session.flush()

    user_profile = _make_user_profile()
    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user_profile, None, mock_science_config, db_session)

    assert len(result.exercises) == 1
    assert result.exercises[0].used_ml is False
    db_session.refresh(pred)
    assert pred.anomaly_flag is False
    assert pred.source_label is not None
    assert "[ядро:" in pred.source_label


def test_bounded_correction_no_prediction(db_session, mock_science_config):
    """No RPEPrediction in DB → source_label == '[ядро]' in AdaptationDecision."""
    exercise = _make_exercise(db_session)
    session = WorkoutSession(session_date="2026-03-09T10:00:00", status="active")
    db_session.add(session)
    db_session.flush()

    planned = json.dumps([{"exercise_id": exercise.id, "sets": 3,
                           "target_weight_kg": 80.0, "target_reps": 8}])
    session.planned_exercises = planned
    db_session.flush()
    db_session.commit()

    user_profile = _make_user_profile()
    engine = AdaptationEngine(rpe_model=None)
    result = engine.adapt(session, user_profile, None, mock_science_config, db_session)

    assert len(result.exercises) == 1
    # Check the explanation contains "[ядро]"
    explanation = result.exercises[0].explanation
    assert "[ядро]" in explanation
```

### Architecture Compliance Checklist

**MANDATORY rules — violation = CI failure:**
- [ ] `import torch` and `import torch.nn` ONLY inside methods (never module-level in `ml/model.py`)
- [ ] Same rule applies to `ml/ewc.py` — ALL torch inside methods
- [ ] `import torch` NEVER in `adaptation/engine.py`, `data/features.py`, or anywhere outside `ml/`
- [ ] `rpe_to_weight()` is a pure function (no DB access, no global state)
- [ ] `AdaptationDecision.source_label` always populated (never None) — default `"[ядро]"`
- [ ] `db_session.flush()` (not `commit()`) when updating RPEPrediction inside adapt() — caller manages transaction
- [ ] All new MLConfig fields must be present in `ScienceEvidence.md` YAML frontmatter (not just Pydantic defaults)
- [ ] FeatureVector field order in `FEATURE_FIELD_ORDER` constant MUST match `FeatureVector` dataclass declaration order

### Project Structure Notes

**New files:**
```
gym-coach-brain/src/gym_coach_brain/ml/
├── constants.py        ← NEW: CONFIDENCE_THRESHOLD, FEATURE_DIM, etc.
├── model.py            ← NEW: RPEModel class
└── ewc.py              ← NEW: EWC class

gym-coach-brain/tests/test_ml/
├── __init__.py         ← NEW: empty package init
└── test_model.py       ← NEW: RPEModel + EWC tests
```

**Modified files:**
```
gym-coach-brain/src/gym_coach_brain/
├── core/science.py                    ← add 3 fields to MLConfig
├── data/features.py                   ← add 4 fields to FeatureVector + build_feature_vector()
├── adaptation/engine.py               ← add rpe_to_weight(), extend AdaptationDecision, bounded correction
└── adaptation/explanation.py          ← update explain() format to include source_label

gym-coach-brain/
├── ScienceEvidence.md                  ← add ml: section to YAML frontmatter

gym-coach-brain/tests/
├── test_adaptation/test_engine.py      ← add 4 bounded correction tests
├── test_adaptation/test_explanation.py ← update explanation format assertions
└── test_data/test_features.py         ← update cold start test (new fields)
```

### Critical Anti-Patterns to Avoid

1. **`import torch` at module level** — will break main process which doesn't have GPU budget
2. **Hardcoded `max_correction_percent = 0.15`** — must come from `science.ml.max_correction_percent`
3. **Not flushing RPEPrediction updates** — must call `db_session.flush()` after updating prediction fields
4. **Wrong feature order in `FEATURE_FIELD_ORDER`** — must exactly match FeatureVector field declaration order (dataclasses preserve insertion order)
5. **Not preserving `_get_network()` lazy init** — calling `self._network = ...` in `__init__` would import torch at construction time
6. **test_model.py importing torch at module level** — wrap in `_has_torch()` or use `pytest.importorskip("torch")`

### References

- Epic 5 story definition: [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Story 5.2]
- Epic 5 Contract Snapshot v1/v2/v3: [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#Planning Alignment Addendum]
- Bounded Correction Contract (§6): [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#6. Bounded Correction Contract]
- Debug Transparency Contract (§7): [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#7. Debug Transparency Contract]
- Extended Feature Contract (§11): [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#11. Extended Feature Contract]
- rpe_to_weight() Contract (§14): [Source: _bmad-output/planning-artifacts/epics/epic-5-ai.md#14. rpe_to_weight() Contract]
- ML Architecture (MLP + MC Dropout): [Source: _bmad-output/planning-artifacts/architecture.md#ML Architecture]
- Lazy PyTorch Import: [Source: _bmad-output/planning-artifacts/architecture.md#Lazy PyTorch Import]
- Class Separation in ML module: [Source: _bmad-output/planning-artifacts/architecture.md#Class Separation in ML module]
- ML constants.py: [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns → ML-specific]
- RPEModel interface: [Source: gym-coach-brain/src/gym_coach_brain/ml/interface.py]
- RPEPrediction model fields: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#RPEPrediction]
- WorkoutSession sleep/readiness fields: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#WorkoutSession]
- Current MLConfig: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py#MLConfig]
- Current FeatureVector: [Source: gym-coach-brain/src/gym_coach_brain/data/features.py]
- Current AdaptationEngine: [Source: gym-coach-brain/src/gym_coach_brain/adaptation/engine.py]
- Current ExplanationLayer: [Source: gym-coach-brain/src/gym_coach_brain/adaptation/explanation.py]
- Previous story learnings (5.1): [Source: _bmad-output/implementation-artifacts/5-1-ml-data-layer.md#Completion Notes List]
- Test fixture pattern: [Source: gym-coach-brain/tests/conftest.py]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (create-story)

### Debug Log References

- `uv run pytest tests/test_data/test_features.py tests/test_ml/test_model.py`
- `uv run pytest tests/test_adaptation/test_explanation.py tests/test_adaptation/test_engine.py`
- `uv run pytest`
- `uv run python -m gym_coach_brain.data.validate_features`

### Completion Notes List

- Added the new `MLConfig` safety controls and synced them into `ScienceEvidence.md`, the feature validator, and the ML feature spec so the bounded-correction path is fully config-driven.
- Expanded `FeatureVector` from 14 to 18 base fields with cold-start defaults for `sleep_hours`, `pre_readiness`, and cyclic workout-hour encoding; `AdaptationEngine` now appends `muscle_group_fatigue_estimate` for a 19-field payload.
- Added `ml/constants.py`, `ml/model.py`, and `ml/ewc.py` with lazy in-method PyTorch imports, MC Dropout inference, save/load support, and EWC regularization helpers.
- Reworked `AdaptationEngine` to compute deterministic core weight first, apply bounded ML correction via `rpe_to_weight()`, emit `source_label` on every path, and flush `RPEPrediction` transparency fields without committing the caller transaction.
- Updated explanation and adaptation tests for the new source-label format and bounded-correction cases; full repo validation passed.

### File List

- `gym-coach-brain/ScienceEvidence.md`
- `gym-coach-brain/src/gym_coach_brain/core/science.py`
- `gym-coach-brain/src/gym_coach_brain/data/features.py`
- `gym-coach-brain/src/gym_coach_brain/data/validate_features.py`
- `gym-coach-brain/src/gym_coach_brain/ml/interface.py`
- `gym-coach-brain/src/gym_coach_brain/ml/constants.py`
- `gym-coach-brain/src/gym_coach_brain/ml/model.py`
- `gym-coach-brain/src/gym_coach_brain/ml/ewc.py`
- `gym-coach-brain/src/gym_coach_brain/adaptation/engine.py`
- `gym-coach-brain/src/gym_coach_brain/adaptation/explanation.py`
- `gym-coach-brain/tests/conftest.py`
- `gym-coach-brain/tests/test_data/test_features.py`
- `gym-coach-brain/tests/test_ml/__init__.py`
- `gym-coach-brain/tests/test_ml/test_model.py`
- `gym-coach-brain/tests/test_adaptation/test_explanation.py`
- `gym-coach-brain/tests/test_adaptation/test_engine.py`
- `docs/ml-feature-spec.md`

## Review Follow-ups (AI)
- [x] [High] Fixed timezone naive datetime subtraction in `data/features.py` that caused `days_since_last_session` to always fall back to 0.
- [x] [Medium] Renamed internal forward method to `_forward` and prediction to `forward` in `RPEModel` to match interface requested in AC 1.
- [x] [Low] Optimized EWC penalty loop to use a list and `sum()` instead of accumulating in a tensor via iteration.

## Change Log

- 2026-03-09: Story 5.2 created via create-story workflow. Comprehensive context engine analysis completed.
- 2026-03-09: Implemented PyTorch RPE model, EWC, 19-feature payload, bounded ML correction, and validation coverage; story moved to review.
- 2026-03-09: [AI Review] Addressed finding regarding datetime operations, corrected model interface, and applied minor performance optimizations.

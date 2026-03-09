# Story 4.5: Adaptation Engine и Explanation Layer

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an athlete,
I want the system to produce an adapted workout plan with scientific justification for each decision,
so that I understand why specific weights and reps are assigned to me.

## Acceptance Criteria

**Given** алгоритмы из Stories 4.1-4.4 и `ScienceConfig` доступны
**When** `AdaptationEngine.adapt(session, user_profile, recovery_signal, science, db_session)` вызывается
**Then** возвращается `AdaptationResult` с адаптированными весами и повторениями для каждого упражнения

**And** при `confidence < science.ml.confidence_threshold` или отсутствии ML-предсказания — автоматический fallback на Double Progression (`calculate_double_progression`); это штатный режим, НЕ exception; порог берётся из `ScienceConfig.ml.confidence_threshold` (не hardcoded)

**And** `ExplanationLayer.explain(decision, science)` возвращает текстовое обоснование со ссылкой на `science.version`

**And** каждое изменение веса сопровождается обоснованием через `ExplanationLayer`

**And** `AdaptationEngine` принимает `rpe_model` как параметр конструктора (duck typing / `RPEModelProtocol` из `ml/interface.py`) — не импортирует `RPEModel` напрямую, обеспечивая изоляцию от PyTorch в Epic 4

**And** `ml/interface.py` создаётся в этой истории: `class RPEModelProtocol(Protocol): def predict(self, features) -> tuple[float, float]: ...`

**And** рекомендация веса вызывает `core.weight_utils.round_to_equipment_increment(weight, equipment_type)` перед возвратом — итоговый вес всегда кратен шагу оборудования (barbell: 2.5кг, dumbbell: 1.0кг, machine: 5.0кг, cable: 2.5кг)

**And** `AdaptationEngine` детектирует плато: если для `exercise_id` за последние `science.plateau_detection_sessions` сессий нет роста ни по весу ни по объёму (reps × sets) — в `AdaptationResult.plateau_warnings` добавляется `"📊 Плато [N] сессий — попробуй другое упражнение или измени диапазон повторений"`; решение остаётся за атлетом/агентом

**And** `ScienceEvidence.md` расширяется секцией `ml.confidence_threshold` и полем `plateau_detection_sessions`; `core/science.py` расширяется `MLConfig(BaseModel)` и полем `plateau_detection_sessions: int`

**And** `tests/conftest.py` обновляется: добавляется `mock_rpe_model` fixture (Mock с `predict() -> (7.5, 0.85)`) и `ml`/`plateau_detection_sessions` поля в `mock_science_config`

**And** `pytest tests/test_adaptation/test_engine.py` и `tests/test_adaptation/test_explanation.py` проходят с `mock_science_config` и `mock_rpe_model`:
- weight округляется корректно для barbell (2.5кг) и dumbbell (1.0кг)
- плато из N одинаковых сессий → предупреждение в `plateau_warnings`
- прогресс за последние N сессий → `plateau_warnings` пуст
- `confidence < threshold` → `used_ml=False`, Double Progression применён
- `confidence >= threshold` → `used_ml=True`

## Tasks / Subtasks

- [x] **Расширить `ScienceEvidence.md`** (AC: ml.confidence_threshold + plateau_detection_sessions)
  - [x] Добавить секцию `ml:` с `confidence_threshold: 0.6`
  - [x] Добавить `plateau_detection_sessions: 3` на верхний уровень
  - [x] Проверить, что `uv run python -c "from gym_coach_brain.core.science import load_science_config; load_science_config()"` работает

- [x] **Расширить `core/science.py`** (AC: MLConfig, plateau_detection_sessions)
  - [x] Добавить `class MLConfig(BaseModel)` с `confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)`
  - [x] Добавить поле `ml: MLConfig = Field(default_factory=MLConfig)` в `ScienceConfig`
  - [x] Добавить поле `plateau_detection_sessions: int = Field(default=3, ge=1)` в `ScienceConfig`
  - [x] Убедиться, что старые тесты (`test_core/test_science.py`) по-прежнему PASS

- [x] **Обновить `tests/conftest.py`** (AC: mock_rpe_model fixture, обновлённый mock_science_config)
  - [x] Добавить `from unittest.mock import Mock` к существующим импортам
  - [x] Добавить `ml=MLConfig(confidence_threshold=0.6)` и `plateau_detection_sessions=3` в `mock_science_config`
  - [x] Добавить `@pytest.fixture def mock_rpe_model()` → `Mock` с `predict.return_value = (7.5, 0.85)`

- [x] **Создать `ml/interface.py`** (AC: RPEModelProtocol)
  - [x] Определить `class RPEModelProtocol(Protocol)` из `typing`
  - [x] Метод `predict(self, features: dict) -> tuple[float, float]`: (predicted_rpe, confidence_score)
  - [x] Добавить docstring with описанием duck typing назначения
  - [x] НЕ импортировать torch — это чистый Protocol

- [x] **Создать `adaptation/engine.py`** (AC: AdaptationEngine, AdaptationResult, AdaptedExercise)
  - [x] Определить `@dataclass class AdaptedExercise`: exercise_id, exercise_name, sets, rep_range, target_reps, target_weight_kg, explanation, used_ml
  - [x] Определить `@dataclass class AdaptationResult`: exercises, science_version, plateau_warnings
  - [x] Определить `@dataclass class AdaptationDecision` (передаётся в ExplanationLayer)
  - [x] Реализовать `class AdaptationEngine`:
    - [x] `__init__(self, rpe_model: RPEModelProtocol | None = None)`
    - [x] `adapt(self, session, user_profile, recovery_signal, science, db_session) -> AdaptationResult`
  - [x] В `adapt()`: вызвать `select_methodology(user_profile, science)` для получения `Methodology`
  - [x] В `adapt()`: для каждого упражнения в `session.planned_exercises` (JSON list):
    - [x] Попытаться получить `RPEPrediction` из DB для `session.id` и `exercise_id`
    - [x] Если `rpe_model` есть и `confidence >= science.ml.confidence_threshold` → ML путь
    - [x] Иначе → вызвать `calculate_double_progression()` (fallback)
    - [x] Применить `round_to_equipment_increment(weight, equipment_type, science)`
    - [x] Создать `AdaptationDecision` и вызвать `ExplanationLayer.explain(decision, science)`
  - [x] Плато-детекция: запросить последние `science.plateau_detection_sessions` сессий для каждого `exercise_id`; если нет роста (вес и reps×sets не изменились) → добавить в `plateau_warnings`
  - [x] Вернуть `AdaptationResult(exercises=..., science_version=science.version, plateau_warnings=...)`

- [x] **Создать `adaptation/explanation.py`** (AC: ExplanationLayer.explain)
  - [x] Реализовать `class ExplanationLayer` со статическим методом `explain(decision, science) -> str`
  - [x] Формат объяснения: `"{exercise}: {prev_weight}кг → {new_weight}кг ({reason}, ScienceEvidence v{version})"`
  - [x] `reason` для ML пути: `"ML RPE {rpe:.1f}, уверенность {conf:.2f}"`
  - [x] `reason` для Double Progression: `"Double Progression"`

- [x] **Создать `tests/test_adaptation/__init__.py`** (пустой файл)

- [x] **Создать `tests/test_adaptation/test_engine.py`** (AC: все AC-тесты для engine)
  - [x] `test_barbell_weight_rounded_to_2_5kg` — barbell → кратно 2.5кг
  - [x] `test_dumbbell_weight_rounded_to_1kg` — dumbbell → кратно 1.0кг
  - [x] `test_plateau_detected_after_n_identical_sessions` — N одинаковых → plateau_warnings непуст
  - [x] `test_no_plateau_when_weight_increases` — рост веса → plateau_warnings пуст
  - [x] `test_no_plateau_when_volume_increases` — рост volume (reps×sets) → plateau_warnings пуст
  - [x] `test_low_confidence_triggers_double_progression_fallback` — confidence < threshold → used_ml=False
  - [x] `test_high_confidence_uses_ml_prediction` — confidence >= threshold → used_ml=True
  - [x] `test_no_rpe_model_uses_double_progression` — rpe_model=None → used_ml=False для всех
  - [x] `test_science_version_in_result` — AdaptationResult.science_version == science.version

- [x] **Создать `tests/test_adaptation/test_explanation.py`** (AC: ExplanationLayer)
  - [x] `test_explanation_includes_science_version` — строка содержит `science.version`
  - [x] `test_explanation_ml_path_includes_rpe_and_confidence` — ML путь: "ML RPE" в объяснении
  - [x] `test_explanation_fallback_path_mentions_double_progression` — fallback: "Double Progression"
  - [x] `test_explanation_shows_weight_change` — prev и new weight в строке

- [x] **Регрессионная проверка:**
  - [x] `uv run pytest -v` — полная регрессия PASS (267 passed)

### Review Follow-ups (AI)

- [x] [AI-Review][CRITICAL] Missing mandatory `loguru` logging for ML fallbacks (Requirement violation) [adaptation/engine.py]
- [x] [AI-Review][CRITICAL] Plateau detection logic is too strict (requires exact equality) and ignores regressions [adaptation/engine.py:_is_plateau]
- [x] [AI-Review][MEDIUM] Hardcoded RPE adjustment thresholds (7.0, 8.5) should be moved to ScienceConfig [adaptation/engine.py:_adjust_weight_by_rpe]
- [x] [AI-Review][MEDIUM] Performance: _is_plateau fetches entire exercise history into memory [adaptation/engine.py:_is_plateau]
- [x] [AI-Review][MEDIUM] Missing error handling for json.loads of planned_exercises [adaptation/engine.py:adapt]
- [x] [AI-Review][LOW] Mixed languages in end-user explanation strings (Russian/English) [adaptation/explanation.py]
- [x] [AI-Review][LOW] Fallback progression assumes successful step even if planner already handled it [adaptation/engine.py:_double_progression_weight]
- [x] [AI-Review][HIGH] DB prediction selection is nondeterministic: `query(RPEPrediction)...first()` can pick an older low-confidence row and ignore a newer high-confidence prediction for the same `(session_id, exercise_id)` [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:157]
- [x] [AI-Review][HIGH] Double Progression fallback is not based on actual previous performance: `_double_progression_weight()` hardcodes `current_reps=rep_range[1]`, so fallback always advances load even when the last completed session did not hit rep max [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:279]
- [x] [AI-Review][HIGH] AC gap: `AdaptationResult` does not expose adapted repetitions per exercise, only `rep_range`; the story requires adapted weights and reps for each exercise [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:48]
- [x] [AI-Review][MEDIUM] Direct `rpe_model.predict()` path uses placeholder features (`historical_rpe`, `readiness_score`, `days_since_last_session`, fatigue) instead of real session/user history, reducing prediction quality and bypassing available recovery context [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:307]
- [x] [AI-Review][CRITICAL] Fix "Double Adaptation Bug": prevent reactive progression on planned values when history is missing [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:155]
- [x] [AI-Review][HIGH] Add "muscle_group_fatigue_estimate" to RPEModelProtocol features passed in engine.py [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:228]
- [x] [AI-Review][MEDIUM] Fetch canonical exercise name from DB for ExplanationLayer to avoid UI typos [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:192]
- [x] [AI-Review][MEDIUM] Re-evaluate "working weight" logic in _get_previous_performance for pyramid sets [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:270]
- [x] [AI-Review][LOW] Replace deprecated datetime.utcnow() with datetime.now(datetime.UTC) [gym-coach-brain/src/gym_coach_brain/data/features.py:177]
- [x] [AI-Review][LOW] Remove redundant sorting in _get_previous_performance subquery [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:246]
- [x] [AI-Review][MEDIUM] `_estimate_muscle_group_fatigue` uses `min_rest_days_per_muscle_group` (a rest-days value) as a session count for fatigue lookback — semantic mismatch; introduce `fatigue_lookback_sessions` in `MLConfig` or `PlanningConfig` [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:621]
- [x] [AI-Review][MEDIUM] `test_barbell_weight_rounded_to_2_5kg` doesn't exercise rounding: planned weight 80.0 is already a valid barbell multiple and returned unchanged with no history; use a non-multiple planned weight (e.g. 79.3) to actually verify rounding [gym-coach-brain/tests/test_adaptation/test_engine.py:122]
- [x] [AI-Review][LOW] Dead-code defensive `getattr` in `ExplanationLayer.explain()`: `getattr(science.ml, "confidence_threshold", 0.6)` hardcodes a fallback that can silently diverge from `MLConfig` default; replace with `science.ml.confidence_threshold` [gym-coach-brain/src/gym_coach_brain/adaptation/explanation.py:64]
- [x] [AI-Review][LOW] `_build_features()` always passes `set_number=1` in the direct ML path; for pyramid sessions this reduces feature quality since fatigue increases with each set [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:427]
- [x] [AI-Review][LOW] Recovery coefficient ignored when `has_completed_history=False`: `_fallback_recommendation` returns `planned_weight` without applying `recovery_coeff`, inconsistent with all other adaptation paths [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:398]
- [x] [AI-Review][LOW] No test verifies that `recovery_coeff` scales the final adapted weight in the ML path; `test_direct_ml_path_uses_real_feature_vector_context` only checks `readiness_score` in features, not the `adjusted_weight * recovery_coeff` output [gym-coach-brain/tests/test_adaptation/test_engine.py:430]
- [x] [AI-Review][HIGH] Discrepancy between Epic 4 and Story 4.5: Epic says "machine: no rounding", Story says "machine: 5.0kg". Verify which is scientifically correct for the equipment catalog. [_bmad-output/implementation-artifacts/4-5-adaptation-engine.md]
- [x] [AI-Review][LOW] Nondeterministic plateau detection: `_is_plateau` needs `id.desc()` secondary sort for same-day sessions to ensure the "most recent" session is actually the last one. [gym-coach-brain/src/gym_coach_brain/adaptation/engine.py:596]
- [x] [AI-Review][LOW] Language mix: the "technical terms" exception for language parity should be fixed to pure Russian in end-user strings or explicitly justified in the dev notes. [gym-coach-brain/src/gym_coach_brain/adaptation/explanation.py]

## Dev Notes

### ⚠️ Критический Prerequisite: Story 4.4 должна быть реализована ПЕРВОЙ

Story 4.5 **зависит** от `core/methodology.py` из Story 4.4:
```python
from gym_coach_brain.core.methodology import select_methodology, Methodology, RepRange, ProgressionType
```

Проверить наличие перед началом:
```bash
cd gym-coach-brain
ls src/gym_coach_brain/core/methodology.py  # должен существовать
uv run pytest tests/test_core/test_methodology.py -v  # должен PASS
```

---

### Шаг 1: Расширение `ScienceEvidence.md` и `core/science.py`

Добавить в `ScienceEvidence.md` YAML-frontmatter (после секции `planning:`):

```yaml
ml:
  confidence_threshold: 0.6   # float — MC Dropout confidence below which fallback to Double Progression (architecture ADR-001)

plateau_detection_sessions: 3  # int — number of consecutive sessions without progress to trigger plateau warning
```

Добавить в `core/science.py` (после `PlanningConfig`):

```python
class MLConfig(BaseModel):
    """ML thresholds for Adaptation Engine.

    confidence_threshold: MC Dropout confidence score below which the
        Adaptation Engine falls back to Double Progression instead of using
        the ML RPE prediction. Architecture ADR-001.
    """
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
```

Обновить `ScienceConfig`:
```python
class ScienceConfig(BaseModel):
    # ... существующие поля ...
    ml: MLConfig = Field(default_factory=MLConfig)
    plateau_detection_sessions: int = Field(default=3, ge=1)
```

**Важно:** `default_factory=MLConfig` означает, что существующий `mock_science_config` без секции `ml:` продолжит работать (backward-compatible default). Но для явности — обновить `conftest.py`.

[Source: gym-coach-brain/src/gym_coach_brain/core/science.py#ScienceConfig]
[Source: gym-coach-brain/ScienceEvidence.md#YAML frontmatter]

---

### Шаг 2: Обновление `tests/conftest.py`

Текущий `conftest.py` импортирует из `core/science`:
```python
from gym_coach_brain.core.science import (
    ScienceConfig, PUOSConfig, ProgressionConfig, RecoveryConfig,
    MethodologySpec, MethodologiesConfig, PlanningConfig,
)
```

После обновления добавить `MLConfig` в импорты и обновить `mock_science_config`:
```python
from gym_coach_brain.core.science import (
    ScienceConfig, PUOSConfig, ProgressionConfig, RecoveryConfig,
    MethodologySpec, MethodologiesConfig, PlanningConfig, MLConfig,  # добавить MLConfig
)
```

Дополнить `mock_science_config` fixture:
```python
return ScienceConfig(
    # ... все существующие поля ...
    ml=MLConfig(confidence_threshold=0.6),
    plateau_detection_sessions=3,
)
```

Добавить `mock_rpe_model` fixture:
```python
from unittest.mock import Mock

@pytest.fixture
def mock_rpe_model():
    """Mock RPEModelProtocol for unit tests — no PyTorch required.

    Returns (predicted_rpe=7.5, confidence_score=0.85) — confident prediction
    above the default threshold of 0.6.
    """
    model = Mock()
    model.predict.return_value = (7.5, 0.85)
    return model
```

[Source: gym-coach-brain/tests/conftest.py]
[Source: _bmad-output/planning-artifacts/architecture.md#Test Fixtures]

---

### Шаг 3: `ml/interface.py` — RPEModelProtocol

```python
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
```

[Source: _bmad-output/planning-artifacts/architecture.md#ML Architecture]
[Source: docs/ml-feature-spec.md]

---

### Шаг 4: Полная реализация `adaptation/engine.py`

```python
"""
Adaptation Engine — coordinates ML predictions with deterministic fallback.

Reads RPE predictions from DB (produced by MLWorker), applies confidence
threshold, falls back to Double Progression when ML is unavailable/uncertain.
Detects training plateaus and includes weight rounding.

Architecture:
    - ADR-001: ML Layer Isolation (RPEModelProtocol, no direct torch import)
    - ADR-002: ScienceConfig as parameter (never module-level global)
    - Dependency: api → adaptation → core → data (no reverse deps)

References:
    [Source: _bmad-output/planning-artifacts/architecture.md#Adaptation Engine]
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.5]
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import UserProfile, WorkoutSession
    from gym_coach_brain.core.readiness import RecoverySignal
    from gym_coach_brain.ml.interface import RPEModelProtocol


# ─── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class AdaptationDecision:
    """Structured decision record passed to ExplanationLayer."""
    exercise_name: str
    previous_weight: float
    new_weight: float
    used_ml: bool
    ml_rpe: float | None
    ml_confidence: float | None
    fallback_reason: str | None  # e.g. "confidence below threshold", "no prediction"


@dataclass
class AdaptedExercise:
    """Single exercise in the adapted plan."""
    exercise_id: int
    exercise_name: str
    sets: int
    rep_range: tuple[int, int]        # (min, max)
    target_weight_kg: float
    explanation: str                   # from ExplanationLayer.explain()
    used_ml: bool


@dataclass
class AdaptationResult:
    """Full adapted workout plan for a session."""
    exercises: list[AdaptedExercise]
    science_version: str               # science.version — traceability
    plateau_warnings: list[str] = field(default_factory=list)


# ─── Engine ───────────────────────────────────────────────────────────────────

class AdaptationEngine:
    """Coordinates ML predictions with deterministic fallback.

    Accepts rpe_model via constructor (duck typing). When rpe_model is None
    or returns low-confidence predictions, falls back to Double Progression.
    No direct PyTorch import — uses RPEModelProtocol interface.

    Usage:
        engine = AdaptationEngine(rpe_model=None)  # deterministic only
        engine = AdaptationEngine(rpe_model=some_rpe_model)  # with ML

        result = engine.adapt(session, user_profile, recovery_signal, science, db_session)
    """

    def __init__(self, rpe_model: "RPEModelProtocol | None" = None) -> None:
        self._rpe_model = rpe_model

    def adapt(
        self,
        session: "WorkoutSession",
        user_profile: "UserProfile",
        recovery_signal: "RecoverySignal | None",
        science: "ScienceConfig",
        db_session: "SASession",
    ) -> AdaptationResult:
        """Produce an adapted workout plan from a planned session.

        For each exercise in session.planned_exercises:
          1. Attempt ML RPE prediction (via rpe_predictions table or rpe_model)
          2. If confidence >= science.ml.confidence_threshold: use ML
          3. Otherwise: call calculate_double_progression() (deterministic fallback)
          4. Apply round_to_equipment_increment(weight, equipment_type, science) on all weights
          5. Generate explanation via ExplanationLayer

        Then check plateau for each exercise across last science.plateau_detection_sessions.

        Args:
            session: WorkoutSession ORM object with planned_exercises JSON
            user_profile: UserProfile ORM object (goal, equipment, etc.)
            recovery_signal: RecoverySignal or None (coefficient 0-1)
            science: ScienceConfig (passed at startup, never a module global)
            db_session: SQLAlchemy Session for DB reads

        Returns:
            AdaptationResult with exercises, science_version, plateau_warnings
        """
        from gym_coach_brain.adaptation.explanation import ExplanationLayer
        from gym_coach_brain.core.methodology import select_methodology
        from gym_coach_brain.core.progression import calculate_double_progression
        from gym_coach_brain.core.weight_utils import round_to_equipment_increment
        from gym_coach_brain.data.models import RPEPrediction, WorkoutSet, Exercise, EquipmentType

        methodology = select_methodology(user_profile, science)
        rep_range = (methodology.rep_range.min, methodology.rep_range.max)

        planned = json.loads(session.planned_exercises or "[]")
        adapted_exercises: list[AdaptedExercise] = []
        plateau_warnings: list[str] = []

        recovery_coeff = recovery_signal.coefficient if recovery_signal is not None else 1.0

        for planned_ex in planned:
            exercise_id = planned_ex["exercise_id"]
            exercise_name = planned_ex["exercise_name"]
            sets = planned_ex.get("sets", 3)
            last_weight = planned_ex.get("target_weight_kg", 0.0)

            # Retrieve exercise metadata for equipment type
            exercise = db_session.query(Exercise).filter_by(id=exercise_id).first()
            equipment_type = (
                EquipmentType(exercise.equipment_type) if exercise else EquipmentType.barbell
            )
            is_compound = exercise.is_compound if exercise else True

            # ── ML path ──────────────────────────────────────────────────────
            used_ml = False
            ml_rpe: float | None = None
            ml_confidence: float | None = None
            fallback_reason: str | None = None

            # Check rpe_predictions table first (populated by MLWorker async)
            db_prediction = (
                db_session.query(RPEPrediction)
                .filter_by(session_id=session.id, exercise_id=exercise_id)
                .first()
            )
            if db_prediction and db_prediction.confidence_score >= science.ml.confidence_threshold:
                used_ml = True
                ml_rpe = db_prediction.predicted_rpe
                ml_confidence = db_prediction.confidence_score
                # Adjust weight based on predicted RPE (high RPE → hold weight; low RPE → advance)
                adjusted_weight = _adjust_weight_by_rpe(
                    ml_rpe, last_weight, science, is_compound
                )
                new_weight = round_to_equipment_increment(adjusted_weight * recovery_coeff, equipment_type, science)
            elif self._rpe_model is not None:
                # Fallback to direct model call (e.g., in-process during session)
                features = _build_features(exercise_id, last_weight, db_session)
                rpe_pred, conf = self._rpe_model.predict(features)
                if conf >= science.ml.confidence_threshold:
                    used_ml = True
                    ml_rpe = rpe_pred
                    ml_confidence = conf
                    adjusted_weight = _adjust_weight_by_rpe(rpe_pred, last_weight, science, is_compound)
                    new_weight = round_to_equipment_increment(adjusted_weight * recovery_coeff, equipment_type, science)
                else:
                    fallback_reason = f"confidence {conf:.2f} below threshold {science.ml.confidence_threshold}"
                    new_weight = _double_progression_weight(
                        last_weight, rep_range, science, equipment_type, is_compound, recovery_coeff
                    )
                    new_weight = round_to_equipment_increment(new_weight, equipment_type, science)
            else:
                # No ML available — pure deterministic
                fallback_reason = "no rpe_model provided"
                new_weight = _double_progression_weight(
                    last_weight, rep_range, science, equipment_type, is_compound, recovery_coeff
                )
                new_weight = round_to_equipment_increment(new_weight, equipment_type, science)

            decision = AdaptationDecision(
                exercise_name=exercise_name,
                previous_weight=last_weight,
                new_weight=new_weight,
                used_ml=used_ml,
                ml_rpe=ml_rpe,
                ml_confidence=ml_confidence,
                fallback_reason=fallback_reason,
            )
            explanation = ExplanationLayer.explain(decision, science)

            adapted_exercises.append(AdaptedExercise(
                exercise_id=exercise_id,
                exercise_name=exercise_name,
                sets=sets,
                rep_range=rep_range,
                target_weight_kg=new_weight,
                explanation=explanation,
                used_ml=used_ml,
            ))

            # ── Plateau detection ─────────────────────────────────────────────
            if _is_plateau(exercise_id, science.plateau_detection_sessions, db_session):
                n = science.plateau_detection_sessions
                plateau_warnings.append(
                    f"📊 Плато {n} сессий [{exercise_name}] — попробуй другое упражнение или измени диапазон повторений"
                )

        return AdaptationResult(
            exercises=adapted_exercises,
            science_version=science.version,
            plateau_warnings=plateau_warnings,
        )


# ─── Private Helpers ──────────────────────────────────────────────────────────

def _adjust_weight_by_rpe(
    predicted_rpe: float,
    current_weight: float,
    science: "ScienceConfig",
    is_compound: bool,
) -> float:
    """Adjust weight based on ML-predicted RPE.

    RPE < 7: athlete has capacity → increment weight (Double Progression step)
    RPE 7-8.5: on target → keep weight
    RPE > 8.5: close to failure → hold or decrease by isolation increment
    """
    increment = (
        science.progression.compound_increment_kg if is_compound
        else science.progression.isolation_increment_kg
    )
    if predicted_rpe < 7.0:
        return current_weight + increment
    elif predicted_rpe > 8.5:
        return max(0.0, current_weight - increment)
    return current_weight


def _double_progression_weight(
    last_weight: float,
    rep_range: tuple[int, int],
    science: "ScienceConfig",
    equipment_type: "EquipmentType",
    is_compound: bool,
    recovery_coeff: float,
) -> float:
    """Compute next-session weight via Double Progression then apply recovery scaling."""
    from gym_coach_brain.core.progression import calculate_double_progression
    # Use rep_max as current_reps to trigger weight progression (conservative assumption)
    result = calculate_double_progression(
        current_reps=rep_range[1],
        current_weight=last_weight,
        rep_range=rep_range,
        science=science,
        equipment_type=equipment_type,
        is_compound=is_compound,
    )
    return result.new_weight * recovery_coeff


def _build_features(
    exercise_id: int,
    last_weight: float,
    db_session: "SASession",
) -> dict:
    """Build feature dict for RPEModelProtocol.predict()."""
    return {
        "exercise_id": exercise_id,
        "weight": last_weight,
        "set_number": 1,
        "reps": 0,
        "historical_rpe": 0.0,
        "readiness_score": 1.0,
        "days_since_last_session": 0,
        "muscle_group_fatigue_estimate": 0.0,
    }


def _is_plateau(
    exercise_id: int,
    n_sessions: int,
    db_session: "SASession",
) -> bool:
    """Return True if no weight or volume growth in last n_sessions for exercise_id.

    Plateau = same or decreasing (weight AND volume) across all N sessions.
    If fewer than n_sessions of data exist → no plateau (not enough data).
    """
    from gym_coach_brain.data.models import WorkoutSet, WorkoutSession

    # Get last n_sessions completed sessions containing this exercise
    rows = (
        db_session.query(WorkoutSet)
        .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
        .filter(
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSession.status == "completed",
        )
        .order_by(WorkoutSession.session_date.desc())
        .all()
    )

    # Group by session to compute per-session max_weight and total_volume
    from collections import defaultdict
    session_data: dict[int, dict] = defaultdict(lambda: {"weight": 0.0, "volume": 0})

    for row in rows:
        sid = row.session_id
        session_data[sid]["weight"] = max(session_data[sid]["weight"], row.weight_kg)
        session_data[sid]["volume"] += (row.weight_kg * row.reps if row.weight_kg > 0 else row.reps)

    sessions = list(session_data.values())
    if len(sessions) < n_sessions:
        return False  # Not enough history

    recent = sessions[:n_sessions]
    weights = [s["weight"] for s in recent]
    volumes = [s["volume"] for s in recent]

    # Plateau: no growth in either metric
    return (max(weights) == min(weights)) and (max(volumes) == min(volumes))
```

---

### Шаг 5: `adaptation/explanation.py`

```python
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
        elif decision.fallback_reason and "confidence" in decision.fallback_reason and decision.ml_confidence is not None:
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
```

---

### Архитектурные ограничения

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.adaptation.engine import AdaptationEngine    # ✅
from gym_coach_brain.ml.interface import RPEModelProtocol         # ✅
from ..core.methodology import select_methodology                  # ❌ запрещено

# 2. Dependency direction — adaptation/ → core/ (не наоборот):
# adaptation/engine.py МОЖЕТ импортировать из core/
# core/ НЕ импортирует из adaptation/

# 3. PyTorch изоляция:
# adaptation/ НЕ импортирует torch напрямую
# ml/interface.py НЕ импортирует torch
# RPEModelProtocol — чистый Protocol без PyTorch deps

# 4. ScienceConfig как параметр:
def adapt(self, ..., science: ScienceConfig): ...   # ✅
SCIENCE = load_science_config()                     # ❌ запрещено

# 5. SQLAlchemy context manager (в API слое, не здесь):
# adapt() получает уже открытую db_session — НЕ создаёт сам

# 6. Lazy imports внутри методов для circular import prevention:
def adapt(self, ...):
    from gym_coach_brain.adaptation.explanation import ExplanationLayer  # ✅ lazy
    from gym_coach_brain.core.methodology import select_methodology       # ✅ lazy
```

[Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
[Source: _bmad-output/planning-artifacts/architecture.md#Import Rules]

---

### Library & Framework Requirements

- **Python 3.14+** — `from __future__ import annotations`, нативный `str | None`, `tuple[float, float]`
- **Pydantic 2.0+** — `MLConfig(BaseModel)` добавляется в `core/science.py`
- **SQLAlchemy 2.0+** — `db_session.query(RPEPrediction)...` — паттерн из существующих handlers
- **typing.Protocol** — для `RPEModelProtocol` (stdlib, не PyTorch)
- **unittest.mock.Mock** — для `mock_rpe_model` fixture в conftest.py
- **НЕ импортировать torch** в adaptation/ и ml/interface.py
- **loguru** — WARNING при fallback: `logger.warning("ML fallback: {reason}", reason=...)`

---

### Testing Requirements

**Fixtures** из `tests/conftest.py` (после обновления):
- `mock_science_config` — с `ml=MLConfig(confidence_threshold=0.6)` и `plateau_detection_sessions=3`
- `mock_rpe_model` — `Mock()` с `predict.return_value = (7.5, 0.85)` (high confidence)
- `db_session` — in-memory SQLite с полной схемой

**Стратегия тестирования:**
- Тесты engine: передавать `mock_rpe_model` для high confidence path; Mock с `(7.5, 0.3)` для low confidence
- Plateau тесты: создать `WorkoutSession` + `WorkoutSet` записи в `db_session` с `status="completed"`
- Тесты explanation: передавать `AdaptationDecision` напрямую, без реальной сессии

**Пример теста plateau:**
```python
def test_plateau_detected_after_n_identical_sessions(mock_science_config, db_session):
    from gym_coach_brain.adaptation.engine import AdaptationEngine, _is_plateau
    from gym_coach_brain.data.models import WorkoutSession, WorkoutSet
    import datetime

    # Create exercise in DB
    # Create N completed sessions, all with same weight and reps
    n = mock_science_config.plateau_detection_sessions  # = 3

    for i in range(n):
        sess = WorkoutSession(
            session_date=f"2026-03-0{i+1}",
            status="completed",
        )
        db_session.add(sess)
        db_session.flush()
        ws = WorkoutSet(
            session_id=sess.id,
            exercise_id=1,
            set_number=1,
            weight_kg=80.0,  # same every session
            reps=8,           # same every session
        )
        db_session.add(ws)
    db_session.flush()

    assert _is_plateau(exercise_id=1, n_sessions=n, db_session=db_session) is True
```

**Запуск:**
```bash
cd gym-coach-brain
uv run pytest tests/test_adaptation/ -v
uv run pytest -v   # полная регрессия
```

---

### Project Structure Notes

**Файлы, создаваемые в Story 4.5:**

```
src/gym_coach_brain/
├── ml/
│   └── interface.py            ← СОЗДАТЬ (RPEModelProtocol)
└── adaptation/
    ├── engine.py               ← СОЗДАТЬ (AdaptationEngine, AdaptationResult, AdaptedExercise)
    └── explanation.py          ← СОЗДАТЬ (ExplanationLayer)

tests/
└── test_adaptation/
    ├── __init__.py             ← СОЗДАТЬ (пустой)
    ├── test_engine.py          ← СОЗДАТЬ
    └── test_explanation.py     ← СОЗДАТЬ
```

**Файлы, изменяемые в Story 4.5:**

```
gym-coach-brain/ScienceEvidence.md      ← добавить ml: + plateau_detection_sessions:
src/gym_coach_brain/core/science.py     ← добавить MLConfig, обновить ScienceConfig
tests/conftest.py                       ← добавить MLConfig импорт, mock_rpe_model fixture, обновить mock_science_config
```

**Файлы, НЕ изменяемые:**
```
core/apre.py, core/progression.py, core/puos.py, core/readiness.py  ← НЕ трогать
core/weight_utils.py                                                   ← НЕ трогать
core/methodology.py                                                    ← НЕ трогать (Story 4.4)
data/models.py                                                         ← НЕ трогать
api/handlers.py                                                        ← НЕ трогать
```

**Следующие истории — потребители `AdaptationEngine`:**
- Story 4.6 (Recap/Summary): не зависит от AdaptationEngine напрямую
- Story 4.7 (WorkoutPlanner): не зависит напрямую, но pipeline: WorkoutPlanner → AdaptationEngine → ExplanationLayer
- Story 6.1 (API handlers): `api/handlers.py` вызовет `AdaptationEngine.adapt()`

---

### Previous Story Intelligence (Story 4.4)

Паттерны из Story 4.4, применимые к Story 4.5:

1. **Структурные паттерны** — `RepRange`, `Methodology`, `ProgressionType` из `core/methodology.py` уже существуют:
   ```python
   methodology = select_methodology(user_profile, science)
   rep_range = (methodology.rep_range.min, methodology.rep_range.max)
   ```

2. **`@dataclass(frozen=True)`** — для `AdaptedExercise` (immutable результат). `AdaptationResult` — не frozen (содержит list).

3. **`from __future__ import annotations` + `TYPE_CHECKING`** — обязательный паттерн:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from gym_coach_brain.adaptation.engine import AdaptationDecision
   ```

4. **`UserProfile.__new__(UserProfile)` в тестах** — для создания без DB (для тестов ExplanationLayer).

---

### Git Intelligence

```
11b8cbb Reposition README with product narrative and unique value proposition
425df73 Add GitHub stars and forks badges to README header
d005f82 Rewrite README in English
e324018 Replace README header banner with logo image
201009c feat: add bmad planning artifacts, project docs, gym-coach-brain and skill
```

**Выводы:**
- Последние 4 коммита — только README, кодовая база gym-coach-brain не менялась
- Вся модульная структура в коммите `201009c`:
  - `adaptation/__init__.py` — существует (пустой)
  - `ml/__init__.py` — существует (пустой)
  - `tests/test_adaptation/` — **НЕ СУЩЕСТВУЕТ** → создать `__init__.py` при добавлении тестов
- Story 4.5 расширяет оба существующих модуля новыми файлами

---

### References

- Story 4.5 требования: [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.5]
- Architecture ADR-001 ML Isolation: [Source: _bmad-output/planning-artifacts/architecture.md#ADR-001]
- Architecture ADR-002 ScienceConfig: [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
- Enforcement Summary: [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
- ScienceConfig types: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py]
- WorkoutSet, RPEPrediction models: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py]
- RecoverySignal pattern: [Source: gym-coach-brain/src/gym_coach_brain/core/readiness.py]
- Double Progression: [Source: gym-coach-brain/src/gym_coach_brain/core/progression.py]
- Weight rounding: [Source: gym-coach-brain/src/gym_coach_brain/core/weight_utils.py]
- Existing conftest.py: [Source: gym-coach-brain/tests/conftest.py]
- Mock methodology pattern: [Source: _bmad-output/implementation-artifacts/4-4-methodology-selector.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

UserProfile.__new__() не инициализирует SQLAlchemy _sa_instance_state — заменён на Mock() в тестах для engine.
Direct ML path now builds features from `data.features.build_feature_vector()`, while Double Progression fallback uses the latest completed exercise performance instead of assuming rep-max success.
Second review-fix pass preserved planned targets when no completed history exists, added `muscle_group_fatigue_estimate` to direct ML features, switched explanations/results to canonical DB exercise names, and changed previous-performance lookup to prefer repeated working-set loads in pyramid sessions.
Final review-fix pass introduced `MLConfig.fatigue_lookback_sessions`, made same-day plateau ordering deterministic with `session_date DESC, id DESC`, propagated planned set count into direct ML features, applied recovery scaling consistently in the no-history fallback, translated end-user explanations to pure Russian, and aligned Epic 4 machine rounding to the accepted 5.0kg equipment-step contract.

### Completion Notes List

✅ Все 10 задач выполнены. 267 тестов прошли (16 новых + 251 регрессия). ScienceEvidence.md расширена ml.confidence_threshold и plateau_detection_sessions. MLConfig добавлен в ScienceConfig с backward-compatible defaults. AdaptationEngine реализован с duck-typing RPEModelProtocol, ML/fallback путями, plateau detection и weight rounding. ExplanationLayer генерирует трассируемые обоснования со ссылкой на science.version. RPEModelProtocol создан без PyTorch импорта (ADR-001 соблюдён).

✅ Resolved review finding [CRITICAL]: Added loguru WARNING logging for all ML fallback paths in engine.py
✅ Resolved review finding [CRITICAL]: Fixed _is_plateau — replaced strict equality with most_recent<=oldest comparison (handles regressions); also added n_sessions-limited subquery for performance
✅ Resolved review finding [MEDIUM]: Moved hardcoded RPE thresholds (7.0, 8.5) to MLConfig.rpe_easy_threshold/rpe_hard_threshold in science.py and ScienceEvidence.md
✅ Resolved review finding [MEDIUM]: _is_plateau now uses scalar_subquery() limiting DB fetch to n_sessions rows only
✅ Resolved review finding [MEDIUM]: Added json.JSONDecodeError handling for json.loads in adapt() with loguru error logging
✅ Resolved review finding [LOW]: Documented language convention (English technical terms + Russian descriptive) in explanation.py
✅ Resolved review finding [LOW]: Added explicit comment in _double_progression_weight explaining rep_max assumption and future improvement path

271 тестов прошли (4 новых + 267 регрессия): test_plateau_detected_on_regression, test_bad_planned_exercises_json_returns_empty_result, test_rpe_easy_threshold_from_science_config, test_rpe_hard_threshold_from_science_config.

✅ Resolved review finding [HIGH]: DB prediction lookup is now deterministic via newest-row ordering for `(session_id, exercise_id)` before applying the confidence threshold.
✅ Resolved review finding [HIGH]: Double Progression fallback now reads the latest completed session for the exercise and uses actual achieved reps/weight instead of assuming rep-max completion.
✅ Resolved review finding [HIGH]: `AdaptedExercise` now exposes `target_reps`, so `AdaptationResult` returns adapted weights and repetitions per exercise.
✅ Resolved review finding [MEDIUM]: Direct `rpe_model.predict()` now receives a real feature vector from `data.features.build_feature_vector()` and overlays the current `RecoverySignal` readiness coefficient when present.

275 тестов прошли (4 новых review-follow-up tests + 271 existing): test_latest_db_prediction_is_selected_for_exercise, test_double_progression_fallback_uses_previous_completed_reps, test_adaptation_result_exposes_adapted_repetitions, test_direct_ml_path_uses_real_feature_vector_context.

✅ Resolved review finding [CRITICAL]: Prevented "Double Adaptation" on first-session plans by preserving planned weight/reps when no completed exercise history exists.
✅ Resolved review finding [HIGH]: Added `muscle_group_fatigue_estimate` to direct ML feature payload using normalized recent same-muscle workload.
✅ Resolved review finding [MEDIUM]: Adaptation results and explanations now use the canonical exercise name from the DB instead of typo-prone planned JSON labels.
✅ Resolved review finding [MEDIUM]: `_get_previous_performance()` now prefers the repeated working-set load over a one-off top set for pyramid sessions.
✅ Resolved review finding [LOW]: Replaced deprecated `datetime.utcnow()` in `data/features.py` with timezone-aware `datetime.now(timezone.utc)`.
✅ Resolved review finding [LOW]: Removed redundant set-number ordering from the latest-session lookup in `_get_previous_performance()`.

279 тестов прошли (4 новых review-follow-up tests + 275 existing): test_direct_ml_path_includes_muscle_group_fatigue_estimate, test_no_history_does_not_reactively_progress_planned_values, test_canonical_exercise_name_from_db_is_used_in_result_and_explanation, test_previous_performance_prefers_working_set_weight_for_pyramid_sessions.

✅ Resolved review finding [MEDIUM]: Added `MLConfig.fatigue_lookback_sessions` and switched fatigue estimation to a real session-count lookback instead of reusing rest-days semantics.
✅ Resolved review finding [MEDIUM]: Strengthened `test_barbell_weight_rounded_to_2_5kg` with a non-multiple planned weight (`79.3kg`) so the rounding branch is exercised explicitly.
✅ Resolved review finding [LOW]: Removed defensive `getattr()` fallback in `ExplanationLayer.explain()` and now read `science.ml.confidence_threshold` directly.
✅ Resolved review finding [LOW]: Direct ML feature generation now passes the planned set count instead of hardcoding `set_number=1`.
✅ Resolved review finding [LOW]: No-history fallback now applies `recovery_coeff` before final equipment rounding, keeping behavior consistent with the other adaptation paths.
✅ Resolved review finding [LOW]: Added a dedicated regression test proving that ML-path output weight is scaled by `recovery_coeff`.
✅ Resolved review finding [HIGH]: Verified the machine-rounding contract against Epic 4.1 / `ScienceEvidence.md` / `core.weight_utils.py` and aligned Epic 4 Story 4.5 wording to `machine: 5.0kg`.
✅ Resolved review finding [LOW]: Plateau detection now uses `id.desc()` as a same-day tiebreaker, and the behavior is locked by regression coverage.
✅ Resolved review finding [LOW]: End-user explanation strings are now consistently Russian (`RPE модели`, `двойная прогрессия`) instead of mixed-language output.

284 тестов прошли (5 новых review-follow-up tests + 279 existing): test_direct_ml_path_uses_planned_set_count_in_feature_vector, test_no_history_applies_recovery_coefficient_to_planned_weight, test_direct_ml_path_scales_final_weight_by_recovery_coefficient, test_fatigue_lookback_sessions_is_independent_from_rest_days, test_plateau_detection_uses_session_id_as_same_day_tiebreaker.

### File List

gym-coach-brain/ScienceEvidence.md
gym-coach-brain/src/gym_coach_brain/core/science.py
gym-coach-brain/src/gym_coach_brain/ml/interface.py
gym-coach-brain/src/gym_coach_brain/adaptation/engine.py
gym-coach-brain/src/gym_coach_brain/adaptation/explanation.py
gym-coach-brain/src/gym_coach_brain/data/features.py
gym-coach-brain/tests/conftest.py
gym-coach-brain/tests/test_adaptation/__init__.py
gym-coach-brain/tests/test_adaptation/test_engine.py
gym-coach-brain/tests/test_adaptation/test_explanation.py
_bmad-output/planning-artifacts/epics/epic-4.md
_bmad-output/implementation-artifacts/4-5-adaptation-engine.md
_bmad-output/implementation-artifacts/sprint-status.yaml

## Senior Developer Review (AI)

### Reviewer

Codex GPT-5

### Date

2026-03-08

### Outcome

Changes Requested

### Summary

Validated story 4.5 against the current implementation and working tree. Adaptation tests pass and full regression currently reports `271 passed`, but the story still has unresolved review issues that block completion: nondeterministic DB prediction selection, fallback progression that always assumes rep-max success, missing adapted-reps data in `AdaptationResult`, and placeholder feature generation for the direct ML path.

### Evidence

- Focused tests: `uv run pytest tests/test_adaptation -q` → 20 passed
- Full regression: `uv run pytest -q` → 271 passed, 1 unrelated warning
- Manual repro: duplicate `RPEPrediction` rows for one exercise caused fallback to trigger from an older 0.20-confidence row while a newer 0.90-confidence row existed
- Manual repro: prior completed set at `80kg x 6` still produced fallback recommendation `82.5kg`

## Change Log

- 2026-03-08: Senior AI code review completed. Added 4 open review follow-ups, recorded review evidence, and moved story status from `review` to `in-progress`.
- 2026-03-08: Resolved 4 remaining AI review follow-ups in Adaptation Engine, reran full regression (`uv run pytest -q` → 275 passed), and moved story status back to `review`.
- 2026-03-08: Resolved final 6 AI review follow-ups in Adaptation Engine and feature plumbing, reran full regression (`uv run pytest -q` → 279 passed), and kept story status at `review`.
- 2026-03-09: Resolved the final 9 AI review follow-ups in adaptation/config/spec artifacts, reran focused adaptation tests (`uv run pytest tests/test_adaptation -q` → 33 passed) and full regression (`uv run pytest -q` → 284 passed), and restored story status to `review`.

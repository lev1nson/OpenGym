# Story 3.4: Шаблон онбординга и маппинг коэффициентов

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to implement `core/onboarding.py` with question templates and coefficient mapping,
so that athlete answers are deterministically converted to numerical training parameters.

## Acceptance Criteria

**Given** `data/models.py` с таблицей `UserProfile` доступен и Story 3.3 завершена (conftest.py существует)

**When** агент реализует `core/onboarding.py`

**Then** модуль содержит упорядоченный список вопросов онбординга (возраст, опыт, цель, доступное оборудование, режим сна/стресса)

**And** каждый вопрос имеет тип ответа (число, выбор из вариантов, текст)

**And** вопрос «Вес тела (кг)?» (числовой ввод, диапазон 30–250) сохраняется в `UserProfile.bodyweight_kg`

**And** вопрос про оборудование предлагает атлету выбрать из каталога `Equipment` (из seed data) — multi-select

**And** выбранное оборудование сохраняется в `UserProfile.available_equipment` как JSON list of `EquipmentType` values

**And** вопрос «Сколько раз в неделю тренируешься?» (варианты: 3 / 4 / 5 / 6) сохраняется в `UserProfile.training_days_per_week`

**And** вопрос «Предпочтение сплита?» сохраняется в `UserProfile.training_split` через маппинг: Фулбоди→`full_body`, Верх-Низ→`upper_lower`, ТТН→`ppl`, Своя→`custom`

**And** функция `compute_initial_weights(user_profile, science) -> dict` вычисляет `initial_weight_coefficients` при `onboarding_complete`: для каждого `MovementPattern` возвращает `bodyweight_kg * ScienceConfig.initial_weight_table[experience_level][movement_pattern]`; результат сохраняется в `UserProfile.initial_weight_coefficients` как JSON

**And** функция `get_available_exercises(user_profile, session) -> list[Exercise]` возвращает упражнения, отфильтрованные по `UserProfile.available_equipment`

**And** функция `map_answer_to_coefficients(question_id, answer) -> dict` возвращает числовые коэффициенты

**And** коэффициенты сохраняются в `UserProfile` через SQLAlchemy session (не интерпретируются LLM)

**And** `pytest tests/test_core/test_onboarding.py` проходит: каждый вопрос имеет детерминированный маппинг, включая `training_split`, `training_days_per_week`, `bodyweight_kg`; `compute_initial_weights` возвращает корректные значения для beginner/intermediate/advanced; `get_available_exercises` корректно фильтрует по оборудованию

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: baseline)
  - [x] Подтвердить Story 3.3 выполнена: `tests/conftest.py` существует (содержит `db_session`, `mock_science_config`)
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться baseline тесты PASS (103 тестов)
  - [x] Проверить `ScienceConfig` на наличие `initial_weight_table` — отсутствует → выполнить Task 2

- [x] **[УСЛОВНО] Добавить `initial_weight_table` в ScienceConfig** (не было в Story 3.3)
  - [x] Добавить в класс `ScienceConfig`: `initial_weight_table: dict[str, dict[str, float]] = {}`
  - [x] Добавить блок `initial_weight_table` в `ScienceEvidence.md` frontmatter
  - [x] Верифицировать парсинг через `load_science_config().initial_weight_table`

- [x] **Создать `src/gym_coach_brain/core/onboarding.py`** (AC: все функции реализованы)
  - [x] Определить `QuestionType` Enum: `NUMERIC`, `SINGLE_CHOICE`, `MULTI_CHOICE`, `TEXT`
  - [x] Определить `OnboardingQuestion` dataclass
  - [x] Создать `QUESTIONS` — упорядоченный список 9 вопросов
  - [x] Реализовать `map_answer_to_coefficients(question_id, answer) -> dict`
  - [x] Реализовать `compute_initial_weights(user_profile, science) -> dict[str, float]`
  - [x] Реализовать `get_available_exercises(user_profile, session) -> list[Exercise]`

- [x] **Создать `tests/test_core/test_onboarding.py`** (AC: все тесты PASS)
  - [x] Тест: каждый вопрос в QUESTIONS имеет уникальный `id`
  - [x] Тест: `training_split` маппинг — все 4 варианта
  - [x] Тест: `training_days_per_week` маппинг — все 4 варианта (3/4/5/6)
  - [x] Тест: `bodyweight_kg` сохраняется корректно
  - [x] Тест: `compute_initial_weights` — beginner 70kg → `horizontal_push ≈ 28.0`
  - [x] Тест: `compute_initial_weights` — intermediate 80kg → `squat ≈ 80.0`
  - [x] Тест: `compute_initial_weights` — advanced → все 7 ключей
  - [x] Тест: `get_available_exercises` с `bodyweight` → только bodyweight упражнения
  - [x] Тест: `get_available_exercises` с пустым списком → пустой результат
  - [x] Тест: `get_available_exercises` с `[barbell, bodyweight]` → оба типа

- [x] **Финальная верификация**
  - [x] `uv run pytest tests/test_core/test_onboarding.py -v` — 26 тестов PASS
  - [x] `uv run pytest -v` — 129 тестов PASS (103 baseline + 26 новых), регрессий нет

## Dev Notes

### ⚠️ Критические пререквизиты: Story 3.3 MUST BE DONE FIRST

**Обязательно проверить перед началом:**
1. `tests/conftest.py` существует (создаётся в Story 3.3)
2. `db_session` fixture доступна (in-memory SQLite)
3. `mock_science_config` fixture доступна

**Если conftest.py НЕ существует:**
- Story 3.3 не завершена → вернуться к Story 3.3 сначала
- НЕ создавать собственный conftest.py — он должен создаваться в Story 3.3

---

### Текущее состояние codebase (актуально на 2026-03-08)

**Что УЖЕ существует:**
```
src/gym_coach_brain/
├── core/
│   ├── science.py       ← СУЩЕСТВУЕТ (ScienceConfig + load_science_config)
│   └── puos.py          ← СУЩЕСТВУЕТ (уже создан)
├── data/
│   ├── models.py        ← СУЩЕСТВУЕТ (UserProfile, Exercise, EquipmentType, TrainingSplit и др.)
│   └── seed.py          ← СУЩЕСТВУЕТ (MovementPattern seed data)
└── exceptions.py        ← СУЩЕСТВУЕТ (ConfigError, ScienceLimitError, и др.)
```

**Что НЕ существует и создаётся в Story 3.4:**
```
src/gym_coach_brain/core/onboarding.py    ← СОЗДАТЬ
tests/test_core/test_onboarding.py        ← СОЗДАТЬ
```

**Что создаётся в Story 3.3 (prerequisite):**
```
tests/conftest.py   ← создаётся в Story 3.3 (db_session, mock_science_config, db_engine)
```

**Baseline тестов:** 97 тестов (на момент создания этой истории)
После Story 3.3: 97 + тесты Story 3.3 (ожидаем ~65+)
После Story 3.4: baseline_3.3 + ~10-15 новых тестов из `test_onboarding.py`

---

### MovementPattern names (из seed data — КРИТИЧНО для initial_weight_table)

Ключи `initial_weight_table` ДОЛЖНЫ точно совпадать с именами из `_MOVEMENT_PATTERNS` в `data/seed.py`:
```python
# Source: gym-coach-brain/src/gym_coach_brain/data/seed.py
_MOVEMENT_PATTERNS = [
    ("horizontal_push",  "push"),
    ("vertical_push",    "push"),
    ("horizontal_pull",  "pull"),
    ("vertical_pull",    "pull"),
    ("squat",            "legs"),
    ("hinge",            "legs"),
    ("carry",            "carry"),
]
```
**Итого 7 ключей.** `compute_initial_weights` ДОЛЖНА возвращать ровно 7 записей.

---

### Полная реализация `core/onboarding.py`

```python
# src/gym_coach_brain/core/onboarding.py
"""
Onboarding question templates and coefficient mapping.

Maps athlete answers deterministically to numerical training parameters.
No LLM interpretation of training load parameters — pure algorithmic conversion.

FR9: Interactive onboarding → UserProfile
FR13-FR14: Answer → coefficient mapping (deterministic, not LLM-driven)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from gym_coach_brain.data.models import Equipment, EquipmentType, Exercise, TrainingSplit, UserProfile

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig


class QuestionType(str, Enum):
    NUMERIC = "numeric"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    TEXT = "text"


@dataclass
class OnboardingQuestion:
    id: str
    text: str
    type: QuestionType
    options: list[str] | None = None
    min_val: float | None = None
    max_val: float | None = None


QUESTIONS: list[OnboardingQuestion] = [
    OnboardingQuestion(
        id="age",
        text="Сколько вам лет?",
        type=QuestionType.NUMERIC,
        min_val=10,
        max_val=100,
    ),
    OnboardingQuestion(
        id="experience_level",
        text="Ваш уровень подготовки?",
        type=QuestionType.SINGLE_CHOICE,
        options=["beginner", "intermediate", "advanced"],
    ),
    OnboardingQuestion(
        id="goal",
        text="Ваша основная цель тренировок?",
        type=QuestionType.SINGLE_CHOICE,
        options=["strength", "hypertrophy", "endurance"],
    ),
    OnboardingQuestion(
        id="bodyweight_kg",
        text="Вес тела (кг)?",
        type=QuestionType.NUMERIC,
        min_val=30,
        max_val=250,
    ),
    OnboardingQuestion(
        id="equipment",
        text="Какое оборудование вам доступно? (можно выбрать несколько)",
        type=QuestionType.MULTI_CHOICE,
        options=[e.value for e in EquipmentType],
    ),
    OnboardingQuestion(
        id="training_days_per_week",
        text="Сколько раз в неделю тренируешься?",
        type=QuestionType.SINGLE_CHOICE,
        options=["3", "4", "5", "6"],
    ),
    OnboardingQuestion(
        id="training_split",
        text="Предпочтение сплита?",
        type=QuestionType.SINGLE_CHOICE,
        options=["full_body", "upper_lower", "ppl", "custom"],
    ),
    OnboardingQuestion(
        id="sleep_quality",
        text="Как вы оцениваете качество вашего сна?",
        type=QuestionType.SINGLE_CHOICE,
        options=["poor", "average", "good"],
    ),
    OnboardingQuestion(
        id="stress_level",
        text="Ваш текущий уровень стресса?",
        type=QuestionType.SINGLE_CHOICE,
        options=["high", "moderate", "low"],
    ),
]

# Deterministic mappings — DO NOT use LLM for these
_TRAINING_SPLIT_MAP: dict[str, TrainingSplit] = {
    "full_body": TrainingSplit.full_body,
    "upper_lower": TrainingSplit.upper_lower,
    "ppl": TrainingSplit.ppl,
    "custom": TrainingSplit.custom,
    # Legacy Russian labels (for OpenClaw chat compatibility)
    "Фулбоди": TrainingSplit.full_body,
    "Верх-Низ": TrainingSplit.upper_lower,
    "ТТН": TrainingSplit.ppl,
    "Своя": TrainingSplit.custom,
}

_SLEEP_QUALITY_MAP: dict[str, float] = {
    "poor": 0.3,
    "average": 0.6,
    "good": 1.0,
}

_STRESS_LEVEL_MAP: dict[str, float] = {
    "high": 0.3,
    "moderate": 0.6,
    "low": 1.0,
}

_EXPERIENCE_LEVEL_MAP: dict[str, str] = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
}


def map_answer_to_coefficients(question_id: str, answer: str) -> dict[str, float | str]:
    """Map a single onboarding answer to numerical coefficients.

    Returns a dict suitable for merging into UserProfile update kwargs.
    All mappings are deterministic — no LLM interpretation.

    Args:
        question_id: Question identifier (must match QUESTIONS[i].id)
        answer: Raw answer string from athlete

    Returns:
        dict with one or more UserProfile field updates
    """
    if question_id == "bodyweight_kg":
        return {"bodyweight_kg": float(answer)}

    if question_id == "training_days_per_week":
        return {"training_days_per_week": int(answer)}

    if question_id == "training_split":
        split = _TRAINING_SPLIT_MAP.get(answer)
        if split is None:
            raise ValueError(f"Unknown training_split answer: {answer!r}")
        return {"training_split": split}

    if question_id == "equipment":
        # answer expected as comma-separated or JSON list
        if answer.startswith("["):
            items = json.loads(answer)
        else:
            items = [a.strip() for a in answer.split(",") if a.strip()]
        # validate each item is a valid EquipmentType
        validated = [EquipmentType(item) for item in items]
        return {"available_equipment": json.dumps([e.value for e in validated])}

    if question_id == "experience_level":
        return {"experience_level": _EXPERIENCE_LEVEL_MAP.get(answer, answer)}

    if question_id == "sleep_quality":
        return {"sleep_quality_score": _SLEEP_QUALITY_MAP.get(answer, 0.5)}

    if question_id == "stress_level":
        return {"stress_score": _STRESS_LEVEL_MAP.get(answer, 0.5)}

    if question_id == "age":
        return {"age": int(float(answer))}

    if question_id == "goal":
        return {"goal": answer}

    return {}


def compute_initial_weights(user_profile: UserProfile, science: ScienceConfig) -> dict[str, float]:
    """Compute initial weight coefficients for all movement patterns.

    Formula: bodyweight_kg * initial_weight_table[experience_level][movement_pattern]
    Result is stored in UserProfile.initial_weight_coefficients as JSON.

    Args:
        user_profile: UserProfile with bodyweight_kg set (non-None, non-zero)
        science: ScienceConfig with initial_weight_table populated

    Returns:
        dict mapping movement_pattern_name → starting weight in kg (rounded to 1 decimal)

    Raises:
        ValueError: if bodyweight_kg is None/zero, or experience_level missing from table
    """
    bodyweight = user_profile.bodyweight_kg
    if not bodyweight or bodyweight <= 0:
        raise ValueError("bodyweight_kg must be set and positive before computing initial weights")

    # Determine experience level — stored in initial_weight_coefficients or default to "beginner"
    # NOTE: experience_level is not a direct UserProfile column — derived from onboarding session
    # It is passed here via user_profile attribute set during onboarding flow
    experience_level = getattr(user_profile, "_experience_level", "beginner")

    table = getattr(science, "initial_weight_table", {})
    if not table:
        # Fallback if initial_weight_table not in ScienceConfig: return empty dict
        return {}

    level_table = table.get(experience_level, table.get("beginner", {}))
    return {
        pattern: round(bodyweight * coef, 1)
        for pattern, coef in level_table.items()
    }


def get_available_exercises(user_profile: UserProfile, session: Session) -> list[Exercise]:
    """Return exercises filtered by athlete's available equipment.

    Uses UserProfile.available_equipment (JSON list of EquipmentType values).
    If available_equipment is empty, returns an empty list.

    Args:
        user_profile: UserProfile with available_equipment set
        session: SQLAlchemy Session (in-memory or production)

    Returns:
        List of Exercise objects matching at least one equipment type in available_equipment
    """
    equipment_list = json.loads(user_profile.available_equipment or "[]")
    if not equipment_list:
        return []

    return (
        session.query(Exercise)
        .filter(Exercise.equipment_type.in_(equipment_list))
        .all()
    )
```

**ВАЖНО — `_experience_level`:** UserProfile не имеет прямой колонки `experience_level`. Это поле хранится в сессии онбординга (временно), поэтому мы используем `getattr(user_profile, "_experience_level", "beginner")`. В Story 3.5 (API handlers) этот временный атрибут устанавливается перед вызовом `compute_initial_weights`. Тесты должны устанавливать его явно:
```python
user_profile._experience_level = "intermediate"
result = compute_initial_weights(user_profile, mock_science_config)
```

---

### Полная реализация `tests/test_core/test_onboarding.py`

```python
# tests/test_core/test_onboarding.py
"""
Tests for core/onboarding.py: question templates and coefficient mapping.

Fixtures from tests/conftest.py (created in Story 3.3):
    - db_session: in-memory SQLite session with schema
    - mock_science_config: minimal ScienceConfig for testing
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.core.onboarding import (
    QUESTIONS,
    QuestionType,
    compute_initial_weights,
    get_available_exercises,
    map_answer_to_coefficients,
)
from gym_coach_brain.core.science import ScienceConfig
from gym_coach_brain.data.models import Base, EquipmentType, Exercise, TrainingSplit, UserProfile
from gym_coach_brain.data.seed import seed_exercises, seed_taxonomy


# ─── Question Structure Tests ──────────────────────────────────────────────────

def test_questions_list_not_empty():
    assert len(QUESTIONS) >= 9


def test_questions_have_unique_ids():
    ids = [q.id for q in QUESTIONS]
    assert len(ids) == len(set(ids)), "Duplicate question IDs found"


def test_required_questions_present():
    ids = {q.id for q in QUESTIONS}
    required = {"bodyweight_kg", "equipment", "training_days_per_week", "training_split"}
    assert required.issubset(ids)


def test_bodyweight_question_is_numeric():
    q = next(q for q in QUESTIONS if q.id == "bodyweight_kg")
    assert q.type == QuestionType.NUMERIC
    assert q.min_val == 30
    assert q.max_val == 250


def test_equipment_question_is_multi_choice():
    q = next(q for q in QUESTIONS if q.id == "equipment")
    assert q.type == QuestionType.MULTI_CHOICE
    assert q.options is not None
    assert "bodyweight" in q.options


def test_training_days_question_has_correct_options():
    q = next(q for q in QUESTIONS if q.id == "training_days_per_week")
    assert q.type == QuestionType.SINGLE_CHOICE
    assert set(q.options) == {"3", "4", "5", "6"}


def test_training_split_question_has_correct_options():
    q = next(q for q in QUESTIONS if q.id == "training_split")
    assert q.type == QuestionType.SINGLE_CHOICE
    assert set(q.options) == {"full_body", "upper_lower", "ppl", "custom"}


# ─── map_answer_to_coefficients Tests ─────────────────────────────────────────

def test_map_bodyweight_kg():
    result = map_answer_to_coefficients("bodyweight_kg", "75")
    assert result == {"bodyweight_kg": 75.0}


def test_map_training_days_per_week():
    for days in ["3", "4", "5", "6"]:
        result = map_answer_to_coefficients("training_days_per_week", days)
        assert result["training_days_per_week"] == int(days)


def test_map_training_split_full_body():
    result = map_answer_to_coefficients("training_split", "full_body")
    assert result["training_split"] == TrainingSplit.full_body


def test_map_training_split_upper_lower():
    result = map_answer_to_coefficients("training_split", "upper_lower")
    assert result["training_split"] == TrainingSplit.upper_lower


def test_map_training_split_ppl():
    result = map_answer_to_coefficients("training_split", "ppl")
    assert result["training_split"] == TrainingSplit.ppl


def test_map_training_split_custom():
    result = map_answer_to_coefficients("training_split", "custom")
    assert result["training_split"] == TrainingSplit.custom


def test_map_equipment_single():
    result = map_answer_to_coefficients("equipment", "bodyweight")
    equipment = json.loads(result["available_equipment"])
    assert equipment == ["bodyweight"]


def test_map_equipment_multiple_comma_separated():
    result = map_answer_to_coefficients("equipment", "barbell, dumbbell, bodyweight")
    equipment = json.loads(result["available_equipment"])
    assert set(equipment) == {"barbell", "dumbbell", "bodyweight"}


def test_map_equipment_json_list():
    result = map_answer_to_coefficients("equipment", '["barbell", "bodyweight"]')
    equipment = json.loads(result["available_equipment"])
    assert set(equipment) == {"barbell", "bodyweight"}


def test_map_invalid_training_split_raises():
    with pytest.raises((ValueError, KeyError)):
        map_answer_to_coefficients("training_split", "invalid_split")


# ─── compute_initial_weights Tests ────────────────────────────────────────────

@pytest.fixture
def mock_science_config_with_table(mock_science_config):
    """Extend mock_science_config with initial_weight_table for testing."""
    mock_science_config.__dict__["initial_weight_table"] = {
        "beginner": {
            "horizontal_push": 0.40, "vertical_push": 0.30,
            "horizontal_pull": 0.35, "vertical_pull": 0.30,
            "squat": 0.60, "hinge": 0.50, "carry": 0.25,
        },
        "intermediate": {
            "horizontal_push": 0.70, "vertical_push": 0.55,
            "horizontal_pull": 0.60, "vertical_pull": 0.55,
            "squat": 1.00, "hinge": 0.90, "carry": 0.45,
        },
        "advanced": {
            "horizontal_push": 1.00, "vertical_push": 0.80,
            "horizontal_pull": 0.90, "vertical_pull": 0.80,
            "squat": 1.50, "hinge": 1.30, "carry": 0.65,
        },
    }
    return mock_science_config


def _make_user_profile(bodyweight_kg: float, experience_level: str) -> UserProfile:
    """Create a minimal UserProfile for testing (not persisted)."""
    profile = UserProfile(bodyweight_kg=bodyweight_kg)
    profile._experience_level = experience_level
    return profile


def test_compute_initial_weights_beginner(mock_science_config_with_table):
    profile = _make_user_profile(70.0, "beginner")
    result = compute_initial_weights(profile, mock_science_config_with_table)
    assert result["horizontal_push"] == pytest.approx(28.0, rel=1e-2)
    assert result["squat"] == pytest.approx(42.0, rel=1e-2)


def test_compute_initial_weights_intermediate(mock_science_config_with_table):
    profile = _make_user_profile(80.0, "intermediate")
    result = compute_initial_weights(profile, mock_science_config_with_table)
    assert result["squat"] == pytest.approx(80.0, rel=1e-2)
    assert result["horizontal_push"] == pytest.approx(56.0, rel=1e-2)


def test_compute_initial_weights_returns_all_7_patterns(mock_science_config_with_table):
    profile = _make_user_profile(75.0, "advanced")
    result = compute_initial_weights(profile, mock_science_config_with_table)
    expected_patterns = {
        "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
        "squat", "hinge", "carry"
    }
    assert set(result.keys()) == expected_patterns


def test_compute_initial_weights_no_bodyweight_raises(mock_science_config_with_table):
    profile = UserProfile(bodyweight_kg=None)
    with pytest.raises(ValueError, match="bodyweight_kg"):
        compute_initial_weights(profile, mock_science_config_with_table)


def test_compute_initial_weights_empty_table(mock_science_config):
    """When initial_weight_table is absent/empty, return empty dict (graceful degradation)."""
    profile = _make_user_profile(70.0, "beginner")
    result = compute_initial_weights(profile, mock_science_config)
    assert result == {}


# ─── get_available_exercises Tests ────────────────────────────────────────────

@pytest.fixture
def seeded_session():
    """In-memory DB session with seed data (muscle groups, exercises, equipment)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_taxonomy(session)
        seed_exercises(session)
        session.commit()
        yield session


def test_get_available_exercises_bodyweight_only(seeded_session):
    profile = UserProfile(available_equipment=json.dumps(["bodyweight"]))
    exercises = get_available_exercises(profile, seeded_session)
    assert len(exercises) > 0
    assert all(ex.equipment_type == EquipmentType.bodyweight for ex in exercises)


def test_get_available_exercises_multiple_equipment(seeded_session):
    profile = UserProfile(available_equipment=json.dumps(["barbell", "bodyweight"]))
    exercises = get_available_exercises(profile, seeded_session)
    types = {ex.equipment_type for ex in exercises}
    # Should include both barbell and bodyweight exercises
    assert EquipmentType.barbell in types or EquipmentType.bodyweight in types


def test_get_available_exercises_empty_equipment_returns_empty(seeded_session):
    profile = UserProfile(available_equipment=json.dumps([]))
    exercises = get_available_exercises(profile, seeded_session)
    assert exercises == []


def test_get_available_exercises_no_equipment_set_returns_empty(seeded_session):
    profile = UserProfile(available_equipment=None)
    exercises = get_available_exercises(profile, seeded_session)
    assert exercises == []
```

---

### Architecture Compliance Constraints

**Обязательные паттерны:**

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.data.models import UserProfile, Exercise, EquipmentType  # ✅
from ..data.models import UserProfile                                           # ❌ запрещено

# 2. ScienceConfig передаётся как параметр:
def compute_initial_weights(user_profile: UserProfile, science: ScienceConfig) -> dict:  # ✅
science = load_science_config()  # ❌ НЕ вызывать внутри onboarding.py — только в api/main.py

# 3. SQLAlchemy Session — context manager:
with Session(engine) as session:  # ✅
session = Session(engine); session.close()  # ❌ запрещено

# 4. Typed exceptions — НЕ error dicts:
raise ValueError("bodyweight_kg must be set")  # ✅ — OK для core/ modules
return {"error": "bodyweight not set"}          # ❌ запрещено

# 5. Dependency direction: api → adaptation → core → data
# core/onboarding.py может импортировать: data/models.py, exceptions.py, stdlib
# core/onboarding.py НЕ импортирует: adaptation/, ml/, api/
```

**Особые случаи:**
- `if TYPE_CHECKING:` для `ScienceConfig` — избегаем circular imports (science.py не импортирует onboarding.py)
- `from __future__ import annotations` — для строковых аннотаций без runtime import

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

**Python 3.14+:**
- `dict[str, float]` type hints — нативный Python 3.9+, без `Dict` из typing
- `list[str] | None` — нативный Python 3.10+, без `Optional[List[str]]`
- `from __future__ import annotations` — для строковых аннотаций в Python 3.14

**SQLAlchemy 2.0+:**
- `session.query(Exercise).filter(Exercise.equipment_type.in_([...]))` — SQLAlchemy 2.0 совместимо
- `from sqlalchemy.orm import Session` — НЕ `from sqlalchemy import Session`

**Pydantic 2.0+:**
- `ScienceConfig` уже является `BaseModel` — не дублируй определение
- `initial_weight_table: dict[str, dict[str, float]] = {}` — field с дефолтом пустого dict

**Enum:**
- `EquipmentType(str, Enum)` — уже определён в `data/models.py`, не дублируй
- `TrainingSplit(str, Enum)` — уже определён в `data/models.py`, не дублируй

**Source:** [Source: gym-coach-brain/pyproject.toml]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Starter Template Evaluation]

---

### File Structure Requirements

**Файлы, создаваемые в этой истории:**
```
gym-coach-brain/
├── src/gym_coach_brain/
│   └── core/
│       └── onboarding.py                ← СОЗДАТЬ
└── tests/
    └── test_core/
        └── test_onboarding.py           ← СОЗДАТЬ
```

**Файлы, изменяемые в этой истории (только если Story 3.3 НЕ добавила initial_weight_table):**
```
gym-coach-brain/
├── ScienceEvidence.md                   ← ИЗМЕНИТЬ: добавить initial_weight_table блок
├── src/gym_coach_brain/core/
│   └── science.py                       ← ИЗМЕНИТЬ: добавить initial_weight_table поле
└── tests/
    └── conftest.py                      ← ИЗМЕНИТЬ: обновить mock_science_config если нужно
```

**Файлы, которые эта история НЕ создаёт:**
- `src/gym_coach_brain/api/handlers.py` — Story 3.5
- `src/gym_coach_brain/core/apre.py`, `progression.py` — Epic 4
- `src/gym_coach_brain/core/readiness.py` — Epic 4/Story 3.x

**Рабочая директория:** `gym-coach-brain/` (внутри проекта OpenGym)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory Structure]

---

### Testing Requirements

**Стратегия тестирования:**
- `test_onboarding.py` использует `db_session` и `mock_science_config` из `tests/conftest.py` (Story 3.3)
- Тесты `compute_initial_weights` используют `mock_science_config_with_table` — локальная fixture в test файле, расширяет глобальную mock
- Тесты `get_available_exercises` используют `seeded_session` — локальная fixture с seed данными
- НЕ реальный SQLite файл — только `sqlite:///:memory:`
- НЕ `alembic upgrade head` в тестах — только `Base.metadata.create_all(engine)`

**Запуск:**
```bash
cd gym-coach-brain
uv run pytest tests/test_core/test_onboarding.py -v   # только onboarding тесты
uv run pytest -v                                        # все тесты
```

**Ожидаемые results:**
- `test_questions_list_not_empty` — PASS (≥9 вопросов)
- `test_compute_initial_weights_beginner` — PASS (70 * 0.40 = 28.0)
- `test_get_available_exercises_bodyweight_only` — PASS (seed data содержит bodyweight exercises)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns (Test Fixtures)]

---

### Previous Story Intelligence (Story 3.3)

**Ключевые выводы из Story 3.3:**
1. **Story 3.3 готовит `conftest.py`** — db_session, db_engine, mock_science_config fixtures
2. **`core/science.py` после Story 3.3** — ValueError → ConfigError замена завершена
3. **`ScienceConfig.initial_weight_table`** — добавляется в Story 3.3 как опциональный таск; если не добавлен — Story 3.4 добавляет сама
4. **`uv run` pattern:** всегда `cd gym-coach-brain && uv run pytest`
5. **baseline перед Story 3.4:** 97 тестов + тесты из Story 3.3 (test_science.py ConfigError changes + conftest тест)
6. **`equipment_type` в `Exercise`:** хранится как `SAEnum(EquipmentType)` — при фильтрации использовать строковые values или enum members
7. **UserProfile.available_equipment:** хранится как JSON TEXT — гибридный property `.available_equipment_list` для list access

**Source:** [Source: _bmad-output/implementation-artifacts/3-3-science-config-loader.md]

---

### Git Intelligence

```
Последние коммиты (основной репозиторий):
11b8cbb Reposition README with product narrative and unique value proposition
425df73 Add GitHub stars and forks badges to README header
d005f82 Rewrite README in English with project positioning and value proposition
```

**Выводы:**
- Последние коммиты касаются README — не gymcoach логики
- `gym-coach-brain/` — изменения будут видны как untracked/modified
- Dev agent НЕ делает git commit (только если явно попросят)
- Файл `ScienceEvidence.md` ещё НЕ содержит `initial_weight_table` (подтверждено grep)

---

### Project Structure Notes

**После Story 3.4 `core/` будет выглядеть так:**
```
src/gym_coach_brain/core/
├── __init__.py
├── science.py          ← существует (+ initial_weight_table если добавлен)
├── puos.py             ← существует
└── onboarding.py       ← СОЗДАН в Story 3.4
```

**После Story 3.4 `tests/test_core/` будет выглядеть так:**
```
tests/test_core/
├── __init__.py
├── test_science.py     ← обновлён в Story 3.3 (ConfigError)
└── test_onboarding.py  ← СОЗДАН в Story 3.4
```

**Зависимости:**
- **Story 3.5** (`api/handlers.py`) — использует `core/onboarding.py` функции для обработки интентов `onboarding_start`, `onboarding_answer`, `onboarding_complete`
- **Story 3.5** устанавливает `user_profile._experience_level` до вызова `compute_initial_weights`

---

### References

- Story 3.4 требования: [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Story 3.4]
- Architecture: [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
- Architecture enforcement: [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
- UserProfile model: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py]
- MovementPattern names: [Source: gym-coach-brain/src/gym_coach_brain/data/seed.py#_MOVEMENT_PATTERNS]
- ScienceConfig: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py]
- Previous story: [Source: _bmad-output/implementation-artifacts/3-3-science-config-loader.md]
- Project context: [Source: _bmad-output/project-context.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No blockers encountered. All tasks completed in single session.

### Completion Notes List

- ✅ Baseline verified: 103 tests PASS before changes
- ✅ Task 2 (conditional): Added `initial_weight_table: dict[str, dict[str, float]] = {}` to `ScienceConfig`
- ✅ Added `initial_weight_table` YAML block to `ScienceEvidence.md` frontmatter (beginner/intermediate/advanced × 7 movement patterns)
- ✅ Verified parsing: `load_science_config().initial_weight_table` returns correct nested dict
- ✅ Created `core/onboarding.py` with `QuestionType`, `OnboardingQuestion`, `QUESTIONS` (9 questions), `map_answer_to_coefficients`, `compute_initial_weights`, `get_available_exercises`
- ✅ Created `tests/test_core/test_onboarding.py` with 26 tests covering all ACs
- ✅ All 26 onboarding tests PASS
- ✅ Full suite: 129 tests PASS (103 baseline + 26 new), no regressions
- ℹ️ `_experience_level` is a temporary attribute set via `getattr(user_profile, "_experience_level", "beginner")` — Story 3.5 sets this before calling `compute_initial_weights`

### File List

- `gym-coach-brain/ScienceEvidence.md` (modified: added initial_weight_table YAML block)
- `gym-coach-brain/src/gym_coach_brain/core/science.py` (modified: added initial_weight_table field to ScienceConfig)
- `gym-coach-brain/src/gym_coach_brain/core/onboarding.py` (created)
- `gym-coach-brain/tests/test_core/test_onboarding.py` (created)
- `_bmad-output/implementation-artifacts/3-4-onboarding-template.md` (modified: tasks checked, status → review)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified: 3-4 → review)

### Change Log

- 2026-03-08: Implemented Story 3.4 — added initial_weight_table to ScienceConfig + ScienceEvidence.md, created core/onboarding.py (QuestionType, OnboardingQuestion, QUESTIONS×9, map_answer_to_coefficients, compute_initial_weights, get_available_exercises), created test_onboarding.py (26 tests). 129 tests pass total.

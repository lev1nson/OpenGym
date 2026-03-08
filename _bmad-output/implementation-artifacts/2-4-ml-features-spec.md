# Story 2.4: ML Feature Specification and Validation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to define and validate the complete ML feature specification,
so that the RPEModel receives clean, well-structured input data for training and inference.

## Acceptance Criteria

**Given** все таблицы мастер-данных заполнены (Stories 2.1-2.3: muscle_groups, movement_patterns, exercises, equipment)

**When** агент создаёт документ `docs/ml-feature-spec.md` и модуль `gym_coach_brain/data/features.py` с FeatureVector builder

**Then** документ описывает полный feature vector с 14 фичами:
- `exercise_id` (categorical — per-athlete, per-exercise персонализация)
- `movement_pattern_id` (categorical, int 0–6)
- `primary_muscle_id` (categorical)
- `is_compound` (bool → int 0/1)
- `stretch_mediated` (bool → int 0/1)
- `equipment_type` (categorical, int — EquipmentType enum ordinal)
- `set_number` (int)
- `weight_kg` (float)
- `reps` (int)
- `historical_rpe` (float, из WorkoutSet.rpe прошлых сессий)
- `avg_rpe_last_3_sessions_for_exercise` (float, скользящее среднее RPE по athlete+exercise)
- `sessions_count_for_exercise` (int, количество сессий с данным упражнением у атлета)
- `readiness_score` (float, из ReadinessLog.recovery_score)
- `days_since_last_session` (int, days since most recent completed session)

**And** для каждой фичи указаны: тип, диапазон значений, метод нормализации

**And** для фич с cold start определены fallback значения:
- `avg_rpe_last_3_sessions_for_exercise` → медиана RPE по всем упражнениям из seed data
- `sessions_count_for_exercise` → 0
- `historical_rpe` → глобальная медиана RPE (6.0 для новых атлетов)

**And** валидационный скрипт `python -m gym_coach_brain.data.validate_features` проходит без ошибок:
все фичи присутствуют в схеме БД (проверяет таблицы и колонки через SQLAlchemy inspect)

**And** `pytest tests/test_data/test_features.py` проходит: feature vector собирается без None/NaN значений для seed упражнений

**And** `pytest tests/test_data/test_features.py::test_cold_start` проходит: feature vector для атлета без истории по упражнению заполняется fallback значениями (не None, не NaN)

**And** существующие 92 тестов продолжают PASS (регрессии не допускаются)

**Definition of Done для Epic 2:** `docs/ml-feature-spec.md` должен пройти review у архитектора (архитектурная роль) до старта Epic 5 — подтверждается что feature vector достаточен для RPEModel.

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: baseline)
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться что 92 теста PASS
  - [x] Убедиться что `src/gym_coach_brain/data/features.py` НЕ существует
  - [x] Убедиться что `src/gym_coach_brain/data/validate_features.py` НЕ существует
  - [x] Убедиться что `tests/test_data/test_features.py` НЕ существует
  - [x] Убедиться что `docs/ml-feature-spec.md` НЕ существует

- [x] **Создать `src/gym_coach_brain/data/features.py`** (AC: feature vector builder)
  - [x] Создать dataclass `FeatureVector` с 14 полями (все float/int, NO None)
  - [x] Реализовать `build_feature_vector(exercise_id, session_id, session, cold_start_rpe=6.0)` → `FeatureVector`
  - [x] Получить exercise данные из `exercises` JOIN `muscle_groups`, `movement_patterns`
  - [x] `equipment_type_int`: ordinal из `list(EquipmentType)` (alphabetical enum ordering)
  - [x] `historical_rpe`: последний RPE из `WorkoutSet.rpe` для athlete+exercise (fallback: 6.0)
  - [x] `avg_rpe_last_3_sessions_for_exercise`: avg RPE из последних 3 сессий с этим упражнением (fallback: 6.0)
  - [x] `sessions_count_for_exercise`: COUNT DISTINCT session_id где exercise использовалось (fallback: 0)
  - [x] `readiness_score`: `ReadinessLog.recovery_score` за последнюю дату (fallback: 5.0)
  - [x] `days_since_last_session`: days между today и последней completed session (fallback: 0)
  - [x] ALL fallbacks: если нет данных → numeric default (не None, не NaN)
  - [x] Проверить что `FeatureVector` содержит ТОЛЬКО numeric типы (float/int)

- [x] **Создать `src/gym_coach_brain/data/validate_features.py`** (AC: validate script)
  - [x] `if __name__ == "__main__":` entry point для `python -m gym_coach_brain.data.validate_features`
  - [x] Функция `validate_schema(engine)` через `sqlalchemy.inspect`
  - [x] Проверить наличие всех нужных таблиц: `exercises`, `workout_sets`, `readiness_logs`, `workout_sessions`, `muscle_groups`, `movement_patterns`
  - [x] Проверить наличие нужных колонок в каждой таблице
  - [x] Проверить что `EquipmentType` enum имеет ожидаемые значения
  - [x] Exit code 0 при успехе, exit code 1 при ошибке с конкретным сообщением

- [x] **Создать `docs/ml-feature-spec.md`** (AC: specification document)
  - [x] Заголовок, версия, дата
  - [x] Feature vector overview: 14 фичей, их типы, назначение
  - [x] Таблица каждой фичи: имя, тип, диапазон, нормализация, источник (таблица.колонка)
  - [x] Cold start fallbacks секция
  - [x] Секция нормализации для PyTorch модели
  - [x] SQL примеры для ключевых агрегатных фичей

- [x] **Создать `tests/test_data/test_features.py`** (AC: test coverage)
  - [x] Fixture `feature_session` — in-memory DB + seed_taxonomy() + seed_exercises()
  - [x] `test_feature_vector_no_none_nan`: build_feature_vector на seed упражнении → нет None, нет NaN
  - [x] `test_cold_start`: атлет без истории → все fallback значения (sessions_count=0, historical_rpe=6.0)
  - [x] `test_feature_vector_with_history`: 3 сессии с рабочими RPE → avg корректно считается
  - [x] `test_equipment_type_is_int`: equipment_type_int в диапазоне 0-7
  - [x] `test_all_features_numeric`: все 14 полей — float или int

- [x] **Финальная верификация**
  - [x] `cd gym-coach-brain && uv run pytest` — 99 тестов PASS (92 original + 7 new, no regressions)
  - [x] `cd gym-coach-brain && python -m gym_coach_brain.data.validate_features` — exit 0
  - [x] `docs/ml-feature-spec.md` создан в project root `docs/` (не в `_bmad-output/`)
  - [x] НЕТ новых Alembic-миграций (схема не меняется в этой истории)

## Dev Notes

### Текущее состояние после Story 2.3

```
src/gym_coach_brain/
├── data/
│   ├── __init__.py
│   ├── models.py          ← все 9 моделей: MuscleGroup, MovementPattern, Equipment,
│   │                         Exercise, WorkoutSession, WorkoutSet, ReadinessLog,
│   │                         MLJob, RPEPrediction
│   ├── session.py         ← engine + Session factory
│   └── seed.py            ← seed_taxonomy(), seed_exercises(), seed_equipment(), seed_all()
├── core/
│   ├── __init__.py
│   ├── science.py
│   └── puos.py            ← fractional_volume()
├── api/
│   ├── __init__.py
│   └── handlers.py        ← handle_exercise_add()
└── exceptions.py

tests/
├── test_core/
├── test_data/
│   ├── test_models.py          ← структурные тесты моделей
│   ├── test_seed_coverage.py   ← coverage тесты seed
│   └── test_exercises.py       ← exercise + equipment seed тесты
└── test_api/
    ├── __init__.py
    └── test_handlers.py        ← 7 тестов для handle_exercise_add

docs/                       ← project root (не в gym-coach-brain/)
├── architecture.md
├── data-models.md
├── development-guide.md
└── ...                     ← ml-feature-spec.md СОЗДАТЬ ЗДЕСЬ
```

**Baseline**: 92 теста PASS (верифицировано)

### ⚠️ КРИТИЧЕСКИЙ КОНТЕКСТ: Откуда брать данные для feature vector

**Схема данных уже существует, NEW код не меняет её:**

```python
# WorkoutSet — источник historical_rpe, avg_rpe, sessions_count, set_number, weight_kg, reps
class WorkoutSet(Base):
    session_id     → ForeignKey("workout_sessions.id")
    exercise_id    → ForeignKey("exercises.id")
    set_number     # set number within session
    weight_kg      # float
    reps           # int
    rpe            # COMPUTED: 10.0 - rir. NULL если rir = NULL
    rir            # athlete input (0=failure, 4=easy)

# ReadinessLog — источник readiness_score
class ReadinessLog(Base):
    session_date   # ISO 8601
    recovery_score # composite float

# WorkoutSession — источник days_since_last_session
class WorkoutSession(Base):
    session_date  # ISO 8601
    status        # "planned" | "active" | "completed"
```

**ВАЖНО: `rpe` может быть NULL** в `WorkoutSet` если `rir` не задан.
Весь код feature builder должен обрабатывать NULL RPE через fallback.

### Полная реализация `features.py`

```python
# src/gym_coach_brain/data/features.py
"""
ML feature vector builder for RPEModel.

Assembles a 14-dimensional feature vector from the database for a given
(exercise_id, session_id) pair. All values are numeric (float/int).
Cold start fallbacks ensure no None/NaN values.

Cold start defaults:
- historical_rpe: 6.0 (moderate perceived effort — reasonable global median)
- avg_rpe_last_3_sessions_for_exercise: 6.0
- sessions_count_for_exercise: 0
- readiness_score: 5.0 (neutral recovery — midpoint of 1-10 scale)
- days_since_last_session: 0 (first session → no gap)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import (
    EquipmentType,
    Exercise,
    MuscleGroup,
    MovementPattern,
    ReadinessLog,
    WorkoutSession,
    WorkoutSet,
)

# Stable ordering for equipment_type → int mapping
_EQUIPMENT_ORDER: list[str] = sorted(e.value for e in EquipmentType)

# Cold start defaults
_DEFAULT_RPE: float = 6.0
_DEFAULT_READINESS: float = 5.0
_DEFAULT_DAYS_SINCE: int = 0
_DEFAULT_SESSIONS_COUNT: int = 0


@dataclass
class FeatureVector:
    """14-dimensional feature vector for RPEModel input.

    All fields are numeric (float or int). Never None, never NaN.
    """
    exercise_id: int
    movement_pattern_id: int
    primary_muscle_id: int
    is_compound: int                              # bool → 0/1
    stretch_mediated: int                          # bool → 0/1
    equipment_type_int: int                        # EquipmentType ordinal 0-7
    set_number: int
    weight_kg: float
    reps: int
    historical_rpe: float                          # last RPE for this athlete+exercise
    avg_rpe_last_3_sessions_for_exercise: float    # rolling avg RPE, last 3 sessions
    sessions_count_for_exercise: int               # total sessions with this exercise
    readiness_score: float                         # from ReadinessLog.recovery_score
    days_since_last_session: int                   # days since last completed session


def build_feature_vector(
    exercise_id: int,
    session_id: int,
    set_number: int,
    weight_kg: float,
    reps: int,
    session: Session,
    cold_start_rpe: float = _DEFAULT_RPE,
) -> FeatureVector:
    """Build a complete feature vector for a given exercise+session context.

    Args:
        exercise_id: Exercise PK from exercises table
        session_id: Current WorkoutSession PK
        set_number: Set number within the session (1-based)
        weight_kg: Weight to be used in this set
        reps: Planned repetitions
        session: SQLAlchemy Session (caller manages lifecycle)
        cold_start_rpe: Fallback RPE when no history exists (default 6.0)

    Returns:
        FeatureVector with all 14 features. Never raises for missing data.
    """
    # ── Exercise static features ───────────────────────────────────────────────
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise ValueError(f"Exercise {exercise_id} not found in database")

    equipment_type_int = _EQUIPMENT_ORDER.index(exercise.equipment_type.value)

    # ── Historical RPE for this exercise ──────────────────────────────────────
    last_rpe_row = (
        session.execute(
            select(WorkoutSet.rpe)
            .where(
                WorkoutSet.exercise_id == exercise_id,
                WorkoutSet.session_id != session_id,
                WorkoutSet.rpe.is_not(None),
            )
            .order_by(WorkoutSet.id.desc())
            .limit(1)
        )
        .first()
    )
    historical_rpe: float = last_rpe_row[0] if last_rpe_row else cold_start_rpe

    # ── Avg RPE last 3 sessions for this exercise ──────────────────────────────
    # Get last 3 distinct session_ids with RPE data for this exercise
    recent_sessions_with_rpe = (
        session.execute(
            select(WorkoutSet.session_id)
            .where(
                WorkoutSet.exercise_id == exercise_id,
                WorkoutSet.session_id != session_id,
                WorkoutSet.rpe.is_not(None),
            )
            .distinct()
            .order_by(WorkoutSet.session_id.desc())
            .limit(3)
        )
        .scalars()
        .all()
    )

    if recent_sessions_with_rpe:
        avg_rpe_row = session.execute(
            select(func.avg(WorkoutSet.rpe))
            .where(
                WorkoutSet.exercise_id == exercise_id,
                WorkoutSet.session_id.in_(recent_sessions_with_rpe),
                WorkoutSet.rpe.is_not(None),
            )
        ).scalar()
        avg_rpe_last_3 = float(avg_rpe_row) if avg_rpe_row is not None else cold_start_rpe
    else:
        avg_rpe_last_3 = cold_start_rpe

    # ── Sessions count for this exercise ──────────────────────────────────────
    sessions_count = session.execute(
        select(func.count(WorkoutSet.session_id.distinct()))
        .where(
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSet.session_id != session_id,
        )
    ).scalar() or 0

    # ── Readiness score (most recent log entry) ────────────────────────────────
    readiness_row = (
        session.execute(
            select(ReadinessLog.recovery_score)
            .order_by(ReadinessLog.session_date.desc())
            .limit(1)
        )
        .scalar()
    )
    readiness_score: float = float(readiness_row) if readiness_row is not None else _DEFAULT_READINESS

    # ── Days since last session ────────────────────────────────────────────────
    last_session_date_row = (
        session.execute(
            select(WorkoutSession.session_date)
            .where(
                WorkoutSession.status == "completed",
                WorkoutSession.id != session_id,
            )
            .order_by(WorkoutSession.session_date.desc())
            .limit(1)
        )
        .scalar()
    )

    if last_session_date_row:
        try:
            last_dt = datetime.fromisoformat(last_session_date_row)
            # Architecture rule: "НЕ datetime.now() (localtime risk)". 
            # Use utcnow() as defined in "Write: datetime.utcnow().isoformat()" pattern.
            now = datetime.utcnow()
            days_since = max(0, (now - last_dt).days)
        except (ValueError, TypeError):
            days_since = _DEFAULT_DAYS_SINCE
    else:
        days_since = _DEFAULT_DAYS_SINCE

    return FeatureVector(
        exercise_id=exercise_id,
        movement_pattern_id=exercise.movement_pattern_id,
        primary_muscle_id=exercise.primary_muscle_id,
        is_compound=int(exercise.is_compound),
        stretch_mediated=int(exercise.stretch_mediated),
        equipment_type_int=equipment_type_int,
        set_number=set_number,
        weight_kg=float(weight_kg),
        reps=int(reps),
        historical_rpe=historical_rpe,
        avg_rpe_last_3_sessions_for_exercise=avg_rpe_last_3,
        sessions_count_for_exercise=int(sessions_count),
        readiness_score=readiness_score,
        days_since_last_session=days_since,
    )
```

### Полная реализация `validate_features.py`

```python
# src/gym_coach_brain/data/validate_features.py
"""
ML feature vector schema validator.

Usage:
    python -m gym_coach_brain.data.validate_features <database_url>

Validates that all tables and columns required for feature vector assembly
exist in the database schema. Exits 0 on success, 1 on failure.
"""
import sys

from sqlalchemy import create_engine, inspect

from gym_coach_brain.data.models import Base, EquipmentType


# Feature vector schema requirements:
# {table_name: [required_columns]}
REQUIRED_SCHEMA = {
    "exercises": [
        "id", "primary_muscle_id", "movement_pattern_id",
        "is_compound", "stretch_mediated", "equipment_type",
    ],
    "muscle_groups": ["id", "name"],
    "movement_patterns": ["id", "name"],
    "workout_sets": [
        "id", "session_id", "exercise_id",
        "set_number", "weight_kg", "reps", "rpe",
    ],
    "workout_sessions": ["id", "session_date", "status"],
    "readiness_logs": ["id", "session_date", "recovery_score"],
}

# Expected EquipmentType enum values for feature encoding
EXPECTED_EQUIPMENT_TYPES = sorted(e.value for e in EquipmentType)


def validate_schema(engine) -> list[str]:
    """Return list of validation errors. Empty list = success."""
    errors: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, required_cols in REQUIRED_SCHEMA.items():
        if table not in existing_tables:
            errors.append(f"MISSING TABLE: {table}")
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table)}
        for col in required_cols:
            if col not in existing_cols:
                errors.append(f"MISSING COLUMN: {table}.{col}")

    # Validate equipment type ordering consistency (feature encoding depends on this)
    if len(EXPECTED_EQUIPMENT_TYPES) != 8:
        errors.append(
            f"EquipmentType enum has {len(EXPECTED_EQUIPMENT_TYPES)} values, expected 8. "
            f"feature encoding depends on stable ordering."
        )

    return errors


if __name__ == "__main__":
    # Use database URL if provided, otherwise default to gym_coach.sqlite
    # To truly validate migrations, we do NOT call Base.metadata.create_all(engine)
    # when checking a real file — we want to ensure Alembic did its job.
    db_url = sys.argv[1] if len(sys.argv) > 1 else "sqlite:///gym_coach.sqlite"
    
    # If using memory, we create it for unit test purposes
    engine = create_engine(db_url)
    if ":memory:" in db_url:
        Base.metadata.create_all(engine)

    errors = validate_schema(engine)

    if errors:
        print(f"❌ Feature schema validation FAILED for {db_url}:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"✅ Feature schema validation PASSED for {db_url}")
    print(f"   Tables verified: {list(REQUIRED_SCHEMA.keys())}")
    print(f"   Equipment types ({len(EXPECTED_EQUIPMENT_TYPES)}): {EXPECTED_EQUIPMENT_TYPES}")
    sys.exit(0)
```

### Спецификация `tests/test_data/test_features.py`

```python
# tests/test_data/test_features.py
"""
Tests for data/features.py — ML feature vector builder.

Uses in-memory DB with seed data. Validates:
- No None/NaN in feature vector for seeded exercises
- Cold start fallbacks work correctly
- Historical RPE aggregation
- Numeric type constraints
"""
import math

import pytest

from gym_coach_brain.data.features import FeatureVector, build_feature_vector, _EQUIPMENT_ORDER
from gym_coach_brain.data.models import (
    Base, Exercise, MuscleGroup, ReadinessLog, WorkoutSession, WorkoutSet,
)
from gym_coach_brain.data.seed import seed_taxonomy, seed_exercises


@pytest.fixture
def feature_session(db_session):
    """Reuse db_session from conftest.py, seeding taxonomy + exercises."""
    seed_taxonomy(db_session)
    seed_exercises(db_session)
    db_session.commit()
    return db_session


@pytest.fixture
def session_id(feature_session):
    """Create a placeholder workout session and return its ID."""
    ws = WorkoutSession(session_date="2026-03-08T10:00:00", status="active")
    feature_session.add(ws)
    feature_session.flush()
    return ws.id


def _get_first_exercise(session) -> Exercise:
    return session.query(Exercise).first()


# ─── PRIMARY TESTS (required by AC) ───────────────────────────────────────────

def test_feature_vector_no_none_nan(feature_session, session_id):
    """Feature vector has no None or NaN for seed exercise (cold start). [AC primary]"""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    # Check all 14 fields
    for field_name, value in vars(fv).items():
        assert value is not None, f"Field {field_name} is None"
        if isinstance(value, float):
            assert not math.isnan(value), f"Field {field_name} is NaN"


def test_cold_start(feature_session, session_id):
    """Cold start: athlete with no history uses fallback values (not None, not NaN). [AC cold_start]"""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=80.0,
        reps=8,
        session=feature_session,
    )
    # Cold start expectations
    assert fv.historical_rpe == 6.0, f"Expected cold start RPE 6.0, got {fv.historical_rpe}"
    assert fv.avg_rpe_last_3_sessions_for_exercise == 6.0
    assert fv.sessions_count_for_exercise == 0
    assert fv.readiness_score == 5.0  # default readiness
    assert fv.days_since_last_session == 0  # no prior sessions

    # Verify no None / NaN anywhere
    for field_name, value in vars(fv).items():
        assert value is not None, f"Cold start field {field_name} is None"
        if isinstance(value, float):
            assert not math.isnan(value), f"Cold start field {field_name} is NaN"


# ─── SUPPORTING TESTS ─────────────────────────────────────────────────────────

def test_feature_vector_with_history(feature_session):
    """Feature vector with 3 prior sessions computes avg RPE correctly."""
    exercise = _get_first_exercise(feature_session)

    # Create 3 completed sessions with known RPE data
    sessions = []
    for i in range(3):
        ws = WorkoutSession(
            session_date=f"2026-03-0{i+1}T10:00:00",
            status="completed",
        )
        feature_session.add(ws)
        feature_session.flush()
        wset = WorkoutSet(
            session_id=ws.id,
            exercise_id=exercise.id,
            set_number=1,
            weight_kg=100.0,
            reps=5,
            rpe=7.0 + i,  # 7.0, 8.0, 9.0
        )
        feature_session.add(wset)
        sessions.append(ws.id)

    # Current session (not completed)
    current_ws = WorkoutSession(session_date="2026-03-08T10:00:00", status="active")
    feature_session.add(current_ws)
    feature_session.flush()

    feature_session.commit()

    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=current_ws.id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )

    # avg of [7.0, 8.0, 9.0] = 8.0
    assert abs(fv.avg_rpe_last_3_sessions_for_exercise - 8.0) < 0.01
    assert fv.sessions_count_for_exercise == 3
    assert fv.historical_rpe == 9.0  # most recent set
    assert fv.days_since_last_session >= 0


def test_equipment_type_is_int(feature_session, session_id):
    """equipment_type_int is an integer in range 0-7."""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    assert isinstance(fv.equipment_type_int, int)
    assert 0 <= fv.equipment_type_int <= 7, f"equipment_type_int={fv.equipment_type_int} out of range"


def test_all_features_numeric(feature_session, session_id):
    """All 14 feature vector fields are float or int (never str, bool, None)."""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    for field_name, value in vars(fv).items():
        assert isinstance(value, (int, float)), (
            f"Field {field_name} is {type(value).__name__}, expected int or float"
        )
        # bool is subclass of int in Python — disallow it
        assert not isinstance(value, bool), f"Field {field_name} is bool, use int 0/1 instead"


def test_is_compound_and_stretch_mediated_are_int(feature_session, session_id):
    """is_compound and stretch_mediated are int 0 or 1 (not Python bool)."""
    exercise = _get_first_exercise(feature_session)
    fv = build_feature_vector(
        exercise_id=exercise.id,
        session_id=session_id,
        set_number=1,
        weight_kg=100.0,
        reps=5,
        session=feature_session,
    )
    assert fv.is_compound in (0, 1)
    assert fv.stretch_mediated in (0, 1)
    assert not isinstance(fv.is_compound, bool)
    assert not isinstance(fv.stretch_mediated, bool)


def test_equipment_order_is_stable():
    """_EQUIPMENT_ORDER is deterministic — critical for feature encoding stability."""
    order1 = sorted(e.value for e in __import__("gym_coach_brain.data.models", fromlist=["EquipmentType"]).EquipmentType)
    assert _EQUIPMENT_ORDER == order1, "Equipment ordering must be alphabetically sorted and stable"
    assert len(_EQUIPMENT_ORDER) == 8
```

### Architecture Compliance

**Import pattern (ОБЯЗАТЕЛЬНО):**
```python
# ПРАВИЛЬНО:
from gym_coach_brain.data.features import FeatureVector, build_feature_vector
from gym_coach_brain.data.models import Exercise, EquipmentType, WorkoutSet
from gym_coach_brain.data.validate_features import validate_schema

# ЗАПРЕЩЕНО:
from ..data.features import ...    # relative imports запрещены
import gym_coach_brain             # не использовать root import
```

**Session pattern:**
```python
# ПРАВИЛЬНО — build_feature_vector принимает session как параметр
fv = build_feature_vector(exercise_id=..., session_id=..., session=session)

# ЗАПРЕЩЕНО — не создавать session внутри функции
def build_feature_vector(...):
    with Session(engine) as session:  # ← ЗАПРЕЩЕНО
        ...
```

**Нет новых Alembic миграций** — Story 2.4 не изменяет схему БД. Только новые Python файлы и docs/ml-feature-spec.md.

**`validate_features.py` использует in-memory DB** — не требует prod БД, проверяет ORM definitions.

**Sources:**
- [Source: _bmad-output/planning-artifacts/architecture.md#Import Rules]
- [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns → Test Fixtures]
- [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns]

### Key SQL Queries for Feature Assembly

```sql
-- historical_rpe: last RPE for this athlete+exercise (excluding current session)
SELECT rpe FROM workout_sets
WHERE exercise_id = :exercise_id
  AND session_id != :session_id
  AND rpe IS NOT NULL
ORDER BY id DESC
LIMIT 1;

-- avg_rpe_last_3_sessions: average RPE across last 3 distinct sessions
SELECT AVG(rpe) FROM workout_sets
WHERE exercise_id = :exercise_id
  AND session_id IN (
    SELECT DISTINCT session_id FROM workout_sets
    WHERE exercise_id = :exercise_id AND rpe IS NOT NULL
    ORDER BY session_id DESC LIMIT 3
  )
  AND rpe IS NOT NULL;

-- sessions_count_for_exercise
SELECT COUNT(DISTINCT session_id) FROM workout_sets
WHERE exercise_id = :exercise_id
  AND session_id != :session_id;

-- readiness_score
SELECT recovery_score FROM readiness_logs
ORDER BY session_date DESC LIMIT 1;

-- days_since_last_session
SELECT session_date FROM workout_sessions
WHERE status = 'completed' AND id != :session_id
ORDER BY session_date DESC LIMIT 1;
```

### Learnings из предыдущих историй (2.1, 2.2, 2.3)

1. **92 теста PASS** — baseline. НЕ ломать.
2. **`uv run pytest` pattern** — всегда запускать через `uv`.
3. **`conftest.py`** — использовать `db_session` fixture для изоляции тестов.
4. **`models.py` НЕ изменять** — схема завершена, Story 2.4 не добавляет колонки.
5. **`bool` vs `int`**: SQLAlchemy `Boolean` columns возвращают Python `bool`. Явно конвертировать через `int()` для feature vector.
6. **`WorkoutSet.rpe` может быть NULL** — `rpe = Column(Float, nullable=True)`. Всегда фильтровать `WorkoutSet.rpe.is_not(None)`.
7. **НЕ делать git commit** — dev agent только реализует.
8. **`docs/` в project root** — это `/gym-coach-brain/docs/` (уже существует с другими файлами).

**Source:** [Source: _bmad-output/implementation-artifacts/2-3-equipment-catalog.md#Learnings]

### Git Intelligence

```
Последние 5 коммитов: исключительно README изменения (11b8cbb, 425df73, d005f82, e324018, a72869e)
gym-coach-brain код: untracked/modified в git (не закоммичен)
Dev agent НЕ коммитит.
```

### Project Structure After Story 2.4

**Добавляется:**
```
src/gym_coach_brain/
└── data/
    ├── features.py          ← СОЗДАТЬ (FeatureVector + build_feature_vector)
    └── validate_features.py ← СОЗДАТЬ (-m entrypoint)

tests/
└── test_data/
    └── test_features.py     ← СОЗДАТЬ

docs/                        ← В PROJECT ROOT (gym-coach-brain/docs/)
└── ml-feature-spec.md       ← СОЗДАТЬ
```

**Что НЕ трогаем:**
- `alembic/` — никаких новых миграций
- `data/models.py` — схема не меняется
- Все существующие тесты — не трогаем (за исключением исправлений по результатам ревью)

### Definition of Done — Epic 2

После завершения Story 2.4 Epic 2 считается **технически завершённым**.
Перед стартом Epic 5 (ML): `docs/ml-feature-spec.md` должен получить review от архитектора — подтверждение что feature vector достаточен для RPEModel обучения без переработки.

### References

- Story 2.4 requirements: [Source: _bmad-output/planning-artifacts/epics/epic-2.md#Story 2.4]
- Architecture ML architecture: [Source: _bmad-output/planning-artifacts/architecture.md#ML Architecture]
- Architecture ML features: [Source: _bmad-output/planning-artifacts/architecture.md#ML Architecture → input features]
- Architecture import rules: [Source: _bmad-output/planning-artifacts/architecture.md#Import Rules]
- Test fixture pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns → Test Fixtures]
- SQLAlchemy session pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]
- Previous story context: [Source: _bmad-output/implementation-artifacts/2-3-equipment-catalog.md]
- WorkoutSet.rpe nullable: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#WorkoutSet]
- Exercise schema: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#Exercise]
- ML job queue: [Source: _bmad-output/planning-artifacts/architecture.md#ML Job Queue]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Fixed `datetime.utcnow()` violation in `features.py`.
- Fixed `validate_features.py` to support real DB URL validation.
- Fixed `test_features.py` to reuse `db_session` from `conftest.py`.

### Completion Notes List

- ✅ Created `FeatureVector` dataclass (14 fields, all float/int, never None/NaN)
- ✅ Implemented `build_feature_vector()` with full cold start fallback logic
- ✅ Equipment type encoding: alphabetically sorted `_EQUIPMENT_ORDER` for stable ordinal mapping
- ✅ NULL-safe RPE queries: all WorkoutSet.rpe queries filter `.is_not(None)`
- ✅ `validate_features.py` supports real DB validation and in-memory fallback
- ✅ 7 new tests added covering: no-None/NaN, cold start, historical aggregation, type constraints, encoding stability
- ✅ Full regression suite: 99 tests PASS (92 original + 7 new)
- ✅ `docs/ml-feature-spec.md` created with full feature table, normalization guidance, SQL examples, DoD for Epic 5

### File List

- `gym-coach-brain/src/gym_coach_brain/data/features.py`
- `gym-coach-brain/src/gym_coach_brain/data/validate_features.py`
- `gym-coach-brain/tests/test_data/test_features.py`
- `docs/ml-feature-spec.md`
- `gym-coach-brain/src/gym_coach_brain/core/science.py` (modified: exception type fix)
- `gym-coach-brain/src/gym_coach_brain/data/seed.py` (modified: added exercises/equipment)
- `gym-coach-brain/tests/conftest.py` (new: shared fixtures)
- `gym-coach-brain/src/gym_coach_brain/api/handlers.py` (modified)
- `gym-coach-brain/src/gym_coach_brain/core/puos.py` (modified)

### Change Log

- 2026-03-08: Story 2.4 implemented and reviewed. Fixed architecture violations and functional defects. ML feature specification and validation complete. Epic 2 technically complete.

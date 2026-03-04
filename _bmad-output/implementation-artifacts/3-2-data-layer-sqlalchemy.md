# Story 3.2: Data Layer — SQLAlchemy модели и Alembic

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to define all SQLAlchemy models and initialize Alembic migrations,
so that the database schema is version-controlled and reproducible.

## Acceptance Criteria

**Given** проект инициализирован (Story 3.1 завершена): sqlalchemy, alembic установлены; `data/__init__.py` существует

**When** агент создаёт `data/models.py`, `data/session.py` и инициализирует Alembic

**Then** `data/models.py` содержит ВСЕ 10 SQLAlchemy моделей (единственный источник истины схемы):
- `UserProfile`, `WorkoutSession`, `WorkoutSet`, `Exercise`, `MuscleGroup`, `MovementPattern`, `Equipment`, `ReadinessLog`, `MLJob`, `RPEPrediction`

**And** `data/models.py` содержит `EquipmentType(str, Enum)` с фиксированными значениями: `barbell`, `dumbbell`, `machine`, `cable`, `bodyweight`, `resistance_band`, `pullup_bar`, `dips_bar`

**And** `data/models.py` содержит `TrainingSplit(str, Enum)` с фиксированными значениями: `ppl`, `upper_lower`, `full_body`, `custom`

**And** `Exercise.equipment_type` использует `SQLAlchemyEnum(EquipmentType)` — не свободная строка

**And** `UserProfile.available_equipment` хранит JSON list of EquipmentType values

**And** `UserProfile.training_split` использует `SQLAlchemyEnum(TrainingSplit)`, default `full_body`

**And** `UserProfile.training_days_per_week: Integer` (3–6), default 3

**And** `WorkoutSet` дополнен полем `rir: Integer nullable` (range 0–4; 0 = до отказа, 4 = очень легко)

**And** `WorkoutSet.rpe: Float nullable` остаётся вычисляемым (rpe = 10.0 - rir) — конвертация в `api/handlers.py`, не в модели

**And** `WorkoutSet` имеет `UniqueConstraint('session_id', 'exercise_id', 'set_number')` — защита от дублирования

**And** `data/session.py` содержит engine factory с `DATABASE_URL` env var (default: `sqlite:///gym_coach.sqlite`)

**And** `data/session.py` содержит `MODEL_DIR` env var (default: `./models/`)

**And** `alembic init alembic` выполнен, `env.py` импортирует `Base` из `data/models.py`

**And** `alembic revision --autogenerate -m "initial_schema"` создаёт корректную миграцию со всеми 10 таблицами, включая поля `UserProfile.training_split`, `training_days_per_week`, `bodyweight_kg`, `initial_weight_coefficients`, `WorkoutSet.rir`, `WorkoutSession.split_day_label`

**And** `alembic revision -m "seed_data"` создаёт `alembic/versions/002_seed_data.py` с seed данными:
- `MuscleGroup`: 10+ групп (chest, back, shoulders, biceps, triceps, quadriceps, hamstrings, glutes, calves, abs)
- `MovementPattern`: 7 паттернов (horizontal_push, vertical_push, horizontal_pull, vertical_pull, squat, hinge, carry)
- `Equipment`: 10+ единиц с `available_home` и `available_gym` флагами
- `Exercise`: 30+ упражнений с корректными FK, `secondary_muscle_ids` (JSON), `is_compound`, `stretch_mediated`, `equipment_type`

**And** для каждой из 10 групп мышц существует хотя бы одно упражнение с `equipment_type=bodyweight`

**And** `alembic upgrade head` применяет оба файла миграции без ошибок

**And** `pytest tests/test_data/test_seed_coverage.py` проходит: каждая MuscleGroup имеет хотя бы один Exercise с `equipment_type=bodyweight`

**And** `pytest tests/test_data/test_models.py` проходит: FK constraints, column types, nullable поля, EquipmentType enum валидация, UniqueConstraint enforcement

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: baseline)
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться что 18 тестов PASS (baseline из Story 3.1)
  - [x] `python -c "import sqlalchemy; import alembic; print('OK')"` — deps доступны
  - [x] `ls src/gym_coach_brain/data/` — есть только `__init__.py`
  - [x] `ls` — нет директории `alembic/`

- [x] **Создать enums в data/models.py**
  - [x] Создать `src/gym_coach_brain/data/models.py`
  - [x] Добавить `EquipmentType(str, Enum)`: barbell, dumbbell, machine, cable, bodyweight, resistance_band, pullup_bar, dips_bar
  - [x] Добавить `TrainingSplit(str, Enum)`: ppl, upper_lower, full_body, custom
  - [x] Добавить `Base = declarative_base()`

- [x] **Создать lookup/reference модели** (без FK)
  - [x] `MuscleGroup`: id, name, body_region, is_push, is_pull, stretch_mediated
  - [x] `MovementPattern`: id, name, category
  - [x] `Equipment`: id, name, type, available_home, available_gym

- [x] **Создать основные модели** (с FK)
  - [x] `UserProfile`: id, bodyweight_kg Float, initial_weight_coefficients TEXT, available_equipment TEXT, training_split SQLAlchemyEnum(TrainingSplit) default full_body, training_days_per_week Integer default 3, + onboarding поля
  - [x] `Exercise`: id, name, primary_muscle_id FK(MuscleGroup), movement_pattern_id FK(MovementPattern), secondary_muscle_ids TEXT, is_compound Boolean, stretch_mediated Boolean, equipment_type SQLAlchemyEnum(EquipmentType)
  - [x] `WorkoutSession`: id, session_date, status, methodology, planned_exercises TEXT nullable, split_day_label String nullable
  - [x] `WorkoutSet`: id, session_id FK(WorkoutSession), exercise_id FK(Exercise), set_number Integer, weight_kg Float, reps Integer, rpe Float nullable, rir Integer nullable, notes String nullable, created_at, UniqueConstraint(session_id, exercise_id, set_number)
  - [x] `ReadinessLog`: id, session_date, sleep_hours Float, stress_level Integer, hrv_score Float nullable, recovery_score Float
  - [x] `MLJob`: id, job_type String, status String default 'pending', session_ids TEXT, created_at, processed_at nullable
  - [x] `RPEPrediction`: id, session_id FK(WorkoutSession), exercise_id Integer, predicted_rpe Float, confidence_score Float, model_version String, created_at

- [x] **Создать data/session.py**
  - [x] `DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_coach.sqlite")`
  - [x] `MODEL_DIR = os.getenv("MODEL_DIR", "./models/")`
  - [x] `get_engine()` функция → `create_engine(DATABASE_URL)`
  - [x] `Session = sessionmaker(bind=engine)` или использовать `Session(engine)`

- [x] **Создать test директории**
  - [x] `mkdir -p tests/test_data && touch tests/test_data/__init__.py`

- [x] **Инициализировать Alembic**
  - [x] `cd gym-coach-brain && alembic init alembic` (или `uv run alembic init alembic`)
  - [x] Отредактировать `alembic/env.py`: импортировать `Base` из `gym_coach_brain.data.models`, установить `target_metadata = Base.metadata`
  - [x] Отредактировать `alembic.ini`: установить `sqlalchemy.url = %(DATABASE_URL)s` (или env var pattern)
  - [x] `uv run alembic revision --autogenerate -m "initial_schema"` → создаёт 001_*.py

- [x] **Создать seed migration**
  - [x] `uv run alembic revision -m "seed_data"` → создаёт 002_*.py (пустой shell)
  - [x] Заполнить `002_seed_data.py` функцией `upgrade()` с INSERT данных:
    - 10+ MuscleGroup записей
    - 7 MovementPattern записей
    - 10+ Equipment записей
    - 30+ Exercise записей (каждая muscle group ≥ 1 bodyweight exercise)
  - [x] `downgrade()` функция должна удалять все seed data

- [x] **Верифицировать migrations**
  - [x] `uv run alembic upgrade head` — без ошибок, создаёт gym_coach.sqlite с обеими миграциями
  - [x] `uv run python -c "from gym_coach_brain.data.models import Base; print(list(Base.metadata.tables.keys()))"` — видим все 10 таблиц

- [x] **Написать тесты**
  - [x] Создать `tests/test_data/test_models.py`: FK constraints, column types, nullable, EquipmentType enum, UniqueConstraint
  - [x] Создать `tests/test_data/test_seed_coverage.py`: каждая MuscleGroup → ≥1 bodyweight Exercise
  - [x] `uv run pytest tests/test_data/ -v` — все тесты PASS

- [x] **Финальная верификация**
  - [x] `uv run pytest` — все тесты PASS (18 existing + новые test_data тесты)
  - [x] Удалить `gym_coach.sqlite` если создан в project root (тесты используют :memory:)

### Review Follow-ups (AI)
- [x] [AI-Review][CRITICAL] RPEPrediction.exercise_id missing ForeignKey("exercises.id") [src/gym_coach_brain/data/models.py:165]
- [x] [AI-Review][HIGH] Exercise.equipment_type should use SQLAlchemyEnum(EquipmentType) per AC [src/gym_coach_brain/data/models.py:92]
- [x] [AI-Review][HIGH] UserProfile.training_split should use SQLAlchemyEnum(TrainingSplit) per AC [src/gym_coach_brain/data/models.py:73]
- [x] [AI-Review][HIGH] WorkoutSet.rir missing range validation (0-4) per AC [src/gym_coach_brain/data/models.py:133]
- [x] [AI-Review][HIGH] UserProfile.training_days_per_week missing range validation (3-6) per AC [src/gym_coach_brain/data/models.py:76]
- [x] [AI-Review][MEDIUM] Brittle Seed Data - use variables/subqueries instead of hardcoded IDs [alembic/versions/73aae0fcf2ec_seed_data.py]
- [x] [AI-Review][MEDIUM] Missing defaults for created_at columns [src/gym_coach_brain/data/models.py]
- [x] [AI-Review][MEDIUM] Missing database-level validation for Enums and status strings [src/gym_coach_brain/data/models.py]
- [x] [AI-Review][LOW] JSON Handling improvements (hybrid_property for serialization) [src/gym_coach_brain/data/models.py]

## Dev Notes

### ⚠️ Текущее состояние после Story 3.1

**Что уже есть:**
- `src/gym_coach_brain/data/__init__.py` — пустой
- `sqlalchemy>=2.0.48`, `alembic>=1.18.4` в deps
- `exceptions.py` с `GymCoachError`, `ScienceLimitError`, `MLPredictionError`, `ConfigError`
- 18 тестов PASS

**Что создаём в этой истории:**
- `src/gym_coach_brain/data/models.py` — все 10 моделей + 2 enums
- `src/gym_coach_brain/data/session.py` — engine factory + env vars
- `alembic/` директория (через `alembic init`)
- `tests/test_data/__init__.py`, `test_models.py`, `test_seed_coverage.py`

**Рабочая директория:** `/home/ubuntu/.openclaw/gym-coach-brain/`

---

### Полная реализация data/models.py

```python
# src/gym_coach_brain/data/models.py
"""
SQLAlchemy ORM models — single source of truth for database schema.

ALL schema changes must be made here first, then regenerated via:
    uv run alembic revision --autogenerate -m "description"
"""
import json
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class EquipmentType(str, Enum):
    barbell = "barbell"
    dumbbell = "dumbbell"
    machine = "machine"
    cable = "cable"
    bodyweight = "bodyweight"
    resistance_band = "resistance_band"
    pullup_bar = "pullup_bar"
    dips_bar = "dips_bar"


class TrainingSplit(str, Enum):
    ppl = "ppl"
    upper_lower = "upper_lower"
    full_body = "full_body"
    custom = "custom"


# ─── Reference / Lookup Tables ────────────────────────────────────────────────

class MuscleGroup(Base):
    __tablename__ = "muscle_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    body_region = Column(String, nullable=False)  # upper / lower / core
    is_push = Column(Boolean, nullable=False, default=False)
    is_pull = Column(Boolean, nullable=False, default=False)
    stretch_mediated = Column(Boolean, nullable=False, default=False)

    exercises = relationship("Exercise", back_populates="primary_muscle", foreign_keys="Exercise.primary_muscle_id")


class MovementPattern(Base):
    __tablename__ = "movement_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)  # push / pull / legs / carry

    exercises = relationship("Exercise", back_populates="movement_pattern")


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)  # matches EquipmentType values
    available_home = Column(Boolean, nullable=False, default=False)
    available_gym = Column(Boolean, nullable=False, default=True)


# ─── Core Models ──────────────────────────────────────────────────────────────

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bodyweight_kg = Column(Float, nullable=True)
    # JSON dict {movement_pattern_name: float} — starting weight coefficients
    initial_weight_coefficients = Column(Text, nullable=True)
    # JSON list of EquipmentType values
    available_equipment = Column(Text, nullable=True, default="[]")
    training_split = Column(
        String,  # stored as string, validated via EquipmentType enum
        nullable=False,
        default=TrainingSplit.full_body.value,
    )
    training_days_per_week = Column(Integer, nullable=False, default=3)
    onboarding_complete = Column(Boolean, nullable=False, default=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=True)


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    primary_muscle_id = Column(Integer, ForeignKey("muscle_groups.id"), nullable=False)
    movement_pattern_id = Column(Integer, ForeignKey("movement_patterns.id"), nullable=False)
    # JSON-encoded list of MuscleGroup IDs
    secondary_muscle_ids = Column(Text, nullable=False, default="[]")
    is_compound = Column(Boolean, nullable=False, default=True)
    stretch_mediated = Column(Boolean, nullable=False, default=False)
    equipment_type = Column(String, nullable=False)  # EquipmentType enum value

    primary_muscle = relationship("MuscleGroup", back_populates="exercises", foreign_keys=[primary_muscle_id])
    movement_pattern = relationship("MovementPattern", back_populates="exercises")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_date = Column(String, nullable=False)  # ISO 8601 UTC
    status = Column(String, nullable=False, default="planned")  # planned / active / completed
    methodology = Column(String, nullable=True)  # strength / hypertrophy / endurance
    # JSON-encoded list of PlannedExercise dicts
    planned_exercises = Column(Text, nullable=True)
    # push / pull / legs / upper / lower / full_body
    split_day_label = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

    sets = relationship("WorkoutSet", back_populates="session")
    rpe_predictions = relationship("RPEPrediction", back_populates="session")


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    set_number = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    # rpe is COMPUTED: 10.0 - rir. Set by api/handlers.py, NOT by model.
    rpe = Column(Float, nullable=True)
    # rir = Reps In Reserve (0=to failure, 4=very easy). Athlete input.
    rir = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "exercise_id", "set_number", name="uq_workout_set"),
    )

    session = relationship("WorkoutSession", back_populates="sets")
    exercise = relationship("Exercise")


class ReadinessLog(Base):
    __tablename__ = "readiness_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_date = Column(String, nullable=False)  # ISO 8601 UTC date
    sleep_hours = Column(Float, nullable=False)
    stress_level = Column(Integer, nullable=False)  # 1–10 scale
    hrv_score = Column(Float, nullable=True)        # optional (wearable)
    recovery_score = Column(Float, nullable=False)  # composite computed score


class MLJob(Base):
    __tablename__ = "ml_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String, nullable=False)    # "FINE_TUNE" | "PREDICT"
    status = Column(String, nullable=False, default="pending")  # pending/processing/done/failed
    session_ids = Column(Text, nullable=False)   # JSON array of session IDs
    created_at = Column(String, nullable=False)
    processed_at = Column(String, nullable=True)


class RPEPrediction(Base):
    __tablename__ = "rpe_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.id"), nullable=False)
    exercise_id = Column(Integer, nullable=False)
    predicted_rpe = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    model_version = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

    session = relationship("WorkoutSession", back_populates="rpe_predictions")
```

---

### Полная реализация data/session.py

```python
# src/gym_coach_brain/data/session.py
"""
Database engine and session factory.

Environment variables:
    DATABASE_URL: SQLAlchemy connection string (default: sqlite:///gym_coach.sqlite)
    MODEL_DIR: Directory for PyTorch model weights (default: ./models/)
"""
import os

from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_coach.sqlite")
MODEL_DIR = os.getenv("MODEL_DIR", "./models/")


def get_engine(url: str = DATABASE_URL):
    """Create SQLAlchemy engine. Use url param to override DATABASE_URL."""
    return _create_engine(url)


# Module-level default engine — created once per process
_engine = None


def get_default_engine():
    """Get or create the default engine (lazy initialization)."""
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def get_session(engine=None) -> Session:
    """Create a new session. Caller is responsible for context management.

    Usage:
        with get_session() as session:
            session.add(...)
            session.commit()
    """
    if engine is None:
        engine = get_default_engine()
    return Session(engine)
```

---

### Alembic env.py: обязательные изменения

После `alembic init alembic`, изменить `alembic/env.py`:

```python
# В начале файла, после imports:
import os
import sys

# Add project src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gym_coach_brain.data.models import Base

# Найти строку: target_metadata = None
# Заменить на:
target_metadata = Base.metadata
```

Изменить `alembic.ini` (строка `sqlalchemy.url`):
```ini
# Закомментировать/заменить хардкодированный URL на env var:
sqlalchemy.url = sqlite:///gym_coach.sqlite
```

Альтернативно — в `env.py` установить `config.set_main_option("sqlalchemy.url", DATABASE_URL)` из `gym_coach_brain.data.session`.

---

### Seed Data: полный список (002_seed_data.py)

**Muscle Groups (10):**
```
chest      | upper | is_push=True  | stretch_mediated=True
back       | upper | is_pull=True  | stretch_mediated=True
shoulders  | upper | is_push=True  | stretch_mediated=False
biceps     | upper | is_pull=True  | stretch_mediated=True
triceps    | upper | is_push=True  | stretch_mediated=True
quadriceps | lower | is_push=True  | stretch_mediated=True
hamstrings | lower | is_pull=True  | stretch_mediated=True
glutes     | lower | is_push=False | stretch_mediated=True
calves     | lower | is_push=True  | stretch_mediated=True
abs        | core  | is_push=False | stretch_mediated=False
```

**Movement Patterns (7):**
```
horizontal_push | push
vertical_push   | push
horizontal_pull | pull
vertical_pull   | pull
squat           | legs
hinge           | legs
carry           | carry
```

**Equipment (10+):**
```
Barbell          | barbell         | home=False | gym=True
Dumbbell (pair)  | dumbbell        | home=True  | gym=True
Barbell+Plates   | barbell         | home=False | gym=True  (gym barbell)
Cable Machine    | cable           | home=False | gym=True
Resistance Band  | resistance_band | home=True  | gym=True
Pull-up Bar      | pullup_bar      | home=True  | gym=True
Dip Bars         | dips_bar        | home=True  | gym=True
Smith Machine    | machine         | home=False | gym=True
Leg Press        | machine         | home=False | gym=True
Cable Fly Station| cable           | home=False | gym=True
```

**Exercises (30+ — bodyweight coverage гарантирована для всех 10 muscle groups):**

| Exercise | Primary Muscle | Movement Pattern | Equipment | Compound | Stretch |
|---|---|---|---|---|---|
| Push-up | chest | horizontal_push | bodyweight | True | True |
| Bench Press | chest | horizontal_push | barbell | True | True |
| Dumbbell Fly | chest | horizontal_push | dumbbell | False | True |
| Pull-up | back | vertical_pull | pullup_bar | True | True |
| Barbell Row | back | horizontal_pull | barbell | True | True |
| Cable Row | back | horizontal_pull | cable | True | True |
| Pike Push-up | shoulders | vertical_push | bodyweight | False | False |
| Overhead Press | shoulders | vertical_push | barbell | True | False |
| Lateral Raise | shoulders | vertical_push | dumbbell | False | False |
| Chin-up | biceps | vertical_pull | pullup_bar | True | True |
| Dumbbell Curl | biceps | horizontal_pull | dumbbell | False | True |
| Resistance Band Curl | biceps | horizontal_pull | resistance_band | False | True |
| Dip | triceps | horizontal_push | dips_bar | True | True |
| Diamond Push-up | triceps | horizontal_push | bodyweight | False | True |
| Tricep Pushdown | triceps | horizontal_push | cable | False | True |
| Bodyweight Squat | quadriceps | squat | bodyweight | True | True |
| Barbell Squat | quadriceps | squat | barbell | True | True |
| Leg Press | quadriceps | squat | machine | True | True |
| Nordic Curl | hamstrings | hinge | bodyweight | False | True |
| Romanian Deadlift | hamstrings | hinge | barbell | True | True |
| Good Morning | hamstrings | hinge | barbell | True | True |
| Glute Bridge | glutes | hinge | bodyweight | False | True |
| Hip Thrust | glutes | hinge | barbell | True | True |
| Cable Pull-Through | glutes | hinge | cable | False | True |
| Calf Raise (standing) | calves | squat | bodyweight | False | True |
| Seated Calf Raise | calves | squat | machine | False | True |
| Dumbbell Calf Raise | calves | squat | dumbbell | False | True |
| Plank | abs | carry | bodyweight | False | False |
| Hanging Leg Raise | abs | vertical_pull | pullup_bar | False | False |
| Ab Wheel Rollout | abs | carry | bodyweight | False | True |
| Deadlift | back | hinge | barbell | True | True |
| Incline Dumbbell Press | chest | horizontal_push | dumbbell | True | True |

**Гарантия bodyweight coverage (CRITICAL AC):**
- chest → Push-up ✅
- back → Pull-up ✅ (pullup_bar)  ← NOTE: pullup_bar equipment — home=True, gym=True
- shoulders → Pike Push-up ✅
- biceps → Chin-up ✅ (pullup_bar) ← NOTE: pullup_bar equipment — home=True
- triceps → Diamond Push-up ✅
- quadriceps → Bodyweight Squat ✅
- hamstrings → Nordic Curl ✅
- glutes → Glute Bridge ✅
- calves → Calf Raise (standing) ✅
- abs → Plank ✅

---

### Architecture Compliance Constraints

**Naming conventions (ОБЯЗАТЕЛЬНО):**
- Tables: `snake_case` plural — `workout_sessions`, `ml_jobs`, `rpe_predictions`
- Columns: `snake_case` — `session_id`, `created_at`, `confidence_score`
- SQLAlchemy models: `PascalCase` singular — `class WorkoutSession(Base)`
- Foreign keys: `{table_singular}_id` — `session_id`, `exercise_id`
- Alembic revision message: imperative verb — `initial_schema`, `seed_data`

**ML-specific naming:**
- Job types: string enum uppercase — `"FINE_TUNE"`, `"PREDICT"`
- Job statuses: string enum lowercase — `"pending"`, `"processing"`, `"done"`, `"failed"`

**DateTime:**
- В SQLite: ISO 8601 UTC strings — `"2026-03-02T14:30:00"`
- Write: `datetime.utcnow().isoformat()`
- Read: `datetime.fromisoformat(value)`
- НЕ unix timestamps, НЕ `datetime.now()`

**SQLAlchemy Session Pattern (ОБЯЗАТЕЛЬНО):**
```python
# ПРАВИЛЬНО:
with Session(engine) as session:
    session.add(obj)
    session.commit()

# ЗАПРЕЩЕНО:
session = Session(engine)
session.close()  # без context manager
```

**Alembic Single Source of Truth:**
- SQLAlchemy models = единственный источник истины
- Alembic: ТОЛЬКО `--autogenerate` — никогда manual SQL в миграциях
- Тесты используют `Base.metadata.create_all(engine)` (быстро, без миграций)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]

---

### Import Rules (КРИТИЧНО)

```python
# ПРАВИЛЬНО — абсолютные импорты:
from gym_coach_brain.data.models import Base, UserProfile, Exercise
from gym_coach_brain.data.session import get_session, get_engine
from gym_coach_brain.exceptions import GymCoachError

# ЗАПРЕЩЕНО — relative импорты:
from ..data.models import Base       # запрещено
from .models import UserProfile      # запрещено
```

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]

---

### Testing Requirements

**Test fixtures в `tests/conftest.py` (добавить если не существует):**

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import Base
from gym_coach_brain.core.science import ScienceConfig


@pytest.fixture
def db_session():
    """In-memory SQLite session for tests. NO real file."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def db_engine():
    """In-memory engine with schema (no seed data)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine
```

**КРИТИЧНО:**
- НЕ реальный SQLite файл в тестах — только `sqlite:///:memory:`
- `Base.metadata.create_all(engine)` для тестов (не `alembic upgrade head`)

**test_models.py — минимальный набор тестов:**
```python
# tests/test_data/test_models.py
def test_muscle_group_creation(db_session):
    """MuscleGroup can be created with required fields."""

def test_exercise_fk_constraint(db_session):
    """Exercise requires valid primary_muscle_id FK."""

def test_workout_set_unique_constraint(db_session):
    """Duplicate (session_id, exercise_id, set_number) raises IntegrityError."""

def test_equipment_type_values():
    """EquipmentType has exactly 8 values."""

def test_training_split_values():
    """TrainingSplit has exactly 4 values."""

def test_ml_job_status_default(db_session):
    """MLJob.status defaults to 'pending'."""

def test_workout_set_rir_nullable(db_session):
    """WorkoutSet.rir is nullable (can be None)."""

def test_workout_set_rpe_nullable(db_session):
    """WorkoutSet.rpe is nullable (computed by api layer)."""
```

**test_seed_coverage.py:**
```python
# tests/test_data/test_seed_coverage.py
# Uses real alembic migrations (not create_all) via alembic upgrade head
# OR: applies seed data directly to in-memory db for fast testing

def test_each_muscle_group_has_bodyweight_exercise(db_session_with_seed):
    """Every MuscleGroup has at least one Exercise with equipment_type=bodyweight."""
    from gym_coach_brain.data.models import MuscleGroup, Exercise, EquipmentType
    muscle_groups = db_session_with_seed.query(MuscleGroup).all()
    assert len(muscle_groups) >= 10
    for mg in muscle_groups:
        bodyweight_count = db_session_with_seed.query(Exercise).filter(
            Exercise.primary_muscle_id == mg.id,
            Exercise.equipment_type == EquipmentType.bodyweight.value
        ).count()
        assert bodyweight_count >= 1, f"No bodyweight exercise for {mg.name}"
```

**Note:** `db_session_with_seed` fixture нужно создать — либо запускать alembic upgrade head на temp DB, либо напрямую вызывать seed функцию на in-memory DB.

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Test Fixtures]

---

### ⚠️ Важные нюансы реализации

**1. `training_split` хранение:**
Epic 3 AC говорит `UserProfile.training_split` использует `SQLAlchemyEnum(TrainingSplit)`. Однако, использование SQLAlchemy's native Enum type может вызвать проблемы при миграциях. Рекомендуемый подход:
```python
# Хранить как String, валидировать через Python enum
training_split = Column(String, nullable=False, default=TrainingSplit.full_body.value)
# При чтении: TrainingSplit(user_profile.training_split)
```
Аналогично для `Exercise.equipment_type`.

**2. `secondary_muscle_ids` — JSON TEXT:**
```python
# При записи:
exercise.secondary_muscle_ids = json.dumps([1, 3, 5])
# При чтении:
ids = json.loads(exercise.secondary_muscle_ids)
```
НЕ использовать SQLAlchemy JSON type (не поддерживается в SQLite одинаково надёжно).

**3. Alembic autogenerate и Enum types:**
Если используется `SQLAlchemy.Enum(EquipmentType)` (нативный), autogenerate может генерировать лишние ALTER TABLE. Используй `String` в колонках и `SQLAlchemy.Enum` только через CheckConstraint если нужно.

**4. `alembic upgrade head` создаёт файл `gym_coach.sqlite` в CWD.**
В тестах НЕ использовать alembic migrations — только `Base.metadata.create_all(engine)`.
После ручной проверки `alembic upgrade head` — удалить созданный `gym_coach.sqlite` из project root.

**5. `sys.path` в `alembic/env.py`:**
При запуске `uv run alembic`, Python может не найти `gym_coach_brain` пакет если `src/` не в path. Добавить в начало `env.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
```

---

### Previous Story Intelligence (Story 3.1)

**Ключевые выводы:**
1. **18 тестов PASS** после Story 3.1 — это baseline, не ломать
2. **uv run pattern** работает стабильно: `cd gym-coach-brain && uv run pytest`
3. **Структура `data/`** создана — есть только `__init__.py`, всё остальное новое
4. **Логирование (loguru)** установлено но не используется в data layer — не добавлять

**Source:** [Source: _bmad-output/implementation-artifacts/3-1-project-init.md#Completion Notes List]

---

### Git Intelligence

```
Последние коммиты:
0195177 feat: add bmad planning artifacts and expand gym-coach skill
8440199 feat: add gym coach skill
```

**Выводы:**
- `gym-coach-brain/` всё ещё staged but uncommitted (A status в git)
- Dev agent НЕ делает git commit
- Новые файлы (models.py, session.py, alembic/, test_data/) будут untracked — нормально

---

### Project Structure Notes

**После этой истории `gym-coach-brain/` будет выглядеть так:**
```
gym-coach-brain/
├── alembic/
│   ├── alembic.ini              ← создан через alembic init
│   ├── env.py                   ← изменён: Base import + target_metadata
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py  ← autogenerate
│       └── 002_seed_data.py       ← manual seed
├── src/gym_coach_brain/
│   ├── data/
│   │   ├── __init__.py          ← уже существует
│   │   ├── models.py            ← СОЗДАТЬ
│   │   └── session.py           ← СОЗДАТЬ
│   └── exceptions.py            ← уже существует
└── tests/
    ├── conftest.py               ← СОЗДАТЬ (db_session fixture)
    └── test_data/
        ├── __init__.py           ← СОЗДАТЬ
        ├── test_models.py        ← СОЗДАТЬ
        └── test_seed_coverage.py ← СОЗДАТЬ
```

**Конфликт с Epic 2:** Epic 2 Stories не могут начаться пока эта история не завершена. Story 3.2 завершение = `alembic upgrade head` без ошибок + тесты PASS.

---

### References

- Story 3.2 требования: [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Story 3.2]
- SQLAlchemy models structure: [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory Structure]
- Naming patterns: [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns]
- Session pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]
- Test fixtures: [Source: _bmad-output/planning-artifacts/architecture.md#Test Fixtures]
- ML job schema: [Source: _bmad-output/planning-artifacts/architecture.md#ML Job Queue]
- Epic ordering constraint: [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Epic 3 intro]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

N/A — implementation completed without blockers. One spec conflict resolved: `back` and `biceps` muscle groups lacked `bodyweight` exercises (story spec listed Pull-up/Chin-up as `pullup_bar`). Added `Inverted Row` (back, bodyweight) and `Bodyweight Chin-up` (biceps, bodyweight) to satisfy AC.

### Completion Notes List

- Created `data/models.py` with all 10 SQLAlchemy models (DeclarativeBase pattern) and 2 enums (EquipmentType×8, TrainingSplit×4)
- Stored enum values as String columns (not native SQLAlchemy Enum) for Alembic compatibility — validated via Python enum at application layer
- Created `data/session.py` with DATABASE_URL/MODEL_DIR env vars, lazy-initialized default engine, and context-manager-ready `get_session()`
- Initialized Alembic with `env.py` modified to import Base + set `target_metadata = Base.metadata`; DATABASE_URL sourced from `data/session.py`
- `alembic revision --autogenerate` detected all 10 tables correctly
- Seed migration adds: 10 MuscleGroups, 7 MovementPatterns, 10 Equipment, 34 Exercises (every muscle group has ≥1 bodyweight exercise)
- All 43 tests PASS: 18 baseline (Story 3.1) + 17 test_models + 8 test_seed_coverage
- `alembic upgrade head` applies both migrations without errors; gym_coach.sqlite cleaned up post-verification
- **Review Follow-ups resolved (2026-03-04):** 9 AI review items addressed — RPEPrediction FK added, SAEnum for equipment_type/training_split, CheckConstraints for rir(0-4) and training_days(3-6), CheckConstraints for status strings, server_default for all created_at columns, seed migration refactored to name-based subqueries, hybrid_property added for JSON fields
- All 63 tests PASS: 43 prior + 20 new review-coverage tests

### File List

- gym-coach-brain/src/gym_coach_brain/data/models.py (created, then updated with review fixes)
- gym-coach-brain/src/gym_coach_brain/data/session.py (created)
- gym-coach-brain/alembic/env.py (modified — Base import, target_metadata, DATABASE_URL)
- gym-coach-brain/alembic/alembic.ini (generated by alembic init)
- gym-coach-brain/alembic/script.py.mako (generated by alembic init)
- gym-coach-brain/alembic/README (generated by alembic init)
- gym-coach-brain/alembic/versions/4463cdaca3c1_initial_schema.py (regenerated with full constraints)
- gym-coach-brain/alembic/versions/20b31ec66e8e_seed_data.py (created — seed data with subquery lookups)
- gym-coach-brain/tests/test_data/__init__.py (created)
- gym-coach-brain/tests/test_data/test_models.py (created, then extended with 20 review-coverage tests)
- gym-coach-brain/tests/test_data/test_seed_coverage.py (created)

## Change Log

- 2026-03-04: Story 3.2 implemented — SQLAlchemy models (10 tables, 2 enums), Alembic migrations (initial_schema + seed_data with 34 exercises), data/session.py engine factory. All 43 tests PASS.
- 2026-03-04: Addressed code review findings — 9 items resolved (Date: 2026-03-04): RPEPrediction FK, SAEnum for equipment_type/training_split, CheckConstraints for rir range, training_days range, status strings, server_default for created_at, hybrid_property for JSON fields, seed migration refactored to subqueries. Migrations regenerated. 63 tests PASS.
- 2026-03-04: Adversarial Code Review completed. Fixed created_at server_defaults for atomicity, added UserProfile.updated_at on-update logic. Verified all 63 tests PASS.

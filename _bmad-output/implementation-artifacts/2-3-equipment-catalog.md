# Story 2.3: Каталог оборудования и интент exercise_add

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an athlete,
I want the system to know available equipment and allow adding new exercises,
so that workout plans use only exercises I can actually perform.

## Acceptance Criteria

**Given** таблица `exercises` заполнена seed data (Story 2.2 — 37 упражнений с secondary_muscle_ids), таблица `equipment` уже создана в initial_schema из Story 3.2

**When** агент добавляет `seed_equipment(session)` в `data/seed.py`

**Then** seed data покрывает: Barbell (barbell), Dumbbell pair (dumbbell), Cable Machine (cable), Resistance Band (resistance_band), Pull-up Bar (pullup_bar), Dip Bars (dips_bar), Smith Machine (machine), Leg Press Machine (machine), Cable Fly Station (cable), Bodyweight (bodyweight)

**And** seed data вставляется через SQLAlchemy session (НЕ через новую Alembic-миграцию)

**And** `seed_equipment()` идемпотентна: повторный вызов на prod DB (где Alembic 002 уже вставил те же 10 записей) вставляет 0 новых записей

**And** `seed_all()` обновлена для вызова `seed_equipment()` после `seed_taxonomy()` и до `seed_exercises()`

**When** OpenClaw отправляет интент `exercise_add` с параметрами упражнения

**Then** `api/handlers.py::handle_exercise_add(argv, session)` создаёт новое упражнение в `exercises` с полными метаданными

**And** упражнение автоматически доступно для расчёта PUOS (функция `fractional_volume` работает с ним немедленно)

**And** `pytest tests/test_api/test_handlers.py::test_exercise_add` проходит

**And** существующие 81 тест продолжают PASS (регрессии не допускаются)

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: baseline)
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться что 81 тест PASS
  - [x] Убедиться что `src/gym_coach_brain/api/handlers.py` НЕ существует
  - [x] Убедиться что `tests/test_api/` НЕ существует

- [x] **Добавить `seed_equipment` в `data/seed.py`** (AC: equipment seed)
  - [x] Добавить `Equipment` к import из `gym_coach_brain.data.models`
  - [x] Добавить константу `_EQUIPMENT` — 10 записей (имена совпадают с Alembic 002)
  - [x] Реализовать `seed_equipment(session: Session) -> int` с get-or-create логикой
  - [x] Обновить `seed_all(session)`: добавить `eq_count = seed_equipment(session)` и включить в return dict
  - [x] Проверить что `uv run pytest` всё ещё 81 PASS (модификация seed.py не должна ломать тесты)

- [x] **Создать `src/gym_coach_brain/api/handlers.py`** (AC: exercise_add intent)
  - [x] Импортировать: `import argparse`, `import json`, `from sqlalchemy.orm import Session`
  - [x] Импортировать: `from gym_coach_brain.data.models import Exercise, EquipmentType, MuscleGroup, MovementPattern`
  - [x] Реализовать `handle_exercise_add(argv: list[str], session: Session) -> tuple[str, int]`
  - [x] Парсить argv через argparse (Required: `--name`, `--muscle`, `--pattern`, `--equipment`; Optional: `--secondary`, `--compound`, `--stretch`)
  - [x] Валидировать: muscle exists, pattern exists, equipment in EquipmentType values
  - [x] Проверять duplicate name → return `(message, 1)`
  - [x] Создать `Exercise` record и вызвать `session.flush()` (НЕ commit — caller commits)

- [x] **Создать `tests/test_api/__init__.py`** (пустой файл)

- [x] **Создать `tests/test_api/test_handlers.py`** (AC: test coverage)
  - [x] Добавить fixture `handler_session` (in-memory DB + seed_taxonomy + seed_exercises)
  - [x] `test_exercise_add`: создаёт упражнение, exit_code=0, запись в БД
  - [x] `test_exercise_add_with_secondary_muscles`: --secondary передаётся корректно
  - [x] `test_exercise_add_duplicate_name_returns_error`: exit_code=1
  - [x] `test_exercise_add_unknown_muscle_returns_error`: exit_code=1
  - [x] `test_exercise_add_invalid_equipment_returns_error`: exit_code=1
  - [x] `test_exercise_add_available_for_puos`: fractional_volume работает с новым упражнением

- [x] **Финальная верификация**
  - [x] `uv run pytest` — все тесты PASS (81 baseline + новые test_handlers.py тесты)
  - [x] Нет новых Alembic-миграций создано
  - [x] Нет `gym_coach.sqlite` файлов в project root

## Dev Notes

### Текущее состояние после Story 2.2

```
src/gym_coach_brain/
├── data/
│   ├── __init__.py
│   ├── models.py          ← Equipment модель уже существует
│   ├── session.py
│   └── seed.py            ← seed_taxonomy(), seed_exercises(), seed_all() — уже существуют
├── core/
│   ├── __init__.py
│   ├── science.py
│   └── puos.py            ← fractional_volume() — уже существует (Story 2.2)
├── api/
│   └── __init__.py        ← пустой, handlers.py НЕ существует
└── exceptions.py

tests/
├── test_core/
└── test_data/
    ├── test_models.py     ← 69 тестов
    ├── test_seed_coverage.py ← 8 тестов
    └── test_exercises.py  ← 12 тестов (Story 2.2)
# test_api/ НЕ существует
```

**Baseline**: 81 тест PASS (63 структурных + 6 taxonomy + 8 seed_coverage + 12 exercises)

### ⚠️ КРИТИЧЕСКИЙ КОНТЕКСТ: Equipment в Alembic vs seed.py

**Что уже в prod БД (Alembic 002_seed_data.py, Story 3.2):**
```
Equipment записи (10 штук):
('Barbell',           'barbell',          False, True)
('Dumbbell (pair)',   'dumbbell',         True,  True)
('Cable Machine',     'cable',            False, True)
('Resistance Band',   'resistance_band',  True,  True)
('Pull-up Bar',       'pullup_bar',       True,  True)
('Dip Bars',          'dips_bar',         True,  True)
('Smith Machine',     'machine',          False, True)
('Leg Press Machine', 'machine',          False, True)
('Cable Fly Station', 'cable',            False, True)
('Bodyweight',        'bodyweight',       True,  True)
```

**Что делает `seed_equipment()` (Story 2.3):**
- Для КАЖДОЙ записи из `_EQUIPMENT`: INSERT если name не существует, SKIP если существует
- На prod DB: вставляет 0 (все 10 уже есть от Alembic)
- На in-memory test DB: вставляет все 10
- ОБЯЗАТЕЛЬНО: имена в `_EQUIPMENT` должны ТОЧНО совпадать с именами в Alembic

### Модель Equipment

```python
# src/gym_coach_brain/data/models.py — уже существует, НЕ изменять!
class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)      # matches EquipmentType values
    available_home = Column(Boolean, nullable=False, default=False)
    available_gym = Column(Boolean, nullable=False, default=True)
```

### Полная реализация `seed_equipment`

```python
# src/gym_coach_brain/data/seed.py — ДОБАВИТЬ после _EXERCISES константы

from gym_coach_brain.data.models import MuscleGroup, MovementPattern, Exercise, Equipment  # расширить import

_EQUIPMENT = [
    # name                  type                available_home  available_gym
    # ⚠️ Имена ДОЛЖНЫ совпадать с Alembic 002_seed_data.py — идемпотентность на prod
    ("Barbell",             "barbell",          False,          True),
    ("Dumbbell (pair)",     "dumbbell",         True,           True),
    ("Cable Machine",       "cable",            False,          True),
    ("Resistance Band",     "resistance_band",  True,           True),
    ("Pull-up Bar",         "pullup_bar",       True,           True),
    ("Dip Bars",            "dips_bar",         True,           True),
    ("Smith Machine",       "machine",          False,          True),
    ("Leg Press Machine",   "machine",          False,          True),
    ("Cable Fly Station",   "cable",            False,          True),
    ("Bodyweight",          "bodyweight",       True,           True),
]


def seed_equipment(session: Session) -> int:
    """Insert missing equipment records. Returns count of new records inserted.

    Idempotent: matches Alembic 002_seed_data.py exactly.
    Running on prod DB inserts 0 (all 10 already exist from Alembic).
    Running on in-memory test DB inserts all 10.
    """
    inserted = 0
    for name, type_, available_home, available_gym in _EQUIPMENT:
        existing = session.query(Equipment).filter_by(name=name).first()
        if not existing:
            session.add(Equipment(
                name=name,
                type=type_,
                available_home=available_home,
                available_gym=available_gym,
            ))
            inserted += 1
    session.flush()
    return inserted


def seed_all(session: Session) -> dict[str, int]:
    """Seed all reference data: taxonomy + equipment + exercises. Idempotent.
    ORDER MATTERS: taxonomy → equipment → exercises (exercises depend on taxonomy)
    """
    taxonomy_result = seed_taxonomy(session)
    eq_count = seed_equipment(session)
    ex_count = seed_exercises(session)
    return {**taxonomy_result, "equipment": eq_count, "exercises": ex_count}
```

**⚠️ ВАЖНО**: Старая `seed_all()` уже существует. ЗАМЕНИТЬ её целиком на новую версию выше.

### Полная реализация `handle_exercise_add`

```python
# src/gym_coach_brain/api/handlers.py — СОЗДАТЬ (файл не существует)
"""
OpenClaw JSON contract handlers — one function per intent.

Handler contract:
- Input: argv (list[str]), session (SQLAlchemy Session, NOT committed here)
- Output: (stdout: str, exit_code: int)
  exit_code 0 = success
  exit_code 1 = user error (invalid input, duplicate, unknown reference)
  exit_code 2 = system error (reserved for api/main.py layer)
- Handler calls session.flush() but NEVER session.commit() — caller commits
"""
import argparse
import json

from sqlalchemy.orm import Session

from gym_coach_brain.data.models import Equipment, EquipmentType, Exercise, MuscleGroup, MovementPattern


def handle_exercise_add(argv: list[str], session: Session) -> tuple[str, int]:
    """Handle exercise_add intent: create a new exercise with full metadata.

    argv format (all flags, NO "exercise add" prefix — intent name is the verb):
        Required: ["--name", "<name>", "--muscle", "<primary>", "--pattern", "<pattern>",
                   "--equipment", "<equip_type>"]
        Optional: ["--secondary", "muscle1,muscle2", "--compound", "true|false",
                   "--stretch", "true|false"]

    Valid muscle names: same as MuscleGroup.name in muscle_groups table
    Valid pattern names: same as MovementPattern.name in movement_patterns table
    Valid equipment values: barbell, dumbbell, machine, cable, bodyweight,
                            resistance_band, pullup_bar, dips_bar
    """
    parser = argparse.ArgumentParser(prog="exercise_add", add_help=False)
    parser.add_argument("--name", required=True)
    parser.add_argument("--muscle", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--equipment", required=True)
    parser.add_argument("--secondary", default="")
    parser.add_argument("--compound", default="true", choices=["true", "false"])
    parser.add_argument("--stretch", default="false", choices=["true", "false"])

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        valid_eq = sorted(e.value for e in EquipmentType)
        return (
            "exercise_add: missing required arguments.\n"
            "Required: --name, --muscle, --pattern, --equipment\n"
            f"Valid equipment: {valid_eq}",
            1,
        )

    # Validate primary muscle group
    muscle = session.query(MuscleGroup).filter_by(name=args.muscle).first()
    if muscle is None:
        return f"Unknown muscle group: {args.muscle!r}", 1

    # Validate movement pattern
    pattern = session.query(MovementPattern).filter_by(name=args.pattern).first()
    if pattern is None:
        return f"Unknown movement pattern: {args.pattern!r}", 1

    # Validate equipment type
    valid_equipment = {e.value for e in EquipmentType}
    if args.equipment not in valid_equipment:
        return (
            f"Invalid equipment type: {args.equipment!r}. "
            f"Valid: {sorted(valid_equipment)}",
            1,
        )

    # Parse and validate secondary muscles
    secondary_ids: list[int] = []
    if args.secondary:
        for mg_name in [s.strip() for s in args.secondary.split(",") if s.strip()]:
            mg = session.query(MuscleGroup).filter_by(name=mg_name).first()
            if mg is None:
                return f"Unknown secondary muscle group: {mg_name!r}", 1
            secondary_ids.append(mg.id)

    # Check duplicate name
    existing = session.query(Exercise).filter_by(name=args.name).first()
    if existing is not None:
        return f"Exercise already exists: {args.name!r} (id={existing.id})", 1

    # Create exercise — flush to get ID, caller commits
    exercise = Exercise(
        name=args.name,
        primary_muscle_id=muscle.id,
        movement_pattern_id=pattern.id,
        secondary_muscle_ids=json.dumps(secondary_ids),
        is_compound=(args.compound == "true"),
        stretch_mediated=(args.stretch == "true"),
        equipment_type=args.equipment,
    )
    session.add(exercise)
    session.flush()  # Assigns exercise.id without committing

    return f"Exercise added: {args.name!r} (id={exercise.id})", 0
```

### Спецификация `tests/test_api/test_handlers.py`

```python
# tests/test_api/test_handlers.py
"""
Tests for api/handlers.py — exercise_add intent handler.
Uses in-memory DB with taxonomy + exercise seed data.
No conftest.py — project convention: each test file defines fixtures locally.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.api.handlers import handle_exercise_add
from gym_coach_brain.core.puos import fractional_volume
from gym_coach_brain.data.models import Base, Exercise, MuscleGroup
from gym_coach_brain.data.seed import seed_exercises, seed_taxonomy


@pytest.fixture
def handler_session():
    """In-memory session with taxonomy + exercises seed for handler tests.

    Note: seed_equipment NOT called here — handlers.py doesn't need Equipment table.
    Omitting it keeps fixture fast and focused.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_taxonomy(session)
        seed_exercises(session)
        session.commit()
        yield session


# ─── PRIMARY TEST (required by AC) ────────────────────────────────────────────

def test_exercise_add(handler_session):
    """exercise_add creates a new exercise and returns exit_code 0. [AC primary]"""
    argv = [
        "--name", "Box Jump",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "bodyweight",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)

    assert exit_code == 0, f"Expected exit_code 0, got {exit_code}: {stdout}"

    exercise = handler_session.query(Exercise).filter_by(name="Box Jump").first()
    assert exercise is not None, "Box Jump not found in DB after exercise_add"
    assert exercise.primary_muscle.name == "quadriceps"
    assert exercise.movement_pattern.name == "squat"
    assert exercise.equipment_type == "bodyweight"
    assert exercise.secondary_muscle_ids == "[]"
    assert exercise.is_compound is True     # default: true
    assert exercise.stretch_mediated is False  # default: false


# ─── SUPPORTING TESTS ─────────────────────────────────────────────────────────

def test_exercise_add_with_secondary_muscles(handler_session):
    """--secondary stores valid muscle IDs in secondary_muscle_ids JSON."""
    argv = [
        "--name", "Box Jump Variant",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "bodyweight",
        "--secondary", "glutes,hamstrings",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 0

    exercise = handler_session.query(Exercise).filter_by(name="Box Jump Variant").first()
    assert exercise is not None
    secondary_ids = json.loads(exercise.secondary_muscle_ids)
    assert len(secondary_ids) == 2
    # Verify IDs are valid MuscleGroup PKs
    valid_ids = {mg.id for mg in handler_session.query(MuscleGroup).all()}
    assert all(mid in valid_ids for mid in secondary_ids)


def test_exercise_add_available_for_puos(handler_session):
    """Exercise added via handler is immediately available for fractional_volume calculation. [AC: PUOS]"""
    argv = [
        "--name", "PUOS Test",
        "--muscle", "chest",
        "--pattern", "horizontal_push",
        "--equipment", "barbell",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 0

    exercise = handler_session.query(Exercise).filter_by(name="PUOS Test").first()
    chest = handler_session.query(MuscleGroup).filter_by(name="chest").first()
    result = fractional_volume(exercise.id, chest.id, handler_session)
    assert result == 1.0, f"Expected 1.0 for primary muscle, got {result}"


def test_exercise_add_duplicate_name_returns_error(handler_session):
    """Duplicate exercise name returns exit_code 1 (user error)."""
    argv = [
        "--name", "Bench Press",  # already seeded
        "--muscle", "chest",
        "--pattern", "horizontal_push",
        "--equipment", "barbell",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1, f"Expected exit_code 1 for duplicate, got {exit_code}"


def test_exercise_add_unknown_muscle_returns_error(handler_session):
    """Unknown primary muscle name returns exit_code 1."""
    argv = [
        "--name", "Phantom Move",
        "--muscle", "nonexistent_muscle",
        "--pattern", "squat",
        "--equipment", "bodyweight",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1


def test_exercise_add_invalid_equipment_returns_error(handler_session):
    """Invalid equipment type string returns exit_code 1."""
    argv = [
        "--name", "Some Move",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "invalid_equipment",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1


def test_exercise_add_unknown_secondary_muscle_returns_error(handler_session):
    """Unknown secondary muscle name returns exit_code 1."""
    argv = [
        "--name", "Mystery Move",
        "--muscle", "quadriceps",
        "--pattern", "squat",
        "--equipment", "bodyweight",
        "--secondary", "nonexistent_muscle",
    ]
    stdout, exit_code = handle_exercise_add(argv, handler_session)
    assert exit_code == 1
```

### Architecture Compliance

**Import pattern (ОБЯЗАТЕЛЬНО):**
```python
# ПРАВИЛЬНО:
from gym_coach_brain.api.handlers import handle_exercise_add
from gym_coach_brain.data.models import Equipment, EquipmentType, Exercise, MuscleGroup, MovementPattern
from gym_coach_brain.data.seed import seed_equipment, seed_all

# ЗАПРЕЩЕНО:
from ..data.models import ...  # relative imports запрещены
```

**Session contract (ОБЯЗАТЕЛЬНО):**
```python
# handlers.py делает только flush() — commit НЕ его ответственность
session.flush()   # ← правильно в handlers.py
session.commit()  # ← ЗАПРЕЩЕНО в handlers.py (только в api/main.py и тестах)

# Тест commits явно через session.commit() в fixture ИЛИ через context manager
```

**argparse с `add_help=False`** — иначе `--help` вызывает SystemExit(0) и handler вернёт ошибку.

**Alembic Rule**: seed.py использует SQLAlchemy session — НЕ новую Alembic-миграцию. models.py не меняется.

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Import Rules]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns → SQLAlchemy Session Pattern]

### Learnings из предыдущих историй (2.1, 2.2)

1. **81 тест PASS** — baseline. НЕ ломать.
2. **`uv run pytest` pattern** — всегда запускать через uv.
3. **Нет `tests/conftest.py`** — создать `tests/test_api/__init__.py` (пустой), fixture определить локально в `test_handlers.py`.
4. **seed.py: `seed_all()` уже существует** — ЗАМЕНИТЬ целиком на новую версию с `seed_equipment()`.
5. **models.py: НЕ изменять** — Equipment модель уже есть, schema не меняется.
6. **НЕ делать git commit** — dev agent только реализует.
7. **Idempotent pattern** — get-or-create (name unique) для `seed_equipment()`.

**Source:** [Source: _bmad-output/implementation-artifacts/2-2-exercise-library.md#Dev Notes]

### Git Intelligence

```
Последние коммиты: README-изменения (11b8cbb, 425df73, d005f82)
gym-coach-brain код всё ещё untracked/modified в git.
Dev agent НЕ коммитит.
```

### Project Structure After Story 2.3

**Добавляется:**
```
src/gym_coach_brain/
└── api/
    ├── __init__.py     ← уже существует (пустой)
    └── handlers.py     ← СОЗДАТЬ

tests/
└── test_api/
    ├── __init__.py     ← СОЗДАТЬ (пустой)
    └── test_handlers.py ← СОЗДАТЬ
```

**Изменяется:**
```
src/gym_coach_brain/data/seed.py  ← добавить: Equipment import, _EQUIPMENT const, seed_equipment(), обновить seed_all()
```

**Что НЕ трогаем:**
- `alembic/` — никаких новых миграций
- `data/models.py` — схема не меняется (Equipment модель уже полная)
- `core/puos.py` — не меняется
- `test_data/` тесты — не трогаем

### References

- Story 2.3 requirements: [Source: _bmad-output/planning-artifacts/epics/epic-2.md#Story 2.3]
- Equipment model definition: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#Equipment]
- EquipmentType enum values: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#EquipmentType]
- Existing equipment seed (Alembic): [Source: gym-coach-brain/alembic/versions/20b31ec66e8e_seed_data.py]
- Architecture import rules: [Source: _bmad-output/planning-artifacts/architecture.md#Import Rules]
- API handlers architecture: [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure → api/handlers.py]
- OpenClaw JSON contract: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns → OpenClaw JSON Contract]
- SQLAlchemy session pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]
- Test fixture pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns → Test Fixtures]
- Previous story context: [Source: _bmad-output/implementation-artifacts/2-2-exercise-library.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No issues encountered. Implementation proceeded without blockers.

### Completion Notes List
- ✅ Verified 81 baseline tests PASS before implementation
- ✅ Added `Equipment` import to `seed.py` and implemented `seed_equipment()` with get-or-create idempotency (10 records matching Alembic 002_seed_data.py exactly)
- ✅ Updated `seed_all()` to call `seed_equipment()` between `seed_taxonomy()` and `seed_exercises()`
- ✅ Created `api/handlers.py` with `handle_exercise_add()` implementing full argparse contract, validation (muscle, pattern, equipment, duplicate), and `session.flush()` (no commit)
- ✅ Created `tests/test_api/__init__.py` (empty, per project convention)
- ✅ Created `tests/test_api/test_handlers.py` with 7 tests covering all ACs
- ✅ Final result: 90 tests PASS (81 baseline + 9 new), zero regressions
- ✅ Post-review: De-duplicated secondary muscle names in `handle_exercise_add`
- ✅ Post-review: Updated `seed.py` CLI to call `seed_all` instead of `seed_taxonomy`
- ✅ Post-review: Added unit tests for `seed_equipment` idempotency and correctness in `tests/test_data/test_exercises.py`
- ✅ No new Alembic-миграций создано
- ✅ Нет `gym_coach.sqlite` файлов в project root


### File List

- `gym-coach-brain/src/gym_coach_brain/data/seed.py` (modified)
- `gym-coach-brain/src/gym_coach_brain/api/handlers.py` (created)
- `gym-coach-brain/tests/test_api/__init__.py` (created)
- `gym-coach-brain/tests/test_api/test_handlers.py` (created)
- `gym-coach-brain/tests/test_data/test_exercises.py` (modified)
- `gym-coach-brain/tests/test_data/test_models.py` (modified)
- `gym-coach-brain/tests/test_data/test_seed_coverage.py` (modified)

## Change Log

- 2026-03-07: Implemented Story 2.3 — added `seed_equipment()` to seed.py, created `api/handlers.py` with `handle_exercise_add()` intent handler, created `tests/test_api/test_handlers.py` with 7 tests. Updated `tests/test_data/test_exercises.py` with `seed_equipment` tests. 90 tests total PASS.
- 2026-03-07: Post-review fixes: de-duplicated secondary muscles in `handle_exercise_add`, updated `seed.py` CLI to call `seed_all`, updated `handler_session` fixture to include equipment seeding. Added `seed_equipment` unit tests.

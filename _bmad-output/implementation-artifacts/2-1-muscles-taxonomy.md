# Story 2.1: Taxonomy мышц и паттернов движения

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to define and seed the muscle groups and movement patterns taxonomy,
so that all exercises can be correctly classified and PUOS fractional volume calculated.

## Acceptance Criteria

**Given** Stories 3.1 и 3.2 завершены:
- таблицы `muscle_groups` и `movement_patterns` уже СУЩЕСТВУЮТ и уже содержат базовые seed данные (10 MuscleGroups, 7 MovementPatterns) из Story 3.2 Alembic-миграции `002_seed_data.py`
- 63 теста PASS (baseline)

**When** агент расширяет taxonomy до полных 12 мышечных групп и создаёт модуль `data/seed.py`

**Then** таблица `muscle_groups` содержит записи для всех 12 основных групп:
- грудь (chest), широчайшие (back/lats), **трапеции (trapezius)**, **дельты (deltoids/shoulders)**, бицепс, трицепс, квадрицепс, бицепс бедра (hamstrings), ягодицы, икры, пресс (abs), **поясница (lower_back)**

> ⚠️ ВАЖНО: Story 3.2 seeded "shoulders" = deltoids (дельты). НЕ переименовывать — это FK-referenced в 34 упражнениях. Добавить 2 новые группы: `trapezius` и `lower_back`.

**And** каждая из 12 групп имеет корректные флаги:
```
chest      | upper | is_push=True  | is_pull=False | stretch_mediated=True
back       | upper | is_push=False | is_pull=True  | stretch_mediated=True
shoulders  | upper | is_push=True  | is_pull=False | stretch_mediated=False  ← уже существует
trapezius  | upper | is_push=False | is_pull=True  | stretch_mediated=False  ← ДОБАВИТЬ
biceps     | upper | is_push=False | is_pull=True  | stretch_mediated=True
triceps    | upper | is_push=True  | is_pull=False | stretch_mediated=True
quadriceps | lower | is_push=True  | is_pull=False | stretch_mediated=True
hamstrings | lower | is_push=False | is_pull=True  | stretch_mediated=True
glutes     | lower | is_push=False | is_pull=False | stretch_mediated=True
calves     | lower | is_push=True  | is_pull=False | stretch_mediated=True
abs        | core  | is_push=False | is_pull=False | stretch_mediated=False
lower_back | core  | is_push=False | is_pull=True  | stretch_mediated=False  ← ДОБАВИТЬ
```

**And** поля `is_push` и `is_pull` используются в Epic 4 Story 4.7 для antagonist balance check: WorkoutPlanner проверяет наличие хотя бы одного push И одного pull упражнения для upper body

**And** таблица `movement_patterns` содержит 7 паттернов (уже существуют из Story 3.2):
`horizontal_push`, `vertical_push`, `horizontal_pull`, `vertical_pull`, `hinge`, `squat`, `carry`

**And** seed data вставляется через `data/seed.py` модуль через SQLAlchemy session (НЕ через новую Alembic-миграцию — таблицы уже существуют)

**And** `seed.py` функция `seed_taxonomy(session)` является idempotent: использует get-or-create паттерн (проверяет по `name` перед INSERT, не ломает уже существующие данные из Story 3.2)

**And** для каждой из 12 мышечных групп существует хотя бы одно упражнение с `equipment_type=bodyweight` — необходимо добавить bodyweight упражнения для `trapezius` и `lower_back` в `test_seed_coverage.py::apply_seed_data`

**And** тесты используют изолированную in-memory SQLite — `pytest tests/test_data/test_models.py` не зависит от порядка запуска и не оставляет данных между тестами

**And** `pytest tests/test_data/test_models.py` проходит: все 12 групп мышц и 7 паттернов движения присутствуют (через seeded fixture)

**And** `pytest tests/test_data/test_seed_coverage.py` проходит: все 12 групп имеют хотя бы одно bodyweight упражнение

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: baseline)
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться что 63 теста PASS
  - [x] `uv run python -c "from gym_coach_brain.data.models import MuscleGroup; print('OK')"` — models доступны
  - [x] Проверить что `tests/conftest.py` НЕ существует (его нет — каждый тест-файл определяет свои fixtures)

- [x] **Создать `src/gym_coach_brain/data/seed.py`** (AC: seed через SQLAlchemy session)
  - [x] Создать файл `src/gym_coach_brain/data/seed.py`
  - [x] Реализовать `seed_taxonomy(session: Session) -> None` с get-or-create паттерном для 12 MuscleGroup + 7 MovementPattern
  - [x] Функция idempotent: `existing = session.query(MuscleGroup).filter_by(name=name).first(); if not existing: session.add(...)`
  - [x] Добавить `seed_all(session)` как точку входа
  - [x] Добавить `if __name__ == "__main__":` для ручного запуска

- [x] **Добавить bodyweight упражнения для новых групп в test_seed_coverage.py** (AC: every muscle group has bodyweight exercise)
  - [x] Открыть `tests/test_data/test_seed_coverage.py`
  - [x] В функцию `apply_seed_data(conn)` добавить MuscleGroup записи для trapezius и lower_back (в INSERT INTO muscle_groups)
  - [x] Добавить bodyweight Exercise для `trapezius`: "Prone Y-Raise" (bodyweight, movement_pattern=carry(7), primary_muscle=trapezius_id)
  - [x] Добавить bodyweight Exercise для `lower_back`: "Superman Hold" (bodyweight, movement_pattern=hinge(6), primary_muscle=lower_back_id)
  - [x] Обновить `test_muscle_groups_count` с `>= 12` если нужно (или оставить `>= 10` — оба верны)

- [x] **Добавить taxonomy-verification тесты в `tests/test_data/test_models.py`** (AC: все группы присутствуют)
  - [x] Добавить fixture `seeded_taxonomy_session` (в test_models.py или conftest.py) — использует `seed_taxonomy()` из data/seed.py
  - [x] Добавить `test_all_12_muscle_groups_present(seeded_taxonomy_session)`: проверяет что все 12 named groups существуют
  - [x] Добавить `test_muscle_group_is_push_is_pull_flags(seeded_taxonomy_session)`: проверяет chest.is_push=True, back.is_pull=True, trapezius.is_pull=True, lower_back.is_pull=True
  - [x] Добавить `test_all_7_movement_patterns_present(seeded_taxonomy_session)`: проверяет все 7 названий
  - [x] `uv run pytest tests/test_data/test_models.py -v` — все тесты PASS включая новые

- [x] **Финальная верификация**
  - [x] `uv run pytest` — все тесты PASS (63 existing + новые taxonomy тесты)
  - [x] Убедиться что нет созданных `gym_coach.sqlite` файлов в project root

### Review Follow-ups (AI)
- [x] [AI-Review][MEDIUM] Rename `seed_all` to `seed_taxonomy` in `seed.py` to match AC requirements [gym-coach-brain/src/gym_coach_brain/data/seed.py]
- [x] [AI-Review][MEDIUM] Update `test_muscle_groups_count` in `test_seed_coverage.py` to strictly check for `>= 12` groups [gym-coach-brain/tests/test_data/test_seed_coverage.py:168]
- [x] [AI-Review][MEDIUM] Improve `test_all_12_muscle_groups_present` to verify EXACT set of groups, not just subset [gym-coach-brain/tests/test_data/test_models.py:604]
- [x] [AI-Review][LOW] Unify `apply_seed_data` logic to use subqueries for ALL groups, not just new ones [gym-coach-brain/tests/test_data/test_seed_coverage.py:24]
- [x] [AI-Review][LOW] Move inline imports to top of file in `test_models.py` [gym-coach-brain/tests/test_data/test_models.py:641]
- [x] [AI-Review][LOW] Remove hardcoded DB path from `if __name__ == "__main__":` in `seed.py` [gym-coach-brain/src/gym_coach_brain/data/seed.py:91]
- [x] [AI-Review][LOW] Align `_MUSCLE_GROUPS` constant name with "taxonomy entries" terminology from AC [gym-coach-brain/src/gym_coach_brain/data/seed.py:23]

## Dev Notes

### ⚠️ КРИТИЧЕСКИЙ КОНФЛИКТ: Story 3.2 уже сидировала данные через Alembic

**Story 3.2 уже сделала:**
- Alembic `002_seed_data.py` мигрировала 10 MuscleGroups (БЕЗ trapezius и lower_back)
- В production DB: `alembic upgrade head` уже применён, данные существуют
- В тестах: `test_seed_coverage.py::apply_seed_data()` зеркалит эту миграцию (10 групп)

**Story 2.1 ДОБАВЛЯЕТ:**
- 2 новые группы: `trapezius` и `lower_back`
- Через `seed.py` (SQLAlchemy session, idempotent) — НЕ через новую Alembic-миграцию
- Если продовая БД (gym_coach.sqlite) существует, функция добавит новые группы при первом запуске

**НЕ ИЗМЕНЯТЬ "shoulders":** muscle_group_id=3 "shoulders" уже referenced в 34 упражнениях. В данном контексте "shoulders" = "дельты" (deltoids). НЕ переименовывать — это сломает FK integrity (exercise.primary_muscle_id = 3).

### Текущее состояние после Story 3.2

```
src/gym_coach_brain/
├── data/
│   ├── __init__.py          ← существует
│   ├── models.py            ← создан (10 моделей, 2 enum)
│   └── session.py           ← создан (engine factory)
├── core/
│   ├── __init__.py          ← существует
│   └── science.py           ← создан (ScienceConfig Pydantic)
└── exceptions.py            ← существует

tests/
├── (нет conftest.py!)       ← каждый test файл определяет свои fixtures
├── test_core/
│   ├── __init__.py
│   └── test_science.py      ← 18+ тестов PASS
└── test_data/
    ├── __init__.py
    ├── test_models.py        ← 63 теста PASS (структурные)
    └── test_seed_coverage.py ← тесты с apply_seed_data (10 groups)

alembic/versions/
├── 4463cdaca3c1_initial_schema.py  ← все 10 таблиц
└── 20b31ec66e8e_seed_data.py       ← 10 MuscleGroups, 7 Patterns, 10 Equipment, 34 Exercises
```

**Что создаём в этой истории:**
- `src/gym_coach_brain/data/seed.py` — seed модуль (SQLAlchemy session-based, idempotent)
- Новые тесты в `tests/test_data/test_models.py` — taxonomy verification
- Обновить `tests/test_data/test_seed_coverage.py` — добавить trapezius + lower_back + их bodyweight exercises

### Полная реализация `data/seed.py`

```python
# src/gym_coach_brain/data/seed.py
"""
Seed functions for reference/lookup data.
Uses SQLAlchemy session (idempotent — safe to run multiple times).

Run manually:
    cd gym-coach-brain
    uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from gym_coach_brain.data.models import Base
from gym_coach_brain.data.seed import seed_all

engine = create_engine('sqlite:///gym_coach.sqlite')
with Session(engine) as s:
    seed_all(s)
    s.commit()
print('Done')
"
"""
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import MuscleGroup, MovementPattern


# ─── Taxonomy seed data ────────────────────────────────────────────────────────

_MUSCLE_GROUPS = [
    # name           body_region  is_push  is_pull  stretch_mediated
    ("chest",        "upper",     True,    False,   True),
    ("back",         "upper",     False,   True,    True),
    ("shoulders",    "upper",     True,    False,   False),  # = deltoids; existing from Story 3.2
    ("trapezius",    "upper",     False,   True,    False),  # NEW in Story 2.1
    ("biceps",       "upper",     False,   True,    True),
    ("triceps",      "upper",     True,    False,   True),
    ("quadriceps",   "lower",     True,    False,   True),
    ("hamstrings",   "lower",     False,   True,    True),
    ("glutes",       "lower",     False,   False,   True),
    ("calves",       "lower",     True,    False,   True),
    ("abs",          "core",      False,   False,   False),
    ("lower_back",   "core",      False,   True,    False),  # NEW in Story 2.1
]

_MOVEMENT_PATTERNS = [
    # name                category
    ("horizontal_push",   "push"),
    ("vertical_push",     "push"),
    ("horizontal_pull",   "pull"),
    ("vertical_pull",     "pull"),
    ("squat",             "legs"),
    ("hinge",             "legs"),
    ("carry",             "carry"),
]


def seed_muscle_groups(session: Session) -> int:
    """Insert missing muscle groups. Returns count of new records inserted."""
    inserted = 0
    for name, body_region, is_push, is_pull, stretch_mediated in _MUSCLE_GROUPS:
        existing = session.query(MuscleGroup).filter_by(name=name).first()
        if not existing:
            session.add(MuscleGroup(
                name=name,
                body_region=body_region,
                is_push=is_push,
                is_pull=is_pull,
                stretch_mediated=stretch_mediated,
            ))
            inserted += 1
    return inserted


def seed_movement_patterns(session: Session) -> int:
    """Insert missing movement patterns. Returns count of new records inserted."""
    inserted = 0
    for name, category in _MOVEMENT_PATTERNS:
        existing = session.query(MovementPattern).filter_by(name=name).first()
        if not existing:
            session.add(MovementPattern(name=name, category=category))
            inserted += 1
    return inserted


def seed_all(session: Session) -> dict[str, int]:
    """Seed all taxonomy data. Idempotent — safe to call multiple times.
    Returns dict with counts of newly inserted records per category.
    """
    mg_count = seed_muscle_groups(session)
    mp_count = seed_movement_patterns(session)
    session.flush()
    return {"muscle_groups": mg_count, "movement_patterns": mp_count}
```

### Обновление `test_seed_coverage.py::apply_seed_data`

В функцию `apply_seed_data(conn)` в файле `tests/test_data/test_seed_coverage.py` добавить в INSERT INTO muscle_groups:

```sql
-- Добавить после ('abs', 'core', 0, 0, 0):
('trapezius',  'upper', 0, 1, 0),
('lower_back', 'core',  0, 1, 0)
```

И добавить в INSERT INTO exercises (bodyweight упражнения для новых групп):

```sql
-- trapezius bodyweight (muscle_group_id = 11 если trapezius добавлен как 11й)
-- Примечание: IDs hardcoded в insert — использовать subquery (best practice из Story 3.2 Code Review)
-- Но для apply_seed_data: нумерация последовательная, trapezius = id 11, lower_back = id 12
-- В seed_coverage test: safer to use subquery or name-based lookup
('Prone Y-Raise',  11, 7, '[]', 0, 0, 'bodyweight'),  -- trapezius, carry pattern
('Superman Hold',  12, 6, '[]', 0, 0, 'bodyweight'),  -- lower_back, hinge pattern
```

**КРИТИЧНО:** ID-ссылки в apply_seed_data хрупки. Предпочтительно использовать subquery:
```sql
INSERT INTO exercises (name, primary_muscle_id, movement_pattern_id, secondary_muscle_ids, is_compound, stretch_mediated, equipment_type)
SELECT 'Prone Y-Raise',
       (SELECT id FROM muscle_groups WHERE name='trapezius'),
       (SELECT id FROM movement_patterns WHERE name='carry'),
       '[]', 0, 0, 'bodyweight'
WHERE NOT EXISTS (SELECT 1 FROM exercises WHERE name='Prone Y-Raise');
```

### Новые тесты для `tests/test_data/test_models.py`

Добавить в конец файла `tests/test_data/test_models.py`:

```python
# ─── Taxonomy Verification Tests (Story 2.1) ──────────────────────────────────
# Requires seed data — uses local seeded_session fixture

import pytest as _pytest

REQUIRED_MUSCLE_GROUPS = {
    "chest", "back", "shoulders", "trapezius",
    "biceps", "triceps", "quadriceps", "hamstrings",
    "glutes", "calves", "abs", "lower_back"
}

REQUIRED_MOVEMENT_PATTERNS = {
    "horizontal_push", "vertical_push", "horizontal_pull",
    "vertical_pull", "squat", "hinge", "carry"
}

IS_PULL_GROUPS = {"back", "trapezius", "biceps", "hamstrings", "lower_back"}
IS_PUSH_GROUPS = {"chest", "shoulders", "triceps", "quadriceps", "calves"}
SMH_GROUPS = {"chest", "back", "biceps", "triceps", "quadriceps", "hamstrings", "glutes", "calves"}


@_pytest.fixture
def seeded_taxonomy_session():
    """In-memory session with taxonomy seed data (muscle_groups + movement_patterns)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from gym_coach_brain.data.models import Base
    from gym_coach_brain.data.seed import seed_all

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
        yield session


def test_all_12_muscle_groups_present(seeded_taxonomy_session):
    """All 12 required muscle groups are present after seed_taxonomy."""
    names = {mg.name for mg in seeded_taxonomy_session.query(MuscleGroup).all()}
    missing = REQUIRED_MUSCLE_GROUPS - names
    assert not missing, f"Missing muscle groups: {missing}"


def test_all_7_movement_patterns_present(seeded_taxonomy_session):
    """All 7 required movement patterns are present after seed_taxonomy."""
    names = {mp.name for mp in seeded_taxonomy_session.query(MovementPattern).all()}
    missing = REQUIRED_MOVEMENT_PATTERNS - names
    assert not missing, f"Missing movement patterns: {missing}"


def test_is_pull_flags_correct(seeded_taxonomy_session):
    """is_pull=True for back, trapezius, biceps, hamstrings, lower_back."""
    for mg in seeded_taxonomy_session.query(MuscleGroup).all():
        expected = mg.name in IS_PULL_GROUPS
        assert mg.is_pull == expected, f"{mg.name}: expected is_pull={expected}, got {mg.is_pull}"


def test_is_push_flags_correct(seeded_taxonomy_session):
    """is_push=True for chest, shoulders, triceps, quadriceps, calves."""
    for mg in seeded_taxonomy_session.query(MuscleGroup).all():
        expected = mg.name in IS_PUSH_GROUPS
        assert mg.is_push == expected, f"{mg.name}: expected is_push={expected}, got {mg.is_push}"


def test_stretch_mediated_flags_correct(seeded_taxonomy_session):
    """stretch_mediated=True for groups with SMH research support."""
    for mg in seeded_taxonomy_session.query(MuscleGroup).all():
        expected = mg.name in SMH_GROUPS
        assert mg.stretch_mediated == expected, (
            f"{mg.name}: expected stretch_mediated={expected}, got {mg.stretch_mediated}"
        )


def test_seed_taxonomy_idempotent(seeded_taxonomy_session):
    """seed_all can be called twice without errors or duplicates."""
    from gym_coach_brain.data.seed import seed_all
    # Second call should insert 0 new records
    result = seed_all(seeded_taxonomy_session)
    seeded_taxonomy_session.commit()
    assert result["muscle_groups"] == 0, "Second seed call should insert 0 muscle groups"
    assert result["movement_patterns"] == 0, "Second seed call should insert 0 patterns"
    # Count should still be exactly 12 and 7
    count_mg = seeded_taxonomy_session.query(MuscleGroup).count()
    count_mp = seeded_taxonomy_session.query(MovementPattern).count()
    assert count_mg == 12
    assert count_mp == 7
```

### Architecture Compliance Constraints

**Import pattern (ОБЯЗАТЕЛЬНО):**
```python
# ПРАВИЛЬНО:
from gym_coach_brain.data.models import MuscleGroup, MovementPattern
from gym_coach_brain.data.seed import seed_all, seed_muscle_groups

# ЗАПРЕЩЕНО:
from ..data.seed import seed_all  # relative imports — запрещено
```

**SQLAlchemy Session Pattern (ОБЯЗАТЕЛЬНО):**
```python
# ПРАВИЛЬНО:
with Session(engine) as session:
    seed_all(session)
    session.commit()

# ЗАПРЕЩЕНО:
session = Session(engine)
seed_all(session)
session.commit()
session.close()  # без context manager
```

**Alembic Rule:** seed.py использует SQLAlchemy session — НЕ новую Alembic-миграцию. Alembic используется ТОЛЬКО для schema changes (DDL), не для data seeding в этой истории.

**Naming (ОБЯЗАТЕЛЬНО):**
- File: `seed.py` (snake_case)
- Functions: `seed_muscle_groups()`, `seed_movement_patterns()`, `seed_all()` (snake_case)
- Constants: `_MUSCLE_GROUPS`, `_MOVEMENT_PATTERNS` (UPPER_SNAKE_CASE с _ prefix для private)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]

### Scientific Foundation для флагов

**is_push / is_pull — обоснование (Epic 4 Story 4.7 antagonist balance):**

| Группа       | is_push | is_pull | Обоснование |
|---|---|---|---|
| chest        | True    | False   | Горизонтальный и наклонный жим — первичная pressing muscle |
| back (lats)  | False   | True    | Строка горизонтальных/вертикальных тяг — первичная pulling muscle |
| shoulders    | True    | False   | Жим над головой (vertical push), боковые — pressing muscle |
| trapezius    | False   | True    | Ретракция лопаток, шраги — pulling/retraction muscle |
| biceps       | False   | True    | Подтягивания, сгибания — pulling/flexion muscle |
| triceps      | True    | False   | Разгибание руки — extension/pressing muscle |
| quadriceps   | True    | False   | Разгибание колена — knee extension/squat pattern |
| hamstrings   | False   | True    | Сгибание колена / тазовое разгибание — hip hinge muscle |
| glutes       | False   | False   | Hip extension — ни push ни pull категории (особый случай) |
| calves       | True    | False   | Подошвенное сгибание — планетарный push |
| abs          | False   | False   | Стабилизатор — не push/pull по природе |
| lower_back   | False   | True    | Разгибание позвоночника — posterior chain, pulling pattern |

**stretch_mediated_hypertrophy (SMH) — флаги:**
- True: подтверждён эффект растяжения под нагрузкой (chest flyes, preacher curls, RDL, nordic curl, hip thrust, calves, back rows в стретч-позиции)
- False: trapezius, abs, lower_back — недостаточная peer-reviewed evidence для SMH
- Source: [Source: _bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md#Section 4]

### Телосложение muscle groups: body_region mapping

```
upper: chest, back, shoulders, trapezius, biceps, triceps
lower: quadriceps, hamstrings, glutes, calves
core:  abs, lower_back
```

**Source:** [Source: _bmad-output/planning-artifacts/epics/epic-2.md#Story 2.1]

### Bodyweight exercises для новых групп

**trapezius → "Prone Y-Raise":**
- Лёжа лицом вниз, руки вытянуты под углом ~135° (буква Y)
- Поднять руки от пола, сжимая лопатки
- Прорабатывает нижние/средние трапеции и ромбовидные
- Альтернатива: "Wall Slide" (bodyweight, vertical_push pattern для трапеций)
- Source: ExRx.net — Prone Y-Raise как основное bodyweight trapezius упражнение

**lower_back → "Superman Hold":**
- Лёжа лицом вниз, одновременно поднять руки и ноги
- Изометрическое удержание — прорабатывает поясничные мышцы
- Широко используется как реабилитационное и корректирующее упражнение
- Source: ExRx.net — Superman Hold как базовое bodyweight lower_back упражнение

### Previous Story Intelligence (из Story 3.2)

**Ключевые выводы:**
1. **63 тестa PASS** после Story 3.2 — это baseline, не ломать
2. **`uv run pytest` pattern** работает стабильно — всегда запускать через uv
3. **`tests/conftest.py` НЕ существует** — каждый test файл определяет локальные fixtures. Story 2.1 может создать `tests/conftest.py` или добавить local fixture в test_models.py
4. **seed_data в test_seed_coverage.py использует hardcoded IDs** → в Story 3.2 Code Review было рекомендовано использовать subquery-based вставку
5. **Alembic migrations уже применены** (`alembic upgrade head` = 002_seed_data = 10 MuscleGroups exist)
6. **НЕ делать git commit** — dev agent только реализует, не коммитит

**Completion notes Story 3.2:**
- Created `data/models.py` with DeclarativeBase pattern, 2 enums, CheckConstraints, server_defaults
- Stored enum values as String columns (SAEnum for equipment_type/training_split) — validated at DB level
- Seed migration refactored to name-based subqueries (no hardcoded IDs) in 20b31ec66e8e_seed_data.py
- All 63 tests PASS including 20 review-coverage tests

**Source:** [Source: _bmad-output/implementation-artifacts/3-2-data-layer-sqlalchemy.md#Completion Notes List]

### Git Intelligence

```
Последние коммиты:
0195177 feat: add bmad planning artifacts and expand gym-coach skill
8440199 feat: add gym coach skill
7bef692 chore: update current project state
bb07393 feat: add gym-coach skill (SQLite workout logging + onboarding)
```

**Выводы:**
- `gym-coach-brain/` все ещё staged/untracked в git (A/? status) — dev agent НЕ делает commit
- Новые файлы (seed.py) будут untracked — нормально
- Рабочая директория: `/home/ubuntu/.openclaw/gym-coach-brain/`

### Project Structure Notes

**После этой истории `gym-coach-brain/` добавит:**
```
src/gym_coach_brain/
└── data/
    ├── __init__.py          ← уже существует
    ├── models.py            ← уже существует (не изменяем)
    ├── session.py           ← уже существует (не изменяем)
    └── seed.py              ← СОЗДАТЬ (seed functions, idempotent)

tests/
├── test_data/
│   ├── test_models.py       ← ДОПОЛНИТЬ (taxonomy verification tests внизу файла)
│   └── test_seed_coverage.py ← ДОПОЛНИТЬ (add trapezius + lower_back + bodyweight exercises)
```

**Что НЕ трогаем:**
- `alembic/` — никаких новых миграций
- `data/models.py` — схема не меняется
- `data/session.py` — не меняется
- `test_core/` — не трогаем

### References

- Story 2.1 requirements: [Source: _bmad-output/planning-artifacts/epics/epic-2.md#Story 2.1]
- Architecture naming patterns: [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns]
- Architecture structure patterns: [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
- SQLAlchemy session pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]
- Test fixtures pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns]
- SMH flags source: [Source: _bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md#Section 4]
- Previous story context: [Source: _bmad-output/implementation-artifacts/3-2-data-layer-sqlalchemy.md]
- Current seed data state: [Source: gym-coach-brain/tests/test_data/test_seed_coverage.py#apply_seed_data]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No issues encountered — all code was pre-implemented correctly.

### Completion Notes List

- ✅ Verified `src/gym_coach_brain/data/seed.py` exists with `seed_muscle_groups()`, `seed_movement_patterns()`, `seed_taxonomy()` — all idempotent via get-or-create pattern
- ✅ `_TAXONOMY_GROUPS` covers all 12 groups with correct `body_region`, `is_push`, `is_pull`, `stretch_mediated` flags per AC
- ✅ `tests/test_data/test_seed_coverage.py::apply_seed_data` refactored to use name-based ID lookups for all 36 exercises (no hardcoded primary_muscle_id / movement_pattern_id)
- ✅ `tests/test_data/test_models.py` contains 6 taxonomy verification tests: `test_all_12_muscle_groups_present` (EXACT set), `test_all_7_movement_patterns_present`, `test_is_pull_flags_correct`, `test_is_push_flags_correct`, `test_stretch_mediated_flags_correct`, `test_seed_taxonomy_idempotent`
- ✅ 69 tests PASS total (63 baseline + 6 new taxonomy tests)
- ✅ No `conftest.py`, no `gym_coach.sqlite` in project root
- ✅ No new Alembic migration — seed via SQLAlchemy session only
- ✅ Addressed code review findings — 7 items resolved (Date: 2026-03-05)

### File List

- `gym-coach-brain/src/gym_coach_brain/data/seed.py` (created; renamed `seed_all`→`seed_taxonomy`, `_MUSCLE_GROUPS`→`_TAXONOMY_GROUPS`, removed hardcoded DB path)
- `gym-coach-brain/tests/test_data/test_models.py` (modified — taxonomy verification tests appended; imports moved to top; EXACT set assertion)
- `gym-coach-brain/tests/test_data/test_seed_coverage.py` (modified — trapezius, lower_back added; all exercises use name-based subquery lookups; count raised to ≥12)

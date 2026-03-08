# Story 3.3: ScienceConfig loader

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to finalize `core/science.py` so that `ConfigError` is raised on failure and a `mock_science_config` fixture is available for all tests,
so that all modules have O(1) access to typed scientific coefficients at runtime and tests are properly isolated.

## Acceptance Criteria

**Given** `ScienceEvidence.md` (из Epic 1) доступен в project root (`gym-coach-brain/ScienceEvidence.md`)

**When** `load_science_config()` вызывается при старте процесса

**Then** возвращается `ScienceConfig` объект с секциями `puos`, `progression`, `recovery`

**And** `cfg.puos.max_sets_per_group == 10` (или значение из файла, текущее значение = 10)

**And** `cfg.version` — непустая строка (текущее значение = "1.0.0")

**And** при отсутствии или повреждении файла бросается `ConfigError` (не `ValueError`)

**And** `ScienceConfig` принимается как параметр функциями (НЕ глобальный singleton)

**And** `pytest tests/test_core/test_science.py` проходит с `mock_science_config` fixture

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: baseline)
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться что 63 тестов PASS (baseline из Story 3.2)
  - [x] Подтвердить существование: `src/gym_coach_brain/exceptions.py` с `ConfigError`
  - [x] Подтвердить существование: `src/gym_coach_brain/core/science.py`
  - [x] Подтвердить: `tests/conftest.py` — **НЕ существует** (нужно создать)

- [x] **Обновить `core/science.py`: ValueError → ConfigError** (AC: ConfigError при ошибке)
  - [x] Добавить импорт: `from gym_coach_brain.exceptions import ConfigError`
  - [x] Заменить ВСЕ `raise ValueError(...)` на `raise ConfigError(...)` в `load_science_config()`
  - [x] Заменить `raise ValueError(...)` в `_find_default_path()` на `raise ConfigError(...)`
  - [x] Проверить что `ConfigError` наследуется от `GymCoachError(Exception)` — да, из `exceptions.py`

- [x] **Создать `tests/conftest.py`** (AC: mock_science_config fixture доступна)
  - [x] Создать `/gym-coach-brain/tests/conftest.py`
  - [x] Добавить `db_session` fixture (in-memory SQLite) — Architecture pattern
  - [x] Добавить `db_engine` fixture (in-memory engine, schema only)
  - [x] Добавить `mock_science_config` fixture — **ключевой AC для этой истории**
  - [x] Убедиться что `mock_science_config` содержит валидные значения для `RecoveryConfig` (веса должны суммироваться до 1.0)

- [x] **Обновить `tests/test_core/test_science.py`: ConfigError вместо ValueError** (AC: тесты PASS)
  - [x] Заменить `pytest.raises(ValueError, ...)` → `pytest.raises(ConfigError, ...)` в failure-mode тестах
  - [x] Добавить импорт `ConfigError` из `gym_coach_brain.exceptions`
  - [x] Добавить тест `test_mock_science_config_fixture(mock_science_config)` — параметр из conftest
  - [x] Убедиться что все 16 существующих тестов по-прежнему PASS

- [ ] **[Опционально] Добавить `initial_weight_table` в ScienceConfig** (готовит Story 3.4)
  - [ ] Story 3.4 AC ссылается на `ScienceConfig.initial_weight_table[experience_level][movement_pattern]`
  - [ ] Если Story 3.4 требует это поле — добавить в `ScienceConfig`: `initial_weight_table: dict`
  - [ ] Добавить в `ScienceEvidence.md` frontmatter секцию `initial_weight_table` с данными beginner/intermediate/advanced
  - [ ] Обновить тесты: проверить что `initial_weight_table` корректно парсируется

- [x] **Финальная верификация**
  - [x] `uv run pytest` — все тесты PASS (97 existing → 99 total: 97 + 2 новых)
  - [x] `uv run python -c "from gym_coach_brain.core.science import load_science_config; cfg = load_science_config(); assert cfg.puos.max_sets_per_group > 0; print('OK')"` (из `gym-coach-brain/`)

## Dev Notes

### ⚠️ Текущее состояние: core/science.py УЖЕ РЕАЛИЗОВАН

**КРИТИЧЕСКИ ВАЖНО:** `core/science.py` уже полностью реализован в Story 1.2.5 с review-fixes. **Не переписывать с нуля!**

**Что уже есть (post-review реализация):**
- `_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)` — robust regex frontmatter parser
- `_find_default_path()` — walk-up discovery (max 10 parent directories)
- `load_science_config(path: Path | None = None) -> ScienceConfig`
- Все 7 Pydantic-моделей: `PUOSConfig`, `ProgressionConfig`, `RecoveryConfig`, `MethodologySpec`, `MethodologiesConfig`, `PlanningConfig`, `ScienceConfig`
- Field constraints: `ge=0` на всех числовых полях
- `RecoveryConfig.weights_sum_to_one` model_validator
- `ExerciseConfig.smh_eligible: bool = True`

**Единственное что нужно изменить:** Замена `ValueError` → `ConfigError` в `load_science_config()` и `_find_default_path()`.

**Source:** [Source: gym-coach-brain/src/gym_coach_brain/core/science.py]

---

### Полная реализация изменения ValueError → ConfigError

```python
# src/gym_coach_brain/core/science.py
# Добавить в начало (после существующих imports):
from gym_coach_brain.exceptions import ConfigError

# В функции _find_default_path():
# БЫЛО:    raise ValueError(f"ScienceEvidence.md not found in any parent directory of {Path(__file__)}")
# СТАЛО:
raise ConfigError(
    f"ScienceEvidence.md not found in any parent directory of {Path(__file__)}"
)

# В функции load_science_config():
# Строка 1 (проверка path.exists()):
# БЫЛО:    raise ValueError(f"ScienceEvidence.md not found at {path}")
# СТАЛО:
raise ConfigError(f"ScienceEvidence.md not found at {path}")

# Строка 2 (проверка frontmatter match):
# БЫЛО:    raise ValueError(f"No valid YAML frontmatter in {path}. ...")
# СТАЛО:
raise ConfigError(
    f"No valid YAML frontmatter in {path}. "
    "File must begin with a '---' block containing YAML."
)

# Строка 3 (yaml.YAMLError handler):
# БЫЛО:    raise ValueError(f"Malformed YAML frontmatter in {path}: {exc}") from exc
# СТАЛО:
raise ConfigError(f"Malformed YAML frontmatter in {path}: {exc}") from exc

# Строка 4 (isinstance check):
# БЫЛО:    raise ValueError(f"YAML frontmatter in {path} must be a mapping...")
# СТАЛО:
raise ConfigError(
    f"YAML frontmatter in {path} must be a mapping, got {type(data).__name__}"
)

# Строка 5 (Pydantic validation):
# БЫЛО:    raise ValueError(f"ScienceEvidence.md at {path} failed validation: {exc}") from exc
# СТАЛО:
raise ConfigError(
    f"ScienceEvidence.md at {path} failed validation: {exc}"
) from exc
```

**Source:** [Source: gym-coach-brain/src/gym_coach_brain/exceptions.py] — ConfigError уже определён

---

### Полная реализация tests/conftest.py

```python
# tests/conftest.py
"""
Shared pytest fixtures for gym-coach-brain tests.

Fixtures:
    db_engine: in-memory SQLite engine with schema (no seed data)
    db_session: in-memory SQLite session with schema (for unit tests)
    mock_science_config: minimal ScienceConfig for testing (no real file I/O)
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.data.models import Base
from gym_coach_brain.core.science import (
    ScienceConfig,
    PUOSConfig,
    ProgressionConfig,
    RecoveryConfig,
    MethodologySpec,
    MethodologiesConfig,
    PlanningConfig,
)


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with full schema. No seed data. No real file."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """In-memory SQLite session with schema. Use as context manager in tests.

    Usage:
        def test_something(db_session):
            db_session.add(obj)
            db_session.commit()
    """
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def mock_science_config() -> ScienceConfig:
    """Minimal valid ScienceConfig for unit tests. No file I/O.

    Uses test-representative values (not placeholder zeros):
    - max_sets_per_group=11 — PUOS limit from science evidence
    - recovery weights sum to 1.0 (required by model_validator)
    """
    return ScienceConfig(
        version="test-1.0",
        puos=PUOSConfig(
            max_sets_per_group=11,
            smh_volume_multiplier=1.2,
        ),
        progression=ProgressionConfig(
            compound_increment_kg=2.5,
            isolation_increment_kg=1.25,
            apre_6_step_min_kg=2.5,
            apre_6_step_max_kg=5.0,
            hypertrophy_rep_min=6,
            hypertrophy_rep_max=12,
        ),
        recovery=RecoveryConfig(
            hrv_weight=0.5,
            sleep_weight=0.3,
            stress_weight=0.2,
        ),
        exercises={},
        methodologies=MethodologiesConfig(
            strength=MethodologySpec(
                rep_min=1, rep_max=5,
                frequency_per_week_min=2, frequency_per_week_max=4,
            ),
            hypertrophy=MethodologySpec(
                rep_min=6, rep_max=12,
                frequency_per_week_min=2, frequency_per_week_max=4,
            ),
            endurance=MethodologySpec(
                rep_min=15, rep_max=30,
                frequency_per_week_min=3, frequency_per_week_max=5,
            ),
        ),
        planning=PlanningConfig(
            min_rest_days_per_muscle_group=2,
            min_rest_days_compound=3,
        ),
    )
```

**КРИТИЧНО:**
- `recovery weights` ДОЛЖНЫ суммироваться до 1.0 (hrv=0.5 + sleep=0.3 + stress=0.2 = 1.0)
- Используй `sqlite:///:memory:` — никогда реальный файл в тестах
- `db_session` зависит от `db_engine` через fixture chain (правильно — pytest управляет lifecycle)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Test Fixtures (conftest.py)]

---

### Обновление tests/test_core/test_science.py: ConfigError

```python
# tests/test_core/test_science.py
# Добавить импорт ConfigError:
from gym_coach_brain.exceptions import ConfigError

# Изменить ВСЕ failure-mode тесты:
# БЫЛО:
def test_load_science_config_missing_file_raises():
    with pytest.raises(ValueError, match="not found"):
        load_science_config(Path("/nonexistent/ScienceEvidence.md"))

# СТАЛО:
def test_load_science_config_missing_file_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_science_config(Path("/nonexistent/ScienceEvidence.md"))

# Аналогично для ВСЕХ других failure-mode тестов:
# test_load_science_config_no_frontmatter_raises → pytest.raises(ConfigError, ...)
# test_load_science_config_malformed_yaml_raises → pytest.raises(ConfigError, ...)
# test_load_science_config_missing_required_key_raises → pytest.raises(ConfigError, ...)
# test_load_science_config_negative_value_raises → pytest.raises(ConfigError, ...)
# test_load_science_config_type_mismatch_raises → pytest.raises(ConfigError, ...)
# test_load_science_config_invalid_recovery_weights_raises → pytest.raises(ConfigError, ...)
# test_exercise_overrides_validation → pytest.raises(ConfigError, ...)

# Добавить новый тест использующий mock_science_config fixture из conftest:
def test_mock_science_config_fixture(mock_science_config):
    """Verifies mock_science_config fixture is valid and injectable."""
    assert isinstance(mock_science_config, ScienceConfig)
    assert mock_science_config.version == "test-1.0"
    assert mock_science_config.puos.max_sets_per_group == 11

def test_science_config_is_injectable(mock_science_config):
    """ScienceConfig is passed as parameter — not a singleton."""
    # Demonstrating the injection pattern used across all modules
    def some_function(science: ScienceConfig) -> int:
        return science.puos.max_sets_per_group
    assert some_function(mock_science_config) == 11
```

**Важно:** `mock_science_config` fixture в тесте принимается как **параметр функции** — pytest автоматически инжектирует из `tests/conftest.py`. Никаких явных импортов не нужно.

---

### [Опционально] initial_weight_table для Story 3.4

Story 3.4 AC ссылается на:
```python
ScienceConfig.initial_weight_table[experience_level][movement_pattern]
# Пример: initial_weight_table["beginner"]["horizontal_push"] → 0.4
# Результат: bodyweight_kg * coefficient
```

Если Story 3.4 заблокирована без этого поля — добавить в Story 3.3:

**В `ScienceEvidence.md` frontmatter:**
```yaml
initial_weight_table:
  beginner:
    horizontal_push: 0.40   # bodyweight coefficient for starting weight
    vertical_push: 0.30
    horizontal_pull: 0.35
    vertical_pull: 0.30
    squat: 0.60
    hinge: 0.50
    carry: 0.25
  intermediate:
    horizontal_push: 0.70
    vertical_push: 0.55
    horizontal_pull: 0.60
    vertical_pull: 0.55
    squat: 1.00
    hinge: 0.90
    carry: 0.45
  advanced:
    horizontal_push: 1.00
    vertical_push: 0.80
    horizontal_pull: 0.90
    vertical_pull: 0.80
    squat: 1.50
    hinge: 1.30
    carry: 0.65
```

**В `ScienceConfig` Pydantic model:**
```python
class ScienceConfig(BaseModel):
    ...
    initial_weight_table: dict[str, dict[str, float]] = {}  # optional, populated in Epic 3
```

Ключи верхнего уровня: `beginner`, `intermediate`, `advanced`
Ключи второго уровня: имена MovementPattern из seed data (snake_case)

**Если не добавлять в Story 3.3** — Story 3.4 должна сама добавить это поле.

---

### Architecture Compliance Constraints

**Обязательные паттерны:**

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.exceptions import ConfigError  # ✅
from ..exceptions import ConfigError                 # ❌ запрещено

# 2. ScienceConfig — НЕ глобальный singleton:
# ПРАВИЛЬНО — создаётся ОДИН РАЗ в точке входа (api/main.py), передаётся параметром:
science = load_science_config()
result = some_function(science=science)

# ЗАПРЕЩЕНО:
SCIENCE = load_science_config()  # ❌ модульный синглтон — нельзя мокировать в тестах

# 3. Исключения из internal modules:
# НЕ возвращать {"error": "..."} — только typed exceptions
# api/ — единственный слой конвертирующий exceptions в exit_code

# 4. ConfigError → api/ конвертирует в exit_code=2 (системная ошибка)
```

**Dependency direction:** `api → adaptation → core → data`
`core/science.py` может импортировать только `exceptions.py` и stdlib — НЕ data/, adaptation/, ml/

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

**Python 3.14+:**
- `Path | None` type union — нативный Python 3.10+, без `Optional`
- `re.compile(r"...", re.DOTALL)` — стандартный stdlib

**Pydantic 2.0+ (используется уже в проекте):**
- `from pydantic import BaseModel, Field, model_validator` — уже импортированы
- `@model_validator(mode="after")` — v2 синтаксис (используется в RecoveryConfig)
- `Model(**data)` — работает в v2

**pyyaml (уже установлен):**
- `yaml.safe_load()` — единственный допустимый метод (security; никогда `yaml.load()`)

**Проверить установлен ли:** `python -c "import yaml; print(yaml.__version__)"` (из `gym-coach-brain/` через `uv run`)

**Source:** [Source: gym-coach-brain/pyproject.toml]

---

### File Structure Requirements

**Файлы, изменяемые в этой истории:**
```
gym-coach-brain/
├── src/gym_coach_brain/
│   └── core/
│       └── science.py           ← ИЗМЕНИТЬ: ValueError → ConfigError (5 мест)
└── tests/
    ├── conftest.py               ← СОЗДАТЬ: db_engine, db_session, mock_science_config
    └── test_core/
        └── test_science.py      ← ИЗМЕНИТЬ: ValueError → ConfigError + новые тесты
```

**Файлы, которые эта история НЕ создаёт:**
- `src/gym_coach_brain/core/apre.py`, `progression.py`, `puos.py` — Epic 4
- `src/gym_coach_brain/core/onboarding.py` — Story 3.4
- `src/gym_coach_brain/api/` — Story 3.5+

**Рабочая директория:** `gym-coach-brain/` (внутри проекта OpenGym)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory Structure]

---

### Testing Requirements

**Стратегия тестирования:**
- `test_science.py` — использует **реальный** `ScienceEvidence.md` для happy-path тестов (интеграционный уровень)
- `conftest.py.mock_science_config` — для unit-тестов, изолированных от файловой системы
- `conftest.py.db_session` — для всех тестов, работающих с БД (Stories 3.4, 3.5+)
- НЕ реальный SQLite файл в тестах — только `sqlite:///:memory:`
- НЕ `alembic upgrade head` в тестах — только `Base.metadata.create_all(engine)`

**Запуск:**
```bash
cd gym-coach-brain
uv run pytest tests/test_core/test_science.py -v  # только science тесты
uv run pytest -v                                   # все тесты (ожидаем 65+)
```

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns (Test Fixtures)]

---

### Previous Story Intelligence (Story 3.2)

**Ключевые выводы из Story 3.2:**
1. **63 тестов PASS** после Story 3.2 — baseline, не ломать
2. `tests/conftest.py` **НЕ был создан** в Story 3.2 (только `tests/test_data/__init__.py`, `test_models.py`, `test_seed_coverage.py`)
3. `data/models.py` хранит `training_split` и `equipment_type` как `String` с Python enum validation (не native SQLAlchemy Enum) — Alembic compatibility
4. `uv run` pattern: всегда `cd gym-coach-brain && uv run pytest`
5. `exceptions.py` содержит `ConfigError` — готов к использованию в `core/science.py`

**Из Story 3.2 Completion Notes:**
- Review items включали ForeignKey, CheckConstraints, server_default — всё resolved
- `data/session.py.get_session()` возвращает `Session(engine)` — использовать в conftest.py

**Source:** [Source: _bmad-output/implementation-artifacts/3-2-data-layer-sqlalchemy.md#Completion Notes List]

---

### Git Intelligence

```
Последние коммиты (основной репозиторий):
11b8cbb Reposition README with product narrative and unique value proposition
425df73 Add GitHub stars and forks badges to README header
d005f82 Rewrite README in English with project positioning and value proposition
```

**Выводы:**
- `gym-coach-brain/` находится внутри OpenGym репозитория
- Dev agent НЕ делает git commit (только если явно попросят)
- Файлы будут видны как modified/untracked — нормально

---

### Project Structure Notes

**После этой истории `tests/` будет выглядеть так:**
```
gym-coach-brain/tests/
├── conftest.py               ← СОЗДАТЬ (db_engine, db_session, mock_science_config)
├── test_core/
│   ├── __init__.py           ← уже существует
│   └── test_science.py       ← ИЗМЕНИТЬ (ConfigError + mock fixture тест)
├── test_data/
│   ├── __init__.py           ← уже существует
│   ├── test_models.py        ← уже существует (63 тестов baseline)
│   └── test_seed_coverage.py ← уже существует
```

**Зависимости:**
- **Story 3.4** (`core/onboarding.py`) — использует `mock_science_config` из conftest.py
- **Story 3.5** (`api/handlers.py`) — использует `mock_science_config` + `db_session`

---

### References

- Story 3.3 требования: [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Story 3.3]
- Реализация core/science.py: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py]
- ConfigError definition: [Source: gym-coach-brain/src/gym_coach_brain/exceptions.py]
- Architecture conftest pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Test Fixtures]
- Previous story learnings: [Source: _bmad-output/implementation-artifacts/3-2-data-layer-sqlalchemy.md]
- Story 1.2.5 (science.py original): [Source: _bmad-output/implementation-artifacts/1-2-5-core-science-pydantic.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No blockers encountered. All tasks completed in single session.

### Completion Notes List

- ✅ Baseline verified: 97 tests PASS before changes
- ✅ Added `from gym_coach_brain.exceptions import ConfigError` import to `core/science.py`
- ✅ Replaced all `ValueError` with `ConfigError` in `science.py` (including docstrings and internal validators)
- ✅ Created `tests/conftest.py` with `db_engine`, `db_session`, and `mock_science_config` fixtures
- ✅ Updated `test_science.py` (8 failure-mode tests + 2 new tests)
- ✅ All 99 tests PASS (97 existing + 2 new)
- ✅ **AI-Review**: Fixed docstring mismatch and RecoveryConfig validator exception type
- ✅ **AI-Review**: Documented side-effect changes in seed.py and test_data/

### File List

- `gym-coach-brain/src/gym_coach_brain/core/science.py` (modified: ValueError → ConfigError)
- `gym-coach-brain/tests/conftest.py` (created: shared fixtures)
- `gym-coach-brain/tests/test_core/test_science.py` (modified: ConfigError + new tests)
- `gym-coach-brain/src/gym_coach_brain/data/seed.py` (modified: side-effect from dev session)
- `gym-coach-brain/tests/test_data/test_models.py` (modified: side-effect from dev session)
- `gym-coach-brain/tests/test_data/test_seed_coverage.py` (modified: side-effect from dev session)
- `_bmad-output/implementation-artifacts/3-3-science-config-loader.md` (modified: status → done)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified: 3-3 → done)

### Change Log

- 2026-03-08: Implemented Story 3.3 — replaced ValueError with ConfigError in core/science.py (5 locations), created tests/conftest.py with shared fixtures (db_engine, db_session, mock_science_config), updated test_science.py (8 failure-mode tests + 2 new tests). 99 tests pass.

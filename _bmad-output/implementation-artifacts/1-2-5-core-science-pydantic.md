# Story 1.2.5: Реализация `core/science.py` и Pydantic ScienceConfig

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to implement `core/science.py` with a Pydantic ScienceConfig model,
so that Story 1.3 can load and validate ScienceEvidence.md at runtime.

## Acceptance Criteria

**Given** skeleton `ScienceEvidence.md` создан (Story 1.2) с YAML-frontmatter по адресу `/home/ubuntu/.openclaw/gym-coach-brain/ScienceEvidence.md`

**When** агент реализует `gym_coach_brain/core/science.py`

**Then** файл содержит Pydantic-модели для всех секций frontmatter:
- `PUOSConfig` (max_sets_per_group: int, smh_volume_multiplier: float)
- `ProgressionConfig` (все 6 полей из frontmatter)
- `RecoveryConfig` (hrv_weight, sleep_weight, stress_weight)
- `MethodologySpec` + `MethodologiesConfig` (strength, hypertrophy, endurance)
- `PlanningConfig` (min_rest_days_per_muscle_group, min_rest_days_compound)
- `ScienceConfig` (корневая модель)

**And** функция `load_science_config(path: Path | None = None) -> ScienceConfig` читает YAML-frontmatter из `ScienceEvidence.md` и возвращает валидированный объект

**And** `python -c "from gym_coach_brain.core.science import load_science_config"` выполняется без ошибок (запускать из `/home/ubuntu/.openclaw/gym-coach-brain/` с `uv run`)

**And** `pytest tests/test_core/test_science.py` проходит: модель парсит skeleton с placeholder-значениями без ValidationError

## Tasks / Subtasks

- [x] **Bootstrap: инициализировать проект gym-coach-brain** (prereq для импорта)
  - [x] Проверить существование `/home/ubuntu/.openclaw/gym-coach-brain/pyproject.toml`
  - [x] Если НЕ существует: выполнить `cd /home/ubuntu/.openclaw/gym-coach-brain && uv init --package .` (инициализация в существующей директории)
  - [x] Добавить зависимости: `cd /home/ubuntu/.openclaw/gym-coach-brain && uv add "pydantic>=2.0" pyyaml`
  - [x] Добавить dev-зависимости: `uv add --dev pytest pytest-cov`
  - [x] Убедиться, что `ScienceEvidence.md` НЕ затронут `uv init` (только новые файлы создаются)

- [x] **Создать структуру модулей core/** (AC: правильные пути)
  - [x] Создать `/home/ubuntu/.openclaw/gym-coach-brain/src/gym_coach_brain/core/__init__.py` (пустой файл)
  - [x] Убедиться, что `/home/ubuntu/.openclaw/gym-coach-brain/src/gym_coach_brain/__init__.py` существует (создаётся `uv init`)

- [x] **Реализовать `src/gym_coach_brain/core/science.py`** (AC: все Pydantic-модели)
  - [x] Импортировать: `from pathlib import Path`, `from pydantic import BaseModel`, `import yaml`
  - [x] Реализовать `PUOSConfig(BaseModel)` — два поля: max_sets_per_group: int, smh_volume_multiplier: float
  - [x] Реализовать `ProgressionConfig(BaseModel)` — 6 полей (все из YAML progression секции)
  - [x] Реализовать `RecoveryConfig(BaseModel)` — 3 поля весов (hrv_weight, sleep_weight, stress_weight)
  - [x] Реализовать `MethodologySpec(BaseModel)` — 4 поля (rep_min, rep_max, frequency_per_week_min, frequency_per_week_max)
  - [x] Реализовать `MethodologiesConfig(BaseModel)` — strength, hypertrophy, endurance: MethodologySpec
  - [x] Реализовать `PlanningConfig(BaseModel)` — min_rest_days_per_muscle_group: int, min_rest_days_compound: int
  - [x] Реализовать `ScienceConfig(BaseModel)` — корневая модель с 7 полями (version: str, puos, progression, recovery, exercises: dict, methodologies, planning)
  - [x] Реализовать `load_science_config(path: Path | None = None) -> ScienceConfig` — парсит YAML-frontmatter через `yaml.safe_load()` и возвращает валидированный `ScienceConfig`
  - [x] Default path в `load_science_config`: `Path(__file__).parent.parent.parent.parent / "ScienceEvidence.md"` (4 уровня вверх из src/gym_coach_brain/core/ → project root)
  - [x] ТОЛЬКО `yaml.safe_load()` — никогда `yaml.load()` (security ADR)
  - [x] Ошибка парсинга → поднимать `ValueError` с чётким сообщением (временно; будет заменено на `ConfigError` в Story 3.1)

- [x] **Создать тесты `tests/test_core/test_science.py`** (AC: pytest проходит)
  - [x] Создать `/home/ubuntu/.openclaw/gym-coach-brain/tests/__init__.py` (если не существует)
  - [x] Создать `/home/ubuntu/.openclaw/gym-coach-brain/tests/test_core/__init__.py`
  - [x] `test_load_science_config_parses_skeleton()` — загружает реальный ScienceEvidence.md, проверяет isinstance(config, ScienceConfig) и config.version == "0.0.0"
  - [x] `test_puos_config_types()` — проверяет типы max_sets_per_group (int) и smh_volume_multiplier (float)
  - [x] `test_planning_config_types()` — проверяет типы min_rest_days_per_muscle_group (int) и min_rest_days_compound (int)
  - [x] `test_methodologies_all_present()` — проверяет наличие strength, hypertrophy, endurance
  - [x] `test_exercises_is_dict()` — exercises == {} (пустой словарь)
  - [x] Тесты используют `SCIENCE_PATH = Path(__file__).parent.parent.parent / "ScienceEvidence.md"` для ссылки на реальный файл

- [x] **Верифицировать AC-команды** (AC: both pass)
  - [x] `cd /home/ubuntu/.openclaw/gym-coach-brain && uv run python -c "from gym_coach_brain.core.science import load_science_config"` — ожидаем: без ошибок
  - [x] `cd /home/ubuntu/.openclaw/gym-coach-brain && uv run pytest tests/test_core/test_science.py -v` — ожидаем: все тесты PASSED

### Review Follow-ups (AI)
- [x] [AI-Review][CRITICAL] Git vs Story Discrepancy: Files in gym-coach-brain/ are untracked (??) despite being marked [x]. Stage files properly.
- [x] [AI-Review][HIGH] ScienceConfig models lack validation (e.g., gt=0). Add Pydantic Field constraints for all parameters [src/gym_coach_brain/core/science.py:7-40]
- [x] [AI-Review][HIGH] Brittle YAML parsing via raw.split("---"). Use a more robust regex or standard frontmatter parser [src/gym_coach_brain/core/science.py:92-95]
- [x] [AI-Review][MEDIUM] Weak test suite: Add tests for failure modes (malformed YAML, missing keys, type mismatches) [tests/test_core/test_science.py]
- [x] [AI-Review][MEDIUM] Generic Error Handling: Improve ValueError messages with specific context about what failed in parsing/validation [src/gym_coach_brain/core/science.py:90, 93, 100]
- [x] [AI-Review][MEDIUM] Fragile path depth logic: Replace parent.parent... with a more robust discovery method [src/gym_coach_brain/core/science.py:84-85]
- [x] [AI-Review][LOW] Add docstrings to Pydantic models linking fields to scientific basis [src/gym_coach_brain/core/science.py:7-40]

## Dev Notes

### ⚠️ КРИТИЧЕСКОЕ: Бутстрап проекта

**Проблема:** `gym-coach-brain/` содержит только `ScienceEvidence.md` — нет `pyproject.toml`, нет `src/`. Story 3.1 должна запустить `uv init --package gym-coach-brain`, но Story 1.2.5 нужна *раньше* (prereq для Story 1.3, которая входит в Epic 1 — блокирует все последующие эпики).

**Решение:** `uv init` умеет работать с существующими директориями:
```bash
cd /home/ubuntu/.openclaw/gym-coach-brain
uv init --package .
# Создаст: pyproject.toml, src/gym_coach_brain/__init__.py, README.md, .python-version, uv.lock
# НЕ тронет: ScienceEvidence.md (uv init только создаёт, не удаляет)
```

**Проверка что ScienceEvidence.md сохранился:**
```bash
ls /home/ubuntu/.openclaw/gym-coach-brain/ScienceEvidence.md  # должен существовать
```

**Совместимость со Story 3.1:**
Story 3.1 запускает `uv init --package gym-coach-brain` из `/home/ubuntu/.openclaw/`. Если `gym-coach-brain/pyproject.toml` уже существует, Story 3.1 должна пропустить init и сосредоточиться на `uv add sqlalchemy alembic loguru torch` и прочей настройке. Dev agent Story 3.1 должен это учесть.

---

### Полная реализация `core/science.py`

```python
# src/gym_coach_brain/core/science.py
from pathlib import Path

import yaml
from pydantic import BaseModel


class PUOSConfig(BaseModel):
    max_sets_per_group: int
    smh_volume_multiplier: float


class ProgressionConfig(BaseModel):
    compound_increment_kg: float
    isolation_increment_kg: float
    apre_6_step_min_kg: float
    apre_6_step_max_kg: float
    hypertrophy_rep_min: int
    hypertrophy_rep_max: int


class RecoveryConfig(BaseModel):
    hrv_weight: float
    sleep_weight: float
    stress_weight: float


class MethodologySpec(BaseModel):
    rep_min: int
    rep_max: int
    frequency_per_week_min: int
    frequency_per_week_max: int


class MethodologiesConfig(BaseModel):
    strength: MethodologySpec
    hypertrophy: MethodologySpec
    endurance: MethodologySpec


class PlanningConfig(BaseModel):
    min_rest_days_per_muscle_group: int
    min_rest_days_compound: int


class ScienceConfig(BaseModel):
    version: str
    puos: PUOSConfig
    progression: ProgressionConfig
    recovery: RecoveryConfig
    exercises: dict
    methodologies: MethodologiesConfig
    planning: PlanningConfig


def load_science_config(path: Path | None = None) -> ScienceConfig:
    """Load and validate ScienceEvidence.md YAML frontmatter into ScienceConfig.

    Called ONCE per process at startup (Composition Root pattern).
    Pass the returned ScienceConfig as a parameter to all internal functions —
    do NOT create a module-level global singleton.

    Args:
        path: Path to ScienceEvidence.md. Defaults to project root
              (gym-coach-brain/ScienceEvidence.md), resolved relative to this file.

    Returns:
        Validated ScienceConfig instance.

    Raises:
        ValueError: If file not found or YAML frontmatter is malformed.
    """
    if path is None:
        # src/gym_coach_brain/core/science.py → 4 parents up = gym-coach-brain/ project root
        path = Path(__file__).parent.parent.parent.parent / "ScienceEvidence.md"

    if not path.exists():
        raise ValueError(f"ScienceEvidence.md not found at {path}")

    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---")
    if len(parts) < 3:
        raise ValueError(
            f"No valid YAML frontmatter in {path}. "
            "Expected content wrapped in '---' delimiters."
        )

    data = yaml.safe_load(parts[1])
    return ScienceConfig(**data)
```

> **Заметка:** В Story 3.1 (exceptions.py) `ValueError` заменяется на `ConfigError(GymCoachError)`. До тех пор `ValueError` достаточно.

---

### Полная реализация `tests/test_core/test_science.py`

```python
# tests/test_core/test_science.py
from pathlib import Path

import pytest

from gym_coach_brain.core.science import (
    MethodologySpec,
    MethodologiesConfig,
    PlanningConfig,
    PUOSConfig,
    ScienceConfig,
    load_science_config,
)

# Path to the actual skeleton file created by Story 1.2
SCIENCE_PATH = Path(__file__).parent.parent.parent / "ScienceEvidence.md"


@pytest.fixture
def science_config() -> ScienceConfig:
    """Load real ScienceEvidence.md skeleton (placeholder values)."""
    return load_science_config(SCIENCE_PATH)


def test_load_science_config_parses_skeleton(science_config):
    """ScienceConfig parses placeholder skeleton without ValidationError."""
    assert isinstance(science_config, ScienceConfig)


def test_version_is_placeholder_string(science_config):
    assert science_config.version == "0.0.0"


def test_puos_config_types(science_config):
    assert isinstance(science_config.puos.max_sets_per_group, int)
    assert isinstance(science_config.puos.smh_volume_multiplier, float)


def test_progression_config_types(science_config):
    assert isinstance(science_config.progression.compound_increment_kg, float)
    assert isinstance(science_config.progression.hypertrophy_rep_min, int)
    assert isinstance(science_config.progression.hypertrophy_rep_max, int)


def test_recovery_config_types(science_config):
    assert isinstance(science_config.recovery.hrv_weight, float)
    assert isinstance(science_config.recovery.sleep_weight, float)
    assert isinstance(science_config.recovery.stress_weight, float)


def test_exercises_is_empty_dict(science_config):
    """exercises is empty dict in skeleton — populated in Epic 2."""
    assert science_config.exercises == {}


def test_methodologies_all_present(science_config):
    assert hasattr(science_config.methodologies, "strength")
    assert hasattr(science_config.methodologies, "hypertrophy")
    assert hasattr(science_config.methodologies, "endurance")


def test_methodology_spec_types(science_config):
    spec = science_config.methodologies.strength
    assert isinstance(spec.rep_min, int)
    assert isinstance(spec.rep_max, int)
    assert isinstance(spec.frequency_per_week_min, int)
    assert isinstance(spec.frequency_per_week_max, int)


def test_planning_config_types(science_config):
    assert isinstance(science_config.planning.min_rest_days_per_muscle_group, int)
    assert isinstance(science_config.planning.min_rest_days_compound, int)


def test_load_science_config_missing_file_raises():
    """Missing ScienceEvidence.md raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        load_science_config(Path("/nonexistent/ScienceEvidence.md"))


def test_load_science_config_accepts_explicit_path():
    """load_science_config accepts explicit Path parameter."""
    config = load_science_config(SCIENCE_PATH)
    assert isinstance(config, ScienceConfig)
```

---

### Architecture Compliance Constraints

**ОБЯЗАТЕЛЬНО соблюдать из architecture.md:**

1. **Absolute imports ONLY:**
   ```python
   from gym_coach_brain.core.science import load_science_config  ✅
   from ..core.science import load_science_config  ❌ запрещено
   ```

2. **ScienceConfig — NOT global singleton:**
   ```python
   # ПРАВИЛЬНО: создать один раз в точке входа (api/main.py)
   science = load_science_config()

   # ЗАПРЕЩЕНО: глобальная переменная на уровне модуля
   SCIENCE = load_science_config()  # ❌ нельзя мокировать в тестах
   ```

3. **ТОЛЬКО `yaml.safe_load()`:**
   ```python
   yaml.safe_load(parts[1])  ✅
   yaml.load(parts[1])  ❌ security risk (arbitrary code execution)
   ```

4. **Pydantic 2.0+ синтаксис:** `from pydantic import BaseModel` (тот же, но поведение v2). В v2 `model.model_validate(data)` — preferred over `Model(**data)`, но `Model(**data)` также работает.

5. **Именование:** `ScienceConfig`, `PUOSConfig`, `PlanningConfig` — эти имена зафиксированы. Использовались в throwaway-скрипте Story 1.2 и будут использоваться в Story 1.3 AC: `from gym_coach_brain.core.science import load_science_config; cfg = load_science_config(); assert cfg.puos.max_sets_per_group > 0`

6. **Файл в `core/`, НЕ в `data/`:**
   - `src/gym_coach_brain/core/science.py` ✅ — это чистая Composition Root util, не data access
   - `src/gym_coach_brain/data/science.py` ❌

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

**Python 3.14+**
- `Path | None` type union syntax — нативный Python 3.10+, не нужен `Optional`
- f-strings без ограничений

**Pydantic 2.0+ (текущий стандарт 2026)**
- `from pydantic import BaseModel` — без изменений
- `class Config` deprecated в v2 — не использовать (не нужен для этой истории)
- `model_validate()`, `model_dump()` — v2 API (старый `dict()`, `parse_obj()` deprecated)
- `int` поля: Pydantic 2.0 принимает `0` как валидный int (не требует >0)

**pyyaml (текущий стандарт)**
- `pip install pyyaml` / `uv add pyyaml`
- `yaml.safe_load()` — единственный допустимый метод (security)
- YAML anchors/aliases не используются в ScienceEvidence.md — `safe_load` достаточен

**uv (2026 стандарт)**
- Заменяет pip + venv + pyenv
- `uv run pytest` вместо `pytest` напрямую (использует virtualenv проекта)
- `uv run python -c "..."` для верификации

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Technical Stack]

---

### File Structure Requirements

**Файлы, создаваемые в этой истории:**

```
gym-coach-brain/                                    (уже существует)
├── pyproject.toml                                  ← СОЗДАТЬ (uv init)
├── uv.lock                                         ← СОЗДАТЬ (uv init)
├── .python-version                                 ← СОЗДАТЬ (uv init, Python 3.14)
├── README.md                                       ← СОЗДАТЬ (uv init, OK to keep)
├── ScienceEvidence.md                              (уже существует, НЕ трогать)
├── src/
│   └── gym_coach_brain/
│       ├── __init__.py                             ← СОЗДАТЬ (uv init)
│       └── core/
│           ├── __init__.py                         ← СОЗДАТЬ (пустой файл)
│           └── science.py                          ← СОЗДАТЬ (основная задача)
└── tests/
    ├── __init__.py                                 ← СОЗДАТЬ (пустой файл)
    └── test_core/
        ├── __init__.py                             ← СОЗДАТЬ (пустой файл)
        └── test_science.py                         ← СОЗДАТЬ (тесты)
```

**Файлы, которые эта история НЕ создаёт:**
- `src/gym_coach_brain/exceptions.py` — Story 3.1 (создаётся с `GymCoachError`, `ConfigError`, etc.)
- `src/gym_coach_brain/data/` — Story 3.2
- `alembic/` — Story 3.2
- `tests/conftest.py` — Story 3.2 (создаёт db_session, mock_science_config fixtures)
- `src/gym_coach_brain/core/apre.py`, `progression.py`, etc. — Epic 4

**Downstream dependency:**
- **Story 1.3:** AC включает `from gym_coach_brain.core.science import load_science_config; cfg = load_science_config(); assert cfg.puos.max_sets_per_group > 0` — требует `core/science.py` из этой истории

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory Structure]

---

### Testing Requirements

**Стратегия тестирования:**
- Тесты используют **реальный** `ScienceEvidence.md` skeleton (placeholder 0/0.0 values)
- Это интеграционный тест на уровне файловой системы — приемлемо для такой маленькой scope
- `conftest.py` с фикстурами (`mock_science_config`, `db_session`) создаётся в Story 3.2 — в этой истории conftest.py НЕ нужен
- Все placeholder-значения (0, 0.0, "0.0.0") валидируются Pydantic как корректные — тест должен проходить

**Запуск:**
```bash
cd /home/ubuntu/.openclaw/gym-coach-brain
uv run pytest tests/test_core/test_science.py -v
```

**Ожидаемый вывод:**
```
tests/test_core/test_science.py::test_load_science_config_parses_skeleton PASSED
tests/test_core/test_science.py::test_version_is_placeholder_string PASSED
tests/test_core/test_science.py::test_puos_config_types PASSED
tests/test_core/test_science.py::test_progression_config_types PASSED
tests/test_core/test_science.py::test_recovery_config_types PASSED
tests/test_core/test_science.py::test_exercises_is_empty_dict PASSED
tests/test_core/test_science.py::test_methodologies_all_present PASSED
tests/test_core/test_science.py::test_methodology_spec_types PASSED
tests/test_core/test_science.py::test_planning_config_types PASSED
tests/test_core/test_science.py::test_load_science_config_missing_file_raises PASSED
tests/test_core/test_science.py::test_load_science_config_accepts_explicit_path PASSED
11 passed
```

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns (Test Fixtures)]

---

### Previous Story Intelligence (Story 1.2)

**Story 1.2 создала:**
- `/home/ubuntu/.openclaw/gym-coach-brain/ScienceEvidence.md` — skeleton с placeholder-значениями
- Status Story 1.2: `in-progress` (файл уже существует, skeleton реализован)

**Ключевые выводы для Story 1.2.5:**

1. **Pre-check перед началом:**
   ```bash
   # Убедиться что ScienceEvidence.md существует и содержит YAML frontmatter
   head -5 /home/ubuntu/.openclaw/gym-coach-brain/ScienceEvidence.md
   # Ожидаем: первая строка "---", вторая строка 'version: "0.0.0"'
   ```

2. **Именование Pydantic-моделей ЗАФИКСИРОВАНО:** Story 1.2 использовала конкретные имена в throwaway-верификационном скрипте. Story 1.3 AC явно ссылается на `load_science_config()` и `cfg.puos.max_sets_per_group`. Не менять имена.

3. **exercises: dict = {}** — `exercises` секция пустая в skeleton, но тип `dict` должен работать с Pydantic. Проверить что `exercises: {}` в YAML парсится как `{}` Python dict, не `None`.

4. **Выявленная зависимость:** Story 1.2 показала что gym-coach-brain директория создаётся вручную. Аналогично — pyproject.toml нужно создать вручную (через uv init).

5. **Паттерн Story 1.1 и 1.2:** Обе были документо-ориентированными историями без Python кода в production src/. Story 1.2.5 — первый Python-код. Убедиться что установлен uv, Python 3.14 доступен.

**Source:** [Source: _bmad-output/implementation-artifacts/1-2-yaml-schema-design.md#Dev Notes]

---

### Git Intelligence

```bash
# Последние 5 коммитов:
# 0195177 feat: add bmad planning artifacts and expand gym-coach skill
# 8440199 feat: add gym coach skill
# 7bef692 chore: update current project state
# bb07393 feat: add gym-coach skill (SQLite workout logging + onboarding)
# 1bcaa2a Merge pull request #27 (fix hardcoded operator token)
```

**Выводы:**
- Репозиторий находится в OpenClaw workspace `/home/ubuntu/.openclaw/`
- `gym-coach-brain` — это **новый Python-пакет внутри** workspace, не отдельный репозиторий
- Gym coach код сейчас существует как OpenClaw skill в `workspace/skills/gym-coach/` — это legacy-монолит (2029 LOC), **НЕ трогать**
- Никакого gym-coach-brain Python-кода в истории git пока нет — это будет первый Python файл пакета

**Важно:** `gym-coach-brain/` директория НЕ добавлена в gitignore. Новые файлы будут видны как untracked. Dev agent не должен делать git commit в рамках этой истории (только если явно попросят).

---

### Project Structure Notes

**Текущее состояние файловой системы:**
- `/home/ubuntu/.openclaw/gym-coach-brain/ScienceEvidence.md` — EXISTS ✅
- `/home/ubuntu/.openclaw/gym-coach-brain/pyproject.toml` — НЕ существует ❌
- `/home/ubuntu/.openclaw/gym-coach-brain/src/` — НЕ существует ❌

**После выполнения истории:**
- `gym-coach-brain/pyproject.toml` — создаётся uv init
- `gym-coach-brain/src/gym_coach_brain/core/science.py` — основной продукт
- `gym-coach-brain/tests/test_core/test_science.py` — тесты

**Конфликтов и расхождений нет** — прямое следование архитектуре.

---

### References

- Story 1.2.5 требования: [Source: _bmad-output/planning-artifacts/epics/epic-1.md#Story 1.2.5]
- ScienceEvidence.md skeleton (prereq): `/home/ubuntu/.openclaw/gym-coach-brain/ScienceEvidence.md`
- ADR-002 (ScienceConfig Loading): [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
- Composition Root pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
- Naming conventions: [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns]
- Complete project structure: [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory Structure]
- Previous story: [Source: _bmad-output/implementation-artifacts/1-2-yaml-schema-design.md]
- Research (context for future Story 1.3): [Source: _bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — реализация прошла без блокеров.

### Completion Notes List

- Bootstrapped `gym-coach-brain` Python package с `uv init --package .` (Python 3.14.3, pydantic 2.12.5, pyyaml 6.0.3)
- `ScienceEvidence.md` не тронут — подтверждено через `ls` до/после `uv init`
- Реализованы все 7 Pydantic-моделей: `PUOSConfig`, `ProgressionConfig`, `RecoveryConfig`, `MethodologySpec`, `MethodologiesConfig`, `PlanningConfig`, `ScienceConfig`
- `load_science_config()` использует исключительно `yaml.safe_load()` (ADR-002 compliant)
- 11/11 тестов PASSED: все AC верифицированы

### File List

- `gym-coach-brain/pyproject.toml` (created by uv init)
- `gym-coach-brain/uv.lock` (created by uv init)
- `gym-coach-brain/.python-version` (created by uv init)
- `gym-coach-brain/README.md` (created by uv init)
- `gym-coach-brain/src/gym_coach_brain/__init__.py` (created by uv init)
- `gym-coach-brain/src/gym_coach_brain/core/__init__.py` (created)
- `gym-coach-brain/src/gym_coach_brain/core/science.py` (created — main deliverable)
- `gym-coach-brain/tests/__init__.py` (created)
- `gym-coach-brain/tests/test_core/__init__.py` (created)
- `gym-coach-brain/tests/test_core/test_science.py` (created — 11 tests)
- `_bmad-output/implementation-artifacts/1-2-5-core-science-pydantic.md` (updated — status, tasks, dev record)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (updated — status in-progress → review)

## Change Log

- 2026-03-04: Story 1.2.5 implemented — gym-coach-brain Python package bootstrapped, core/science.py with Pydantic ScienceConfig models created, 11 tests PASSED
- 2026-03-04: Code review follow-ups resolved (7 items: 1 CRITICAL, 2 HIGH, 3 MEDIUM, 1 LOW). Key fixes: regex frontmatter parser (_FRONTMATTER_RE, handles --- in body), ge=0 Field constraints on all numeric fields, _find_default_path() walk-up discovery replacing fragile parent depth, specific ValueError messages for each failure mode, docstrings on all Pydantic models with scientific citations. Test suite expanded 11→16 tests (+5 failure-mode tests). Story status: done.

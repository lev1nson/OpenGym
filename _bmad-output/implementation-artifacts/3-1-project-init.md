# Story 3.1: Инициализация проекта

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to complete the gym-coach-brain project structure (add missing deps, create module packages, CI, docs/),
so that all developers have a reproducible environment and the automated test pipeline is in place.

## Acceptance Criteria

**Given** проект `gym-coach-brain/` уже инициализирован через `uv init --package` (Story 1.2.5),
со структурой `src/gym_coach_brain/core/` и базовыми dev-зависимостями

**When** агент добавляет недостающие зависимости и создаёт оставшуюся структуру

**Then** структура `src/gym_coach_brain/` содержит папки `core/`, `adaptation/`, `ml/`, `data/`, `api/` — каждая с `__init__.py`
**And** `uv add sqlalchemy alembic "pydantic[yaml]" loguru torch` и `uv add --dev pytest pytest-cov` выполнены успешно (уже есть pydantic+pyyaml, pytest+pytest-cov — uv обновит/подтвердит)
**And** директория `docs/` создана в project root (`gym-coach-brain/docs/`)
**And** `uv run pytest` запускается без ошибок (существующие 17+ тестов из `tests/test_core/test_science.py` проходят, не ломаются)
**And** `.github/workflows/ci.yml` создан и запускает pytest при push/PR
**And** `exceptions.py` создан в `src/gym_coach_brain/` с классами `GymCoachError`, `ScienceLimitError`, `MLPredictionError`, `ConfigError`

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: текущее состояние)
  - [x] `ls gym-coach-brain/src/gym_coach_brain/` — убедиться что есть только `__init__.py` и `core/`
  - [x] `cat gym-coach-brain/pyproject.toml` — убедиться что sqlalchemy/alembic/loguru/torch отсутствуют
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться что текущие тесты проходят (baseline)

- [x] **Добавить недостающие зависимости** (AC: uv add succeeds)
  - [x] `cd gym-coach-brain && uv add sqlalchemy alembic "pydantic[yaml]" loguru torch`
  - [x] `uv add --dev pytest pytest-cov` (confirm/update, уже есть)
  - [x] Проверить `pyproject.toml` — все 6 deps присутствуют: sqlalchemy, alembic, pydantic[yaml], loguru, torch
  - [x] Проверить `uv.lock` обновлён

- [x] **Создать пустые субпакеты** (AC: all __init__.py exist)
  - [x] `mkdir -p src/gym_coach_brain/data && touch src/gym_coach_brain/data/__init__.py`
  - [x] `mkdir -p src/gym_coach_brain/ml && touch src/gym_coach_brain/ml/__init__.py`
  - [x] `mkdir -p src/gym_coach_brain/adaptation && touch src/gym_coach_brain/adaptation/__init__.py`
  - [x] `mkdir -p src/gym_coach_brain/api && touch src/gym_coach_brain/api/__init__.py`

- [x] **Создать exceptions.py** (AC: все 4 класса)
  - [x] Создать `src/gym_coach_brain/exceptions.py` с `GymCoachError`, `ScienceLimitError`, `MLPredictionError`, `ConfigError`
  - [x] Убедиться что классы соответствуют иерархии из архитектуры (GymCoachError — базовый)

- [x] **Создать docs/ директорию** (AC: exists)
  - [x] `mkdir -p gym-coach-brain/docs`
  - [x] Создать `gym-coach-brain/docs/.gitkeep` (или `README.md`) — Epic 2 Story 2.4 поместит `ml-feature-spec.md` сюда

- [x] **Создать .github/workflows/ci.yml** (AC: pytest on push/PR)
  - [x] Создать `.github/workflows/` директорию
  - [x] Написать `ci.yml` с шагами: checkout, python setup (3.14), uv install, `uv run pytest`

- [x] **Верифицировать итоговое состояние**
  - [x] `cd gym-coach-brain && uv run pytest` — все тесты PASSED, 0 failures
  - [x] `cd gym-coach-brain && python -c "from gym_coach_brain.exceptions import GymCoachError, ScienceLimitError, MLPredictionError, ConfigError; print('OK')"` — без ошибок
  - [x] `cd gym-coach-brain && python -c "import sqlalchemy; import alembic; import loguru; print('deps OK')"` — без ошибок
  - [x] `ls src/gym_coach_brain/` — видим: `__init__.py`, `core/`, `data/`, `ml/`, `adaptation/`, `api/`, `exceptions.py`
  - [x] `ls docs/` — директория существует

## Dev Notes

### ⚠️ КРИТИЧЕСКИ ВАЖНО: Проект уже частично инициализирован

**НЕ запускать `uv init` — проект уже создан.**

Через Stories 1.1–1.3 уже выполнено:
- `uv init --package gym-coach-brain` + базовая src layout структура
- `src/gym_coach_brain/__init__.py`, `core/__init__.py`, `core/science.py` (полная реализация ScienceConfig)
- `tests/__init__.py`, `tests/test_core/__init__.py`, `tests/test_core/test_science.py` (17+ тестов)
- `ScienceEvidence.md` (production coefficients v1.0.0)
- `pyproject.toml` с pydantic, pyyaml, pytest, pytest-cov
- `.python-version = 3.14`, `uv.lock`

**Что НЕДОСТАЁТ (задача этой истории):**
1. sqlalchemy, alembic, loguru, torch не добавлены в deps
2. `data/`, `ml/`, `adaptation/`, `api/` директории НЕ существуют
3. `exceptions.py` НЕ существует
4. `docs/` НЕ существует
5. `.github/workflows/ci.yml` НЕ существует

**Рабочая директория для всех команд:** `/home/ubuntu/.openclaw/gym-coach-brain/`

---

### Architecture Compliance Constraints

**Из `_bmad-output/planning-artifacts/architecture.md`:**

**Project Structure (итоговая после этой истории):**
```
gym-coach-brain/
├── pyproject.toml                  # uv project config, all dependencies
├── uv.lock                         # Lockfile — committed to git
├── README.md
├── ScienceEvidence.md              # ← уже существует
├── .python-version                 # 3.14 ← уже существует
├── .github/
│   └── workflows/
│       └── ci.yml                  # ← СОЗДАТЬ
├── docs/                           # ← СОЗДАТЬ (пустая, для Epic 2 Story 2.4)
├── src/
│   └── gym_coach_brain/
│       ├── __init__.py             # ← уже существует
│       ├── exceptions.py           # ← СОЗДАТЬ
│       ├── core/
│       │   ├── __init__.py         # ← уже существует
│       │   └── science.py          # ← уже существует (полная реализация)
│       ├── data/                   # ← СОЗДАТЬ (только __init__.py)
│       │   └── __init__.py
│       ├── ml/                     # ← СОЗДАТЬ (только __init__.py)
│       │   └── __init__.py
│       ├── adaptation/             # ← СОЗДАТЬ (только __init__.py)
│       │   └── __init__.py
│       └── api/                    # ← СОЗДАТЬ (только __init__.py)
│           └── __init__.py
└── tests/
    ├── __init__.py                 # ← уже существует
    └── test_core/
        ├── __init__.py             # ← уже существует
        └── test_science.py         # ← уже существует (17 тестов)
```

**Import Rules (критично для всех будущих историй):**
- ТОЛЬКО абсолютные импорты: `from gym_coach_brain.exceptions import GymCoachError`
- НЕ relative: `from ..exceptions import GymCoachError` — запрещено
- Dependency direction: `api → adaptation → core → data` (data не импортирует выше)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]

---

### exceptions.py: точная реализация

```python
# src/gym_coach_brain/exceptions.py
"""
Custom exception hierarchy for gym-coach-brain.

All internal modules raise typed exceptions — NOT return error dicts.
Only api/ layer converts exceptions to exit_code + stdout.
"""


class GymCoachError(Exception):
    """Base exception for all gym-coach-brain errors."""
    pass


class ScienceLimitError(GymCoachError):
    """Raised when PUOS/safety limits are violated.

    Raised by: core/puos.py
    Caught by: adaptation/engine.py (never ignored), api/ (exit_code=1)
    """
    pass


class MLPredictionError(GymCoachError):
    """Raised when ML Worker fails to produce a prediction.

    Raised by: ml/worker.py, ml/model.py
    Caught by: adaptation/engine.py (fallback to Double Progression — NOT re-raised)
    """
    pass


class ConfigError(GymCoachError):
    """Raised when ScienceConfig cannot be parsed.

    Raised by: core/science.py (load_science_config)
    Caught by: api/main.py (exit_code=2, process should restart)
    """
    pass
```

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]

---

### ci.yml: точная реализация

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["**"]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.14
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          version: "latest"

      - name: Install dependencies
        run: uv sync --all-extras --dev

      - name: Run tests
        run: uv run pytest
        working-directory: gym-coach-brain
```

**Note:** `actions/setup-python@v5` и `astral-sh/setup-uv@v5` — актуальные стабильные версии на 2026-03-04. Если workflow находится в repo root `.openclaw/` (а не в `gym-coach-brain/`), `working-directory` указывает на поддиректорию.

---

### Library & Framework Requirements

**uv** (2026 Python standard toolchain):
- Версия: latest (устанавливается через `astral-sh/setup-uv@v5`)
- `uv sync --all-extras --dev` — устанавливает все зависимости включая dev группу
- `uv run pytest` — запускает pytest в изолированном окружении

**SQLAlchemy 2.0+:**
- Session pattern: `with Session(engine) as session:` (context manager)
- НЕ `session = Session(engine); ... ; session.close()` — запрещено
- Установка: `uv add sqlalchemy` (версия 2.0+ по умолчанию на 2026)

**Alembic:**
- Будет инициализирован в Story 3.2 (`alembic init alembic`)
- Story 3.1 только добавляет пакет в deps, не инициализирует

**loguru 0.7.3:**
- Версия: 0.7.3 (стабильная, указана в ADR)
- `uv add loguru` — установит latest (0.7.x)

**PyTorch 2.10.0:**
- `uv add torch` — установит latest stable
- ⚠️ Большой пакет (~2-3 GB), установка займёт время
- Lazy import rule: `import torch` ТОЛЬКО внутри методов `RPEModel`

**pydantic[yaml]:**
- Уже есть `pydantic>=2.0` и `pyyaml>=6.0.3` in deps
- `uv add "pydantic[yaml]"` обновит pyproject.toml чтобы явно указать optional extra
- uv обработает дедупликацию автоматически

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Core Architectural Decisions]

---

### Testing Requirements

**Стратегия тестирования для этой истории:**

История не добавляет новой бизнес-логики — только структуру. Тесты для exceptions.py **не требуются** в этой истории (они будут добавлены когда соответствующие модули используют exceptions).

**КРИТИЧНО:** Существующие 17 тестов `tests/test_core/test_science.py` должны ПРОХОДИТЬ после всех изменений. Добавление deps НЕ должно ломать тесты.

Верификационный чеклист (run в конце):
```bash
cd /home/ubuntu/.openclaw/gym-coach-brain
uv run pytest tests/ -v
# Expected: 17 passed, 0 failed
```

**Source:** [Source: _bmad-output/implementation-artifacts/1-3-fill-science-evidence.md#Testing Requirements]

---

### Previous Story Intelligence (Story 1.3)

**Ключевые выводы из последней завершённой истории (1-3-fill-science-evidence):**

1. **uv run работает корректно** — `uv run pytest tests/test_core/test_science.py -v` даёт 17 passed ✅
2. **science.py реализован полностью** — НЕ трогать в этой истории
3. **Тест `test_version_is_production_string`** проверяет `version == "1.0.0"` — не ломать при добавлении deps
4. **@model_validator в RecoveryConfig** — enforces hrv+sleep+stress==1.0 — это уже в коде
5. **Коммиты не делаются** в рамках story — git commit делается отдельно

**Source:** [Source: _bmad-output/implementation-artifacts/1-3-fill-science-evidence.md#Dev Agent Record]

---

### Git Intelligence

```
Последние 5 коммитов (из .openclaw repo):
0195177 feat: add bmad planning artifacts and expand gym-coach skill
8440199 feat: add gym coach skill
7bef692 chore: update current project state
bb07393 feat: add gym-coach skill (SQLite workout logging + onboarding)
1bcaa2a Merge pull request #27 (fix hardcoded operator token)
```

**Выводы:**
- `gym-coach-brain/` файлы staged (A) но не committed — всё ещё untracked пока нет коммита
- Dev agent НЕ делает git commit в рамках этой истории
- Новые файлы (exceptions.py, ci.yml, docs/.gitkeep) будут untracked — это нормально

---

### Project Structure Notes

**Конфликтов нет.** История добавляет НОВЫЕ файлы/директории, не изменяет существующие.

**Единственное исключение:** `pyproject.toml` и `uv.lock` будут обновлены через `uv add` — это ожидаемо.

**Важно для Epic 2 (блокируемый этой историей):**
- `docs/` создаётся пустой — Story 2.4 разместит здесь `ml-feature-spec.md`
- `data/__init__.py` создаётся пустым — Story 3.2 добавит `models.py`, `session.py`
- `exceptions.py` будет использоваться начиная со Story 3.2 (`from gym_coach_brain.exceptions import GymCoachError`)

**Source:** [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Story 3.1]

---

### References

- Story 3.1 требования: [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Story 3.1]
- Архитектурный ADR-003 (Migration Strategy): [Source: _bmad-output/planning-artifacts/architecture.md#ADR-003]
- Project directory structure: [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory Structure]
- Naming conventions: [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns]
- Exception hierarchy: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]
- Import rules: [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
- Epic ordering constraint (3.1→3.2→Epic2→3.3-3.5): [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Epic 3 intro]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_No issues encountered. All tasks completed cleanly._

### Completion Notes List

- Verified baseline: 18 tests passed before any changes (1 more than expected 17 — pre-existing test)
- Installed runtime deps via `uv add`: sqlalchemy==2.0.48, alembic==1.18.4, loguru==0.7.3, torch==2.10.0, pydantic[yaml] (updated from existing pydantic>=2.0)
- Dev deps (pytest, pytest-cov) already present — confirmed via `uv add --dev` (resolved in 2ms)
- Created 4 empty subpackages: data/, ml/, adaptation/, api/ — each with __init__.py only
- Created exceptions.py with exact hierarchy from architecture: GymCoachError (base) → ScienceLimitError, MLPredictionError, ConfigError
- Created gym-coach-brain/docs/.gitkeep and gym-coach-brain/docs/README.md
- Created .github/workflows/ci.yml at repo root — runs pytest with `working-directory: gym-coach-brain`
- Final verification: 18 passed, 0 failed; all imports OK; structure matches architecture spec
- Code Review Fixes: Added `permissions: contents: read` to `ci.yml` and documentation to `docs/README.md`.

### File List

gym-coach-brain/src/gym_coach_brain/data/__init__.py
gym-coach-brain/src/gym_coach_brain/ml/__init__.py
gym-coach-brain/src/gym_coach_brain/adaptation/__init__.py
gym-coach-brain/src/gym_coach_brain/api/__init__.py
gym-coach-brain/src/gym_coach_brain/exceptions.py
gym-coach-brain/docs/.gitkeep
gym-coach-brain/docs/README.md
gym-coach-brain/pyproject.toml (modified — deps added)
gym-coach-brain/uv.lock (modified — updated with new packages)
.github/workflows/ci.yml

## Change Log

- 2026-03-04: Completed Story 3.1 — project structure initialized. Added sqlalchemy/alembic/loguru/torch to deps; created data/, ml/, adaptation/, api/ subpackages; created exceptions.py with 4-class hierarchy; created docs/ README; created .github/workflows/ci.yml. All 18 tests pass.

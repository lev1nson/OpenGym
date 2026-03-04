---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
workflowType: architecture
lastStep: 8
status: complete
completedAt: '2026-03-02'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/project-context.md
  - _bmad-output/planning-artifacts/research/technical-ai-fitness-coaching-research-2026-03-02.md
  - _bmad-output/implementation-artifacts/tech-spec-gym-coach-bug-fixes.md
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture.md
  - docs/data-models.md
  - docs/api-contracts.md
  - docs/source-tree-analysis.md
  - docs/technology-stack.md
  - docs/development-guide.md
  - workspace/skills/gym-coach/ScienceEvidence.md
workflowType: 'architecture'
project_name: 'gym-coach-brain'
user_name: 'Max'
date: '2026-03-02'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
17 FRs в 5 capability-областях:
- Intelligence & ML (FR1-FR4): threshold-triggered incremental fine-tuning (не after-every-session),
  RPE prediction + Confidence Score, memory management, model versioning + Diff-анализ
- Planning & Safety (FR5-FR8): расчёт плана по SMH-метаданным, PUOS-блокировка (11 сетов/группу),
  Confidence-Based Fallback → Double Progression, Recap + Summary протокол
- Data & Operations (FR9-FR12): closed-loop онбординг, equipment profiles (JSON),
  async JSON API для OpenClaw, fractional volume analytics
- Onboarding & Mapping (FR13-FR14): маппинг ответов в числовые коэффициенты БД,
  детерминированные алгоритмы адаптации (LLM не интерпретирует параметры нагрузки)
- Communication Protocol (FR15-FR17): обязательный Recap перед тренировкой,
  Summary после, lifestyle-коэффициенты через readiness-лог

**Non-Functional Requirements:**
- Performance: нет жёсткого latency limit; async execution для тяжёлых ML-операций
- Scalability: baseline 16 ГБ RAM VPS, архитектурная поддержка масштабирования до 32 ГБ
- Reliability: атомарные транзакции SQLite; обязательный бэкап весов перед fine-tuning
- Privacy: Zero Cloud Leak — все вычисления и хранение строго локально

**Scale & Complexity:**
- Primary domain: Local AI/ML + Python backend + CLI
- Complexity level: Medium-High (N=1 архитектура, ML isolation, brownfield migration)
- Estimated architectural components: ~7 (NL Proxy, Deterministic Core, Adaptation Engine,
  ML Worker Process, ScienceConfig Loader, Explanation Layer, Data Layer)
- Scope: Single-athlete, single-VPS — освобождает от multi-tenancy и enterprise-complexity

### Technical Constraints & Dependencies

- Brownfield: существующий монолит gym_coach.py (2029 LOC) на raw sqlite3 без внешних deps —
  legacy-код, который можно просмотреть на предмет полезных алгоритмов или паттернов.
  Ничего не переносится автоматически — каждый элемент оценивается отдельно на предмет ценности.
- Новые обязательные зависимости: PyTorch, SQLAlchemy 2.0+, Alembic, Pydantic 2.0+, pytest
- Инфраструктура: одиночный VPS 16-32 ГБ RAM, локальная ФС для хранения весов модели
- OpenClaw integration: контракт {intent, argv, stdout, exit_code} является invariant
  на всё время миграции — интерфейс router.py → gym_coach.py не меняется
- ScienceEvidence.md: стабильный свод правил с редкими изменениями.
  Формат: YAML-frontmatter (структурированные данные: лимиты, коэффициенты, version)
  + markdown-body (научные обоснования для человека).
  Парсится при старте в типизированный объект ScienceConfig (Pydantic).
  version field логируется в adaptation_decisions.science_version для полной трассируемости.

### Architectural Decisions (ADR)

**ADR-001: ML Layer Isolation**
Решение: ML-воркер как изолированный процесс (multiprocessing) с контролируемым memory budget.
Rationale: падение PyTorch не роняет основное ядро; изолированный memory budget предотвращает OOM;
расширяет архитектуру без изменений детерминированного ядра.

**ADR-002: ScienceConfig Loading**
Решение: parse-at-startup → ScienceConfig (Pydantic) с version field.
Rationale: O(1) доступ в runtime; строгая типизация исключает магические числа в коде;
версионирование обеспечивает трассируемость каждого решения адаптации.
Обновление методологии = деплой новой версии файла + restart.

**ADR-003: Migration Strategy**
Решение: Модульная переработка с сохранением внешнего контракта.
Rationale: gym_coach.py — монолит, архитектурно непригодный для ML-расширения и модульного тестирования.
Код переписывается как набор независимых модулей. Единственный invariant — внешний JSON-контракт
с OpenClaw {intent, argv, stdout, exit_code}.

Порядок:
(1) Зафиксировать полное поведение существующего кода через pytest (контракт-тесты)
(2) Alembic init на существующей схеме БД (данные мигрируют, не теряются)
(3) Переписать модули независимо: core/, adaptation/, ml/, data/, api/
(4) Каждый модуль заменяет соответствующую часть монолита при готовности
(5) gym_coach.py удаляется когда все модули покрыты тестами и работают в продакшне

Отношение к gym_coach.py: legacy-код, который можно просмотреть на предмет
полезных алгоритмов или паттернов. Ничего не переносится автоматически —
каждый элемент оценивается отдельно на предмет ценности.

### Cross-Cutting Concerns

1. **Science-over-AI priority**: ScienceConfig лимиты всегда > ML-выводы (hardcoded в Adaptation Engine)
2. **Determinism boundary**: чёткая граница между детерминированным ядром и ML-персонализацией
3. **Brownfield invariant**: контракт router.py → gym_coach.py неизменен до завершения миграции
4. **Threshold-triggered fine-tuning**: ML-воркер проверяет порог накопленных данных перед обучением,
   не запускает fine-tuning после каждой сессии
5. **Fine-tuning вне критического пути**: training_job → очередь → ответ агенту немедленно →
   fine-tuning async в фоне
6. **ML process isolation**: отдельный процесс с memory budget; stability + memory isolation
7. **Incremental learning safety**: EWC (готовая PyTorch lib) против catastrophic forgetting
8. **Schema evolution**: Alembic init на существующей БД как первый шаг миграции
9. **Explanation layer**: отдельный слой между Adaptation Engine и OpenClaw Agent;
   каждое решение сопровождается нарративом со ссылкой на ScienceConfig.version
10. **Recovery signal abstraction**: RecoverySignal интерфейс (не хардкод RPE) —
    готов к расширению на HRV/sleep в Phase 2

## Starter Template Evaluation

### Primary Technology Domain

Python Application — CLI tool + Local ML backend.
No web framework, no frontend, no cloud deployment.

### Starter Options Considered

- cookiecutter-pytorch-ml: ML-focused but data-science oriented, no SQLAlchemy/CLI fit
- uv init --app (flat): Too minimal for planned multi-module decomposition
- uv init --package (src layout): Selected — proper isolation for modular architecture

### Selected Starter: uv init --package (src layout)

**Rationale for Selection:**
Planned module decomposition (core/, adaptation/, ml/, data/, api/) requires src layout
for correct import isolation during testing. uv is the 2026 Python toolchain standard —
replaces pip, venv, pipx, pyenv in a single tool with lockfile reproducibility.

**Initialization Command:**

```bash
uv init --package gym-coach-brain
cd gym-coach-brain
uv add sqlalchemy alembic pydantic torch
uv add --dev pytest pytest-cov
```

**Architectural Decisions Provided by Starter:**

- Language & Runtime: Python 3.14+, pyproject.toml as single source of truth
- Dependency Management: uv lockfile — reproducible environments across dev/prod VPS
- Project Layout: src/gym_coach_brain/ — import isolation, no accidental namespace conflicts
- Build System: hatchling (default uv backend)
- Testing: pytest (added manually), isolated from src via package install

**Custom Directory Structure (post-init):**

```
src/gym_coach_brain/
├── core/          # Deterministic engine (PUOS, Double Progression, APRE)
├── adaptation/    # Adaptation Engine + Explanation Layer
├── ml/            # ML Worker process (PyTorch, EWC, fine-tuning queue)
├── data/          # SQLAlchemy models, Alembic migrations, ScienceConfig loader
├── api/           # OpenClaw JSON contract (replaces router.py interface)
└── __init__.py
```

**Note:** Project initialization using this command is the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (блокируют реализацию):**
- ML model architecture: PyTorch MLP + MC Dropout Confidence Score
- Training job queue: SQLite-backed ml_jobs table (persistence across restarts)
- ML worker lifecycle: systemd daemon
- Fine-tuning trigger: threshold-based (configurable N sessions, default N=5)

**Important Decisions (формируют архитектуру):**
- EWC: custom implementation (~50 LOC, no Avalanche dependency)
- Logging: loguru 0.7.3
- ML Worker job types: FINE_TUNE (heavy, threshold-triggered) + PREDICT (light, per-session)

**Deferred Decisions (Post-MVP):**
- Fine-tuning threshold tuning (N=5 default, calibrated после накопления данных)
- HRV/wearable integration (RecoverySignal abstraction готова, Phase 2)
- Model versioning storage structure (filesystem layout, Phase 2)

### ML Architecture

**Model: PyTorch MLP**
- Version: PyTorch 2.10.0
- Architecture: 2-3 fully-connected layers, ~few hundred parameters
- Input features: exercise_id, set_number, weight, reps, historical_rpe, readiness_score,
  days_since_last_session, muscle_group_fatigue_estimate
- Output: predicted_rpe (float), confidence_score (float 0–1)
- Rationale: минимальная архитектура для N=1 dataset; быстрый convergence;
  совместима с EWC; interpretable

**Confidence Score: Monte Carlo Dropout**
- Mechanism: N forward passes с включённым dropout в inference mode, σ outputs = uncertainty
- Low confidence → fallback to Double Progression (детерминированное ядро)
- Threshold: confidence < 0.6 → ignore ML prediction, use deterministic core
- Rationale: нет необходимости в ensemble; нет дополнительных параметров; trivial to implement

**EWC: Custom Implementation**
- ~50 LOC поверх стандартного PyTorch optimizer
- Fisher Information Matrix рассчитывается после каждого fine-tuning цикла
- Rationale: zero additional dependencies; полный контроль; достаточно для одной задачи

**Fine-tuning Trigger: Threshold-Based**
- Default: N=5 завершённых тренировочных сессий
- Configurable: параметр в user_profile или системном конфиге
- Logic: ML Worker polling ml_jobs → count unprocessed PREDICT sessions → если ≥ N → queue FINE_TUNE
- Rationale: одна сессия = шум; 5 сессий ≈ 1-2 недели данных = достаточный signal

### ML Job Queue & Communication Contract

**ml_jobs table:**
```sql
CREATE TABLE ml_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,         -- 'FINE_TUNE' | 'PREDICT'
    status TEXT DEFAULT 'pending',  -- pending / processing / done / failed
    session_ids TEXT NOT NULL,      -- JSON array of session IDs
    created_at TEXT NOT NULL,
    processed_at TEXT
);
```

**rpe_predictions table (ML Worker → Adaptation Engine contract):**
```sql
CREATE TABLE rpe_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES workout_sessions(id),
    exercise_id INTEGER NOT NULL,
    predicted_rpe REAL NOT NULL,
    confidence_score REAL NOT NULL,
    model_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

- PREDICT jobs: создаются при старте сессии, лёгкие, выполняются быстро
- FINE_TUNE jobs: threshold-triggered, тяжёлые, выполняются в фоне
- session_id binding вместо TTL — предсказание валидно только для текущей сессии
- Rationale: конкретный типизированный контракт; zero ambiguity между модулями

### ML Worker Process Lifecycle

**Pattern: systemd Daemon**
- ML Worker запускается как systemd service при старте VPS
- Постоянно читает ml_jobs queue (polling loop, interval: 60s configurable)
- Изолированный memory budget через systemd MemoryLimit=
- Автоматический restart при падении (Restart=on-failure)
- Оба job-типа (PREDICT + FINE_TUNE) обрабатываются одним воркером с приоритизацией:
  PREDICT > FINE_TUNE (быстрый ответ важнее обучения)
- Rationale: VPS всегда работает; systemd даёт memory isolation и supervision бесплатно

### Infrastructure & Observability

**Logging: loguru 0.7.3**
- Structured JSON logs для ML Worker (machine-parseable)
- Human-friendly logs для core/adaptation (developer experience)
- Log rotation: встроенный loguru rotation по размеру файла
- Rationale: minimal deps; excellent DX; достаточно для single-user N=1 системы

**Deployment:**
- Single VPS (16-32 ГБ RAM)
- systemd services: gym-coach-brain-core + gym-coach-brain-ml-worker
- No containerization (overhead не оправдан для single-user)
- CI: GitHub Actions для тестов (pytest)

### Decision Impact Analysis

**Implementation Sequence:**
1. uv init --package + базовая структура проекта
2. SQLAlchemy models + Alembic init на существующей схеме
3. ScienceConfig loader (Pydantic + YAML parser)
4. Deterministic Core (APRE, Double Progression, PUOS)
5. ml_jobs + rpe_predictions tables (schema migration)
6. ML Worker daemon skeleton — оба job-типа (PREDICT + FINE_TUNE) + systemd unit
7. PyTorch MLP + MC Dropout + Custom EWC
8. Adaptation Engine + Explanation Layer
9. API module (JSON contract с OpenClaw)
10. Постепенная замена gym_coach.py модуль за модулем

**Cross-Component Dependencies:**
- ScienceConfig → Deterministic Core (лимиты PUOS, коэффициенты прогрессии)
- Deterministic Core → Adaptation Engine (fallback при confidence < 0.6)
- ml_jobs table → ML Worker (единственный канал команд)
- rpe_predictions table → Adaptation Engine (предсказания per session_id)
- Explanation Layer → ScienceConfig.version (трассируемость каждого решения)
- workout_sessions → ml_jobs PREDICT (при создании сессии → PREDICT job)

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

7 зон где AI-агенты без явных правил сделают несовместимые выборы:
naming (DB/code), module imports, SQLAlchemy session lifecycle,
error propagation, JSON contract format, datetime handling, ML status enums.

### Naming Patterns

**Database Naming (SQLAlchemy + Alembic):**
- Tables: `snake_case` plural — `workout_sessions`, `ml_jobs`, `rpe_predictions`
- Columns: `snake_case` — `session_id`, `created_at`, `confidence_score`
- SQLAlchemy models: `PascalCase` singular — `class WorkoutSession(Base)`
- Foreign keys: `{table_singular}_id` — `session_id`, `exercise_id`
- Indexes: `ix_{table}_{column}` — `ix_ml_jobs_status`
- Alembic revision message: imperative verb — `add_ml_jobs_table`, `add_rpe_predictions`

**Code Naming (Python):**
- Files/modules: `snake_case` — `science_config.py`, `adaptation_engine.py`
- Classes: `PascalCase` — `ScienceConfig`, `AdaptationEngine`, `MLWorker`
- Functions/methods: `snake_case` — `predict_rpe()`, `trigger_fine_tuning()`
- Constants: `UPPER_SNAKE_CASE` — `DEFAULT_FINE_TUNE_THRESHOLD = 5`
- Pydantic models (DTOs): `PascalCase` + `Schema` suffix — `RPEPredictionSchema`
- SQLAlchemy models (ORM): `PascalCase` без suffix — `MLJob`, `RPEPrediction`

**ML-specific Naming:**
- Job types: string enum uppercase — `"FINE_TUNE"`, `"PREDICT"`
- Job statuses: string enum lowercase — `"pending"`, `"processing"`, `"done"`, `"failed"`
- Model weights files: `model_v{version}.pt` — `model_v1.pt`, `model_v2.pt`
- Confidence threshold constant: `CONFIDENCE_THRESHOLD = 0.6` в `ml/constants.py`

### Structure Patterns

**Project Organization:**
```
src/gym_coach_brain/
├── core/               # Deterministic engine — APRE, Double Progression, PUOS
│   └── science.py      # ScienceConfig loader
├── adaptation/         # Adaptation Engine + Explanation Layer
├── ml/                 # MLWorker, RPEModel (PyTorch), EWC, constants
│   └── constants.py    # CONFIDENCE_THRESHOLD, DEFAULT_FINE_TUNE_THRESHOLD
├── data/               # SQLAlchemy models, session factory
│   └── models.py       # ALL SQLAlchemy models в одном файле
├── api/                # OpenClaw JSON contract handler (Composition Root)
└── __init__.py

tests/                  # Все тесты в project root/tests/
├── conftest.py         # Shared fixtures: in-memory DB, mock ScienceConfig
├── test_core/
├── test_adaptation/
├── test_ml/
├── test_data/
└── test_api/

alembic/                # Alembic migrations в project root
ScienceEvidence.md      # В project root
```

**Import Rules:**
- ONLY absolute imports: `from gym_coach_brain.data.models import MLJob`
- НЕ relative imports: `from ..data.models import MLJob` — запрещено
- Dependency direction: `api → adaptation → core → data` (data не импортирует выше)
- НЕ circular imports между модулями

**Composition Root (ScienceConfig):**
- `ScienceConfig` создаётся ONE TIME per process при старте
- `api/` entry point создаёт экземпляр и пробрасывает в каждую функцию
- `ml_worker` создаёт свой независимый экземпляр при старте (два процесса = два экземпляра)
- НЕ global singleton: `SCIENCE = load_science_config()` — запрещено (нельзя мокировать)
- Все internal functions принимают `science: ScienceConfig` как параметр

**Lazy PyTorch Import:**
- `import torch` ТОЛЬКО внутри функций класса `RPEModel`, не на уровне модуля
- `MLWorker` (queue polling, job dispatch) не импортирует torch напрямую
- Позволяет тестировать `MLWorker` без GPU и без загрузки PyTorch

**Class Separation in ML module:**
- `class MLWorker` — queue polling, job dispatch, status updates (testable без PyTorch)
- `class RPEModel` — PyTorch MLP, MC Dropout, EWC (мокируется в тестах MLWorker)

### Format Patterns

**OpenClaw JSON Contract (invariant — НЕ изменять без обновления SKILL.md):**
```json
{"intent": "workout_start", "argv": ["workout", "start"], "stdout": "...", "exit_code": 0}
```
- `stdout` всегда string (никогда dict/list напрямую)
- `exit_code`: 0 = success, 1 = user error, 2 = system error

**Internal Error Propagation:**
```python
class GymCoachError(Exception): pass
class ScienceLimitError(GymCoachError): pass   # PUOS/Safety violations
class MLPredictionError(GymCoachError): pass    # ML Worker failures
class ConfigError(GymCoachError): pass          # ScienceConfig parse errors
```
- Internal modules бросают typed exceptions — НЕ возвращают `{"error": "..."}`
- `api/` — единственный слой конвертирующий exceptions в exit_code

**DateTime Format:**
- В SQLite: ISO 8601 UTC strings — `"2026-03-02T14:30:00"`
- Write: `datetime.utcnow().isoformat()`
- Read: `datetime.fromisoformat(value)`
- НЕ unix timestamps, НЕ `datetime.now()` (localtime risk)

**SQLAlchemy Session Pattern:**
```python
# ПРАВИЛЬНО
with Session(engine) as session:
    session.add(job)
    session.commit()

# ЗАПРЕЩЕНО — ручной close() без context manager
```

**Alembic Single Source of Truth:**
- SQLAlchemy models = единственный источник истины схемы
- Alembic: ТОЛЬКО `--autogenerate` — никогда manual SQL в миграциях
- Добавить колонку в модель → сразу `alembic revision --autogenerate`
- Тесты используют `Base.metadata.create_all(engine)` (быстро, без миграций)

### Communication Patterns

**ML Worker ↔ Core: только через DB tables**
- ml_jobs: команды для ML Worker
- rpe_predictions: результаты для Adaptation Engine
- НЕ shared memory, pipes, или direct function calls между процессами

**Logging Levels (loguru):**
- `DEBUG`: internal ML computations, weight updates, Fisher matrix calculations
- `INFO`: job lifecycle (started/completed), session events, adaptation decisions
- `WARNING`: confidence fallback triggered, PUOS limit approached (≥9 sets), stale prediction
- `ERROR`: job failed, unhandled exception caught, ScienceConfig parse failure

```python
# ML Worker: structured с контекстом
logger.bind(job_id=job.id, job_type=job.job_type).info("Job completed")

# Core: human-friendly
logger.warning("PUOS limit approached: {sets}/11 sets for {muscle}", sets=9, muscle="chest")

# НЕ: print(), НЕ: logger.error() без job_id/session_id контекста
```

### Process Patterns

**Error Handling per Layer:**
- Deterministic Core: `ScienceLimitError` при нарушении PUOS — НИКОГДА не игнорировать
- ML Worker: любая ошибка → `status='failed'` → log ERROR → продолжить polling
- Adaptation Engine: `confidence < 0.6` или `MLPredictionError` → fallback Double Progression
  (НЕ exception — это штатный режим)
- api/: единственное место конвертации exceptions → exit_code + stdout message

**Test Fixtures (conftest.py):**
```python
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture
def mock_science_config():
    return ScienceConfig(version="test-1.0", puos=PUOSConfig(max_sets_per_group=11))

@pytest.fixture
def mock_rpe_model():
    model = Mock(spec=RPEModel)
    model.predict.return_value = (7.5, 0.85)  # (rpe, confidence)
    return model
```
- НЕ реальный SQLite файл в тестах — только `:memory:`
- НЕ реальный `ScienceEvidence.md` — только `mock_science_config`
- НЕ реальный PyTorch в unit-тестах MLWorker — только `mock_rpe_model`

### Enforcement Summary

**All AI Agents MUST:**
- Absolute imports only (`from gym_coach_brain.x.y import Z`)
- Context manager для всех SQLAlchemy sessions
- `ScienceConfig` как параметр, создаётся один раз при старте процесса
- Typed exceptions из internal modules (не error dicts)
- `datetime.utcnow().isoformat()` для всех timestamp записей
- `import torch` только внутри методов `RPEModel`
- log level соответствует типу события (DEBUG/INFO/WARNING/ERROR схема выше)
- НЕ изменять OpenClaw JSON contract без обновления SKILL.md

## Project Structure & Boundaries

### Complete Project Directory Structure

```
gym-coach-brain/
├── pyproject.toml                  # uv project config, all dependencies
├── uv.lock                         # Lockfile — committed to git
├── README.md
├── ScienceEvidence.md              # Scientific methodology rulebook (YAML frontmatter + markdown)
├── .python-version                 # Python 3.14
├── .github/
│   └── workflows/
│       └── ci.yml                  # pytest on push/PR
├── alembic/
│   ├── env.py                      # SQLAlchemy Base import + engine config
│   ├── alembic.ini                 # DB URL via env var
│   └── versions/
│       ├── 001_initial_schema.py   # Snapshot of existing gym_coach.sqlite schema
│       ├── 002_add_ml_jobs.py      # ml_jobs + rpe_predictions tables
│       └── ...
├── systemd/
│   ├── gym-coach-brain.service     # Main API process (systemd unit)
│   └── gym-coach-brain-ml.service  # ML Worker daemon (systemd unit)
├── src/
│   └── gym_coach_brain/
│       ├── __init__.py
│       ├── exceptions.py           # GymCoachError, ScienceLimitError, MLPredictionError, ConfigError
│       │
│       ├── data/                   # Data Layer — SQLAlchemy models + DB factory
│       │   ├── __init__.py
│       │   ├── models.py           # ALL SQLAlchemy models (single source of truth)
│       │   ├── session.py          # engine + Session factory
│       │   └── queue.py            # ml_jobs CRUD helpers
│       │
│       ├── core/                   # Deterministic Engine
│       │   ├── __init__.py
│       │   ├── science.py          # ScienceConfig Pydantic model + YAML loader
│       │   ├── apre.py             # APRE algorithm (pure functions, no DB)
│       │   ├── progression.py      # Double Progression algorithm
│       │   ├── puos.py             # PUOS limits validator + fractional volume
│       │   ├── onboarding.py       # FR9/FR13/FR14: closed-loop onboarding → coefficients
│       │   └── readiness.py        # FR17: lifestyle coefficients from readiness log
│       │
│       ├── adaptation/             # Adaptation Engine + Explanation Layer
│       │   ├── __init__.py
│       │   ├── engine.py           # AdaptationEngine: ML prediction → deterministic fallback
│       │   ├── explanation.py      # Explanation Layer: decision → human narrative + ScienceConfig.version
│       │   ├── recap.py            # FR15: pre-workout Recap generator
│       │   └── summary.py          # FR16: post-workout Summary generator
│       │
│       ├── ml/                     # ML Worker Process
│       │   ├── __init__.py
│       │   ├── constants.py        # CONFIDENCE_THRESHOLD=0.6, DEFAULT_FINE_TUNE_THRESHOLD=5
│       │   ├── worker.py           # MLWorker: polling loop, job dispatch (no torch import)
│       │   ├── model.py            # RPEModel: PyTorch MLP + MC Dropout (lazy torch import)
│       │   ├── ewc.py              # Custom EWC ~50 LOC
│       │   └── __main__.py         # ML Worker entry point (python -m gym_coach_brain.ml)
│       │
│       └── api/                    # OpenClaw JSON Contract + Composition Root
│           ├── __init__.py
│           ├── main.py             # Entry point: creates ScienceConfig, routes intent → handler
│           ├── handlers.py         # One handler per intent group (workout, program, adapt, etc.)
│           └── contract.py         # JSON response builder {intent, argv, stdout, exit_code}
│
└── tests/
    ├── conftest.py                 # db_session, mock_science_config, mock_rpe_model fixtures
    ├── test_core/
    │   ├── test_science.py         # ScienceConfig parsing, YAML frontmatter
    │   ├── test_apre.py            # APRE algorithm correctness
    │   ├── test_progression.py     # Double Progression edge cases
    │   ├── test_puos.py            # PUOS limit enforcement (ScienceLimitError)
    │   └── test_onboarding.py      # Coefficient mapping from onboarding answers
    ├── test_adaptation/
    │   ├── test_engine.py          # Confidence fallback logic, ScienceLimitError propagation
    │   ├── test_explanation.py     # Narrative generation, ScienceConfig.version references
    │   ├── test_recap.py           # Recap format validation
    │   └── test_summary.py         # Summary format validation
    ├── test_ml/
    │   ├── test_worker.py          # Queue polling, job dispatch (mock_rpe_model fixture)
    │   ├── test_model.py           # RPEModel forward pass, MC Dropout variance (requires torch)
    │   └── test_ewc.py             # Fisher matrix calculation, weight regularization
    ├── test_data/
    │   ├── test_models.py          # SQLAlchemy model constraints, FK integrity
    │   └── test_queue.py           # ml_jobs CRUD, status transitions
    └── test_api/
        ├── test_contract.py        # JSON contract format, exit_code mapping
        └── test_handlers.py        # Intent routing, exception → exit_code conversion
```

### Architectural Boundaries

**Process Boundaries:**
```
Process 1: gym-coach-brain (systemd)
  Entry: src/gym_coach_brain/api/main.py
  Reads: OpenClaw stdin (via router.py --text)
  Writes: stdout JSON
  DB access: READ workout_sessions, program_*, user_profile
             WRITE ml_jobs (PREDICT request), reads rpe_predictions

Process 2: gym-coach-brain-ml (systemd daemon)
  Entry: src/gym_coach_brain/ml/__main__.py
  Reads: ml_jobs WHERE status='pending'
  Writes: ml_jobs (status update), rpe_predictions (PREDICT result), model_v*.pt (FINE_TUNE)
  Memory: bounded via systemd MemoryLimit=8G (configurable)
```

**Data Flow: Тренировочная сессия**
```
OpenClaw → router.py (existing, unchanged) → api/main.py
  → core/puos.py (validate limits via ScienceConfig)
  → data/queue.py (INSERT ml_jobs PREDICT for session_id)
  → [async] ml/worker.py reads PREDICT job → model.py inference → rpe_predictions INSERT
  → adaptation/engine.py reads rpe_predictions for session_id
      → confidence ≥ 0.6: use ML prediction
      → confidence < 0.6: core/progression.py Double Progression
  → adaptation/explanation.py generates narrative (ScienceConfig.version reference)
  → adaptation/recap.py or summary.py
  → api/contract.py builds JSON response
  → stdout → OpenClaw agent → Telegram
```

**Data Flow: Fine-tuning**
```
workout_sessions completed (N=5 threshold reached)
  → data/queue.py INSERT ml_jobs FINE_TUNE
  → [daemon] ml/worker.py picks up FINE_TUNE job
  → ml/model.py load weights → train batch → ml/ewc.py update Fisher matrix
  → save model_v{n+1}.pt → ml_jobs status='done'
```

### Requirements to Structure Mapping

| FR | File |
|---|---|
| FR1: incremental fine-tuning | `ml/worker.py`, `ml/model.py`, `ml/ewc.py` |
| FR2: RPE prediction + Confidence Score | `ml/model.py` (MC Dropout) |
| FR3: memory management | `systemd/gym-coach-brain-ml.service` (MemoryLimit) |
| FR4: model versioning + Diff | `ml/worker.py`, `ml/model.py` |
| FR5: training plan calculation | `core/apre.py`, `core/progression.py` |
| FR6: PUOS limit blocking | `core/puos.py` → raises `ScienceLimitError` |
| FR7: Confidence-Based Fallback | `adaptation/engine.py` |
| FR8: adaptation justification | `adaptation/explanation.py` |
| FR9: interactive onboarding | `core/onboarding.py` |
| FR10: equipment profiles | `data/models.py` (user_profile table) |
| FR11: async JSON API для OpenClaw | `api/main.py`, `api/contract.py` |
| FR12: fractional volume analytics | `core/puos.py` |
| FR13-FR14: coefficient mapping | `core/onboarding.py` |
| FR15: pre-workout Recap | `adaptation/recap.py` |
| FR16: post-workout Summary | `adaptation/summary.py` |
| FR17: lifestyle coefficients | `core/readiness.py` |

### Integration Points

**External:**
- `router.py` (existing, unchanged) → `api/main.py` via subprocess stdout
- `ScienceEvidence.md` → `core/science.py` (parse at startup)
- `gym_coach.sqlite` → `data/session.py` (SQLAlchemy engine)
- `model_v*.pt` files → `ml/model.py` (PyTorch load/save)

**Internal (DB-mediated between processes):**
- `api/` → `data/queue.py` → `ml_jobs` table → `ml/worker.py`
- `ml/worker.py` → `rpe_predictions` table → `adaptation/engine.py`

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
- Python 3.14 + PyTorch 2.10.0 + SQLAlchemy 2.0 + Alembic + Pydantic 2.0 + loguru 0.7.3 —
  все зависимости совместимы, управляются через uv lockfile
- SQLite WAL mode поддерживает concurrent reads между двумя процессами (api + ml worker) ✅
- multiprocessing (stdlib) + SQLite-backed queue — zero external deps для IPC ✅
- systemd MemoryLimit изолирует PyTorch процесс без накладных расходов контейнеризации ✅

**Pattern Consistency:**
- snake_case везде в коде, PascalCase для классов — согласованно во всех модулях ✅
- Absolute imports + src layout — взаимно усиливают друг друга ✅
- Context manager для SQLAlchemy 2.0+ — соответствует официальному API ✅
- Lazy `import torch` согласован с MLWorker/RPEModel разделением ✅
- Composition Root в api/main.py согласован с ScienceConfig injection pattern ✅

**Structure Alignment:**
- src layout поддерживает planned modular decomposition (5 модулей) ✅
- tests/ в project root поддерживает absolute import testing ✅
- alembic/ в project root — стандарт для SQLAlchemy проектов ✅

### Requirements Coverage Validation ✅

**Functional Requirements (17/17 покрыты):**

| Статус | FR | Файл |
|---|---|---|
| ✅ | FR1: fine-tuning | ml/worker.py, ml/model.py, ml/ewc.py |
| ✅ | FR2: RPE + Confidence | ml/model.py (MC Dropout) |
| ✅ | FR3: memory management | systemd MemoryLimit |
| ✅ | FR4: model versioning | ml/worker.py, ml/model.py |
| ✅ | FR5: training plan | core/apre.py, core/progression.py |
| ✅ | FR6: PUOS blocking | core/puos.py → ScienceLimitError |
| ✅ | FR7: fallback | adaptation/engine.py |
| ✅ | FR8: justification | adaptation/explanation.py |
| ✅ | FR9: onboarding | core/onboarding.py |
| ✅ | FR10: equipment profiles | data/models.py |
| ✅ | FR11: JSON API | api/main.py, api/contract.py |
| ✅ | FR12: fractional volume | core/puos.py |
| ✅ | FR13-FR14: coefficients | core/onboarding.py |
| ✅ | FR15: Recap | adaptation/recap.py |
| ✅ | FR16: Summary | adaptation/summary.py |
| ✅ | FR17: lifestyle coefficients | core/readiness.py |

**Non-Functional Requirements:**
- Performance: ML вне критического пути (queue + daemon) ✅; no hard latency limit ✅
- Scalability: systemd MemoryLimit, 16-32 GB VPS baseline ✅
- Reliability: SQLite atomic transactions ✅; model_v*.pt backup перед fine-tuning ✅
- Privacy: все вычисления локально, zero cloud calls ✅

### Implementation Readiness Validation ✅

**Decision Completeness:**
- 3 ADR с rationale и версиями ✅
- PyTorch 2.10.0, loguru 0.7.3 — verified versions ✅
- CONFIDENCE_THRESHOLD, DEFAULT_FINE_TUNE_THRESHOLD — explicit constants в ml/constants.py ✅

**Structure Completeness:**
- Полный file tree с именами всех 22 source файлов ✅
- FR → file mapping для всех 17 FRs ✅
- Process boundaries и data flows задокументированы ✅
- Integration points (external + internal) определены ✅

**Pattern Completeness:**
- Naming: DB, code, ML-specific — все категории покрыты ✅
- Error handling: per-layer с конкретными exception типами ✅
- Test fixtures: 3 обязательных фикстуры с примерами кода ✅
- Logging levels: 4-уровневая схема с примерами ✅
- Anti-patterns: явный список запрещённых паттернов ✅
- TDD: покрывается project-context.md (не дублируется в архитектуре) ✅

### Gap Analysis Results

**Critical Gaps:** отсутствуют

**Important Gaps (адресовать в первых stories):**

1. **ScienceEvidence.md YAML schema не определена**
   AI-агенты не знают какие поля создавать в YAML-frontmatter.
   Suggested resolution: добавить skeleton ScienceEvidence.md с version, puos,
   progression секциями до реализации core/science.py.

2. **Model backup strategy не специфицирована**
   NFR требует "backup весов перед fine-tuning", механизм не описан.
   Suggested: `model_v{n}.pt` → `model_v{n}.backup.pt` в той же директории (atomic).

3. **DB path конфигурация**
   Alembic env.py нужна строка подключения.
   Suggested: `DATABASE_URL` env var с дефолтом `sqlite:///gym_coach.sqlite`.

**Nice-to-Have Gaps:**
- Содержимое `.github/workflows/ci.yml`
- Содержимое systemd unit файлов (MemoryLimit значение)

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed (8 assumptions tested, 2 refined)
- [x] Scale and complexity assessed (Medium-High, N=1, single-VPS)
- [x] Technical constraints identified (brownfield, privacy, stdlib-first)
- [x] Cross-cutting concerns mapped (10 concerns documented)

**✅ Architectural Decisions**
- [x] 3 ADR с explicit rationale
- [x] Technology stack fully specified with verified versions
- [x] ML architecture defined (MLP + MC Dropout + Custom EWC)
- [x] Integration patterns defined (ml_jobs + rpe_predictions contract)

**✅ Implementation Patterns**
- [x] Naming conventions (DB, code, ML-specific)
- [x] Structure patterns (imports, Composition Root, lazy torch)
- [x] Communication patterns (logging levels, error propagation)
- [x] Process patterns (SQLAlchemy sessions, test fixtures, anti-patterns)

**✅ Project Structure**
- [x] Complete directory structure (22 source files defined)
- [x] Component boundaries (2 systemd processes)
- [x] Integration points mapped (external + DB-mediated internal)
- [x] FR → file mapping (17/17 FRs)

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**
**Confidence Level: HIGH**

**Key Strengths:**
- Детерминированное ядро полностью изолировано от ML — система стабильна без обученной модели
- Все границы между компонентами проведены через типизированные DB контракты — нет tight coupling
- Brownfield migration риск минимизирован — внешний JSON контракт с OpenClaw invariant
- ScienceConfig injection + typed exceptions делают каждый модуль независимо тестируемым

**Areas for Future Enhancement:**
- ScienceEvidence.md content development (Phase 1 blocker для полного использования)
- HRV/wearable integration через RecoverySignal abstraction (Phase 2)
- Model Diff-анализ UI (FR4, Phase 2)

### Implementation Handoff

**First Implementation Priority:**
```bash
uv init --package gym-coach-brain
cd gym-coach-brain
uv add sqlalchemy alembic "pydantic[yaml]" loguru torch
uv add --dev pytest pytest-cov
```
Затем: exceptions.py → data/models.py → Alembic init → ScienceEvidence.md skeleton → core/science.py

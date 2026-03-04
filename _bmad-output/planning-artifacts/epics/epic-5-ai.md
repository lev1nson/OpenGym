# Epic 5: AI-персонализация нагрузок

Нагрузки точно подстраиваются под физиологию конкретного атлета — система обучается на его данных, предсказывает RPE с автоматическим fallback, весовые файлы версионируются.

**Requires:** Epic 4 (завершён)
**FRs covered:** FR1, FR2, FR3, FR4 (версионирование), FR7
**Note:** FR4 Diff-анализ (model_report интент) — Phase 2, не в MVP

## Story 5.1: ML Data Layer — очередь заданий

As a dev agent,
I want to implement the ML job queue tables and CRUD helpers,
So that the main process and ML worker can communicate exclusively through the database.

**Acceptance Criteria:**

**Given** Data Layer из Story 3.2 готов (модели `MLJob` и `RPEPrediction` уже определены в `data/models.py` и присутствуют в initial Alembic migration)
**When** агент реализует модуль `data/queue.py`
**Then** `data/queue.py` реализует: `enqueue_predict(session_id)`, `enqueue_fine_tune(session_ids)`, `get_pending_jobs()`, `update_job_status(job_id, status)`
**And** `data/queue.py` НЕ импортирует ничего из `gym_coach_brain.ml.*` — изоляция от PyTorch обязательна
**And** все функции используют SQLAlchemy context manager (`with Session(engine) as session`)
**And** `enqueue_predict` создаёт `MLJob` с `job_type="PREDICT"`, `status="pending"`
**And** `enqueue_fine_tune` создаёт `MLJob` с `job_type="FINE_TUNE"`, `status="pending"`, `session_ids` как JSON array
**And** `get_pending_jobs()` возвращает PREDICT-задания с приоритетом над FINE_TUNE
**And** `data/models.py` содержит индекс `Index('ix_mljob_status_type', MLJob.status, MLJob.job_type)` для оптимизации `get_pending_jobs()` queries
**And** `pytest tests/test_data/test_queue.py` проходит без PyTorch: все CRUD операции, статусные переходы (pending→processing→done/failed)

## Story 5.2: RPEModel — PyTorch MLP + MC Dropout + EWC

As a dev agent,
I want to implement the RPE prediction model with uncertainty estimation and catastrophic forgetting prevention,
So that the system can personalize training loads while protecting previously learned patterns.

**Acceptance Criteria:**

**Given** ML Data Layer из Story 5.1 готов и `data/validate_features` проходит (Story 2.4)
**When** агент реализует `ml/model.py` и `ml/ewc.py`
**Then** `class RPEModel` реализует: `forward(features) -> (predicted_rpe, confidence_score)` через MC Dropout (N=20 passes)
**And** `confidence_score < 0.6` → fallback флаг для Adaptation Engine
**And** `import torch` ТОЛЬКО внутри методов `RPEModel`, не на уровне модуля
**And** `class EWC` реализует Fisher Information Matrix расчёт (~50 LOC) без внешних зависимостей
**And** `model_v{n}.pt` сохраняется в `MODEL_DIR` после каждого fine-tuning, `model_v{n}.backup.pt` создаётся перед обучением
**And** feature vector включает `exercise_id` как категориальную фичу — модель должна персонализировать предсказания per-athlete, per-exercise (жим штангой у атлета X — отдельный паттерн отклика от жима гантелями). Полный состав фич определён в `docs/ml-feature-spec.md` (Story 2.4).
**And** `pytest tests/test_ml/test_model.py` проходит: forward pass, MC Dropout variance, EWC weight regularization, корректная размерность feature vector

## Story 5.3: ML Worker daemon — polling loop и systemd

As a dev agent,
I want to implement the ML Worker as an isolated process with systemd supervision,
So that PyTorch failures never crash the main API and memory is bounded.

**Acceptance Criteria:**

**Given** `ml/model.py` и `data/queue.py` готовы
**When** агент реализует `ml/worker.py`, `ml/__main__.py` и systemd unit
**Then** `class MLWorker` реализует polling loop с интервалом 60s (configurable)
**And** PREDICT jobs приоритизируются над FINE_TUNE jobs в очереди
**And** fine-tuning запускается только при накоплении ≥N=5 завершённых сессий (configurable threshold)
**And** любая ошибка job → `status='failed'` + `logger.error(job_id=...)` → polling продолжается
**And** `systemd/gym-coach-brain-ml.service` содержит `MemoryLimit=8G` и `Restart=on-failure`
**And** `class MLWorker` тестируется без PyTorch через `mock_rpe_model` fixture
**And** `pytest tests/test_ml/test_worker.py` проходит: polling, job dispatch, priority, threshold logic

## Story 5.4: Версионирование весов модели

As a dev agent,
I want to implement model weight versioning and backup strategy,
So that the system can roll back to a previous model version if accuracy degrades.

**Acceptance Criteria:**

**Given** `ml/worker.py` и `ml/model.py` готовы
**When** ML Worker завершает fine-tuning цикл
**Then** новые веса сохраняются как `model_v{n+1}.pt` где `n` — текущая версия
**And** перед началом fine-tuning создаётся `model_v{n}.backup.pt` в `MODEL_DIR` (atomic)
**And** `model_version` строка логируется в `rpe_predictions.model_version` при каждом PREDICT
**And** при старте ML Worker загружается последняя доступная версия (`model_v*.pt` с максимальным номером)
**And** при старте ML Worker вызывается `os.makedirs(MODEL_DIR, exist_ok=True)` — директория создаётся автоматически если отсутствует
**And** если ни одного файла весов нет — модель инициализируется с random weights и логируется `WARNING`
**And** `pytest tests/test_ml/test_worker.py::test_versioning` проходит: backup создан, версия инкрементирована

## Story 5.5: Simulation-based E2E валидация системы

As a dev agent,
I want to run a simulated 6-month athlete training history through the full system,
So that correctness of PUOS, progression, and RPE personalization is validated without waiting for real data.

**Acceptance Criteria:**

**Given** Epics 1–5 завершены (детерминированное ядро + ML pipeline работают)
**When** агент запускает `python -m gym_coach_brain.simulation.run --months=6 --sessions-per-week=3`
**Then** симуляция генерирует ≥72 синтетических тренировочных сессий с реалистичными параметрами (веса, RPE, readiness score, recovery)
**And** PUOS fractional volume не превышает `max_sets_per_group` из ScienceEvidence.md ни в одной из сессий
**And** прогрессия весов монотонно растёт (с допустимыми deload-откатами) на протяжении симуляции — нет стагнации >4 недель
**And** RPE-модель снижает MAE (mean absolute error) на тестовой выборке по мере накопления сессий: MAE после 10 сессий > MAE после 50 сессий
**And** `sessions_count_for_exercise` корректно отражает историю для каждого упражнения в симуляции
**And** симуляция завершается без exceptions и без None/NaN в feature vectors
**And** итоговый отчёт `_bmad-output/simulation-report.md` содержит: график прогрессии весов, MAE по эпохам, PUOS utilization по мышечным группам

**Note:** Симуляция — это не mock. Она использует реальный код системы (PUOS engine, APRE progression, RPEModel) с синтетическими входными данными. Цель — найти системные баги (бесконечные циклы, PUOS overload, деградация модели) до реального деплоя.

---

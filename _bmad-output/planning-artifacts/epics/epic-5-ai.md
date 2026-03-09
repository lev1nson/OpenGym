# Epic 5: AI-персонализация нагрузок

Нагрузки точно подстраиваются под физиологию конкретного атлета — система обучается на его данных, предсказывает RPE с автоматическим fallback, весовые файлы версионируются.

**Requires:** Epic 4 (завершён)
**FRs covered:** FR1, FR2, FR3, FR4 (версионирование), FR7
**Note:** FR4 Diff-анализ (model_report интент) — Phase 2, не в MVP

## Planning Alignment Addendum

После ретроспективы Epic 4 этот эпик был уточнён до начала активной реализации. Причина не в смене направления, а в снижении риска поздних смысловых уточнений. Epic 5 сохраняет тот же продуктовый замысел, но теперь опирается на заранее утверждённые контракты и quality gates.

### Epic 5 Contract Snapshot v1

**1. Job Contract**

- Допустимые `job_type`: `PREDICT`, `FINE_TUNE`
- Допустимые `status`: `pending`, `processing`, `done`, `failed`
- Приоритет обработки: `PREDICT > FINE_TUNE`
- `PREDICT` создаётся из workout flow для конкретного `session_id`
- `FINE_TUNE` создаётся только threshold-логикой, а не напрямую из API handler
- `session_ids` всегда хранится как JSON array, даже для одного `session_id`

**2. Prediction Contract**

- `AdaptationEngine` читает только `rpe_predictions`, никогда не читает `ml_jobs`
- Канонической считается самая новая prediction-запись для пары `(session_id, exercise_id)` с детерминированной сортировкой
- Worker не пишет в planning/domain flow за пределами ML-контракта

**3. Feature Contract**

- Feature payload строится в одном каноническом месте: `data.features`
- Worker/model не собирают feature vector “по-своему”
- Источники данных: completed history, текущий planned exercise context, readiness signal, same-muscle fatigue estimate
- При отсутствии истории feature builder возвращает валидный деградированный payload, а не exception

**4. Fallback Contract**

- Если prediction отсутствует, stale, malformed или `confidence < threshold`, система обязана уйти в deterministic fallback
- Отсутствие ML-предсказания — штатный режим, а не пользовательская ошибка
- Fallback не имеет права реактивно прогрессировать на пустой истории
- Fallback обязан применять recovery coefficient и equipment rounding последовательно и предсказуемо

**5. Operational Contract**

- Базовый lifecycle job: `pending -> processing -> done|failed`
- `done` и `failed` worker повторно не обрабатывает
- Зависший `processing` job не возвращается автоматически в `pending`; это operational incident
- Adaptation flow не ждёт ML бесконечно; отсутствие свежей prediction ведёт к fallback
- Структурированный лог-контекст обязателен: `job_id`, `job_type`, `session_ids`, `status`, причина ошибки/fallback

### Epic 5 Contract Snapshot v2

_Добавлен по итогам архитектурного ревью перед стартом имплементации. Уточняет механику ML-корректировки и вводит bounded correction, anomaly detection и debug transparency._

**Продуктовая идея (почему NN, а не только формулы):**

Детерминированное ядро (APRE, Double Progression) работает на основе спортивной науки и рассчитано на «среднего атлета». Нейросеть обучается на истории конкретного атлета и учится его персональным паттернам: как быстро он устаёт внутри сессии, как откликается на нагрузку после плохого сна, какие упражнения дают ему прогресс, а какие — стагнацию. NN — это не замена науки, а её персонализация под конкретную физиологию.

**6. Bounded Correction Contract**

- ML-слой предсказывает RPE → `AdaptationEngine` конвертирует predicted_rpe в целевой вес (`ml_weight_kg`) и вычисляет дельту: `delta = ml_weight_kg - core_weight_kg`
- Дельта ограничена: `abs(delta / core_weight_kg) <= ScienceConfig.ml.max_correction_percent` (default: 0.15, т.е. ±15%)
- Если дельта превышает лимит — ML-коррекция не применяется, используется `core_weight_kg`, выставляется `anomaly_flag=True`
- Пороговое значение не hardcoded — берётся из `ScienceConfig.ml.max_correction_percent`

**7. Debug Transparency Contract**

- Каждое упражнение в плане сопровождается `source_label`:
  - `"[ядро]"` — ML не применялся (fallback: нет prediction / низкий confidence / аномалия)
  - `"[AI: +X.Xкг / RPE прогноз: Y.Y / confidence: Z%]"` — ML-коррекция применена
  - `"[AI заблокирован: дельта X% > Y% лимит]"` — аномалия, использовано ядро
- `source_label` включается в `ExplanationLayer` output и пишется в `RPEPrediction.source_label`
- На этапе MVP это debug-информация для разработки; в будущем может быть скрыта или адаптирована для атлета

**8. Anomaly Detection Contract**

- `RPEPrediction` хранит `anomaly_flag: bool` — выставляется worker'ом при записи prediction
- ML Worker ведёт счётчик `consecutive_anomalies` per-model-version
- Если `consecutive_anomalies >= ScienceConfig.ml.anomaly_rollback_threshold` (default: 5) — worker переходит к предыдущей версии модели (`model_v{n-1}.pt`), логирует `ERROR` с контекстом, сбрасывает счётчик
- Аномалия логируется структурированно: `job_id`, `exercise_id`, `core_weight_kg`, `ml_weight_kg`, `delta_percent`, `model_version`

### Epic 5 Contract Snapshot v3

_Добавлен по итогам брейншторм-сессии команды (2026-03-09). Закрывает пробелы в UX flow, feature vector, идемпотентности очереди, fine-tuning threshold и версионировании._

**Контекст продукта:** OpenGym — single-user приложение на личном VPS с Telegram-ботом. Один атлет, одна модель. Multi-tenancy не предполагается в MVP.

**9. Trigger Contract (когда создаётся PREDICT job)**

- `enqueue_predict(session_id)` вызывается сразу после того, как атлет завершил pre-workout check-in (заполнены `sleep_hours` и `pre_readiness`) — не после `session done`
- Это критично: prediction строится на актуальных данных текущего дня (сон, состояние)
- При запросе плана: если prediction свежая (сессия активна) → ML; нет/сессия брошена → ядро без ожидания
- Prediction валидна только в рамках активной сессии — если сессия брошена, при следующем `/workout` создаётся новая сессия, новый check-in, новый enqueue_predict

**10. Pre/Post Workout Check-in Contract**

- **Pre-workout (обязательный, кнопки в Telegram):**
  - `sleep_hours`: `[< 6ч]` `[6–7ч]` `[7–8ч]` `[8+ ч]` → числа: 5.0, 6.5, 7.5, 9.0
  - `pre_readiness`: `[😴 Разбит]` `[😐 Норм]` `[💪 Огонь]` → числа: 2, 5, 9
  - После ответа на оба вопроса атлет переходит в свободный чат с LLM
- **Post-workout (обязательный, кнопки в Telegram):**
  - `post_feeling`: `[😓 Тяжело]` `[👌 В самый раз]` `[😤 Слишком легко]` → числа: 2, 5, 9
  - После ответа — свободный чат / завершение
- Кнопки обязательные: бот не переходит к следующему шагу без ответа
- `enqueue_fine_tune` вызывается только после заполнения `post_feeling` — незавершённые сессии не входят в обучение

**11. Extended Feature Contract**

Feature vector дополнен временны́ми и физиологическими сигналами:

| Фича | Тип | Источник |
|---|---|---|
| `sleep_hours` | float | Pre-workout кнопки → `sessions.sleep_hours` |
| `pre_readiness` | int (2/5/9) | Pre-workout кнопки → `sessions.pre_readiness` |
| `post_feeling` | int (2/5/9) | Post-workout кнопки → `sessions.post_feeling` (только в FINE_TUNE) |
| `workout_hour_sin` | float | `sin(2π * hour / 24)` из `session.started_at` |
| `workout_hour_cos` | float | `cos(2π * hour / 24)` из `session.started_at` |

Циклическое кодирование времени (`sin/cos`) обязательно — иначе модель не понимает что 23:00 и 00:00 близки.

**12. Idempotency Contract**

- `MLJob` таблица содержит unique constraint `UniqueConstraint('session_id', 'job_type')`
- `enqueue_predict` идемпотентен: повторный вызов для того же `session_id` возвращает существующий job без создания дубля
- Реализация: `INSERT ... ON CONFLICT DO NOTHING` или проверка перед вставкой

**13. Fine-tuning Threshold Contract**

- Threshold `≥5` считается по количеству завершённых сессий где `post_feeling IS NOT NULL`
- Deload-сессии (`is_deload=True`) исключаются из обучающей выборки при `enqueue_fine_tune` — они зашумляют модель нетипично низкими весами
- Поле `is_deload: bool` обязано присутствовать в `sessions` таблице (пробрасывается из APRE-логики Epic 4)

**14. rpe_to_weight() Contract**

- Функция определяется в Story 5.2 как часть `AdaptationEngine`
- Формула: `ml_weight_kg = core_weight_kg * (1 - rpe_sensitivity * (predicted_rpe - target_rpe))`
- `rpe_sensitivity` берётся из `ScienceConfig.ml.rpe_weight_sensitivity` (default: 0.025 — ~2.5% веса за единицу RPE)
- `target_rpe` — целевое RPE для данного упражнения из плана (определено в APRE/Double Progression логике)
- Не hardcoded, не определяется внутри модели — только в `AdaptationEngine`

**15. Versioning Integrity Contract**

- `next_version = max(n for file model_v{n}.pt in MODEL_DIR, excluding .anomaly.pt and .backup.pt) + 1`
- После rollback + rename в `.anomaly.pt` следующий fine-tuning пишет `model_v{old_n}.pt` (счётчик откатывается вместе с моделью)
- При старте ML Worker: валидация последнего файла через `torch.load()` в try/except; если corrupt → удалить, загрузить `model_v{n}.backup.pt` или `model_v{n-1}.pt`, залогировать `WARNING`

### Epic 5 Quality Gates

1. Ни одна story после `5.1` не должна стартовать без опоры на `Epic 5 Contract Snapshot v1`, `v2` и `v3`.
2. `5.1` не считается завершённой, пока queue CRUD/ordering/status behavior не покрыты тестами и не доказана полная изоляция от `gym_coach_brain.ml.*`.
3. До движения в `5.3+` должны существовать минимум два интеграционных пути:
   - path с prediction (ML применён, delta в пределах нормы)
   - path без prediction, подтверждающий безопасный deterministic fallback
4. Дублирующая сборка features вне `data.features` считается архитектурным дефектом.
5. `processing` timeout трактуется как incident, а не как неявный auto-requeue.
6. `AdaptationEngine` не может вернуть план без `source_label` для каждого упражнения — отсутствие метки считается дефектом.
7. Bounded correction и anomaly rollback должны быть покрыты тестами до перехода в `5.4`.

### Sequencing Constraint

- Stories `5.2`–`5.5` не должны уходить в активную реализацию, пока `5.1` не закрепит канонический DB/queue контракт и не пройдёт quality gate #2.

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
**And** `enqueue_predict` создаётся вызовом из workout flow сразу после завершения pre-workout check-in (после записи `sleep_hours` и `pre_readiness` в сессию) — см. Contract Snapshot v3, п.9
**And** `enqueue_predict` идемпотентен: повторный вызов для того же `session_id` не создаёт дубль — используется `UniqueConstraint('session_id', 'job_type')` на таблице `MLJob`
**And** `enqueue_predict` создаёт `MLJob` с `job_type="PREDICT"`, `status="pending"`
**And** `enqueue_fine_tune` создаёт `MLJob` с `job_type="FINE_TUNE"`, `status="pending"`, `session_ids` как JSON array
**And** `enqueue_fine_tune` принимает только сессии где `post_feeling IS NOT NULL` и `is_deload=False` — незавершённые и deload-сессии исключаются
**And** `enqueue_predict` тоже сохраняет `session_ids` как JSON array (`[session_id]`), а не scalar
**And** `get_pending_jobs()` возвращает PREDICT-задания с приоритетом над FINE_TUNE
**And** `data/models.py` содержит индекс `Index('ix_mljob_status_type', MLJob.status, MLJob.job_type)` для оптимизации `get_pending_jobs()` queries
**And** `sessions` таблица расширена полями для pre/post workout check-in и деградации данных:
- `sleep_hours: float` — часы сна (из pre-workout кнопок: 5.0 / 6.5 / 7.5 / 9.0)
- `pre_readiness: int` — состояние до тренировки (2 / 5 / 9)
- `post_feeling: int` — ощущение после тренировки (2 / 5 / 9); `NULL` если сессия не завершена
- `is_deload: bool` — флаг deload-недели, пробрасывается из APRE-логики Epic 4
**And** `RPEPrediction` модель расширена полями для debug transparency и anomaly tracking:
- `core_weight_kg: float` — вес, рассчитанный детерминированным ядром
- `ml_weight_kg: float` — вес, полученный из RPE-предсказания модели (до clamp)
- `ml_adjustment_kg: float` — итоговая применённая дельта (`final_weight - core_weight`; 0.0 при fallback/аномалии)
- `anomaly_flag: bool` — True если дельта превысила `max_correction_percent`
- `source_label: str` — человекочитаемая метка источника рекомендации (см. Contract Snapshot v2, п.7)
- `model_version: str` — версия модели, сформировавшей prediction (уже было, сохраняется)
**And** `pytest tests/test_data/test_queue.py` проходит без PyTorch: все CRUD операции, статусные переходы (pending→processing→done/failed), idempotency enqueue_predict, фильтрация deload/незавершённых сессий в enqueue_fine_tune
**And** story не считается complete, пока тестами не доказано отсутствие любых импортов из `gym_coach_brain.ml.*` и сохранение приоритета `PREDICT > FINE_TUNE`

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
**And** feature vector включает `exercise_id` как категориальную фичу — модель персонализирует предсказания per-exercise. Полный состав фич определён в `docs/ml-feature-spec.md` (Story 2.4) и расширен полями из Contract Snapshot v3, п.11: `sleep_hours`, `pre_readiness`, `workout_hour_sin`, `workout_hour_cos`
**And** `workout_hour_sin = sin(2π * hour / 24)` и `workout_hour_cos = cos(2π * hour / 24)` вычисляются из `session.started_at` — циклическое кодирование обязательно
**And** `RPEModel` принимает уже готовый feature payload из канонического builder `data.features`, а не собирает признаки самостоятельно
**And** `AdaptationEngine` расширяется bounded correction логикой (вызывается при наличии prediction):
- вычисляет `core_weight_kg` детерминированным ядром
- конвертирует `predicted_rpe` в `ml_weight_kg` через `rpe_to_weight(predicted_rpe, target_rpe, core_weight_kg, science)`:
  `ml_weight_kg = core_weight_kg * (1 - science.ml.rpe_weight_sensitivity * (predicted_rpe - target_rpe))`
  где `rpe_weight_sensitivity` из `ScienceConfig.ml` (default: 0.025), `target_rpe` из плана упражнения
- вычисляет `delta_percent = abs(ml_weight_kg - core_weight_kg) / core_weight_kg`
- если `delta_percent > ScienceConfig.ml.max_correction_percent` → `anomaly_flag=True`, `final_weight=core_weight_kg`
- если `confidence < ScienceConfig.ml.confidence_threshold` → fallback, `anomaly_flag=False`, `final_weight=core_weight_kg`
- иначе → `final_weight=ml_weight_kg`, `anomaly_flag=False`
- итоговый `final_weight` округляется через `round_to_equipment_increment` (как и в Epic 4)
**And** `ExplanationLayer` дополняется `source_label` в каждом объяснении:
- ML применён: `"[AI: +2.5кг / RPE прогноз: 7.2 / confidence: 81%]"`
- Fallback (низкий confidence): `"[ядро: confidence 43% < порога]"`
- Аномалия: `"[AI заблокирован: дельта 18% > 15% лимит]"`
- Нет prediction: `"[ядро]"`
**And** `pytest tests/test_ml/test_model.py` проходит: forward pass, MC Dropout variance, EWC weight regularization, корректная размерность feature vector
**And** `pytest tests/test_adaptation/test_engine.py` расширяется bounded correction сценариями:
- delta в пределах нормы → ML-коррекция применена, `source_label` содержит `"[AI:"`, `anomaly_flag=False`
- delta превышает лимит → `final_weight=core_weight`, `anomaly_flag=True`, `source_label` содержит `"заблокирован"`
- низкий confidence → fallback, `source_label` содержит `"[ядро:"`, `anomaly_flag=False`
- нет prediction → `source_label == "[ядро]"`

## Story 5.3: ML Worker daemon — polling loop и systemd

As a dev agent,
I want to implement the ML Worker as an isolated process with systemd supervision,
So that PyTorch failures never crash the main API and memory is bounded.

**Acceptance Criteria:**

**Given** `ml/model.py` и `data/queue.py` готовы
**When** агент реализует `ml/worker.py`, `ml/__main__.py` и systemd unit
**Then** `class MLWorker` реализует polling loop с интервалом 60s (configurable)
**And** PREDICT jobs приоритизируются над FINE_TUNE jobs в очереди
**And** fine-tuning запускается только при накоплении ≥N=5 завершённых сессий где `post_feeling IS NOT NULL` и `is_deload=False` (configurable threshold, suммарно по сессиям — не per-exercise)
**And** любая ошибка job → `status='failed'` + `logger.error(job_id=...)` → polling продолжается
**And** worker никогда не переобрабатывает jobs со статусом `done` или `failed`
**And** timeout для зависшего `processing` job трактуется как operational incident и не приводит к неявному auto-requeue в `pending`
**And** structured logging включает как минимум `job_id`, `job_type`, `session_ids`, `status` и причину ошибки
**And** worker ведёт in-memory счётчик `consecutive_anomalies` (per run): инкрементируется при записи `RPEPrediction` с `anomaly_flag=True`, сбрасывается при `anomaly_flag=False`
**And** если `consecutive_anomalies >= ScienceConfig.ml.anomaly_rollback_threshold` → worker загружает предыдущую версию модели (`model_v{n-1}.pt`), логирует `ERROR` со структурированным контекстом (`model_version`, `consecutive_anomalies`, `exercise_id`), сбрасывает счётчик; если предыдущей версии нет — логирует `CRITICAL` и продолжает работу на текущей
**And** аномальная prediction записывается в БД (с `anomaly_flag=True`) до любого rollback-решения — история аномалий не теряется
**And** `systemd/gym-coach-brain-ml.service` содержит `MemoryLimit=8G` и `Restart=on-failure`
**And** `class MLWorker` тестируется без PyTorch через `mock_rpe_model` fixture
**And** `pytest tests/test_ml/test_worker.py` проходит: polling, job dispatch, priority, threshold logic, anomaly counter increment, anomaly-triggered rollback при достижении порога, сброс счётчика после нормального prediction

## Story 5.4: Версионирование весов модели

As a dev agent,
I want to implement model weight versioning and backup strategy,
So that the system can roll back to a previous model version if accuracy degrades.

**Acceptance Criteria:**

**Given** `ml/worker.py` и `ml/model.py` готовы
**When** ML Worker завершает fine-tuning цикл
**Then** новые веса сохраняются как `model_v{next}.pt` где `next = max(n for model_v{n}.pt in MODEL_DIR, исключая .anomaly.pt и .backup.pt) + 1`
**And** перед началом fine-tuning создаётся `model_v{n}.backup.pt` в `MODEL_DIR` (atomic)
**And** `model_version` строка логируется в `rpe_predictions.model_version` при каждом PREDICT
**And** при старте ML Worker: 1) `os.makedirs(MODEL_DIR, exist_ok=True)`, 2) glob `model_v*.pt` (без суффиксов), 3) загрузка максимальной версии через `torch.load()` в try/except — если corrupt: удалить файл, попробовать `.backup.pt` или `model_v{n-1}.pt`, залогировать `WARNING`
**And** если ни одного файла весов нет — модель инициализируется с random weights и логируется `WARNING`
**And** anomaly-triggered rollback: при срабатывании порога `anomaly_rollback_threshold` (из Story 5.3) worker вызывает `load_model_version(n-1)` — функция из этой story
**And** `load_model_version(n)` → загружает `model_v{n}.pt`; если файл отсутствует — поднимает `ModelVersionNotFoundError` (не silent fail)
**And** после rollback текущий `model_vN.pt` переименовывается в `model_vN.anomaly.pt` (не удаляется) — история сохраняется для post-mortem анализа; следующий fine-tuning использует `max(glob) + 1` и корректно определяет новый номер
**And** `ScienceConfig.ml` расширяется полями: `max_correction_percent: float` (default 0.15), `anomaly_rollback_threshold: int` (default 5), `rpe_weight_sensitivity: float` (default 0.025) — все не hardcoded
**And** `pytest tests/test_ml/test_worker.py::test_versioning` проходит: backup создан, версия инкрементирована через glob (не счётчик), rollback загружает n-1 версию, anomaly файл сохраняется при rollback, corrupt файл при старте обрабатывается gracefully

## Story 5.5: Simulation-based E2E валидация системы

As a dev agent,
I want to run a simulated 6-month athlete training history through the full system,
So that correctness of PUOS, progression, and RPE personalization is validated without waiting for real data.

**Acceptance Criteria:**

**Given** Epics 1–5 завершены (детерминированное ядро + ML pipeline работают)
**When** агент создаёт модуль `gym_coach_brain/simulation/` (scaffolding — первый шаг story):
- `simulation/run.py` — точка входа CLI с аргументами `--months`, `--sessions-per-week`
- `simulation/synthetic_athlete.py` — генератор синтетических данных атлета
**And** запускает `python -m gym_coach_brain.simulation.run --months=6 --sessions-per-week=3`
**Then** симуляция генерирует ≥72 синтетических тренировочных сессий с реалистичными параметрами:
- `sleep_hours` ~ N(7, 1), clamp [4, 10]
- `pre_readiness` коррелирует со сном: при sleep < 6 → P(readiness=2) = 0.6; иначе равновероятно
- `workout_hour` — детерминированный паттерн (например 19:00 ± U(-30, 30) мин)
- `post_feeling` — случайный с лёгким смещением к 5, с шумом
**And** PUOS fractional volume не превышает `max_sets_per_group` из ScienceEvidence.md ни в одной из сессий
**And** прогрессия весов монотонно растёт (с допустимыми deload-откатами) на протяжении симуляции — нет стагнации >4 недель
**And** RPE-модель снижает MAE на тестовой выборке: MAE после 50 сессий **< 1.0** (в единицах RPE по шкале 1–10) **AND** минимум на **15% меньше** чем MAE после 10 сессий
**And** `sessions_count_for_exercise` корректно отражает историю для каждого упражнения в симуляции
**And** симуляция завершается без exceptions и без None/NaN в feature vectors
**And** симуляция явно покрывает bounded correction сценарии:
- сценарий «нормальная коррекция»: ML даёт дельту в пределах лимита → `ml_adjustment_kg != 0`, `anomaly_flag=False` как минимум в 30% сессий к концу симуляции (модель набрала уверенность)
- сценарий «аномалия»: в симуляцию инжектируются намеренно сломанные predictions (дельта > лимита) → `anomaly_flag=True` в записях, worker rollback срабатывает, план строится на ядре
- сценарий «fallback»: симуляция первых 5 сессий (история пуста) → все планы строятся на ядре (`source_label == "[ядро]"`), нет exceptions
**And** итоговый отчёт `_bmad-output/simulation-report.md` содержит:
- график прогрессии весов (core vs AI-adjusted)
- MAE по эпохам
- PUOS utilization по мышечным группам
- распределение `source_label` по сессиям: доля `[ядро]` / `[AI]` / `[AI заблокирован]` по времени
- log аномалий с rollback событиями

**Note:** Симуляция — это не mock. Она использует реальный код системы (PUOS engine, APRE progression, RPEModel) с синтетическими входными данными. Цель — найти системные баги (бесконечные циклы, PUOS overload, деградация модели, аномальные дельты) до реального деплоя.

---

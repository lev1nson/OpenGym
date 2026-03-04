# Epic 3: Основа проекта и профиль атлета

Атлет может пройти интерактивный онбординг через OpenClaw чат, его ответы конвертируются в числовые коэффициенты, создаётся профиль с параметрами и оборудованием в SQLite. Проект инициализирован с нуля (greenfield).

**⚠️ Порядок выполнения (критично):** Stories 3.1–3.2 выполняются ДО Epic 2 (Epic 2 требует Alembic и project structure). Stories 3.3–3.5 выполняются ПОСЛЕ Epic 2.
**Requires (Stories 3.1–3.2):** Epic 1 (завершён)
**Requires (Stories 3.3–3.5):** Epic 1 (завершён), Epic 2 (завершён)
**FRs covered:** FR9, FR10, FR13, FR14

## Story 3.1: Инициализация проекта

> **⚠️ БЛОКИРУЕТ Epic 2 — выполняется ПЕРВОЙ.** Epic 2 Stories не могут начаться пока эта история не завершена. Пререквизит проверяется через AC: `uv run pytest` должен проходить без ошибок.

As a dev agent,
I want to initialize the gym-coach-brain project with uv src layout and CI,
So that all developers have a reproducible environment and automated test pipeline.

**Acceptance Criteria:**

**Given** чистая директория на VPS
**When** агент выполняет `uv init --package gym-coach-brain` и добавляет зависимости
**Then** структура `src/gym_coach_brain/` создана с папками `core/`, `adaptation/`, `ml/`, `data/`, `api/`
**And** `uv add sqlalchemy alembic "pydantic[yaml]" loguru torch` и `uv add --dev pytest pytest-cov` выполнены успешно
**And** директория `docs/` создана в project root (используется в Epic 2 Story 2.4 для `ml-feature-spec.md`)
**And** `uv run pytest` запускается без ошибок (0 тестов — OK)
**And** `.github/workflows/ci.yml` создан и запускает pytest при push/PR
**And** `exceptions.py` создан с классами `GymCoachError`, `ScienceLimitError`, `MLPredictionError`, `ConfigError`

## Story 3.2: Data Layer — SQLAlchemy модели и Alembic

> **⚠️ БЛОКИРУЕТ Epic 2 — выполняется ВТОРОЙ.** Epic 2 Stories не могут начаться пока эта история не завершена. Пререквизит проверяется через AC: `alembic upgrade head` должен проходить без ошибок.

As a dev agent,
I want to define all SQLAlchemy models and initialize Alembic migrations,
So that the database schema is version-controlled and reproducible.

**Acceptance Criteria:**

**Given** проект инициализирован (Story 3.1 завершена)
**When** агент создаёт `data/models.py` и инициализирует Alembic
**Then** `data/models.py` содержит ВСЕ SQLAlchemy модели (единственный источник истины схемы):
- `UserProfile` (профиль атлета: коэффициенты, цели, оборудование; `bodyweight_kg: Float` — вес тела атлета; `initial_weight_coefficients: TEXT` — JSON dict `{movement_pattern_name: float}`, коэффициент к весу тела для стартового веса новых упражнений; вычисляется при `onboarding_complete` из `ScienceConfig.initial_weight_table[experience_level][movement_pattern]`)
- `WorkoutSession` (тренировочная сессия: дата, статус, методология, `planned_exercises: TEXT nullable` — JSON-encoded list of PlannedExercise для сохранения сгенерированного плана, `split_day_label: String nullable` — метка дня сплита, записываемая WorkoutPlanner при генерации; допустимые значения: `push`, `pull`, `legs`, `upper`, `lower`, `full_body`)
- `WorkoutSet` (отдельный подход: `session_id` FK, `exercise_id` FK, `set_number`, `weight_kg`, `reps`, `rpe` nullable, `notes` nullable, `created_at`; `UniqueConstraint('session_id', 'exercise_id', 'set_number')` — защита от дублирования подходов)
- `Exercise` (метаданные упражнения: FK→MuscleGroup (primary), FK→MovementPattern, `secondary_muscle_ids: TEXT` (JSON-encoded list of MuscleGroup IDs), `is_compound`, `stretch_mediated`, `equipment_type`)
- `MuscleGroup` (группы мышц: `name`, `body_region`, `is_push`, `is_pull`, `stretch_mediated`)
- `MovementPattern` (7 паттернов движения: `name`, `category`)
- `Equipment` (каталог оборудования: `name`, `type`, `available_home`, `available_gym`)
- `ReadinessLog` (дневник восстановления: `session_date`, `sleep_hours`, `stress_level`, `hrv_score`, `recovery_score`)
- `MLJob` (очередь ML-задач: `job_type`, `status`, `session_ids` JSON, `created_at`, `processed_at`)
- `RPEPrediction` (предсказания ML Worker: `session_id` FK, `exercise_id`, `predicted_rpe`, `confidence_score`, `model_version`, `created_at`)

**And** `data/models.py` содержит `EquipmentType(str, Enum)` с фиксированными значениями: `barbell`, `dumbbell`, `machine`, `cable`, `bodyweight`, `resistance_band`, `pullup_bar`, `dips_bar`
**And** `data/models.py` содержит `TrainingSplit(str, Enum)` с фиксированными значениями: `ppl`, `upper_lower`, `full_body`, `custom`
**And** `Exercise.equipment_type` использует `SQLAlchemyEnum(EquipmentType)` — не свободная строка
**And** `UserProfile.available_equipment` хранит JSON list of EquipmentType values (оборудование атлета из онбординга)
**And** `UserProfile.training_split` использует `SQLAlchemyEnum(TrainingSplit)`, default `full_body`
**And** `UserProfile.training_days_per_week: Integer` (3–6), default 3
**And** `WorkoutSet` дополнен полем `rir: Integer nullable` (input атлета, диапазон 0–4; 0 = до отказа, 4 = очень легко)
**And** `WorkoutSet.rpe: Float nullable` остаётся вычисляемым (`rpe = 10.0 - rir`) — конвертация происходит в `api/handlers.py` при обработке `workout_log_set`, не в модели
**And** `data/session.py` содержит engine factory с `DATABASE_URL` env var (default: `sqlite:///gym_coach.sqlite`)
**And** `data/session.py` содержит `MODEL_DIR` env var (default: `./models/`) — директория для хранения `model_v*.pt` файлов
**And** `alembic init alembic` выполнен, `env.py` импортирует `Base` из `data/models.py`
**And** `alembic revision --autogenerate -m "initial_schema"` создаёт корректную миграцию со всеми 10 таблицами, включая новые поля `UserProfile.training_split`, `UserProfile.training_days_per_week`, `UserProfile.bodyweight_kg`, `UserProfile.initial_weight_coefficients`, `WorkoutSet.rir`, `WorkoutSession.split_day_label`
**And** `alembic revision -m "seed_data"` создаёт `alembic/versions/002_seed_data.py` с seed данными:
  - `MuscleGroup`: 10+ групп (грудь, спина, плечи, бицепс, трицепс, квадрицепс, бицепс бедра, ягодицы, икры, пресс)
  - `MovementPattern`: 7 паттернов (горизонтальный жим, вертикальный жим, горизонтальная тяга, вертикальная тяга, приседание, шарнир, переноска)
  - `Equipment`: 10+ единиц оборудования с `available_home` и `available_gym` флагами
  - `Exercise`: 30+ базовых упражнений с корректными FK (`primary_muscle_id`, `movement_pattern_id`), `secondary_muscle_ids` (JSON), `is_compound`, `stretch_mediated`, `equipment_type`; **гарантия покрытия:** для каждой из 10 muscle groups существует хотя бы одно упражнение с `equipment_type=bodyweight` — атлет без оборудования всегда получает полный план
**And** `alembic upgrade head` применяет оба migration файла без ошибок
**And** `pytest tests/test_data/test_seed_coverage.py` проверяет: для каждой muscle group из `MuscleGroup` таблицы существует хотя бы один `Exercise` с `equipment_type=bodyweight`
**And** `pytest tests/test_data/test_models.py` проходит (FK constraints, column types, nullable поля для `WorkoutSet.rpe`, корректный `secondary_muscle_ids` как JSON TEXT, `EquipmentType` enum валидация, `UniqueConstraint` на `WorkoutSet` — попытка вставить дублирующий `(session_id, exercise_id, set_number)` бросает `IntegrityError`)

## Story 3.3: ScienceConfig loader

As a dev agent,
I want to implement `core/science.py` with a Pydantic model parsing ScienceEvidence.md,
So that all modules have O(1) access to typed scientific coefficients at runtime.

**Acceptance Criteria:**

**Given** ScienceEvidence.md (из Epic 1) доступен в project root
**When** `load_science_config()` вызывается при старте процесса
**Then** возвращается `ScienceConfig` объект с секциями `puos`, `progression`, `recovery`
**And** `cfg.puos.max_sets_per_group == 11` (или значение из файла)
**And** `cfg.version` — непустая строка
**And** при отсутствии или повреждении файла бросается `ConfigError`
**And** `ScienceConfig` принимается как параметр функциями (НЕ глобальный singleton)
**And** `pytest tests/test_core/test_science.py` проходит с `mock_science_config` fixture

## Story 3.4: Шаблон онбординга и маппинг коэффициентов

As a dev agent,
I want to implement `core/onboarding.py` with question templates and coefficient mapping,
So that athlete answers are deterministically converted to numerical training parameters.

**Acceptance Criteria:**

**Given** `data/models.py` с таблицей `UserProfile` доступен
**When** агент реализует `core/onboarding.py`
**Then** модуль содержит упорядоченный список вопросов онбординга (возраст, опыт, цель, доступное оборудование, режим сна/стресса)
**And** каждый вопрос имеет тип ответа (число, выбор из вариантов, текст)
**And** вопрос «Вес тела (кг)?» (числовой ввод, диапазон 30–250) сохраняется в `UserProfile.bodyweight_kg`
**And** вопрос про оборудование предлагает атлету выбрать из каталога `Equipment` (из seed data) — multi-select
**And** выбранное оборудование сохраняется в `UserProfile.available_equipment` как JSON list of `EquipmentType` values
**And** вопрос «Сколько раз в неделю тренируешься?» (варианты: 3 / 4 / 5 / 6) сохраняется в `UserProfile.training_days_per_week`
**And** вопрос «Предпочтение сплита?» (варианты: Фулбоди / Верх-Низ / Толчок-Тяга-Ноги / Своя программа) сохраняется в `UserProfile.training_split` через маппинг: Фулбоди→`full_body`, Верх-Низ→`upper_lower`, ТТН→`ppl`, Своя→`custom`
**And** функция `compute_initial_weights(user_profile, science) -> dict` вычисляет `initial_weight_coefficients` при `onboarding_complete`: для каждого `MovementPattern` возвращает `bodyweight_kg * ScienceConfig.initial_weight_table[experience_level][movement_pattern]`; результат сохраняется в `UserProfile.initial_weight_coefficients` как JSON
**And** функция `get_available_exercises(user_profile, session) -> list[Exercise]` возвращает упражнения, отфильтрованные по `UserProfile.available_equipment`
**And** функция `map_answer_to_coefficients(question_id, answer) -> dict` возвращает числовые коэффициенты
**And** коэффициенты сохраняются в `UserProfile` через SQLAlchemy session (не интерпретируются LLM)
**And** `pytest tests/test_core/test_onboarding.py` проходит: каждый вопрос имеет детерминированный маппинг, включая `training_split`, `training_days_per_week`, `bodyweight_kg`; `compute_initial_weights` возвращает корректные значения для beginner/intermediate/advanced; `get_available_exercises` корректно фильтрует по оборудованию

## Story 3.5: API handlers онбординга, профиля оборудования и просмотра профиля

As an athlete,
I want to complete onboarding through OpenClaw chat and view my profile,
So that gym-coach-brain personalizes my training based on my parameters.

**Acceptance Criteria:**

**Given** `core/onboarding.py` и `data/models.py` готовы
**When** OpenClaw отправляет интент `onboarding_start`
**Then** возвращается первый вопрос из шаблона в формате `{"intent": "onboarding_start", "stdout": "...", "exit_code": 0}`
**And** интент `onboarding_answer` с ответом сохраняет коэффициент в `UserProfile` и возвращает следующий вопрос
**And** интент `onboarding_complete` сохраняет финальный профиль и возвращает подтверждение
**And** интент `profile_show` возвращает читаемый текст со всеми параметрами атлета и оборудованием
**And** повторный `onboarding_start` при существующем профиле возвращает предупреждение с опцией перезаписи
**And** интент `profile_update_equipment` обновляет `UserProfile.available_equipment` (принимает новый список `EquipmentType` values); возвращает подтверждение с обновлённым списком доступных упражнений
**And** интент `profile_update_split` обновляет `UserProfile.training_split`; сбрасывает `split_day_label` к fallback-значению (как первая тренировка) — PPL → следующая сессия начнётся с `push`, UL → с `upper`; возвращает подтверждение с новым сплитом
**And** `pytest tests/test_api/test_handlers.py` покрывает все 6 интентов (включая `profile_update_equipment` и `profile_update_split`)

---

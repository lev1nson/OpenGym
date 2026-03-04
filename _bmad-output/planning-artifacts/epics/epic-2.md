# Epic 2: База знаний и мастер-данные

Создать полную базу знаний: таксономию мышц и паттернов движения, библиотеку ~35 базовых упражнений с полными метаданными, каталог оборудования и спецификацию ML-фичей. Фундамент для корректной работы PUOS (фракционный объём 1.0/0.5) и нейросети.

**Requires:** Epic 1 (завершён), Stories 3.1–3.2 из Epic 3 (завершены — нужен Alembic)
**Блокирует:** Epic 4, Epic 5
**FRs covered:** Пререквизит для FR5, FR6, FR12

## Story 2.1: Taxonomy мышц и паттернов движения

As a dev agent,
I want to define and seed the muscle groups and movement patterns taxonomy,
So that all exercises can be correctly classified and PUOS fractional volume calculated.

**Acceptance Criteria:**

**Given** Stories 3.1 и 3.2 завершены (таблицы `muscle_groups` и `movement_patterns` уже созданы в initial_schema Alembic-миграции из Story 3.2)
**When** агент наполняет существующие таблицы seed data
**Then** таблица `muscle_groups` содержит записи для всех основных групп: грудь, широчайшие, трапеции, дельты, бицепс, трицепс, квадрицепс, бицепс бедра, ягодицы, икры, пресс, поясница
**And** каждая запись имеет корректно заполненные поля: `name`, `body_region` (upper/lower/core), `is_push`, `is_pull`, `stretch_mediated` (SMH флаг)
**And** поля `is_push` и `is_pull` используются в Epic 4 Story 4.7 для antagonist balance: WorkoutPlanner проверяет что план содержит хотя бы одно push и одно pull упражнение для upper body (предотвращает дисбаланс "только жимы без тяг"); это требование к Story 4.7 — добавить AC на antagonist balance check
**And** таблица `movement_patterns` содержит 7 паттернов: horizontal_push, vertical_push, horizontal_pull, vertical_pull, hinge, squat, carry
**And** seed data вставляется через SQLAlchemy session (НЕ через новую Alembic-миграцию — таблицы уже существуют)
**And** тесты используют изолированную in-memory SQLite через `conftest.py` с `db_session` fixture и rollback после каждого теста — `pytest tests/test_data/test_models.py` не зависит от порядка запуска и не оставляет данных между тестами
**And** `pytest tests/test_data/test_models.py` проходит: все группы мышц и паттерны присутствуют

## Story 2.2: Библиотека упражнений с полными метаданными

As a dev agent,
I want to create an exercise library with ~35 foundational exercises and full metadata,
So that the system can calculate PUOS fractional volume and prepare ML features for any exercise.

**Acceptance Criteria:**

**Given** таблицы `muscle_groups` и `movement_patterns` заполнены seed data (Story 2.1), таблица `exercises` уже создана в initial_schema из Story 3.2
**When** агент наполняет существующую таблицу `exercises` seed data
**Then** seed data содержит ≥35 упражнений, покрывающих все 7 паттернов движения (минимум 4-5 на паттерн, равномерно — не 30 push + 5 остальных; исключение: паттерн `carry` допускает 2–3 упражнения по природе паттерна, не по ошибке — явно пометить в seed файле)
**And** `secondary_muscle_ids` для каждого упражнения определены на основе domain-research из Story 1.1 (основные 8 упражнений покрыты) или ExRx.net как primary source для остальных — субъективные решения не допускаются, каждый спорный случай комментируется в seed файле; для `carry` упражнений (Farmer's Walk, Suitcase Carry и др.) источник ExRx.net достаточен, дополнительный domain-research не требуется
**And** seed data реализована в два этапа: сначала 28 упражнений (4 на паттерн) с полными метаданными как минимально работающий набор, затем расширение до ≥35 — это снижает риск ошибок при заполнении
**And** seed data вставляется через SQLAlchemy session (НЕ через новую Alembic-миграцию)
**And** `fractional_volume(exercise_id, muscle_group_id)` возвращает 1.0 для агониста и 0.5 для синергиста
**And** `pytest tests/test_data/test_exercises.py` проходит: все паттерны покрыты, фракционный объём корректен

## Story 2.3: Каталог оборудования и интент exercise_add

As an athlete,
I want the system to know available equipment and allow adding new exercises,
So that workout plans use only exercises I can actually perform.

**Acceptance Criteria:**

**Given** таблица `exercises` заполнена seed data (Story 2.2), таблица `equipment` уже создана в initial_schema из Story 3.2
**When** агент наполняет существующую таблицу `equipment` seed data
**Then** seed data покрывает: штанга, гантели, кабельный тренажёр, турник, брусья, тренажёры для основных групп мышц
**And** seed data вставляется через SQLAlchemy session (НЕ через новую Alembic-миграцию)
**When** OpenClaw отправляет интент `exercise_add` с параметрами упражнения
**Then** новое упражнение сохраняется в `exercises` с полными метаданными
**And** упражнение автоматически доступно для расчёта PUOS и ML features
**And** `pytest tests/test_api/test_handlers.py::test_exercise_add` проходит

## Story 2.4: Спецификация и валидация ML-фичей

As a dev agent,
I want to define and validate the complete ML feature specification,
So that the RPEModel receives clean, well-structured input data for training and inference.

**Acceptance Criteria:**

**Given** все таблицы мастер-данных заполнены (Stories 2.1-2.3)
**When** агент создаёт документ `docs/ml-feature-spec.md` и валидационный скрипт
**Then** документ описывает полный feature vector: `exercise_id` (categorical — необходим для per-athlete, per-exercise персонализации; модель должна знать что "жим штангой у атлета X" отличается от "жима гантелями"), `movement_pattern_id` (categorical 0–6), `primary_muscle_id` (categorical), `is_compound` (bool), `stretch_mediated` (bool), `equipment_type` (categorical), `set_number` (int), `weight_kg` (float), `reps` (int), `historical_rpe` (float, из `WorkoutSet.rpe` прошлых сессий), `avg_rpe_last_3_sessions_for_exercise` (float, скользящее среднее RPE по конкретному упражнению у атлета), `sessions_count_for_exercise` (int, количество сессий с данным упражнением у атлета), `readiness_score` (float, из `ReadinessLog`), `days_since_last_session` (int)
**And** для каждой фичи указаны: тип, диапазон значений, метод нормализации
**And** для фич с возможным cold start (нет истории по упражнению) определены fallback значения: `avg_rpe_last_3_sessions_for_exercise` → медиана по всем упражнениям из seed data; `sessions_count_for_exercise` → 0; `historical_rpe` → глобальная медиана RPE
**And** валидационный скрипт `python -m gym_coach_brain.data.validate_features` проходит без ошибок: все фичи присутствуют в схеме БД
**And** `pytest tests/test_data/test_features.py` проходит: feature vector собирается без None/NaN значений для seed упражнений
**And** `pytest tests/test_data/test_features.py::test_cold_start` проходит: feature vector для атлета без истории по упражнению заполняется fallback значениями (не None, не NaN)

**Definition of Done для Epic 2:** `docs/ml-feature-spec.md` проходит review у архитектора (Winston / архитектурная роль) до старта Epic 5 — подтверждается что feature vector достаточен для RPEModel и не потребует переработки после начала ML-реализации.

## ⚠️ Open Issues (требуют решения перед имплементацией)

**~~1. Test Database Isolation~~** ✅ **ЗАКРЫТ** (2026-03-04) — Паттерн уже задан в `architecture.md` (Test Fixtures section):

```python
@pytest.fixture          # scope="function" по умолчанию — новый engine на каждый тест
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session    # engine уничтожается после теста → полная изоляция без rollback
```

Единый `tests/conftest.py` автоматически применяется ко всем поддиректориям (`test_data/`, `test_api/`). Story 2.1 AC уже содержит корректное требование. Stories 2.2–2.4 наследуют fixture через pytest conftest lookup — дополнительных AC не требуется.

**~~2. Secondary Muscles Validation~~** ✅ **ЗАКРЫТ** (2026-03-04) — Domain research (`_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md`, Section 8) покрывает 8 основных упражнений с peer-reviewed классификацией (ExRx.net + Israetel). Оставшиеся ~27 упражнений: ExRx.net как primary source — явно разрешено AC Story 2.2. Спорные случаи комментируются inline в seed файле. Отдельный research-таск не требуется.

**3. Epic 5 Simulation** — Story 5.5 в Epic 5 использует seed данные из этого эпика как основу синтетической истории атлета. Убедиться что все 35+ упражнений покрывают все 7 паттернов движения равномерно (не 30 push + 5 остальных) — иначе симуляция будет нерепрезентативной.

---

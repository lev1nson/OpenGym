# Epic 4: Детерминированное тренировочное ядро

Атлет получает научно-обоснованный план тренировки с автоматическим Recap/Summary, PUOS-защитой и lifestyle-коэффициентами. Все алгоритмы реализованы исключительно на основе ScienceEvidence.md. Методологии (гипертрофия, сила и др.) — pluggable через ScienceConfig.

**Requires:** Epic 1 (завершён), Epic 2 (завершён), Epic 3 (завершён)
**FRs covered:** FR5, FR6, FR8, FR15, FR16, FR17

## Story 4.1: APRE и Double Progression алгоритмы

As a dev agent,
I want to implement APRE and Double Progression as pure functions in `core/apre.py` and `core/progression.py`, and weight rounding in `core/weight_utils.py`,
So that the system can calculate training loads deterministically from ScienceConfig coefficients and return physically achievable weights.

**Acceptance Criteria:**

**Given** `ScienceConfig` с секцией `progression` доступен
**When** `calculate_apre_adjustment(actual_reps, target_reps, current_weight, science)` вызывается
**Then** возвращает новый вес согласно APRE-формуле из ScienceConfig коэффициентов
**And** функция — чистая (pure), без side effects, без DB-вызовов
**When** `calculate_double_progression(current_reps, current_weight, rep_range, science)` вызывается
**Then** возвращает `(new_reps, new_weight)` согласно Double Progression логике из ScienceConfig
**And** область применения зафиксирована в docstring и тестах: `calculate_apre_adjustment` вызывается **только внутри активной сессии** — после каждого залоггированного сета для рекомендации следующего сета; `calculate_double_progression` вызывается **только при генерации плана следующей сессии** — использует итоговые данные предыдущей сессии из БД
**And** `core/weight_utils.py` содержит `round_to_equipment_increment(weight_kg: float, equipment_type: EquipmentType, science: ScienceConfig) -> float`: barbell → кратно `science.equipment_increments.barbell` (default 2.5кг), dumbbell → кратно `science.equipment_increments.dumbbell` (default 1.0кг), machine → кратно `science.equipment_increments.machine` (default 5.0кг), cable → кратно `science.equipment_increments.cable` (default 2.5кг), bodyweight → возвращает 0.0, resistance_band/pullup_bar/dips_bar → возвращает без изменений; функция чистая (pure), без side effects
**And** `calculate_double_progression` содержит ветку для `equipment_type=bodyweight`: прогрессия только по `reps` в пределах `rep_range`, `new_weight = 0.0`; при достижении `rep_range.max` возвращает `(reps=rep_range.max, new_weight=0.0, suggest_added_load=True)` — сигнал агенту предложить атлету добавить нагрузку (жилет, резинка)
**And** `pytest tests/test_core/test_apre.py`, `test_progression.py` и `test_weight_utils.py` проходят с edge cases:
- RIR=0 → RPE=10.0
- 82.3кг barbell → 82.5кг; 81.1кг barbell → 80.0кг
- 67.3кг machine → 65.0кг; 53.8кг cable → 52.5кг
- bodyweight → 0.0
- double_progression bodyweight: reps прогрессирует; при верхней границе rep_range → `suggest_added_load=True`

## Story 4.2: PUOS валидатор и фракционный объём

As a dev agent,
I want to implement PUOS limit validation and fractional volume tracking in `core/puos.py`,
So that the system blocks unsafe training volumes and tracks muscle group load accurately.

**Acceptance Criteria:**

**Given** `ScienceConfig` с `puos.max_sets_per_group` и `puos.smh_volume_multiplier` доступен
**When** `validate_puos(muscle_group, planned_sets, science)` вызывается с превышением лимита
**Then** бросается `ScienceLimitError` с описанием нарушения
**When** объём в пределах лимита
**Then** возвращается `FractionalVolume` объект с коэффициентами 1.0 (агонист) / 0.5 (синергист)
**And** если `muscle_group.stretch_mediated = True` — эффективный лимит умножается на `science.puos.smh_volume_multiplier` (например, 1.25): SMH-упражнения (Romanian deadlift, overhead press) переносятся лучше и допускают больший объём согласно Israetel
**And** `accumulate_session_volume(session_sets: list[WorkoutSet], science) -> dict[muscle_group_id, float]` реализует within-session аккумуляцию: для каждого сета суммируется fractional volume (1.0 агонист + 0.5 синергист) по всем задействованным мышцам — если атлет делает жим штангой + жим гантелями + разводку в одной сессии, грудь получает суммарный объём всех трёх; `validate_puos` вызывается на итоговом аккумулированном объёме, не на объёме одного упражнения
**And** при накопленном объёме ≥9 сетов для любой мышечной группы логируется `WARNING` через loguru
**And** `pytest tests/test_core/test_puos.py` проходит:
- блокировка превышения лимита
- корректный фракционный расчёт 1.0/0.5
- SMH multiplier: stretch_mediated мышца допускает `max_sets * smh_volume_multiplier` сетов
- within-session accumulation: жим штангой + жим гантелями = суммарный объём для груди, не независимые проверки

## Story 4.3: Readiness log и lifestyle коэффициенты

As an athlete,
I want to log my readiness (sleep, stress, HRV) before a workout,
So that the system adjusts my training load based on my recovery state.

**Acceptance Criteria:**

**Given** `UserProfile` атлета существует в БД
**When** OpenClaw отправляет интент `readiness_log` с параметрами (sleep_hours, stress_level, hrv_score)
**Then** запись сохраняется в таблице `readiness_log` (имя таблицы SQLAlchemy из `ReadinessLog.__tablename__`) с `session_date`
**And** `core/readiness.py` возвращает `RecoverySignal` с итоговым коэффициентом восстановления (0.0–1.0)
**And** коэффициент рассчитывается детерминированно из ScienceConfig весов, без LLM-интерпретации
**And** при отсутствии readiness-лога для сессии используется дефолтный коэффициент 1.0
**And** `pytest tests/test_core/test_readiness.py` проходит с граничными значениями

## Story 4.4: Селектор тренировочной методологии

As an athlete,
I want the system to select and apply a training methodology based on my profile,
So that my workout plan matches my goals using science-backed protocols.

**Acceptance Criteria:**

**Given** `UserProfile` с целью атлета и `ScienceConfig` с секцией `methodologies` доступны
**When** `select_methodology(user_profile, science)` вызывается
**Then** возвращается `Methodology` объект с `rep_range`, `progression_type`, `frequency`
**And** выбор детерминирован: одинаковый профиль → одинаковая методология
**And** методология применяется как надстройка — передаётся в APRE/Double Progression как параметры
**And** смена методологии не требует изменения кода — только обновления ScienceEvidence.md
**And** `pytest tests/test_core/test_methodology.py` проходит: все методологии из ScienceConfig корректно применяются

## Story 4.5: Adaptation Engine и Explanation Layer

As an athlete,
I want the system to produce an adapted workout plan with scientific justification for each decision,
So that I understand why specific weights and reps are assigned to me.

**Acceptance Criteria:**

**Given** алгоритмы из Stories 4.1-4.4 и `ScienceConfig` доступны
**When** `AdaptationEngine.adapt(session, user_profile, recovery_signal, science)` вызывается
**Then** возвращается адаптированный план с весами и повторениями для каждого упражнения
**And** при `confidence < ScienceConfig.ml.confidence_threshold` или отсутствии ML-предсказания — автоматический fallback на Double Progression (не exception); порог не hardcoded
**And** `ExplanationLayer.explain(decision, science)` возвращает текстовое обоснование со ссылкой на `science.version`
**And** каждое изменение веса сопровождается обоснованием
**And** `AdaptationEngine` принимает `rpe_model` как параметр (duck typing / `RPEModelProtocol` из `ml/interface.py`) — не импортирует `RPEModel` напрямую, обеспечивая изоляцию от PyTorch в Epic 4
**And** `ml/interface.py` создаётся в этой истории: `class RPEModelProtocol(Protocol): def predict(self, features) -> tuple[float, float]: ...`
**And** рекомендация следующего сета вызывает `core.weight_utils.round_to_equipment_increment(weight, equipment_type)` перед возвратом — итоговый вес всегда кратен шагу оборудования (барбелл: 2.5кг, гантели: 1кг, тренажёр: 5.0кг)
**And** `AdaptationEngine` детектирует плато: если для `exercise_id` за последние `ScienceConfig.plateau_detection_sessions` сессий нет роста ни по весу ни по объёму (reps × sets) — в stdout рекомендации добавляется «📊 Плато [N] сессий — попробуй другое упражнение или измени диапазон повторений»; решение остаётся за атлетом/агентом
**And** `pytest tests/test_adaptation/test_engine.py` и `test_explanation.py` проходят с `mock_science_config` и `mock_rpe_model`:
- weight округляется корректно для barbell/dumbbell
- плато из N одинаковых сессий → предупреждение в stdout
- прогресс за последние N сессий → без предупреждения

## Story 4.7: WorkoutPlanner — генерация плана тренировки

As an athlete,
I want the system to generate a complete workout plan for today's session,
So that I just follow the plan without any planning decisions.

**Acceptance Criteria:**

**Given** `UserProfile` с `training_split` и `training_days_per_week`, история `WorkoutSession`/`WorkoutSet` в БД, и `ScienceConfig` доступны
**When** `WorkoutPlanner.generate(user_profile, science, db_session, recovery_signal=None) -> WorkoutPlan` вызывается
**Then** метод определяет muscle groups на сегодня через поле `split_day_label` последней завершённой `WorkoutSession`:
- для `full_body`: все группы каждую сессию; `split_day_label = "full_body"`
- для `upper_lower`: читает `split_day_label` предыдущей сессии; если `upper` → сегодня `lower`, если `lower` → сегодня `upper`; записывает новый `split_day_label` в текущую сессию
- для `ppl`: читает `split_day_label` предыдущей сессии; строгий цикл `push → pull → legs`; записывает новый `split_day_label` в текущую сессию
- `custom`: те же muscle groups, что и в последней завершённой сессии (fallback); `split_day_label = "full_body"`
**And** при отсутствии истории (первая тренировка) применяются fallback-значения: PPL стартует с `push`, UL стартует с `upper`, FullBody/custom → `full_body`
**And** применяется `min_rest_days` из `ScienceConfig`: если muscle group тренировалась менее `min_rest_days` назад — она исключается из сегодняшнего плана (предотвращение перетренированности)
**And** для каждой требуемой muscle group выбирается упражнение из библиотеки:
- фильтр по `UserProfile.available_equipment`
- ротация: предпочитает упражнения, не использовавшиеся в последних 2-х сессиях для данной muscle group (rotation_score = дней с последнего использования)
- при равном rotation_score — случайный выбор с `random.seed(date)` (детерминировано для одного дня)
**And** перед генерацией проверяется разрыв с последней сессией: если `today - last_session_date > ScienceConfig.detraining_threshold_days` (например, 14) — все `target_weight_kg` умножаются на `ScienceConfig.detraining_coefficient` (например, 0.85) и в `WorkoutPlan.warnings` добавляется «⚠️ Перерыв [N] дней — веса снижены для безопасного возврата»
**And** проверяется счётчик мезоцикла: если количество `completed` сессий с момента последнего дилоада (или от начала) ≥ `ScienceConfig.deload_trigger_sessions` (например, 16) — в `WorkoutPlan.warnings` добавляется «💤 Рекомендуется дилоад-неделя — [N] недель непрерывной нагрузки»; дилоад не форсируется
**And** каждому упражнению назначается: количество сетов и rep_range из текущей `Methodology`, стартовый вес = последний использованный вес для этого упражнения (из `WorkoutSet`) или для новых упражнений: `UserProfile.bodyweight_kg * initial_weight_coefficients[exercise.movement_pattern.name]`; для `equipment_type=bodyweight` стартовый вес всегда `0.0`; результат умножается на `recovery_signal.coefficient` (если `recovery_signal` передан; иначе коэффициент = 1.0); итоговый `target_weight_kg` округляется через `core.weight_utils.round_to_equipment_increment(weight, exercise.equipment_type)`
**And** план проходит PUOS-валидацию (`validate_puos`) перед возвратом; при нарушении — автоматически сокращается число сетов самого объёмного упражнения
**And** для upper body сессий план проходит antagonist balance проверку: если есть хотя бы одна `is_push=True` мышца — должно быть хотя бы одно `is_pull=True` упражнение, и наоборот; при нарушении — в `WorkoutPlan.warnings` добавляется «⚠️ Дисбаланс: только [push/pull] упражнения — рекомендуется добавить антагонист»; план не блокируется
**And** если для muscle group из сплита нет ни одного упражнения по фильтру оборудования — группа пропускается без ошибки; добавляется в `WorkoutPlan.skipped_groups: list[str]` с причиной `"no_equipment"`; PUOS-валидация и план строятся на оставшихся группах
**And** применение `min_rest_days` не может оставить план полностью пустым: если после исключения групп по `min_rest_days` не остаётся ни одной — ограничение снимается для всех групп и в `WorkoutPlan.warnings` добавляется «⚠️ Нарушен рекомендуемый отдых — недостаточно времени с последней тренировки»
**And** `WorkoutPlan` — датакласс с полями: `muscle_groups_today: list[str]`, `split_day_label: str`, `exercises: list[PlannedExercise]`, `skipped_groups: list[str]` (default: empty), `warnings: list[str]` (default: empty); `PlannedExercise` содержит `exercise_id`, `exercise_name`, `sets`, `rep_range`, `target_weight_kg`
**And** `WorkoutPlan` расширен полем `split_day_label: str` — записывается в `WorkoutSession.split_day_label` через `api/handlers.py` при `workout_start`
**And** `pytest tests/test_core/test_planner.py` проходит:
- корректное чередование upper/lower и ppl-цикл через `split_day_label`
- первая тренировка (пустая история): PPL → `push`, UL → `upper`, FullBody → `full_body`
- пропуск тренировки не сбивает цикл: следующий `split_day_label` всегда следующий по очереди
- recovery_signal=0.6: `target_weight_kg` всех упражнений снижен на 40% относительно last_used_weight
- recovery_signal=None: `target_weight_kg` = last_used_weight без изменений
- нет оборудования для muscle group: группа в `skipped_groups`, план строится на остальных
- все группы заблокированы min_rest_days: ограничение снимается, `warnings` содержит предупреждение
- перерыв >14 дней: `target_weight_kg` снижен на `detraining_coefficient`, `warnings` содержит предупреждение
- перерыв <14 дней: вес не снижается
- счётчик ≥ `deload_trigger_sessions`: `warnings` содержит рекомендацию дилоада
- `target_weight_kg` для barbell упражнения округлён до кратного 2.5кг
- rotation_score: упражнения из последней сессии получают меньший приоритет
- min_rest_days enforcement: группа тренировавшаяся вчера исключается при достаточном количестве других групп
- PUOS auto-reduction срабатывает при превышении

## Story 4.6: Recap и Summary генераторы

As an athlete,
I want to receive a Recap before my workout and a Summary after,
So that I stay informed about my progress and recovery without manual analysis.

**Acceptance Criteria:**

**Given** история тренировок атлета в БД и адаптированный план готовы
**When** OpenClaw отправляет интент `workout_recap`
**Then** `adaptation/recap.py` возвращает журнал предыдущей тренировки: список упражнений, веса и количество повторений по каждому подходу
**And** Recap — фактические данные из БД (последняя `WorkoutSession`), без LLM-генерации
**And** формат: одна строка на подход, например "Жим лёжа: 80кг × 8, 80кг × 7, 77.5кг × 8"
**And** если предыдущей сессии нет — возвращается сообщение "Первая тренировка — история пока пуста"
**When** OpenClaw отправляет интент `workout_summary`
**Then** `adaptation/summary.py` возвращает оценку завершённой тренировки на основе данных БД
**And** Summary включает: общий объём выполненных подходов, оценку усталости по RPE-тренду ("объёмы хорошие" если средний RPE < порога, "видно что устал" если средний RPE высокий или снижались веса к концу)
**And** Summary включает сравнение плана и факта: список выполненных упражнений сопоставляется с `WorkoutSession.planned_exercises`; пропущенные упражнения явно отмечаются («❌ Пропущено: [название]»); выполненные сверхплана — («➕ Дополнительно: [название]»)
**And** пороги RPE для оценки усталости берутся из `ScienceConfig` (не hardcoded)
**And** оба текста формируются gym-coach-brain детерминированно из данных БД, OpenClaw передаёт stdout в Telegram as-is
**And** `pytest tests/test_adaptation/test_recap.py` и `test_summary.py` проходят с seed данными сессий:
- Summary при полном выполнении плана: нет пропущенных, нет дополнительных
- Summary при пропуске упражнения: `❌ Пропущено` присутствует в stdout
- Summary при сверхплановом упражнении: `➕ Дополнительно` присутствует в stdout

---

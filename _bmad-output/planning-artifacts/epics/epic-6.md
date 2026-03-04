# Epic 6: Финальная интеграция и деплой

gym-coach-brain полностью интегрирован как OpenClaw скилл, все интенты реализованы, router.py и SKILL.md обновлены. ML Worker задеплоен как systemd сервис. Основной API остаётся ephemeral subprocess — вызывается router.py по требованию.

> **Модель взаимодействия (важно):** Атлет общается с системой исключительно через естественный язык в Telegram — он не видит exercise_id, команд API или технических деталей. LLM-агент OpenClaw выступает посредником: получает структурированный stdout от gym-coach-brain, переформатирует его в читаемые сообщения для атлета, отслеживает state тренировки (текущее упражнение, номер подхода), и самостоятельно вызывает нужные интенты API когда атлет говорит «сделал» / «закончил» / «устал». gym-coach-brain — детерминированный движок без диалога; весь диалог на стороне LLM-агента.

**Requires:** Epic 5 (завершён)
**FRs covered:** FR11, FR12

## Story 6.1: Полные API handlers для всех тренировочных интентов

As an athlete,
I want to interact with gym-coach-brain through all workout intents via OpenClaw,
So that the complete training workflow is available through Telegram chat.

**Acceptance Criteria:**

**Given** Epic 3, 4, 5 завершены — все модули готовы
**When** агент дописывает `api/handlers.py` для всех интентов
**Then** реализованы handlers для: `workout_start`, `workout_log_set`, `workout_finish`, `workout_recap`, `workout_summary`, `workout_status`, `readiness_log`
**And** при `workout_start` — перед созданием новой сессии проверяются условия:

- если существует сессия со статусом `in_progress` (любой даты): возвращается `exit_code:1`, `stdout` содержит дату и id orphaned-сессии, флаг `orphaned_session: true` в JSON — агент предлагает атлету завершить её; новая сессия не создаётся
- если существует `completed` сессия с `session_date = today`: возвращается `exit_code:1`, флаг `second_session_today: true`, текущий `split_day_label` сегодняшней сессии — агент уточняет у атлета; повторный вызов с параметром `confirm_second=true` создаёт новую сессию с тем же `split_day_label` (PPL-цикл не сдвигается)

**And** каждый handler возвращает корректный JSON контракт `{intent, argv, stdout, exit_code}`
**And** `exit_code: 0` — success, `exit_code: 1` — user error, `exit_code: 2` — system error
**And** `ScienceLimitError` конвертируется в `exit_code: 1` с понятным сообщением
**And** при `workout_start` выполняется последовательно:

1. handler загружает `ReadinessLog` за сегодня (если есть) → вычисляет `RecoverySignal` через `core/readiness.py`; при отсутствии лога — `recovery_signal=None` (Planner использует коэффициент 1.0)
2. вызывается `WorkoutPlanner.generate(user_profile, science, db_session, recovery_signal)` — генерируется полный план сессии с весами, скорректированными на коэффициент восстановления
3. создаётся `WorkoutSession` в БД со статусом `in_progress`, план сохраняется как `WorkoutSession.planned_exercises` (JSON)
4. автоматически создаётся PREDICT job в `ml_jobs`
5. stdout возвращает план в формате: «Сегодня — [группы мышц]\n\n1. [Упражнение] (id:[exercise_id]): [N]×[rep_range] @ [вес]кг\n2. ...» — `exercise_id` обязателен в каждой строке для использования LLM-агентом OpenClaw при последующих вызовах `workout_log_set`; атлет видит только читаемое имя упражнения в переформатированном сообщении агента
6. `WorkoutSession.split_day_label` сохраняется из `WorkoutPlan.split_day_label`

**And** при `workout_status`:

- если есть `in_progress` сессия: возвращает `WorkoutSession.planned_exercises` (полный план) + все залоггированные `WorkoutSet` этой сессии в stdout; формат: план со статусом каждого упражнения («✅ [сделано сетов]/[запланировано]» vs «⏳ ещё не начато»); `exit_code:0`
- если `in_progress` сессии нет: `exit_code:1`, «Нет активной тренировки»

**And** при `workout_log_set` с параметрами `exercise_id`, `set_number`, `weight_kg`, `rir`:

- входные данные валидируются перед сохранением: `weight_kg >= 0.0`, `reps >= 1`, `rir` ∈ `[0, 4]`; нарушение → `exit_code:1`, «Некорректные данные: [поле]=[значение], допустимо: [диапазон]»
- `rir` (Integer 0–4) сохраняется в `WorkoutSet.rir`
- `rpe` вычисляется как `10.0 - rir` и сохраняется в `WorkoutSet.rpe`
- stdout содержит рекомендацию на следующий сет: скорректированный вес по APRE/Double Progression с кратким обоснованием
- если `set_number` превышает плановое количество сетов для данного `exercise_id` в `WorkoutSession.planned_exercises`: подход логируется (`exit_code:0`), но stdout дополняется предупреждением «⚠️ Этот подход сверх плана ([set_number]/[planned_sets]). Следи за PUOS-лимитом»
- если `(session_id, exercise_id, set_number)` уже существует в `WorkoutSet`: возвращается `exit_code:1`, «Подход №[N] для этого упражнения уже залоггирован»; данные не перезаписываются

**And** при `workout_finish`:

- статус `WorkoutSession` обновляется на `completed`
- автоматически вызывается `adaptation/summary.py` и Summary возвращается в stdout (атлет не должен вызывать `workout_summary` вручную после завершения сессии)
- если `WorkoutSession` не найдена или уже `completed` — возвращается `exit_code: 1` с понятным сообщением

**And** `workout_summary` остаётся отдельным интентом для повторного просмотра Summary завершённых сессий по запросу атлета
**And** `pytest tests/test_api/test_handlers.py` покрывает все интенты включая:

- `workout_start`: orphaned session → `exit_code:1` + флаг; second session today → `exit_code:1` + флаг; confirm_second=true → успешный старт с тем же `split_day_label`; recovery_signal применяется к начальным весам; план содержит `exercise_id` в stdout; `split_day_label` сохранён в `WorkoutSession`
- `workout_log_set`: входная валидация (weight<0, reps<1, rir>4) → `exit_code:1`; RIR→RPE конвертация; сверхплановый set_number → предупреждение при `exit_code:0`; дублирующий set_number → `exit_code:1`
- `workout_status`: активная сессия → план со статусами; нет сессии → `exit_code:1`
- `workout_finish`: статус → `completed`; auto-Summary в stdout; повторный вызов → `exit_code:1`
- error paths для всех интентов

## Story 6.2: Fractional volume analytics

As an athlete,
I want to see my historical fractional training volume by muscle group,
So that I can verify the system is distributing load correctly across muscle groups.

**Acceptance Criteria:**

**Given** история тренировок в БД и таблица `exercises` с метаданными мышц
**When** OpenClaw отправляет интент `volume_report` с параметром `weeks=N`
**Then** возвращается текстовый отчёт с фракционным объёмом по каждой группе мышц за N недель
**And** объём рассчитывается как: агонист × 1.0 + синергист × 0.5 (из `muscle_groups` метаданных)
**And** отчёт включает сравнение с рекомендуемыми диапазонами из ScienceConfig
**And** группы мышц с превышением PUOS лимита за период помечаются `⚠️`
**And** `pytest tests/test_api/test_handlers.py::test_volume_report` проходит с seed данными

## Story 6.3: Интеграция с OpenClaw — router.py и SKILL.md

As a dev agent,
I want to update router.py and SKILL.md to point to the new gym-coach-brain API,
So that OpenClaw routes all gym coaching intents to the new modular system.

**Acceptance Criteria:**

**Given** `api/main.py` принимает все интенты и возвращает корректный JSON контракт
**When** агент обновляет `workspace/skills/gym-coach/router.py` и `workspace/skills/gym-coach/SKILL.md`
**Then** `router.py` вызывает `python -m gym_coach_brain.api` вместо `gym_coach.py`
**And** `SKILL.md` обновлён: удалён `system_prompt: coach-prompt.md`, обновлён entry point
**And** `SKILL.md` содержит полный список поддерживаемых интентов с примерами
**And** старый `gym_coach.py` удалён из репозитория
**And** интеграционный тест `pytest tests/test_api/test_contract.py` проходит: OpenClaw → router.py → api/main.py → корректный JSON
**And** E2E тест `pytest tests/test_api/test_e2e.py` проходит — полный тренировочный цикл на seed DB: `onboarding_complete` (с `bodyweight_kg`) → `readiness_log` → `workout_start` (план возвращён с exercise_ids) → `workout_status` (показывает 0/N сетов) → `workout_log_set` ×3 → `workout_status` (показывает прогресс) → `workout_finish` → проверяет: `WorkoutSession.status=completed`, `WorkoutSet` записи присутствуют, Summary содержит план vs факт сравнение

## Story 6.4: Деплой — ML Worker systemd и CI/CD валидация

> **Архитектурное примечание:** `gym-coach-brain` main API — ephemeral subprocess (не daemon). Его вызывает `router.py` напрямую через `subprocess.run`, он отрабатывает и завершается. Systemd сервис нужен **только** для ML Worker.

As a dev agent,
I want to deploy the ML Worker as a systemd service with CI validation,
So that background model training runs reliably on VPS with automated quality gates.

**Acceptance Criteria:**

**Given** ML Worker реализован и протестирован (Story 5.3)
**When** агент создаёт systemd unit файл и обновляет CI pipeline
**Then** `systemd/gym-coach-brain-ml.service` запускает `python -m gym_coach_brain.ml` с `MemoryLimit=8G` и `Restart=on-failure`
**And** сервис использует `DATABASE_URL` и `MODEL_DIR` env vars из systemd `EnvironmentFile`
**And** основной `gym-coach-brain` API вызывается как ephemeral subprocess через `router.py` — никакого отдельного сервиса не создаётся
**And** `.github/workflows/ci.yml` запускает полный `pytest` suite на push/PR
**And** `README.md` содержит инструкции деплоя: `systemctl enable/start gym-coach-brain-ml` и как router.py вызывает API
**And** `uv run pytest` проходит полностью на чистой машине без дополнительных зависимостей

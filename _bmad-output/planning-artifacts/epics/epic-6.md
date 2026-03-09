# Epic 6: Telegram Bot — финальная интеграция и деплой

gym-coach-brain обёрнут в standalone Telegram бот с LLM-агентом на OpenRouter. Бот реализован на aiogram с абстракцией `BaseChannel` для будущей совместимости с OpenClaw. ML Worker задеплоен как systemd сервис.

> **Модель взаимодействия:** Атлет общается в Telegram на естественном языке. LLM-агент (GPT/Claude через OpenRouter) выступает посредником: форматирует ответы, отслеживает контекст тренировки, вызывает gym-coach-brain интенты через tool calling. gym-coach-brain — детерминированный движок без диалога; весь диалог на стороне LLM-агента. Атлет никогда не видит `exercise_id`, JSON или технических деталей.
>
> **Совместимость с OpenClaw:** Архитектура построена на `BaseChannel` интерфейсе (паттерн из nanobot). Добавление `OpenClawChannel(BaseChannel)` в будущем не требует переписывания AgentLoop или tool calling логики.

**Requires:** Epic 5 (завершён)
**FRs covered:** FR11, FR12

---

## Story 6.1: Полные API handlers для всех тренировочных интентов

As an athlete,
I want all workout intents to be handled by gym-coach-brain,
So that the complete training workflow is available as a deterministic backend API.

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

1. handler загружает `sleep_hours` и `pre_readiness` из текущей сессии (должны быть записаны до вызова через pre-workout check-in в боте); если отсутствуют — `recovery_signal=None`
2. handler загружает `ReadinessLog` за сегодня (если есть) → вычисляет `RecoverySignal` через `core/readiness.py`
3. вызывается `WorkoutPlanner.generate(user_profile, science, db_session, recovery_signal)` — генерируется полный план сессии с весами, скорректированными на коэффициент восстановления
4. создаётся `WorkoutSession` в БД со статусом `in_progress`, план сохраняется как `WorkoutSession.planned_exercises` (JSON)
5. автоматически создаётся PREDICT job в `ml_jobs` (см. Contract Snapshot v3, п.9)
6. stdout возвращает план в формате: «Сегодня — [группы мышц]\n\n1. [Упражнение] (id:[exercise_id]): [N]×[rep_range] @ [вес]кг\n2. ...» — `exercise_id` обязателен в каждой строке для использования LLM-агентом при последующих вызовах `workout_log_set`; атлет видит только читаемое имя упражнения
7. `WorkoutSession.split_day_label` сохраняется из `WorkoutPlan.split_day_label`

**And** при `workout_status`:

- если есть `in_progress` сессия: возвращает `WorkoutSession.planned_exercises` (полный план) + все залоггированные `WorkoutSet` этой сессии; формат: план со статусом каждого упражнения («✅ [сделано сетов]/[запланировано]» vs «⏳ ещё не начато»); `exit_code:0`
- если `in_progress` сессии нет: `exit_code:1`, «Нет активной тренировки»

**And** при `workout_log_set` с параметрами `exercise_id`, `set_number`, `weight_kg`, `rir`:

- входные данные валидируются перед сохранением: `weight_kg >= 0.0`, `reps >= 1`, `rir` ∈ `[0, 4]`; нарушение → `exit_code:1`, «Некорректные данные: [поле]=[значение], допустимо: [диапазон]»
- `rir` (Integer 0–4) сохраняется в `WorkoutSet.rir`
- `rpe` вычисляется как `10.0 - rir` и сохраняется в `WorkoutSet.rpe`
- stdout содержит рекомендацию на следующий сет: скорректированный вес по APRE/Double Progression с кратким обоснованием
- если `set_number` превышает плановое количество сетов: подход логируется (`exit_code:0`), stdout дополняется предупреждением «⚠️ Этот подход сверх плана ([set_number]/[planned_sets]). Следи за PUOS-лимитом»
- если `(session_id, exercise_id, set_number)` уже существует: возвращается `exit_code:1`, «Подход №[N] уже залоггирован»; данные не перезаписываются

**And** при `workout_finish`:

- статус `WorkoutSession` обновляется на `completed`
- автоматически вызывается `adaptation/summary.py`, Summary возвращается в stdout
- если `WorkoutSession` не найдена или уже `completed` — `exit_code: 1`

**And** `workout_summary` остаётся отдельным интентом для повторного просмотра Summary по запросу
**And** `pytest tests/test_api/test_handlers.py` покрывает все интенты включая:

- `workout_start`: orphaned session; second session today; confirm_second=true; recovery_signal; exercise_id в stdout; split_day_label сохранён
- `workout_log_set`: валидация; RIR→RPE; сверхплановый set_number; дублирующий set_number
- `workout_status`: активная сессия; нет сессии
- `workout_finish`: статус completed; auto-Summary; повторный вызов
- error paths для всех интентов

---

## Story 6.2: Fractional volume analytics

As an athlete,
I want to see my historical fractional training volume by muscle group,
So that I can verify the system is distributing load correctly across muscle groups.

**Acceptance Criteria:**

**Given** история тренировок в БД и таблица `exercises` с метаданными мышц
**When** LLM-агент вызывает tool `volume_report` с параметром `weeks=N`
**Then** gym-coach-brain возвращает текстовый отчёт с фракционным объёмом по каждой группе мышц за N недель
**And** объём рассчитывается как: агонист × 1.0 + синергист × 0.5 (из `muscle_groups` метаданных)
**And** отчёт включает сравнение с рекомендуемыми диапазонами из ScienceConfig
**And** группы мышц с превышением PUOS лимита за период помечаются `⚠️`
**And** `pytest tests/test_api/test_handlers.py::test_volume_report` проходит с seed данными

---

## Story 6.3: Telegram Bot scaffold — aiogram + BaseChannel + MessageBus

As a dev agent,
I want to implement the Telegram bot infrastructure with a channel abstraction layer,
So that the bot is decoupled from transport and can be extended with OpenClaw compatibility in the future.

**Acceptance Criteria:**

**Given** aiogram установлен, `TELEGRAM_BOT_TOKEN` доступен через env var
**When** агент реализует `bot/` модуль
**Then** структура `bot/` содержит:
- `bot/channels/base.py` — `BaseChannel` абстрактный класс с методами `send(text, buttons)`, `receive() -> Message`, `user_id`
- `bot/channels/telegram.py` — `TelegramChannel(BaseChannel)` на aiogram 3.x с long polling
- `bot/bus.py` — `MessageBus` с `asyncio.Queue` inbound/outbound; методы `publish_inbound()`, `consume_inbound()`, `publish_outbound()`, `consume_outbound()`
- `bot/state.py` — `UserState` с полями: `pending_checkin_sleep: bool`, `pending_checkin_readiness: bool`, `pending_postcheckin: bool`, `active_session_id: int | None`
- `bot/main.py` — точка входа: инициализация `TelegramChannel` + `MessageBus` + запуск polling

**And** pre-workout check-in реализован как детерминированный flow (не LLM):
- `/workout` → бот отправляет inline keyboard «Как спал? 💤» с кнопками `[< 6ч]` `[6–7ч]` `[7–8ч]` `[8+ ч]`
- после ответа → inline keyboard «Как себя чувствуешь? 💪» с кнопками `[😴 Разбит]` `[😐 Норм]` `[💪 Огонь]`
- после обоих ответов: `sleep_hours` и `pre_readiness` записываются в сессию через gym-coach-brain API, `pending_checkin_*` сбрасываются, управление передаётся в AgentLoop (Story 6.4)

**And** post-workout check-in реализован аналогично:
- после `workout_finish` → inline keyboard «Как прошла тренировка?» с кнопками `[😓 Тяжело]` `[👌 В самый раз]` `[😤 Слишком легко]`
- после ответа: `post_feeling` записывается в сессию, бот возвращается в свободный чат

**And** пока `pending_checkin_*=True` — все текстовые сообщения атлета игнорируются, бот повторно показывает кнопки
**And** `TelegramChannel` регистрирует handlers для text, callback_query (inline buttons), команды `/workout`, `/status`, `/stop`
**And** архитектура позволяет добавить `OpenClawChannel(BaseChannel)` в будущем без изменений в `bus.py` и AgentLoop
**And** `pytest tests/test_bot/test_channel.py` покрывает: check-in flow (кнопки → запись в сессию), state transitions, игнорирование текста при pending_checkin

---

## Story 6.4: AgentLoop — LLM Agent + OpenRouter + Tool Calling

As a dev agent,
I want to implement the LLM agent loop with OpenRouter integration and gym-coach-brain tool calling,
So that the athlete can have natural language conversations with a personal trainer that manages the full workout flow.

**Acceptance Criteria:**

**Given** `bot/bus.py` и `bot/channels/telegram.py` готовы (Story 6.3)
**When** агент реализует `bot/agent.py`
**Then** `class AgentLoop` реализует:
- чтение сообщений из `MessageBus.consume_inbound()`
- вызов OpenRouter API (провайдер конфигурируется через `OPENROUTER_API_KEY` и `OPENROUTER_MODEL` env vars)
- tool calling loop: до 10 итераций за сообщение; tool results возвращаются как `role: tool` сообщения в контекст
- запись ответов в `MessageBus.publish_outbound()`

**And** системный промпт загружается из `bot/prompts/system.md` (не hardcoded), содержит:
- персонаж тренера: «Ты персональный тренер-коуч с глубокими знаниями спортивной науки. Общаешься по-русски, дружелюбно и мотивирующе. Не показываешь техническую информацию (exercise_id, JSON, exit_code) атлету.»
- инструкции по использованию tools: когда вызывать, как интерпретировать exit_code
- правила форматирования ответов для Telegram

**And** gym-coach-brain интенты реализованы как tools (OpenAI function calling schema):

| Tool | Описание | Параметры |
|---|---|---|
| `workout_start` | Начать тренировку (после check-in) | — |
| `workout_log_set` | Залоггировать подход | `exercise_id`, `set_number`, `weight_kg`, `reps`, `rir` |
| `workout_finish` | Завершить тренировку | — |
| `workout_status` | Статус текущей тренировки | — |
| `workout_summary` | Recap завершённой сессии | `session_id?` |
| `readiness_log` | Записать readiness (используется из check-in flow) | `sleep_hours`, `pre_readiness` |
| `volume_report` | Отчёт по объёму | `weeks` |

**And** каждый tool вызывается через `subprocess.run(['python', '-m', 'gym_coach_brain.api', '--intent', tool_name, ...], capture_output=True)` и парсит JSON stdout
**And** при `exit_code: 1` — AgentLoop передаёт понятное сообщение атлету (не техническую ошибку)
**And** при `exit_code: 2` — логирует `ERROR` и сообщает атлету «Что-то пошло не так, попробуй ещё раз»
**And** AgentLoop получает `UserState` из `bot/state.py` и включает его в контекст каждого запроса к LLM (текущее упражнение, номер подхода, active_session_id)
**And** история диалога ограничена последними N=20 сообщениями (configurable) для контроля токенов
**And** `OPENROUTER_MODEL` по умолчанию: `openai/gpt-4o` (легко меняется через env)
**And** `pytest tests/test_bot/test_agent.py` покрывает: tool calling → subprocess mock → корректный parse JSON; exit_code:1 → дружественный ответ; exit_code:2 → error handling; history truncation
**And** E2E тест `pytest tests/test_bot/test_e2e.py` проходит полный цикл на mock LLM + seed DB:
  check-in кнопки → `workout_start` tool → план в чате → `workout_log_set` ×3 → `workout_finish` tool → post check-in кнопки → Summary в чате

---

## Story 6.5: Деплой — ML Worker systemd и CI/CD

As a dev agent,
I want to deploy the ML Worker as a systemd service and the Telegram bot as a daemon with CI validation,
So that the full system runs reliably on VPS with automated quality gates.

> **Архитектурное примечание:** gym-coach-brain main API — ephemeral subprocess (не daemon). Его вызывает AgentLoop через `subprocess.run`, он отрабатывает и завершается. Systemd сервисы нужны для ML Worker и Telegram бота.

**Acceptance Criteria:**

**Given** ML Worker (Story 5.3) и Telegram Bot (Stories 6.3, 6.4) реализованы
**When** агент создаёт systemd unit файлы и обновляет CI pipeline
**Then** `systemd/gym-coach-brain-ml.service` запускает `python -m gym_coach_brain.ml` с `MemoryLimit=8G` и `Restart=on-failure`
**And** `systemd/gym-coach-brain-bot.service` запускает `python -m bot.main` с `Restart=on-failure`
**And** оба сервиса используют env vars из общего `systemd/gym-coach-brain.env`: `DATABASE_URL`, `MODEL_DIR`, `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`
**And** `.github/workflows/ci.yml` запускает полный `pytest` suite на push/PR (без реального Telegram/OpenRouter — всё замокано)
**And** `README.md` содержит инструкции деплоя:
  - `systemctl enable/start gym-coach-brain-ml`
  - `systemctl enable/start gym-coach-brain-bot`
  - как настроить `.env` файл
  - как получить Telegram bot token и OpenRouter API key
**And** `uv run pytest` проходит полностью на чистой машине без дополнительных зависимостей

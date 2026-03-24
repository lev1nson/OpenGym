# Story 6.3: Telegram Bot scaffold — aiogram + BaseChannel + MessageBus

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to implement the Telegram bot infrastructure with a channel abstraction layer,
so that the bot is decoupled from transport and can be extended with OpenClaw compatibility in the future.

## Acceptance Criteria

1. The Telegram bot scaffold is implemented as an installable Python package that preserves the repo’s `src` layout.
   - Create `gym-coach-brain/src/bot/` as the top-level package so `python -m bot.main` works after installation.
   - Do not place runtime bot code in the repository root or inside `gym_coach_brain/api/`.

2. Runtime and dependency constraints are made explicit before bot code is added.
   - Add `aiogram` as a runtime dependency in `gym-coach-brain/pyproject.toml`.
   - Add `pytest-asyncio` as a dev dependency for async bot tests.
   - Reconcile Python support with upstream `aiogram` requirements so the project does not implicitly claim unsupported Python 3.15+ compatibility.

3. `bot/channels/base.py` defines a transport-neutral channel abstraction.
   - `BaseChannel` remains independent of aiogram-specific message and markup types.
   - The abstraction includes `send(text, buttons)`, `receive()`, and `user_id`, but button and message payloads are normalized to internal dataclasses or typed value objects.
   - Future `OpenClawChannel(BaseChannel)` must be able to reuse the same abstraction without changes to `bot/bus.py`.

4. `bot/channels/telegram.py` implements `TelegramChannel(BaseChannel)` on aiogram 3.x using current router/polling patterns.
   - Use aiogram 3 `Router` / `Dispatcher` style, not legacy v2 executor patterns.
   - Register handlers for text messages, `callback_query`, and commands `/workout`, `/status`, `/stop`.
   - Long polling starts from `bot/main.py`.

5. `bot/bus.py` provides a transport-independent `MessageBus` with separate inbound and outbound queues.
   - Back the bus with `asyncio.Queue`.
   - Expose `publish_inbound()`, `consume_inbound()`, `publish_outbound()`, and `consume_outbound()`.
   - The bus API is typed and suitable for the future AgentLoop in Story 6.4.

6. `bot/state.py` provides per-user state for deterministic check-in orchestration.
   - Minimum fields from Epic 6 are present: `pending_checkin_sleep`, `pending_checkin_readiness`, `pending_postcheckin`, `active_session_id`.
   - The implementation also preserves the selected sleep bucket between the first and second check-in steps via an explicit transient field or an equivalently clear mechanism; this must not be hidden in globals or callback-data parsing tricks.

7. Pre-workout check-in is implemented as a deterministic bot-local flow and does not invoke the future LLM layer.
   - `/workout` shows sleep buttons mapped to the backend-approved values `5.0`, `6.5`, `7.5`, `9.0`.
   - After sleep selection, the bot shows readiness buttons mapped to `2`, `5`, `9`.
   - After both inputs are captured, the bot triggers the backend through the API boundary used by Epic 6, writes `sleep_hours` and `pre_readiness` to the workout session creation flow, stores `active_session_id` when the backend surface provides it, clears pending flags, and hands control off through the inbound bus seam for Story 6.4.

8. Pending deterministic check-in state strictly blocks free-form chat.
   - While `pending_checkin_sleep=True` or `pending_checkin_readiness=True`, arbitrary text messages are ignored for orchestration purposes and the correct inline keyboard is shown again.
   - Inline button payloads are deterministic, compact, and safe for Telegram callback data constraints.

9. Post-workout check-in is supported without coupling the bot directly to the database layer.
   - When `pending_postcheckin=True`, callback buttons map to the backend-approved `post_feeling` values `2`, `5`, `9`.
   - Persisting `post_feeling` must go through a backend-facing seam, not direct SQLAlchemy writes from `bot/`.
   - If the current backend lacks a dedicated intent for `post_feeling`, add the narrowest additive API hook needed for bot integration rather than bypassing the API boundary.

10. Command behavior is scoped correctly for Story 6.3.
   - `/status` routes through the existing workout-status backend surface when available.
   - `/stop` only clears local pending conversation/check-in state and does not invent new workout-abort semantics in the backend.
   - Story 6.3 does not implement AgentLoop, OpenRouter, tool-calling, or conversational coaching logic.

11. Automated coverage proves the transport scaffold and deterministic state machine.
   - `pytest gym-coach-brain/tests/test_bot/test_channel.py` covers pre-workout check-in button flow, state transitions, ignored text while pending, and Telegram callback handling.
   - Bot tests avoid real Telegram network calls.
   - Existing backend handler tests continue to pass after dependency and packaging changes.

## Tasks / Subtasks

- [x] Task 1: Add runtime and test dependencies for the bot scaffold (AC: 2)
  - [x] Add `aiogram` to `gym-coach-brain/pyproject.toml`.
  - [x] Add `pytest-asyncio` to the dev dependency group.
  - [x] Reconcile `requires-python` with the supported `aiogram` range so CI and packaging do not advertise unsupported Python versions.

- [x] Task 2: Create the bot package skeleton in the correct place (AC: 1, 3-5)
  - [x] Create `gym-coach-brain/src/bot/__init__.py`.
  - [x] Create `gym-coach-brain/src/bot/channels/base.py`.
  - [x] Create `gym-coach-brain/src/bot/channels/telegram.py`.
  - [x] Create `gym-coach-brain/src/bot/bus.py`.
  - [x] Create `gym-coach-brain/src/bot/state.py`.
  - [x] Create `gym-coach-brain/src/bot/main.py`.

- [x] Task 3: Define transport-neutral message and button primitives (AC: 3, 8)
  - [x] Introduce a minimal internal message type that does not leak aiogram classes across the channel boundary.
  - [x] Introduce a minimal button specification that can be rendered as Telegram inline keyboards today and reused by a future `OpenClawChannel`.
  - [x] Keep callback payloads deterministic and short.

- [x] Task 4: Implement `MessageBus` on top of `asyncio.Queue` (AC: 5)
  - [x] Provide separate inbound and outbound queues.
  - [x] Keep API names aligned with the Epic: `publish_inbound()`, `consume_inbound()`, `publish_outbound()`, `consume_outbound()`.
  - [x] Add graceful shutdown semantics only if they remain simple and testable; do not overdesign the bus in this story.

- [x] Task 5: Implement `TelegramChannel` with aiogram 3 routing and polling hooks (AC: 3-4, 8, 10)
  - [x] Register text handlers, callback-query handlers, and `/workout`, `/status`, `/stop`.
  - [x] Adapt Telegram updates into the transport-neutral message type.
  - [x] Render inline keyboards for deterministic check-ins through the normalized button abstraction.

- [x] Task 6: Implement the deterministic pre-workout check-in controller (AC: 6-8, 10)
  - [x] `/workout` starts the sleep → readiness button flow.
  - [x] Persist the selected sleep bucket across the two-step interaction without globals.
  - [x] Call the backend through the Epic 6 API seam after both values are collected.
  - [x] Reset pending state and publish the handoff event for future AgentLoop consumption.

- [x] Task 7: Implement the post-workout check-in seam and command-local state resets (AC: 9-10)
  - [x] Support `pending_postcheckin=True` with deterministic callback handling.
  - [x] Persist `post_feeling` through a backend-facing seam, not direct DB writes from the bot layer.
  - [x] Keep `/stop` limited to clearing local transport state.

- [x] Task 8: Add focused async tests for the bot scaffold (AC: 11)
  - [x] Add `gym-coach-brain/tests/test_bot/test_channel.py`.
  - [x] Mock the Telegram layer and backend adapter so tests remain local and deterministic.
  - [x] Cover sleep check-in, readiness check-in, pending-text ignore behavior, callback routing, and command behavior.

- [x] Task 9: Verification (AC: 1-11)
  - [x] Run `uv run pytest gym-coach-brain/tests/test_bot/test_channel.py`.
  - [x] Run `uv run pytest gym-coach-brain/tests/test_api/test_handlers.py`.
  - [x] Run `uv run pytest gym-coach-brain/tests/test_api/test_readiness_handler.py`.

## Dev Notes

### Developer Context

- This story is the transport scaffold for Epic 6, not the conversational brain.
  - The current repo contains no `bot/` package at all.
  - Story 6.4 will add AgentLoop + OpenRouter; Story 6.3 must stop at channel, bus, and deterministic check-in orchestration.

- The current backend already stores the exact workout-session fields that the Telegram check-in flow needs.
  - `gym-coach-brain/src/gym_coach_brain/data/models.py` already defines `WorkoutSession.sleep_hours`, `WorkoutSession.pre_readiness`, and `WorkoutSession.post_feeling`.
  - `handle_workout_start()` already requires `--sleep-hours` and `--pre-readiness` and persists them on the created `WorkoutSession`.

- The existing `readiness_log` API is not the right integration surface for the Telegram pre-workout buttons.
  - `handle_readiness_log()` currently expects `--sleep` and `--stress` with optional `--hrv`, and writes a standalone `ReadinessLog`.
  - The Telegram pre-workout flow from Epic 6 must drive the workout-start/session path, not misuse `readiness_log` for a different schema and UX.

- There is a hidden backend dependency for post-workout check-in.
  - The current repo exposes `WorkoutSession.post_feeling` in the ORM, but there is no dedicated public bot-facing handler yet for saving that field.
  - The implementation should add the narrowest backend-facing seam needed instead of opening a direct SQLAlchemy session inside the bot layer.

- There is another hidden state-model dependency in the Epic text.
  - The Epic’s listed `UserState` fields are not sufficient by themselves to carry the selected sleep button between the first and second callback step.
  - Story 6.3 should make that transient value explicit rather than reconstructing it from brittle callback state or module globals.

- Current repo reality should drive the story more than legacy docs.
  - `gym-coach-brain/src/gym_coach_brain/__init__.py` still only prints `"Hello from gym-coach-brain!"`.
  - `docs/api-contracts.md` and `docs/architecture.md` still describe older `router.py` / `gym_coach.py` flows and outdated natural-language routing assumptions.
  - Epic 6 and the current modular Python package are the source of truth for this story, not the legacy CLI narrative.

- Story sequencing matters.
  - Story 6.1 defines the API boundary that the bot should call.
  - Story 6.2 adds analytics but does not create any bot transport surface.
  - Story 6.3 should therefore call the backend through a narrow adapter that can target the 6.1 API entrypoint once merged, rather than importing deep internal functions throughout the bot layer.

### Technical Requirements

- Keep the bot transport-neutral at the abstraction boundary.
  - `BaseChannel` must not expose aiogram `Message`, `CallbackQuery`, `InlineKeyboardMarkup`, or `InlineKeyboardButton` types directly to the rest of the bot stack.
  - Use a small internal message/button model so `TelegramChannel` is an adapter, not the domain shape.

- Keep callback payloads compact and deterministic.
  - Telegram callback data is size-constrained, so use short stable tokens such as `sleep:5.0`, `ready:5`, `post:9`, or an equivalently small format.
  - Do not serialize JSON blobs or arbitrary free text into callback payloads.

- Keep backend access behind a dedicated adapter seam.
  - The bot should not import SQLAlchemy session factories or mutate ORM rows directly.
  - The clean path is a small backend client/helper that calls the gym-coach-brain API boundary for `workout_start`, `workout_status`, and the additive post-check-in hook if needed.
  - If Story 6.1 is not yet merged in code, keep the adapter narrow so it can be switched to `python -m gym_coach_brain.api --intent ...` later without rewriting the state machine.

- Preserve the existing check-in value semantics from the backend.
  - Sleep buttons map to `5.0`, `6.5`, `7.5`, `9.0`.
  - Pre-readiness buttons map to `2`, `5`, `9`.
  - Post-workout feeling buttons map to `2`, `5`, `9`.
  - Do not invent alternate numeric scales in the bot layer.

- Treat `active_session_id` as real state, not a placeholder field.
  - Populate it from the backend response when a workout session is successfully created or resumed.
  - Clear it only when the local bot state intentionally leaves the active-session context.

- Keep command semantics narrow and deterministic.
  - `/workout` starts the pre-workout flow.
  - `/status` is a deterministic transport command that surfaces backend workout status.
  - `/stop` clears local pending interaction state only; it does not cancel an active workout in the backend because that intent does not exist in the modular API yet.

- Avoid accidental scope creep into Story 6.4.
  - No OpenRouter client.
  - No tool-calling loop.
  - No LLM prompt loading.
  - No free-chat coach persona.
  - The only handoff needed in this story is publishing a normalized inbound event to the bus after deterministic check-in completes.

### Architecture Compliance

- Respect the intended boundary between transport, orchestration, and backend domain logic.
  - `bot/` owns Telegram transport and deterministic pre/post check-in orchestration.
  - `gym_coach_brain.api` owns workout/session mutations and status retrieval.
  - `gym_coach_brain.data` and SQLAlchemy models remain behind the backend boundary.

- Preserve the repo’s Python architectural rules.
  - Use absolute imports only.
  - Keep type hints on public functions and message/state types.
  - Keep side effects explicit and local.

- Do not let Telegram-specific details leak into the future OpenClaw-compatible surface.
  - `BaseChannel.user_id` should be normalized in a transport-agnostic way.
  - Button handling should be expressed in the internal abstraction, then rendered into Telegram inline keyboards by the Telegram adapter.

- Keep deterministic check-in logic separate from the future conversational loop.
  - The bot may respond directly with inline keyboards during the check-in flow.
  - The bus exists to hand off free-chat or post-check-in events to the future AgentLoop, not to force every button tap through an unnecessary queue pipeline in this story.

### Library / Framework Requirements

- Use current aiogram 3.x patterns, not legacy tutorials.
  - Build Telegram routing around aiogram `Router` / `Dispatcher`.
  - Start long polling from the dispatcher entrypoint in `bot/main.py`.
  - Do not introduce deprecated aiogram v2 executor-style code.

- Respect the repo’s Python packaging reality.
  - `gym-coach-brain/pyproject.toml` currently declares `requires-python = ">=3.14"`.
  - Upstream `aiogram` currently requires Python `<3.15, >=3.10`.
  - The implementation must reconcile that mismatch explicitly rather than silently relying on a local interpreter that happens to work today.

- Keep async primitives simple and standard-library based.
  - Use `asyncio.Queue` for the bus.
  - If graceful queue draining is implemented, follow the documented `put` / `get` / `task_done` / `join` lifecycle rather than inventing custom queue bookkeeping.

- Use Telegram inline keyboards for deterministic button flows.
  - Inline keyboards are the correct fit for callback-driven sleep/readiness/post-feeling selection.
  - Keep callback payloads within Telegram’s documented callback-data constraints.

- Avoid unnecessary framework additions.
  - No Redis, Celery, FSM storage backend, or HTTP server is needed for Story 6.3.
  - In-memory per-user state is sufficient for the single-athlete system described in the architecture unless a later story explicitly changes that assumption.

### File Structure Requirements

- Primary files expected to be created:
  - `gym-coach-brain/src/bot/__init__.py`
  - `gym-coach-brain/src/bot/channels/base.py`
  - `gym-coach-brain/src/bot/channels/telegram.py`
  - `gym-coach-brain/src/bot/bus.py`
  - `gym-coach-brain/src/bot/state.py`
  - `gym-coach-brain/src/bot/main.py`
  - `gym-coach-brain/tests/test_bot/test_channel.py`

- Existing files expected to be modified:
  - `gym-coach-brain/pyproject.toml`
  - `gym-coach-brain/src/gym_coach_brain/api/__main__.py` only if Story 6.1 is merged incompletely and the bot adapter needs the intended API entrypoint
  - `gym-coach-brain/src/gym_coach_brain/api/main.py` only if Story 6.1 is merged incompletely and the additive post-check-in hook must be added
  - `gym-coach-brain/src/gym_coach_brain/api/handlers.py` only if the narrow post-check-in API hook is added here

- File placement guardrail:
  - Keep the new bot package under `gym-coach-brain/src/` so it remains part of the installed Python distribution.
  - Do not create a parallel root-level `bot/` directory outside the packaged `src` tree.

- Test file placement guardrail:
  - Add bot tests under `gym-coach-brain/tests/test_bot/`.
  - Keep them isolated from backend handler tests by mocking the backend adapter and Telegram transport where possible.

### Testing Requirements

- Add async coverage for the deterministic Telegram state machine.
  - `/workout` shows the sleep keyboard.
  - Sleep callback advances to the readiness keyboard.
  - Readiness callback invokes the backend adapter with the expected numeric values and clears pending flags.
  - While pending check-in, free-form text is ignored and the correct keyboard is re-shown.

- Cover post-workout check-in behavior explicitly.
  - When `pending_postcheckin=True`, a valid callback persists the mapped `post_feeling` value through the backend seam.
  - Non-callback text while `pending_postcheckin=True` is ignored or redirected deterministically according to the chosen UX.

- Cover transport abstraction boundaries.
  - `BaseChannel` tests should prove that the rest of the bot stack consumes internal message/button primitives rather than aiogram-specific classes.
  - `TelegramChannel` tests should prove that Telegram callbacks are converted into normalized internal events.

- Keep tests fully local.
  - No real Telegram token.
  - No real network I/O.
  - No real OpenRouter.
  - Prefer fake bot/update objects or aiogram-compatible mocks.

- Preserve existing repo test expectations.
  - Backend handler tests for `handle_workout_start()` and `handle_readiness_log()` should continue to pass after dependency and packaging updates.
  - Do not let the new bot dependency break the current in-memory SQLite test suite.

### Project Structure Notes

- Alignment with unified project structure:
  - The backend remains in `gym_coach_brain/` under the existing `src` layout.
  - The new transport layer should be an additional top-level installed package under `gym-coach-brain/src/bot/`, not a fork of the backend package.
  - Tests should stay in `gym-coach-brain/tests/`, following the repo’s existing `test_*` directory convention.

- Detected conflicts or variances that the implementation must resolve intentionally:
  - `project-context.md` still mentions `Node.js (LTS): Telegraf, Express`, but Epic 6 and the current codebase are clearly Python-first; treat the Python codebase and Epic 6 as authoritative for this story.
  - `docs/api-contracts.md` still describes legacy `router.py` natural-language intent routing and old command surfaces such as `workout start [--day X]`; do not use that legacy flow as the implementation contract for the Telegram bot.
  - The current backend has no dedicated post-check-in API surface yet even though `post_feeling` exists in the schema; this is a real gap to close through a narrow API seam rather than an excuse to couple the bot directly to SQLAlchemy.
  - The current package entrypoint is still a placeholder (`print("Hello from gym-coach-brain!")`), so any bot/backend integration should target the explicit API module from Story 6.1 rather than the package root.

### References

- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/epics/epic-6.md#Story-6.3-Telegram-Bot-scaffold--aiogram--BaseChannel--MessageBus]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/6-2-fractional-volume-analytics.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/6-1-workout-api-handlers.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/project-context.md#Technology-Stack--Versions]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/pyproject.toml]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/api/handlers.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/data/models.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/data/session.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/__init__.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/tests/test_api/test_handlers.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/tests/test_api/test_readiness_handler.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/tests/conftest.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/docs/api-contracts.md#routerpy--NL-Router]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/docs/architecture.md#Data-Flow-Full-Workout-Session]
- [Source: https://docs.aiogram.dev/en/latest/dispatcher/router.html]
- [Source: https://pypi.org/project/aiogram/]
- [Source: https://docs.python.org/3/library/asyncio-queue.html]
- [Source: https://core.telegram.org/bots/api]

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Story selection: user requested `6-3`, resolved to `6-3-telegram-bot-scaffold` from `sprint-status.yaml`
- Core artifacts loaded: Epic 6, PRD, Architecture, Project Context, previous story `6-2-fractional-volume-analytics`
- Repo surfaces analyzed: `pyproject.toml`, `api/handlers.py`, `data/models.py`, `data/session.py`, current tests, legacy docs
- Git pattern review: last five commits inspected for recent implementation direction and changed files
- External references checked: official aiogram docs/PyPI metadata, official Python `asyncio.Queue` docs, official Telegram Bot API docs

### Completion Notes List

- Added the installable `src/bot/` package with a transport-neutral channel abstraction, typed `asyncio.Queue` message bus, per-user state store, and aiogram 3 router/polling entrypoint.
- Implemented deterministic `/workout` sleep → readiness orchestration, pending-text blocking, `/status`, `/stop`, and post-workout callback handling without coupling the bot layer to SQLAlchemy.
- Added a thin `ApiBackendClient` that reuses the structured `gym_coach_brain.api` boundary and introduced the additive `workout_post_checkin` intent for persisting `WorkoutSession.post_feeling`.
- Kept the 6.3 transport scaffold compatible with the pre-existing `bot.agent` test surface by preserving simple bus/state compatibility shapes while leaving AgentLoop/OpenRouter code out of the 6.3 runtime path.
- Verification passed for the story-mandated commands and the full package-local suite: `uv run --project gym-coach-brain pytest gym-coach-brain/tests` → `464 passed, 1 warning`.

### File List

- gym-coach-brain/pyproject.toml
- gym-coach-brain/src/bot/__init__.py
- gym-coach-brain/src/bot/bus.py
- gym-coach-brain/src/bot/state.py
- gym-coach-brain/src/bot/channels/base.py
- gym-coach-brain/src/bot/channels/telegram.py
- gym-coach-brain/src/bot/main.py
- gym-coach-brain/src/gym_coach_brain/api/handlers.py
- gym-coach-brain/src/gym_coach_brain/api/main.py
- gym-coach-brain/tests/test_api/test_handlers.py
- gym-coach-brain/tests/test_bot/__init__.py
- gym-coach-brain/tests/test_bot/test_channel.py

### Change Log

- Added aiogram/pytest-asyncio dependencies and constrained the package to Python `>=3.14,<3.15` to match aiogram support.
- Added the new `bot` transport package with normalized messages/buttons, typed bus/state primitives, aiogram router hooks, and the long-polling entrypoint.
- Added the narrow `workout_post_checkin` backend API seam plus regression coverage for it.
- Added focused async Telegram scaffold tests and verified the full `gym-coach-brain/tests` package-local suite.

### Previous Story Intelligence

- Story 6.1 established the intended backend boundary for Epic 6.
  - The backend should expose a callable API entrypoint for subprocess-style callers.
  - Handlers remain responsible for domain behavior, while JSON envelope serialization belongs at the API boundary.
  - The bot should reuse that seam rather than inventing a second integration path.

- Story 6.2 reinforced a project pattern that still applies here.
  - Keep new behavior in narrow, reusable modules.
  - Make hidden dependencies explicit in the story instead of letting the dev agent discover them mid-implementation.
  - Prefer additive integration points over bypassing the modular architecture.

### Git Intelligence Summary

- Recent commits show a consistent implementation direction:
  - strong expansion of deterministic workout/session flows in `api/handlers.py`
  - new ML queue and `WorkoutSession` contract fields in `data/models.py` and `data/queue.py`
  - heavy test investment alongside new backend features
  - continued use of absolute imports, in-memory SQLite test patterns, and explicit module boundaries

- Practical implications for Story 6.3:
  - follow the same absolute-import discipline
  - keep the bot state machine small and explicit
  - add tests alongside the new transport code instead of treating them as cleanup
  - integrate through the existing modular backend rather than shortcutting through direct DB access

### Latest Tech Information

- aiogram:
  - Official aiogram documentation currently documents the 3.26.0 line and centers routing around `Router`.
  - Official PyPI metadata currently lists `aiogram` as requiring Python `<3.15, >=3.10`, which matters because the project currently declares `>=3.14` without an upper bound.
  - For this story, use aiogram 3.x router/polling patterns and do not resurrect legacy executor-based code.

- Python `asyncio.Queue`:
  - Official Python docs document `put`, `get`, `task_done`, and `join` as the standard queue-processing lifecycle.
  - Queue shutdown support now exists in modern Python, but it should only be used if graceful stop behavior remains simple and clearly tested in this story.
  - For Story 6.3, a thin `asyncio.Queue` wrapper is sufficient; do not build a custom broker abstraction.

- Telegram Bot API:
  - Official Telegram Bot API documentation defines inline keyboards and callback-query handling as the standard interaction model for button-driven flows.
  - Callback data is size-constrained, so short stable tokens should be used instead of JSON-heavy payloads.
  - `/workout`, `/status`, and `/stop` fit naturally into Telegram’s bot-command model, but command registration should stay lightweight in this scaffold story.

### Project Context Reference

- Rules from `_bmad-output/project-context.md` that still apply directly:
  - use modern typed Python code
  - add pytest coverage for new features
  - keep state out of ad hoc globals
  - keep naming conventions consistent (`snake_case` files/functions, `PascalCase` classes)

- Rule variance to resolve consciously:
  - `project-context.md` still lists a Node/Telegraf stack that no longer matches Epic 6 or the current repo.
  - For Story 6.3, the live Python package, Epic 6, and the modular backend code should override that stale stack assumption.

### Story Completion Status

- Story status set to `review`.
- Output path: `_bmad-output/implementation-artifacts/6-3-telegram-bot-scaffold.md`
- Sprint status must be updated to:
  - `epic-6: in-progress`
  - `6-3-telegram-bot-scaffold: review`

# Story 6.4: AgentLoop - LLM Agent + OpenRouter + Tool Calling

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to implement the LLM agent loop with OpenRouter integration and gym-coach-brain tool calling,
so that the athlete can have natural-language conversations with a personal trainer that manages the full workout flow.

## Acceptance Criteria

1. Story 6.4 builds on the transport/state scaffolding from Story 6.3 without replacing it.
   - `AgentLoop` reads inbound user messages from `MessageBus.consume_inbound()`.
   - `AgentLoop` publishes final assistant replies to `MessageBus.publish_outbound()`.
   - `AgentLoop` consumes `UserState` from `bot/state.py` rather than introducing a second parallel state store.

2. The bot-side package layout is implementation-ready and compatible with the later deployment story.
   - New bot code lives under `gym-coach-brain/src/bot/`, not under `src/gym_coach_brain/`.
   - This is intentional because Story 6.5 deploys the bot with `python -m bot.main`.
   - Existing deterministic backend code remains under `gym_coach_brain`.

3. `gym_coach_brain.api` remains the only deterministic workout backend boundary.
   - AgentLoop does not import workout handlers or core modules directly.
   - Every workout/readiness/analytics operation is invoked through `python -m gym_coach_brain.api --intent ...`.
   - The additive API `data` object from Story 6.1 is supported when present, but the loop remains compatible with the stable top-level keys `intent`, `argv`, `stdout`, and `exit_code`.

4. `bot/agent.py` defines a real agent loop with bounded tool iteration.
   - `class AgentLoop` performs one OpenRouter inference for the current conversation state.
   - If the model returns tool calls, the loop executes them client-side and appends each result as a `role: tool` message.
   - The loop repeats until a final assistant reply is produced or `max_iterations=10` is reached.
   - Hitting the iteration cap is handled as a controlled failure with an athlete-safe fallback reply and an error log entry.

5. OpenRouter integration follows current official API guidance and is not hardcoded into the prompt or business logic.
   - Configuration comes from `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`.
   - Default model remains `openai/gpt-4o` to match Epic 6, but the implementation must keep model selection fully env-driven.
   - Requests use OpenRouter's OpenAI-compatible chat-completions interface and tool-calling message format.
   - The story should prefer the documented OpenAI SDK compatibility path over the OpenRouter Python SDK beta surface.

6. The system prompt is file-backed and versionable.
   - Prompt text is loaded from `gym-coach-brain/src/bot/prompts/system.md`.
   - The prompt includes:
     - Russian-speaking coach persona and Telegram-friendly tone.
     - Explicit instruction to never expose `exercise_id`, raw JSON, `exit_code`, env vars, or subprocess details to the athlete.
     - Tool-usage rules, including when to call `workout_start`, `workout_status`, `workout_log_set`, `workout_finish`, `workout_summary`, `readiness_log`, and `volume_report`.
     - Guidance for interpreting `exit_code=1` as a user/domain issue and `exit_code=2` as a system issue.

7. Tool definitions are explicit, typed, and aligned with the existing backend CLI contract.
   - Tools exposed to the model are exactly:
     - `workout_start`
     - `workout_log_set`
     - `workout_finish`
     - `workout_status`
     - `workout_summary`
     - `readiness_log`
     - `volume_report`
   - Each tool schema uses OpenAI/OpenRouter function-calling JSON schema.
   - The tool argument names must map cleanly to CLI flags without ambiguous translation layers.

8. CLI execution is safe, deterministic, and robust against subprocess failure modes.
   - Tool execution uses `subprocess.run([...], capture_output=True, text=True, timeout=...)`.
   - Commands are passed as argument lists, never through `shell=True`.
   - JSON parsing failures, missing stdout, invalid envelopes, and `subprocess.TimeoutExpired` are treated as system errors.
   - AgentLoop logs technical details but sends the athlete only a safe fallback message.

9. Tool-specific argument mapping preserves current repo behavior.
   - `workout_log_set` maps model arguments to the existing CLI flags `--exercise-id`, `--set-number`, `--weight-kg`, `--reps`, and `--rir`.
   - `workout_start` remains zero-argument for the model after the 6.3 deterministic check-in flow has already written readiness data, except when the agent explicitly needs a second-session confirmation path.
   - `readiness_log` must account for the current backend's actual flag shape when Story 6.4 is implemented; do not assume undocumented parameter names.
   - `volume_report` maps `weeks` to the API contract defined in Story 6.2.

10. AgentLoop uses backend response semantics correctly.
   - `exit_code=0`: tool succeeded; stdout is added back to context and reformatted for the athlete if needed.
   - `exit_code=1`: user/domain issue; the athlete gets a concise, non-technical explanation based on stdout and any additive `data`.
   - `exit_code=2`: system issue; the loop logs the failure and replies with a generic retry-safe message.
   - The loop must never echo the raw JSON envelope to the athlete.

11. Conversation context is bounded and implementation-oriented.
   - Message history is limited to the latest `N=20` turns by default.
   - The limit is configurable in code and easy to override later.
   - Each request to the model includes a compact summary of `UserState` such as active session id, current stage, and any pending structured flow flags.
   - The context format is optimized for model consumption, not for human debugging dumps.

12. Exercise identifiers remain internal-only even though the backend requires them.
   - AgentLoop may parse `exercise_id` values out of tool results and keep them in internal context/state.
   - The athlete-facing message must suppress those ids.
   - If the model needs an `exercise_id` for `workout_log_set`, it should derive it from prior tool output and internal state rather than asking the athlete to supply numeric ids.

13. Logging and observability follow project conventions.
   - Use `loguru`, not ad hoc `print()`.
   - Log OpenRouter request failures, subprocess failures, invalid tool payloads, and max-iteration exits with enough context to debug later.
   - Do not log secrets such as `OPENROUTER_API_KEY` or Telegram tokens.

14. Automated coverage proves the loop in isolation.
   - `gym-coach-brain/tests/test_bot/test_agent.py` covers:
     - tool call -> subprocess mock -> parsed JSON envelope -> assistant reply
     - `exit_code=1` user-error path
     - `exit_code=2` system-error path
     - malformed subprocess JSON
     - history truncation
     - prompt loading from file
     - max-iteration cutoff

15. End-to-end bot behavior is proven with a mock LLM and deterministic backend mocks.
   - `gym-coach-brain/tests/test_bot/test_e2e.py` covers:
     - check-in buttons -> `workout_start`
     - conversation-driven `workout_log_set`
     - `workout_finish`
     - post-workout check-in handoff
     - `workout_summary` response in chat
   - The suite runs without real Telegram or OpenRouter network access.

## Tasks / Subtasks

- [ ] Task 1: Create the AgentLoop surface and internal message model (AC: 1, 4, 11, 12)
  - [ ] Add `gym-coach-brain/src/bot/agent.py` with `AgentLoop`.
  - [ ] Define the loop boundary around inbound bus messages, outbound replies, internal history, and max-iteration handling.
  - [ ] Keep internal state compact and serializable enough for tests.

- [ ] Task 2: Add the OpenRouter client path using current documented integration guidance (AC: 4-6, 13)
  - [ ] Add the minimal dependency/runtime path needed to call OpenRouter through the documented OpenAI-compatible interface.
  - [ ] Keep API key/model lookup in env-driven configuration, not scattered across handlers.
  - [ ] Add timeouts and defensive error handling for request failures.

- [ ] Task 3: Add prompt and tool-definition infrastructure (AC: 6-7, 11-12)
  - [ ] Create `gym-coach-brain/src/bot/prompts/system.md`.
  - [ ] Define the seven tool schemas in code close to `AgentLoop` or in a narrow helper module.
  - [ ] Make sure schemas match the current backend CLI argument names and repo terminology.

- [ ] Task 4: Implement subprocess-backed tool execution (AC: 3, 8-10)
  - [ ] Build a small execution helper that maps tool arguments to `python -m gym_coach_brain.api --intent ...`.
  - [ ] Parse stdout as JSON envelope and normalize failures into a single internal result shape.
  - [ ] Handle malformed JSON, missing fields, non-zero return codes, and timeouts cleanly.

- [ ] Task 5: Integrate `UserState` and internal workout context (AC: 1, 9, 11-12)
  - [ ] Translate `bot/state.py` data into a compact model-facing context block.
  - [ ] Preserve internal knowledge of `exercise_id` / active session metadata without exposing it in outbound chat text.
  - [ ] Keep the free-chat agent loop compatible with the deterministic check-in flow from Story 6.3.

- [ ] Task 6: Add test coverage for the new bot package (AC: 14-15)
  - [ ] Create `gym-coach-brain/tests/test_bot/test_agent.py`.
  - [ ] Create `gym-coach-brain/tests/test_bot/test_e2e.py`.
  - [ ] Use mocks/fakes for OpenRouter responses, subprocess calls, and bus/channel plumbing.

- [ ] Task 7: Verification (AC: 1-15)
  - [ ] Run `uv run pytest gym-coach-brain/tests/test_bot/test_agent.py`.
  - [ ] Run `uv run pytest gym-coach-brain/tests/test_bot/test_e2e.py`.
  - [ ] Run at least one CLI smoke test against `python -m gym_coach_brain.api` with mocked subprocess integration where practical.

## Dev Notes

- This story is the orchestration bridge between the Telegram transport and the deterministic backend.
  - Story 6.3 owns bot/channel/message-bus scaffolding.
  - Story 6.1 owns the backend API contract.
  - Story 6.4 must connect them without collapsing those boundaries.

- Current repo reality that must shape the implementation:
  - `gym-coach-brain/src/gym_coach_brain/api/main.py` and `contract.py` already exist in the workspace and expose the JSON envelope expected by Epic 6.
  - There is currently no `gym-coach-brain/src/bot/` package at all.
  - `gym-coach-brain/src/gym_coach_brain/__init__.py` is still a placeholder and must not become the bot entrypoint.
  - Existing deterministic code already supports `readiness_log`, `workout_start`, `workout_status`, `workout_log_set`, `workout_finish`, and `workout_summary`.

- Critical repo mismatch to resolve explicitly:
  - The high-level architecture document models code under `src/gym_coach_brain/`.
  - Epic 6.3 and 6.5 require `bot/...` and `python -m bot.main`.
  - For this story, follow the epic and create a second top-level package under `src/` for bot transport/orchestration code.

- Another important mismatch:
  - `project-context.md` still contains an outdated Node.js / Telegraf infrastructure note.
  - Epic 6 has already moved the bot direction to Python + aiogram.
  - Follow Epic 6 and current package reality, not the stale Node.js line in project context.

- Backend contract mismatch to watch during implementation:
  - Epic 6 text describes `readiness_log` using `sleep_hours` and `pre_readiness`.
  - Current backend handler in `gym_coach_brain/api/handlers.py` actually parses `--sleep`, `--stress`, and optional `--hrv`.
  - Story 6.4 must align to the implemented backend or coordinate a deliberate follow-up change; do not silently invent unsupported CLI args in AgentLoop.

### Developer Context

- The athlete is talking to a conversational trainer, not to a CLI wrapper.
  - The agent may use tools aggressively.
  - The athlete should never see raw backend protocol details.

- The deterministic backend already owns exercise planning, set logging, readiness, and summaries.
  - AgentLoop is orchestration and phrasing logic.
  - It is not the place to reimplement planning, adaptation, or workout-state rules.

- Tool-calling quality depends on preserving high-signal context.
  - Include recent conversational turns and compact `UserState`.
  - Do not flood the model with large raw logs or the full JSON payload history.

- Exercise ids are a backend necessity, not a UX surface.
  - Parse them from tool output and keep them internal.
  - Maintain a current map of displayed exercise names -> ids inside the loop if needed.

### Technical Requirements

- Prefer a thin OpenRouter integration path that keeps the loop testable.
  - The OpenRouter Python SDK is currently documented as beta.
  - OpenRouter also documents the OpenAI SDK compatibility path with `base_url="https://openrouter.ai/api/v1"`.
  - For this repo, the safest implementation is a narrow client wrapper around the documented OpenAI-compatible API path.

- Use subprocess the safe way.
  - Pass argv as a list.
  - Use `text=True` so stdout/stderr handling stays simple in Python 3.14.
  - Set a timeout and catch `TimeoutExpired`.
  - Never use shell parsing for tool calls.

- Keep model-facing tool schemas and backend CLI flags aligned.
  - `exercise_id` in the tool schema must become `--exercise-id` in subprocess argv.
  - `set_number` must become `--set-number`, and so on.
  - Avoid a fuzzy translation layer that could drift from the API contract.

- Keep the loop deterministic around failure handling.
  - Unknown tool name from the model: reject internally and continue only if safe.
  - Invalid tool JSON arguments: log and return a tool error result, not a crash.
  - Invalid backend JSON envelope: treat as `exit_code=2` class failure.

- Keep history bounded with a simple, explicit rule.
  - A deque or equivalent fixed-length structure is sufficient.
  - Do not invent summarization complexity inside this story unless needed to satisfy tests.

### Architecture Compliance

- Respect the intended separation of concerns:
  - `src/bot/`: transport, LLM orchestration, prompt loading, tool execution.
  - `src/gym_coach_brain/`: deterministic training logic and API boundary.
  - `tests/test_bot/`: bot-specific tests.

- Preserve absolute import discipline.
  - Use imports like `from bot.bus import MessageBus` and `from gym_coach_brain.api...` as appropriate.
  - Do not use relative imports across package boundaries.

- Preserve typed error boundaries.
  - Backend exceptions are already normalized by `gym_coach_brain.api`.
  - AgentLoop should not bypass that normalization by importing handler functions directly.

- Preserve repo logging conventions.
  - Use `loguru`.
  - Avoid `print()` and silent exception swallowing.

### Library / Framework Requirements

- aiogram:
  - PyPI shows `aiogram 3.26.0` published on March 2, 2026.
  - Official aiogram 3 docs show long-polling through `Dispatcher.start_polling()` / `run_polling()`.
  - Keep Story 6.4 compatible with aiogram 3.x patterns introduced in Story 6.3; do not design around aiogram 2.x APIs.

- OpenRouter:
  - Official docs describe the `/api/v1/chat/completions` endpoint and normalize request/response format to the OpenAI Chat API.
  - Official tool-calling docs describe a client-side loop where the app executes the tool and returns `role: tool` messages back to the model.
  - Official docs also document the OpenAI SDK compatibility path and note that the separate OpenRouter Python SDK is beta.

- Python subprocess:
  - Python 3.14 docs continue to recommend `subprocess.run()` for cases it can handle.
  - Docs explicitly note that passing argument lists without `shell=True` avoids implicit shell interpretation and related injection risks.

### File Structure Requirements

- Expected primary files to touch:
  - `gym-coach-brain/pyproject.toml`
  - `gym-coach-brain/src/bot/__init__.py`
  - `gym-coach-brain/src/bot/agent.py`
  - `gym-coach-brain/src/bot/prompts/system.md`
  - `gym-coach-brain/src/bot/main.py` only if Story 6.3 left integration hooks unfinished
  - `gym-coach-brain/src/bot/state.py` only for narrow compatibility adjustments
  - `gym-coach-brain/tests/test_bot/test_agent.py`
  - `gym-coach-brain/tests/test_bot/test_e2e.py`

- Acceptable support files if the implementation benefits from narrower modules:
  - `gym-coach-brain/src/bot/tools.py`
  - `gym-coach-brain/src/bot/openrouter_client.py`
  - `gym-coach-brain/src/bot/history.py`

- Avoid unnecessary spread:
  - Do not move deterministic workout logic into `src/bot/`.
  - Do not create a second API boundary beside `gym_coach_brain.api`.

### Testing Requirements

- Unit-test the loop, not just the happy path.
  - tool call produced by model
  - subprocess success
  - subprocess timeout
  - malformed backend JSON
  - model returns direct text without tools
  - repeated tool calls until final answer
  - iteration cap reached

- E2E-test the orchestration seam.
  - deterministic check-in completes first
  - AgentLoop takes over afterward
  - tool outputs become athlete-safe chat responses
  - technical fields stay hidden from the athlete-facing text

- Keep tests network-free.
  - No real Telegram API
  - No real OpenRouter call
  - No real subprocess to a production DB

### Previous Story Intelligence

- The previous story file in this epic, `6-3-telegram-bot-scaffold.md`, already exists in the workspace but is still a near-template placeholder.
  - It does confirm the intended file names: `bot/channels/base.py`, `bot/channels/telegram.py`, `bot/bus.py`, `bot/state.py`, `bot/main.py`.
  - It does not yet contain actionable implementation learnings.
  - For Story 6.4, rely primarily on the epic, current backend API surface, and repo structure rather than on `6.3` narrative guidance.

- Story 6.1 is the more important prior context for this story.
  - It established the additive JSON envelope and the subprocess-facing API entrypoint.
  - Story 6.4 should consume that surface as-is rather than inventing a side-channel.

### Git Intelligence Summary

- The recent workspace state shows Epic 6 API surfaces already added but not fully settled into git history yet.
  - Untracked files exist for `api/__main__.py`, `api/contract.py`, and `api/main.py`.
  - `docs/api-contracts.md`, `api/handlers.py`, and `tests/test_api/test_handlers.py` are already being edited locally.
  - Practical implication: the bot story should integrate with the live workspace shape and avoid reverting or redesigning those surfaces.

- Recent commits are mostly repo-sync commits rather than feature-specific guidance.
  - There is no commit history yet for bot orchestration.
  - The implementation should therefore anchor itself on current files and explicit story guardrails instead of inferred commit patterns.

### Latest Tech Information

- aiogram:
  - PyPI lists `aiogram 3.26.0` as the latest release, published March 2, 2026.
  - aiogram's current docs show long-polling via `Dispatcher.start_polling()` and `Dispatcher.run_polling()`, which matches the Epic 6.3 bot runtime design.

- OpenRouter:
  - OpenRouter quickstart docs show the OpenAI SDK compatibility path with `base_url="https://openrouter.ai/api/v1"`.
  - OpenRouter's API reference documents `/api/v1/chat/completions` and states that responses are normalized to the OpenAI Chat API schema.
  - OpenRouter's tool-calling docs explicitly describe the client-side execution loop and show a capped agentic loop pattern that matches Epic 6.4's `max_iterations=10`.
  - OpenRouter's Python SDK docs currently label that SDK as beta, which is a reason to prefer the OpenAI-compatible path for this story.

- OpenAI Python SDK:
  - PyPI lists `openai 2.29.0` as the latest release, published March 17, 2026.
  - Given OpenRouter's documented OpenAI compatibility, adding this SDK is a reasonable implementation path if the team prefers a maintained client over raw HTTP.

- Python subprocess:
  - Python 3.14 documentation still recommends `subprocess.run()` for standard subprocess cases.
  - The docs also emphasize that Python will not implicitly use a system shell unless `shell=True` is requested, which is the safer fit for tool execution.

### Project Structure Notes

- Repo alignment:
  - The deterministic product remains a Python package under `src/gym_coach_brain`.
  - The conversational Telegram transport should be introduced as a separate `src/bot` package because the epic and deployment story already depend on that import path.

- Detected conflicts or variances:
  - `project-context.md` mentions Node.js/Telegraf, but Epic 6 requires Python/aiogram.
  - `architecture.md` centers the original backend package but does not yet describe the separate bot package needed by Stories 6.3-6.5.
  - `6-3-telegram-bot-scaffold.md` exists but is still largely unexpanded, so Story 6.4 must carry more concrete guidance than it normally would.

### References

- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/epics/epic-6.md#Story-6.4-AgentLoop---LLM-Agent--OpenRouter--Tool-Calling]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/6-1-workout-api-handlers.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/6-3-telegram-bot-scaffold.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/project-context.md#Project-Context-for-AI-Agents]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/architecture.md#Implementation-Patterns--Consistency-Rules]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/prd.md#Capability-Area-Communication-Protocol]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/docs/api-contracts.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/pyproject.toml]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/api/main.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/api/contract.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/api/handlers.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/data/models.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/__init__.py]
- [Source: https://pypi.org/pypi/aiogram]
- [Source: https://docs.aiogram.dev/en/v3.24.0/dispatcher/long_polling.html]
- [Source: https://openrouter.ai/docs/quickstart]
- [Source: https://openrouter.ai/docs/api/reference/overview/]
- [Source: https://openrouter.ai/docs/guides/features/tool-calling]
- [Source: https://openrouter.ai/docs/sdks/python/overview]
- [Source: https://pypi.org/project/openai/]
- [Source: https://docs.python.org/3.14/library/subprocess.html]

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Story selection: explicit user request for `6-4`
- Planning artifacts loaded: Epic 6, PRD, Architecture, Project Context
- Previous epic context checked: `6-1-workout-api-handlers.md`, `6-3-telegram-bot-scaffold.md`
- Current repo surfaces checked: `pyproject.toml`, `api/main.py`, `api/contract.py`, `api/handlers.py`, `data/models.py`, `src/` package layout, current git status
- Latest technology references checked: aiogram PyPI/docs, OpenRouter quickstart/API/tool-calling docs, OpenRouter Python SDK docs, OpenAI SDK PyPI, Python 3.14 subprocess docs

### Completion Notes List

- Story converted from template to an implementation-ready context document.
- Explicit package-path guidance was added for `src/bot/` vs `src/gym_coach_brain/`.
- Current backend contract mismatches were surfaced, especially around `readiness_log`.
- Latest OpenRouter integration guidance was incorporated with concrete dependency advice.
- Bot testing scope was expanded so the dev agent has clear unit and E2E targets.

### File List

- _bmad-output/implementation-artifacts/6-4-agent-loop-openrouter.md

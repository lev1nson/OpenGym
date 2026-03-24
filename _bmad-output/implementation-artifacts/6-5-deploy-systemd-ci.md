# Story 6.5: Deploy - systemd and CI validation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to deploy the ML Worker as a systemd service and the Telegram bot as a daemon with CI validation,
so that the full system runs reliably on VPS with automated quality gates.

## Acceptance Criteria

1. The deployment model matches the current Epic 6 contract and the real repo architecture.
   - Long-running processes are limited to the ML worker and the future Telegram bot.
   - `gym_coach_brain.api` remains an ephemeral subprocess invoked per request; this story must not introduce a daemonized "core API" service.

2. `gym-coach-brain/systemd/gym-coach-brain-ml.service` is productionized around the existing ML worker entrypoint.
   - `ExecStart` runs `python -m gym_coach_brain.ml`.
   - `Restart=on-failure` remains enabled.
   - The service enforces an 8 GB memory cap.
   - Environment configuration is moved out of inline `Environment=` entries into a shared env file reference.

3. `gym-coach-brain/systemd/gym-coach-brain-bot.service` is added for the Telegram bot daemon.
   - It uses the same shared env file as the ML worker.
   - Its `ExecStart` targets the actual packaged bot entrypoint produced by Stories 6.3 and 6.4.
   - If the bot lands under `src/gym_coach_brain/`, the service must launch the packaged module path, not a repo-root `bot.main` shortcut that breaks the project structure.

4. Secrets are externalized safely.
   - The committed repo contains a template/example env file for operators.
   - The real `systemd/gym-coach-brain.env` used in production is documented but not committed with live credentials.
   - Required variables include `DATABASE_URL`, `MODEL_DIR`, `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL`.

5. A repo-level GitHub Actions workflow is added at `.github/workflows/ci.yml`.
   - It runs on push and pull request.
   - It installs Python and uv using current official actions.
   - It runs from the `gym-coach-brain/` working directory.
   - It installs the locked project environment and executes the full pytest suite.

6. CI remains hermetic and does not call external Telegram or OpenRouter services.
   - Tests use mocks/fakes only.
   - No real secrets are required for CI.
   - The workflow must fail if the full test suite fails.

7. Deployment documentation is added to `gym-coach-brain/README.md`.
   - It includes environment-file setup.
   - It includes `systemctl enable/start` commands for the ML worker and bot services.
   - It includes `journalctl` usage for troubleshooting.
   - It explains how to obtain a Telegram bot token and an OpenRouter API key.

8. The implementation stays aligned with the repo toolchain.
   - Use `uv`, `pyproject.toml`, `.python-version`, and `uv.lock`; do not introduce a parallel `requirements.txt` deployment path.
   - `uv run pytest` must be the canonical validation command on a clean machine.

9. Existing repo workflows remain intact.
   - Do not replace `.github/workflows/docs-check.yml`.
   - Add the new CI workflow alongside it.

10. The story is executable despite the current implementation sequencing.
   - It must call out that Stories 6.3 and 6.4 are already tracked as `ready-for-dev` in `sprint-status.yaml`, but their bot module path is not present in the repo yet, so the service target cannot be finalized by guesswork.
   - The service contract, README, and CI changes should be prepared so 6.5 can land immediately after the bot module path exists.

## Tasks / Subtasks

- [x] Task 1: Normalize the deployment model around actual long-running processes (AC: 1, 2, 3, 10)
  - [x] Preserve `gym_coach_brain.api` as a subprocess boundary; do not add `gym-coach-brain.service` for the API.
  - [x] Update `gym-coach-brain/systemd/gym-coach-brain-ml.service` to consume a shared env file instead of inline secrets/config.
  - [x] Add `gym-coach-brain/systemd/gym-coach-brain-bot.service` using the real packaged bot module path from Stories 6.3 and 6.4.

- [x] Task 2: Externalize runtime configuration safely (AC: 2, 3, 4)
  - [x] Add `gym-coach-brain/systemd/gym-coach-brain.env.example` with all required keys and safe placeholders.
  - [x] Document the real deployment-time env file path and permissions in the README.
  - [x] Keep secrets out of git; if an actual `gym-coach-brain.env` path is referenced by unit files, ensure the committed template and docs make that operational flow explicit.

- [x] Task 3: Add CI for the Python package using the repo's uv workflow (AC: 5, 6, 8, 9)
  - [x] Create `.github/workflows/ci.yml`.
  - [x] Use `actions/checkout` and `actions/setup-python`.
  - [x] Use `astral-sh/setup-uv`.
  - [x] Run `uv sync --locked --dev` from `gym-coach-brain/`.
  - [x] Run `uv run pytest`.
  - [x] Keep docs-only checks in the existing workflow; do not duplicate them here unless they add signal.

- [x] Task 4: Document VPS deployment and operator workflow (AC: 4, 7, 8)
  - [x] Populate `gym-coach-brain/README.md`, which is currently empty.
  - [x] Document expected directory layout on the VPS, env-file setup, service installation, service enable/start commands, restart/logging commands, and test verification.
  - [x] Document where Telegram and OpenRouter credentials come from without hardcoding secrets or provider-specific private values.

- [x] Task 5: Validate deployment artifacts (AC: 2-8)
  - [x] Run `uv run pytest` from `gym-coach-brain/`.
  - [x] If available on the target system, validate service units with `systemd-analyze verify`.
  - [x] Confirm the committed unit files and README agree on the same paths, env file name, and module entrypoints.

## Dev Notes

- This story is deployment-focused, but it has a real dependency gap today:
  - `sprint-status.yaml` shows `6-3-telegram-bot-scaffold` and `6-4-agent-loop-openrouter` as `ready-for-dev`.
  - The repo still has no `bot/` package or bot entrypoint in code.
  - The story must therefore define the deployment contract without inventing a fake module path.

- Current repo reality that must shape the implementation:
  - `gym-coach-brain/src/gym_coach_brain/ml/__main__.py` already exists and is the correct ML worker entrypoint.
  - `gym-coach-brain/systemd/gym-coach-brain-ml.service` already exists, but it still uses inline `Environment=` settings and placeholder deployment metadata.
  - `.github/workflows/` currently contains only `docs-check.yml`; no package test workflow exists yet.
  - `gym-coach-brain/README.md` is empty, so deployment docs are starting from zero.

- Critical architecture mismatch to resolve in this story:
  - The architecture document still contains an older concept of `gym-coach-brain.service` for a long-running API process.
  - Epic 6.5 explicitly supersedes that for the final Telegram/OpenRouter design: the API remains a short-lived subprocess called by the bot/agent loop.
  - Do not revive the old daemonized API idea in service files, docs, or CI.

- Another important mismatch:
  - Epic 6.5 says `python -m bot.main`.
  - The repo architecture uses a `src/gym_coach_brain/` package layout and absolute imports.
  - If Stories 6.3 and 6.4 add the bot inside the package, 6.5 should launch the packaged module path instead of a top-level `bot.main` shortcut.

### Developer Context

- Reuse the ML worker deployment pattern from Story 5.3 instead of replacing it.
  - That story already established `python -m gym_coach_brain.ml`, `Restart=on-failure`, and an 8 GB memory cap.
  - Story 6.5 should refactor configuration handling and add the bot service, not redesign ML worker supervision.

- Keep the bot deployment consistent with package structure.
  - The repo uses `src/gym_coach_brain/` and absolute imports everywhere.
  - A top-level runtime module outside the package would fight the existing architecture, packaging, and CI layout.

- CI needs to be package-aware, not repo-root-naive.
  - The Python project lives under `gym-coach-brain/`.
  - Workflow steps must either set `working-directory: gym-coach-brain` or use equivalent path-aware commands.
  - Running uv from the repo root would target the wrong `pyproject.toml`.

- Do not commit real deployment secrets.
  - The story acceptance criteria want a common env file, but that must be treated as an operator-managed file.
  - The right repo artifact is a template/example plus README instructions, not a committed live secret file.

### Technical Requirements

- Update the ML service unit without breaking the current runtime assumptions:
  - Keep `ExecStart` on `python -m gym_coach_brain.ml`.
  - Keep restart supervision.
  - Keep journal logging.
  - Keep an 8 GB memory cap.
  - Replace inline env declarations with `EnvironmentFile=`.

- The shared env file contract should minimally cover:
  - `DATABASE_URL`
  - `MODEL_DIR`
  - `TELEGRAM_BOT_TOKEN`
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL`
  - any already-supported ML worker settings that remain operationally relevant, such as `ML_POLL_INTERVAL` or `ML_FINE_TUNE_THRESHOLD`

- Prefer current systemd resource-control terminology.
  - The existing repo already uses `MemoryMax=8G`.
  - Epic wording still says `MemoryLimit=8G`.
  - Implement the 8 GB cap using the modern directive and document the epic wording mismatch in comments only if necessary.

- CI should follow the locked uv workflow, not ad hoc pip installation.
  - Use the checked-in `uv.lock`.
  - Use `.python-version` / project Python expectations from `pyproject.toml`.
  - Avoid a second dependency-install path that can drift from local development.

- The bot service entrypoint must be resolved from code, not guessed from the epic text.
  - If Story 6.3 or 6.4 creates `src/gym_coach_brain/bot/__main__.py`, prefer `python -m gym_coach_brain.bot`.
  - If it creates `src/gym_coach_brain/bot/main.py`, use the corresponding packaged module path.
  - Do not hardcode `python -m bot.main` unless the codebase actually ships that module path.

### Architecture Compliance

- Preserve the process boundary established by Epic 6 and Story 6.1:
  - Telegram bot / agent loop = long-running daemon
  - ML worker = long-running daemon
  - `gym_coach_brain.api` = short-lived subprocess boundary

- Preserve package structure and absolute imports.
  - New bot runtime files should live under `gym-coach-brain/src/gym_coach_brain/` if they follow the current architecture.
  - Service units and README instructions must point at that packaged entrypoint.

- Preserve deployment separation of concerns.
  - systemd unit files live under `gym-coach-brain/systemd/`
  - CI lives under `.github/workflows/`
  - operator instructions live in `gym-coach-brain/README.md`
  - secrets stay outside committed source history

- Preserve the repo’s toolchain boundary.
  - Use uv for install/test flow.
  - Do not introduce Docker, Poetry, pipenv, or shell-wrapper deployment paths in this story.

### Library / Framework Requirements

- Current repo runtime/tooling expectations from `gym-coach-brain/pyproject.toml`:
  - Python `>=3.14`
  - SQLAlchemy `>=2.0.48`
  - Alembic `>=1.18.4`
  - loguru `>=0.7.3`
  - torch `>=2.10.0`
  - pytest `>=9.0.2`

- Latest official CI guidance relevant to this story as of March 24, 2026:
  - GitHub Actions Python docs currently show `actions/checkout@v5` and `actions/setup-python@v5` in Python build/test workflows.
  - Astral uv GitHub integration docs currently recommend `astral-sh/setup-uv@v7`, `uv sync`, `uv run`, and built-in uv cache support for CI.

- Latest official deployment guidance relevant to this story:
  - systemd service docs remain the authoritative reference for `Restart=on-failure`.
  - systemd exec docs remain the reference for `EnvironmentFile=`.
  - systemd resource-control docs remain the reference for memory-capped services; use the documented current directive rather than preserving older wording blindly.

- Dependency boundary reminder:
  - aiogram and OpenRouter-specific runtime dependencies belong to Stories 6.3 and 6.4.
  - Story 6.5 should consume those packaged entrypoints and locked dependencies, not re-specify them from scratch.

### File Structure Requirements

- Files expected to be created:
  - `.github/workflows/ci.yml`
  - `gym-coach-brain/systemd/gym-coach-brain-bot.service`
  - `gym-coach-brain/systemd/gym-coach-brain.env.example`

- Files expected to be modified:
  - `gym-coach-brain/systemd/gym-coach-brain-ml.service`
  - `gym-coach-brain/README.md`

- Files that should not be introduced by this story:
  - a daemon service for `gym_coach_brain.api`
  - a parallel `requirements.txt`-based CI path
  - a committed production secrets file with live credentials

- Files that may need light adjustment only if required by bot packaging reality:
  - `gym-coach-brain/pyproject.toml`
  - `gym-coach-brain/uv.lock`
  - bot package entrypoint modules created by Stories 6.3 and 6.4

### Testing Requirements

- CI must prove the locked environment works end-to-end on a clean runner.
  - `uv sync --locked --dev`
  - `uv run pytest`

- Tests must remain network-free.
  - Telegram and OpenRouter interactions stay mocked.
  - No CI secret injection is required for the happy path.

- Deployment artifacts should be verified for consistency.
  - Service unit names, env file names, module paths, and README commands must match exactly.
  - If a Linux verification command such as `systemd-analyze verify` is available, use it as an extra guardrail.

- Do not scope CI down to a handpicked subset.
  - Epic 6.5 explicitly wants the full pytest suite on push/PR.
  - Keep any future selective test jobs additive, not a replacement for the full-suite gate.

### Previous Story Intelligence

- Story 5.3 already established the operational shape of the ML worker.
  - The repo already has `gym_coach_brain.ml` and a service file under `gym-coach-brain/systemd/`.
  - Story 6.5 should extend that work with shared env handling and deploy docs, not duplicate the daemon design.

- Story 6.1 matters here because it codified the API boundary.
  - The JSON API exists as a subprocess-facing composition root in `gym_coach_brain/api/main.py` and `api/__main__.py`.
  - Deployment for Epic 6 must not convert that into a permanent daemon.

- Story 6.2 reinforced the same pattern.
  - Handlers stay deterministic and text-first.
  - Transport/orchestration concerns belong above the handler layer, which supports the bot-daemon plus subprocess-API model.

### Git Intelligence Summary

- Recent commit history is mostly sync/documentation work, not deployment implementation.
  - `cc69b36 chore: sync latest project updates`
  - `e025519 Update story 5.2 status to done`
  - `2e015c8 chore: sync current OpenGym project state`

- The current worktree is already dirty in deployment-adjacent areas.
  - `gym-coach-brain/src/gym_coach_brain/api/*`, `ml/*`, and `systemd/` have active local changes or new files.
  - When implementing 6.5, avoid broad refactors or cleanup that could overwrite unrelated user work.

- Practical implication for this story:
  - keep the change set narrow
  - focus on `systemd/`, `.github/workflows/`, and `README.md`
  - only touch package/runtime files if the actual bot entrypoint path requires it

### Latest Technical Information

- GitHub Actions official Python workflow docs:
  - Current examples use `actions/checkout@v5` and `actions/setup-python@v5`.
  - That is the right baseline for `.github/workflows/ci.yml` on March 24, 2026.

- Astral uv official GitHub integration docs:
  - Current guidance recommends `astral-sh/setup-uv@v7`.
  - Current examples use `uv sync --locked --dev` and `uv run pytest`.
  - The same docs document built-in uv cache support, which is appropriate for this repo once the basic workflow is green.

- systemd official documentation:
  - `systemd.service` documents restart policies such as `Restart=on-failure`.
  - `systemd.exec` documents `EnvironmentFile=`.
  - `systemd.resource-control` documents current memory-cap controls; the implementation should follow current documented directives while still satisfying the epic’s 8 GB cap requirement.

### Project Structure Notes

- Repo-alignment summary:
  - The Python package lives in `gym-coach-brain/`.
  - CI must target that subproject intentionally.
  - systemd artifacts already live in the package root, which is the correct place to continue.

- Detected conflict or variance:
  - `_bmad-output/planning-artifacts/architecture.md` still references a daemonized main API process via `gym-coach-brain.service`.
  - Epic 6.5 supersedes that with the final Telegram bot + subprocess API model.
  - The story should treat the epic as the newer source of truth for deployment topology.

- Another detected variance:
  - Epic 6.5 names `python -m bot.main`.
  - The repo currently has no such top-level module, and the project architecture strongly favors packaged entrypoints under `gym_coach_brain`.
  - Resolve that variance explicitly during implementation; do not leave it ambiguous in the unit file.

### References

- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/epics/epic-6.md#Story-6.5-Деплой-—-ML-Worker-systemd-и-CI-CD]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/5-3-ml-worker-daemon.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/6-1-workout-api-handlers.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/6-2-fractional-volume-analytics.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/project-context.md#Technology-Stack--Versions]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/architecture.md#ML-Worker-Process-Lifecycle]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/planning-artifacts/architecture.md#Project-Structure--Boundaries]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/_bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/systemd/gym-coach-brain-ml.service]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/ml/__main__.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/api/main.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/src/gym_coach_brain/api/contract.py]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/pyproject.toml]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/.python-version]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/gym-coach-brain/README.md]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/.github/workflows/docs-check.yml]
- [Source: /Users/max/Documents/Coding/opengym/OpenGym/docs/api-contracts.md]
- [Source: https://docs.github.com/en/actions/tutorials/build-and-test-code/python]
- [Source: https://docs.astral.sh/uv/guides/integration/github/]
- [Source: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html]
- [Source: https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html]
- [Source: https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html]

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `cat _bmad/core/tasks/workflow.xml`
- `cat _bmad/bmm/workflows/4-implementation/dev-story/workflow.yaml`
- `cat _bmad/bmm/workflows/4-implementation/dev-story/instructions.xml`
- `cat _bmad/bmm/workflows/4-implementation/dev-story/checklist.md`
- `cat _bmad-output/implementation-artifacts/sprint-status.yaml`
- `cat _bmad-output/implementation-artifacts/6-5-deploy-systemd-ci.md`
- `cat _bmad-output/project-context.md`
- `cat _bmad-output/implementation-artifacts/6-3-telegram-bot-scaffold.md`
- `cat _bmad-output/implementation-artifacts/6-4-agent-loop-openrouter.md`
- `cat _bmad-output/implementation-artifacts/6-2-fractional-volume-analytics.md`
- `cat gym-coach-brain/.python-version`
- `cat gym-coach-brain/README.md`
- `cat .github/workflows/docs-check.yml`
- `cat gym-coach-brain/src/gym_coach_brain/ml/__main__.py`
- `cat gym-coach-brain/systemd/gym-coach-brain-ml.service`
- `find gym-coach-brain/src/gym_coach_brain -maxdepth 3 -type f | sort`
- `uv run pytest tests/test_deployment/test_artifacts.py`
- `uv run pytest`
- `command -v systemd-analyze || true`
- `cat gym-coach-brain/pyproject.toml`
- `git status --short`

### Completion Notes List

- 2026-03-24: Updated the ML worker unit to load operator-managed settings from `systemd/gym-coach-brain.env`, preserving `python -m gym_coach_brain.ml`, `Restart=on-failure`, journal logging, and the `MemoryMax=8G` cap.
- 2026-03-24: Added `gym-coach-brain-bot.service` on the packaged `python -m bot.main` contract established by Stories 6.3 and 6.4, while keeping the API documented as a subprocess boundary rather than a daemon.
- 2026-03-24: Added `gym-coach-brain.env.example`, a repo-level GitHub Actions workflow, deployment documentation in `gym-coach-brain/README.md`, and deployment artifact tests that lock unit-file, env-file, CI, and README consistency.
- 2026-03-24: Validation passed with `uv run pytest tests/test_deployment/test_artifacts.py` and a full `uv run pytest` run (`449 passed`); `systemd-analyze` was not available in the current macOS environment, so unit validation was documented for the Linux target host instead.
- 2026-03-24 (code review): Relocated `src/bot/` → `src/gym_coach_brain/bot/` to conform with project architecture (all bot sources now reside inside the declared `gym_coach_brain` package). Updated `ExecStart` in bot service to `python -m gym_coach_brain.bot.main`, added `MemoryMax=2G` to bot service, fixed CI action versions `@v6` → `@v5`, updated test import paths, split production/dev `uv sync` in README, added `.gitignore` entry for operator secrets file. (456 passed after review fixes)
- 2026-03-24 (code review): Identified that `agent.py`, `openrouter_client.py`, `tools.py` (story 6.4 work) exist only as `.pyc` cache — source was never committed. `tests/test_bot/test_agent.py` and `test_e2e.py` imports updated to `gym_coach_brain.bot.*` but tests remain non-runnable until 6.4 source is restored.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/implementation-artifacts/6-5-deploy-systemd-ci.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `gym-coach-brain/tests/test_deployment/test_artifacts.py`
- `gym-coach-brain/systemd/gym-coach-brain-ml.service`
- `gym-coach-brain/systemd/gym-coach-brain-bot.service`
- `gym-coach-brain/systemd/gym-coach-brain.env.example`
- `gym-coach-brain/README.md`
- `gym-coach-brain/.gitignore`
- `gym-coach-brain/src/gym_coach_brain/bot/__init__.py` *(relocated from src/bot/ — architecture fix)*
- `gym-coach-brain/src/gym_coach_brain/bot/bus.py`
- `gym-coach-brain/src/gym_coach_brain/bot/state.py`
- `gym-coach-brain/src/gym_coach_brain/bot/main.py`
- `gym-coach-brain/src/gym_coach_brain/bot/channels/__init__.py`
- `gym-coach-brain/src/gym_coach_brain/bot/channels/base.py`
- `gym-coach-brain/src/gym_coach_brain/bot/channels/telegram.py`
- `gym-coach-brain/tests/test_bot/test_channel.py` *(imports updated)*
- `gym-coach-brain/tests/test_bot/test_agent.py` *(imports updated, awaits missing agent/tools source from 6.4)*
- `gym-coach-brain/tests/test_bot/test_e2e.py` *(imports updated, awaits missing agent/tools source from 6.4)*
- *Note: gym-coach-brain/src/gym_coach_brain/api/\*, core/\*, tests/conftest.py, test_api/\*, test_core/\*, pyproject.toml, uv.lock changed as part of combined 6.3–6.5 commit — belong to those stories*

### Change Log

- 2026-03-24: Externalized shared runtime configuration for the ML worker and Telegram bot, added CI for locked `uv` test runs, documented VPS deployment steps, and added deployment artifact regression tests.

### Story Completion Status

- Story status set to `review`.
- Output path: `_bmad-output/implementation-artifacts/6-5-deploy-systemd-ci.md`
- Sprint status must be updated to:
  - `epic-6: in-progress`
  - `6-5-deploy-systemd-ci: review`

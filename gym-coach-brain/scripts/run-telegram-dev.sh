#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PROJECT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/systemd/gym-coach-brain.env}"

SHELL_DATABASE_URL="${DATABASE_URL:-}"
SHELL_MODEL_DIR="${MODEL_DIR:-}"
SHELL_OPENROUTER_MODEL="${OPENROUTER_MODEL:-}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "TELEGRAM_BOT_TOKEN is required" >&2
  exit 1
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is required" >&2
  exit 1
fi

export DATABASE_URL="${SHELL_DATABASE_URL:-sqlite:///${PROJECT_DIR}/gym_coach.sqlite}"
export MODEL_DIR="${SHELL_MODEL_DIR:-${REPO_ROOT}/model_weights}"
export OPENROUTER_MODEL="${SHELL_OPENROUTER_MODEL:-${OPENROUTER_MODEL:-openai/gpt-4o}}"
export ML_POLL_INTERVAL="${ML_POLL_INTERVAL:-60}"
export ML_FINE_TUNE_THRESHOLD="${ML_FINE_TUNE_THRESHOLD:-5}"

if pgrep -f 'gym_coach_brain.bot.main' >/dev/null 2>&1; then
  echo "Existing local bot process detected. Restarting..."
  pkill -f 'gym_coach_brain.bot.main' || true

  for _ in {1..20}; do
    if ! pgrep -f 'gym_coach_brain.bot.main' >/dev/null 2>&1; then
      break
    fi
    sleep 0.2
  done

  if pgrep -f 'gym_coach_brain.bot.main' >/dev/null 2>&1; then
    pkill -9 -f 'gym_coach_brain.bot.main' || true
  fi
fi

mkdir -p "${MODEL_DIR}"

cd "${PROJECT_DIR}"

uv sync --locked --dev
uv run alembic upgrade heads
uv run python -m gym_coach_brain.data.seed "${DATABASE_URL}"
exec uv run python -m gym_coach_brain.bot.main

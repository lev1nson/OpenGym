# OpenGym Telegram Bot

An AI-powered fitness coaching bot for Telegram that provides personalized workout planning, progress tracking, and conversational guidance.

## Quick Start

### For Local Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed setup instructions.

**TL;DR:**
```bash
# Install dependencies
uv sync

# Set up environment variables (see docs/environment-variables.md)
cp systemd/gym-coach-brain.env.example .env
# Edit .env with your API keys

# Run the bot
uv run python -m gym_coach_brain.bot.main
```

### For Production Deployment

See the [Production Deployment](#production-deployment) section below.

## Features

- 🤖 **Conversational AI Coach** - Natural language interaction powered by LLMs
- 🎤 **Voice Message Support** - Send voice messages, get text responses
- 💪 **Workout Planning** - Science-based progressive overload programs
- 📊 **Progress Tracking** - Monitor performance and adaptation
- 🔄 **Persistent State** - User data survives bot restarts
- ⏰ **Smart Timeouts** - Automatic cleanup of stale conversations

## Documentation

- [Local Development Guide](DEVELOPMENT.md) - Set up and run locally
- [Environment Variables](docs/environment-variables.md) - Complete configuration reference
- [Architecture Overview](../docs/architecture.md) - System design and components
- [API Contracts](../docs/api-contracts.md) - Backend API documentation

---

# Production Deployment

`gym_coach_brain.api` is not a long-running service in Epic 6. The long-lived processes on the VPS are:

- `gym-coach-brain-ml.service` for the ML worker
- `gym-coach-brain-bot.service` for the Telegram bot daemon

The bot unit is wired to `python -m gym_coach_brain.bot.main`, which is the packaged runtime contract defined by Stories 6.3 and 6.4. The backend API (`execute_intent`) is called in-process by the bot daemon — no separate API service or subprocess boundary is needed. Do not introduce a separate `gym-coach-brain.service` for the API layer.

## Prerequisites

- Python version from [`.python-version`](./.python-version)
- `uv` installed on the VPS
- A checkout at `/opt/opengym/gym-coach-brain`
- A deployment user such as `opengym`

## Directory Layout

Expected layout on the host:

```text
/opt/opengym/
  gym-coach-brain/
    .venv/
    gym_coach.sqlite
    systemd/
      gym-coach-brain-ml.service
      gym-coach-brain-bot.service
      gym-coach-brain.env
  model_weights/
```

## Environment File Setup

Create the real env file from the committed template and keep it out of git:

```bash
cd /opt/opengym/gym-coach-brain
cp systemd/gym-coach-brain.env.example systemd/gym-coach-brain.env
chmod 600 systemd/gym-coach-brain.env
```

Required variables in `systemd/gym-coach-brain.env`:

- `DATABASE_URL`
- `MODEL_DIR`
- `TELEGRAM_BOT_TOKEN`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `ML_POLL_INTERVAL`
- `ML_FINE_TUNE_THRESHOLD`

## Installing The Services

Install the package environment:

```bash
cd /opt/opengym/gym-coach-brain
uv sync --locked
```

Validate the codebase before enabling services (installs dev dependencies on the host once):

```bash
uv sync --locked --dev
uv run pytest
```

Bootstrap the runtime database before starting the daemons. The worker expects
the migrated schema, including `ml_jobs`, and the reference taxonomy data:

```bash
uv run alembic upgrade head
uv run python -m gym_coach_brain.data.seed "$DATABASE_URL"
```

Copy the unit files into systemd and reload:

```bash
sudo cp systemd/gym-coach-brain-ml.service /etc/systemd/system/
sudo cp systemd/gym-coach-brain-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
```

Enable and start the daemons:

```bash
sudo systemctl enable --now gym-coach-brain-ml.service
sudo systemctl enable --now gym-coach-brain-bot.service
```

## Operations

Check service status:

```bash
sudo systemctl status gym-coach-brain-ml.service
sudo systemctl status gym-coach-brain-bot.service
```

Restart services after config or code changes:

```bash
sudo systemctl restart gym-coach-brain-ml.service
sudo systemctl restart gym-coach-brain-bot.service
```

Stream logs from journald:

```bash
sudo journalctl -u gym-coach-brain-ml.service -f
sudo journalctl -u gym-coach-brain-bot.service -f
```

If `systemd-analyze` is available on the target host, verify the unit files before enabling them:

```bash
sudo systemd-analyze verify /etc/systemd/system/gym-coach-brain-ml.service
sudo systemd-analyze verify /etc/systemd/system/gym-coach-brain-bot.service
```

## Secrets And External Providers

Get the Telegram bot token from `@BotFather` in Telegram and place it in `TELEGRAM_BOT_TOKEN`.

Get the OpenRouter API key from the OpenRouter dashboard and place it in `OPENROUTER_API_KEY`. Set `OPENROUTER_MODEL` to the production model you want the bot to use.

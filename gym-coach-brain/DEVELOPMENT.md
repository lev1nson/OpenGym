# OpenGym Telegram Bot - Local Development Guide

This guide will help you set up and run the OpenGym Telegram bot locally for development and testing.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.14** (required)
- **uv** package manager ([installation guide](https://github.com/astral-sh/uv))
- **Git** for version control
- **SQLite** (usually pre-installed on most systems)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd OpenGym/gym-coach-brain
```

### 2. Install Dependencies

Using `uv` (recommended):

```bash
uv sync
```

This will create a virtual environment and install all required dependencies.

### 3. Obtain API Credentials

#### Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the prompts to create your bot:
   - Choose a name for your bot (e.g., "My Gym Coach Dev")
   - Choose a username (must end in 'bot', e.g., "my_gym_coach_dev_bot")
4. Copy the API token provided (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### OpenAI API Key (for Whisper voice transcription)

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-`)

**Note:** Voice message support requires OpenAI API access. If you don't have an API key, the bot will still work but voice messages will be disabled.

#### OpenRouter API Key (for LLM agent)

1. Go to [OpenRouter](https://openrouter.ai/)
2. Sign up or log in
3. Navigate to Keys section
4. Create a new API key
5. Copy the key

### 4. Configure Environment Variables

Create a `.env` file in the `gym-coach-brain` directory:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional - for voice message support
OPENAI_API_KEY=your_openai_api_key_here

# Optional - configuration
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
BOT_STATE_DB_PATH=bot_state.db
CONVERSATION_TIMEOUT_HOURS=24
```

See [docs/environment-variables.md](docs/environment-variables.md) for a complete list of environment variables.

### 5. Initialize the Database

The main application database will be created automatically on first run. The bot state database is also created automatically.

If you need to run migrations manually:

```bash
uv run alembic upgrade head
```

### 6. Run the Bot

Start the bot in development mode:

```bash
uv run python -m gym_coach_brain.bot.main
```

You should see log output indicating the bot has started successfully:

```
INFO     | SQLite user state store initialized at bot_state.db
INFO     | Whisper transcriber initialized successfully
INFO     | Using persistent state storage at bot_state.db
```

### 7. Test the Bot

1. Open Telegram and find your bot by username
2. Send `/start` to begin
3. Try sending text messages
4. Try sending voice messages (if OpenAI API key is configured)
5. Use `/workout` to start a workout session
6. Use `/status` to check workout status
7. Use `/stop` to clear local state

## Development Workflow

### Project Structure

```
gym-coach-brain/
├── src/gym_coach_brain/
│   ├── bot/                    # Telegram bot implementation
│   │   ├── agent.py           # Conversational agent loop
│   │   ├── main.py            # Bot entrypoint
│   │   ├── persistence.py     # State persistence
│   │   ├── speech.py          # Voice transcription
│   │   ├── state.py           # User state management
│   │   └── channels/
│   │       └── telegram.py    # Telegram adapter
│   ├── api/                   # Backend API handlers
│   ├── core/                  # Core business logic
│   └── data/                  # Database models
├── tests/                     # Test suite
├── pyproject.toml            # Dependencies
└── DEVELOPMENT.md            # This file
```

### Running Tests

Run the full test suite:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov=gym_coach_brain --cov-report=html
```

Run specific tests:

```bash
uv run pytest tests/bot/test_agent.py
```

### Code Style

The project follows standard Python conventions:

- Type hints for all function signatures
- Docstrings for public APIs
- Line length: 100 characters (soft limit)

Format code with:

```bash
uv run ruff format .
```

Lint code with:

```bash
uv run ruff check .
```

### Debugging

#### Enable Debug Logging

Set the log level in your code or environment:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Inspect Database State

View user states:

```bash
sqlite3 bot_state.db "SELECT * FROM user_states;"
```

View main database:

```bash
sqlite3 gym_coach.sqlite "SELECT * FROM athletes;"
```

#### Common Issues

**Bot doesn't respond:**
- Check that the bot token is correct
- Verify the bot is running (check logs)
- Ensure no firewall is blocking connections

**Voice messages don't work:**
- Verify `OPENAI_API_KEY` is set correctly
- Check OpenAI API quota/billing
- Look for transcription errors in logs

**State not persisting:**
- Check that `bot_state.db` file exists and is writable
- Verify no database lock errors in logs
- Ensure `BOT_STATE_DB_PATH` points to correct location

**Agent not responding:**
- Verify `OPENROUTER_API_KEY` is valid
- Check OpenRouter API status
- Look for API errors in logs

## Advanced Configuration

### Using In-Memory State (Testing Only)

To disable persistent state storage:

```python
# In main.py
await run(use_persistent_state=False)
```

**Warning:** All state will be lost when the bot restarts.

### Custom Conversation Timeout

Set a custom timeout for conversation cleanup:

```bash
export CONVERSATION_TIMEOUT_HOURS=48  # 48 hours instead of default 24
```

### Custom State Database Location

```bash
export BOT_STATE_DB_PATH=/path/to/custom/bot_state.db
```

### Using a Different LLM Model

```bash
export OPENROUTER_MODEL=openai/gpt-4-turbo
```

See [OpenRouter models](https://openrouter.ai/models) for available options.

## Deployment

For production deployment instructions, see [README.md](README.md).

## Troubleshooting

### Database Locked Error

If you see "database is locked" errors:

1. Ensure only one bot instance is running
2. Check for stale lock files
3. Consider using WAL mode (enabled by default in SQLite 3.7+)

### Memory Issues

If the bot consumes too much memory:

1. Reduce `CONVERSATION_TIMEOUT_HOURS` to clean up conversations more frequently
2. Check for memory leaks in custom code
3. Monitor conversation history size

### API Rate Limits

If you hit API rate limits:

1. **OpenAI Whisper:** Reduce voice message usage or upgrade plan
2. **OpenRouter:** Check your rate limits and consider upgrading
3. Implement request queuing if needed

## Getting Help

- Check the [main documentation](../docs/index.md)
- Review [environment variables](docs/environment-variables.md)
- Look at existing tests for examples
- Check logs for error messages

## Contributing

When contributing code:

1. Write tests for new features
2. Update documentation
3. Follow existing code style
4. Add type hints
5. Include docstrings

## License

See [LICENSE](../LICENSE) file for details.
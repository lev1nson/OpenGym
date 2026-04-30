# Environment Variables Reference

This document lists all environment variables used by the OpenGym Telegram bot.

## Required Variables

These variables must be set for the bot to function:

### `TELEGRAM_BOT_TOKEN`

**Type:** String  
**Required:** Yes  
**Default:** None

The API token for your Telegram bot, obtained from [@BotFather](https://t.me/BotFather).

**Example:**
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**How to obtain:**
1. Message @BotFather on Telegram
2. Send `/newbot` command
3. Follow prompts to create your bot
4. Copy the token provided

---

### `OPENROUTER_API_KEY`

**Type:** String  
**Required:** Yes  
**Default:** None

API key for OpenRouter, used for LLM-powered conversational agent.

**Example:**
```bash
OPENROUTER_API_KEY=sk-or-v1-abc123def456...
```

**How to obtain:**
1. Visit [OpenRouter](https://openrouter.ai/)
2. Sign up or log in
3. Navigate to Keys section
4. Create a new API key

---

## Optional Variables

These variables have sensible defaults but can be customized:

### `OPENAI_API_KEY`

**Type:** String  
**Required:** No (but required for voice message support)  
**Default:** None

OpenAI API key for Whisper speech-to-text transcription.

**Example:**
```bash
OPENAI_API_KEY=sk-proj-abc123def456...
```

**Notes:**
- If not set, voice message support will be disabled
- Users can still send text messages
- Bot will notify users that voice messages are unavailable

**How to obtain:**
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new API key

---

### `OPENROUTER_MODEL`

**Type:** String  
**Required:** No  
**Default:** `anthropic/claude-3.5-sonnet` (or as configured in code)

The LLM model to use for the conversational agent.

**Example:**
```bash
OPENROUTER_MODEL=openai/gpt-4-turbo
```

**Popular options:**
- `anthropic/claude-3.5-sonnet` - Balanced performance and cost
- `openai/gpt-4-turbo` - High quality, higher cost
- `openai/gpt-3.5-turbo` - Faster, lower cost
- `meta-llama/llama-3.1-70b-instruct` - Open source option

See [OpenRouter models](https://openrouter.ai/models) for full list.

---

### `BOT_STATE_DB_PATH`

**Type:** String (file path)  
**Required:** No  
**Default:** `bot_state.db`

Path to the SQLite database file for storing user state.

**Example:**
```bash
BOT_STATE_DB_PATH=/var/lib/gym-coach/bot_state.db
```

**Notes:**
- Path can be relative or absolute
- Directory must exist and be writable
- File will be created automatically if it doesn't exist
- Backup this file regularly to prevent data loss

---

### `CONVERSATION_TIMEOUT_HOURS`

**Type:** Integer  
**Required:** No  
**Default:** `24`

Number of hours of inactivity before a conversation is cleaned up from memory.

**Example:**
```bash
CONVERSATION_TIMEOUT_HOURS=48
```

**Notes:**
- Helps manage memory usage
- Does not affect persistent user state (profiles, workouts)
- Only clears conversation history
- Set to `0` to disable cleanup (not recommended)

**Recommended values:**
- Development: `1-4` hours (faster cleanup for testing)
- Production: `24-48` hours (balance between memory and UX)

---

## Database Configuration

### Main Application Database

The main application database (`gym_coach.sqlite`) is configured separately and typically doesn't require environment variables for local development.

For production deployments, you may want to configure:

- Database connection string
- Connection pool settings
- Backup schedule

These are typically configured in the deployment scripts or systemd service files.

---

## Advanced Configuration

### Logging

While not directly configurable via environment variables in the current implementation, you can modify logging behavior by:

1. Setting Python's `PYTHONUNBUFFERED=1` for immediate log output
2. Configuring loguru in code for custom log levels
3. Redirecting logs to files in production

**Example systemd configuration:**
```ini
[Service]
Environment="PYTHONUNBUFFERED=1"
StandardOutput=append:/var/log/gym-coach-bot/output.log
StandardError=append:/var/log/gym-coach-bot/error.log
```

---

## Environment File Example

Create a `.env` file in the `gym-coach-brain` directory:

```bash
# Required
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
OPENROUTER_API_KEY=sk-or-v1-abc123def456...

# Optional - Voice support
OPENAI_API_KEY=sk-proj-abc123def456...

# Optional - Configuration
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
BOT_STATE_DB_PATH=bot_state.db
CONVERSATION_TIMEOUT_HOURS=24
```

**Security Notes:**
- Never commit `.env` files to version control
- Add `.env` to `.gitignore`
- Use different tokens for development and production
- Rotate API keys regularly
- Restrict file permissions: `chmod 600 .env`

---

## Loading Environment Variables

### Development

The bot automatically loads environment variables from:
1. System environment
2. `.env` file (if present)

### Production

For production deployments, set environment variables in:

1. **systemd service file:**
   ```ini
   [Service]
   Environment="TELEGRAM_BOT_TOKEN=..."
   Environment="OPENROUTER_API_KEY=..."
   ```

2. **Docker/Container:**
   ```yaml
   environment:
     - TELEGRAM_BOT_TOKEN=...
     - OPENROUTER_API_KEY=...
   ```

3. **Shell profile:**
   ```bash
   export TELEGRAM_BOT_TOKEN=...
   export OPENROUTER_API_KEY=...
   ```

---

## Validation

The bot validates required environment variables on startup:

- **Missing `TELEGRAM_BOT_TOKEN`:** Bot will not start, raises `RuntimeError`
- **Missing `OPENROUTER_API_KEY`:** Agent loop may fail, check logs
- **Missing `OPENAI_API_KEY`:** Voice support disabled, warning logged

Check logs on startup to verify configuration:

```
INFO     | Using persistent state storage at bot_state.db
INFO     | Whisper transcriber initialized successfully
INFO     | Bot started successfully
```

Or if there are issues:

```
WARNING  | Whisper transcriber not available: OpenAI API key is required
INFO     | Voice messages will not be supported
```

---

## Troubleshooting

### "TELEGRAM_BOT_TOKEN is required" Error

**Cause:** The `TELEGRAM_BOT_TOKEN` environment variable is not set.

**Solution:**
1. Verify the variable is set: `echo $TELEGRAM_BOT_TOKEN`
2. Check `.env` file exists and is in the correct directory
3. Ensure no typos in variable name
4. Restart the bot after setting the variable

### Voice Messages Not Working

**Cause:** `OPENAI_API_KEY` is not set or invalid.

**Solution:**
1. Set the `OPENAI_API_KEY` variable
2. Verify the key is valid on OpenAI platform
3. Check API quota and billing status
4. Restart the bot

### Agent Not Responding

**Cause:** `OPENROUTER_API_KEY` is not set or invalid.

**Solution:**
1. Verify the key is set correctly
2. Check OpenRouter account status
3. Review API logs for errors
4. Try a different model if current one is unavailable

---

## Security Best Practices

1. **Never hardcode credentials** in source code
2. **Use different keys** for development and production
3. **Rotate keys regularly** (every 90 days recommended)
4. **Restrict file permissions** on `.env` files
5. **Monitor API usage** for unusual activity
6. **Revoke compromised keys** immediately
7. **Use secrets management** in production (e.g., HashiCorp Vault, AWS Secrets Manager)

---

## See Also

- [DEVELOPMENT.md](../DEVELOPMENT.md) - Local development setup
- [README.md](../README.md) - Production deployment guide
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)
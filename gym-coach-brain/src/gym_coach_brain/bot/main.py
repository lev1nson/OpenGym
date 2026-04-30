"""Long-polling entrypoint for the Telegram bot scaffold."""
from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher
from loguru import logger

from gym_coach_brain.bot.agent import AgentLoop
from gym_coach_brain.bot.bus import MessageBus
from gym_coach_brain.bot.channels.telegram import BackendClient, BackendResult, TelegramBotController
from gym_coach_brain.bot.openrouter_client import OpenRouterClient
from gym_coach_brain.bot.persistence import SQLiteUserStateStore
from gym_coach_brain.bot.speech import WhisperTranscriber
from gym_coach_brain.bot.state import InMemoryUserStateStore
from gym_coach_brain.api.main import execute_intent
from gym_coach_brain.core.science import ScienceConfig, load_science_config
from gym_coach_brain.data.session import get_session


class ApiBackendClient(BackendClient):
    """Thin adapter that calls the structured gym_coach_brain API boundary."""

    def __init__(
        self,
        *,
        engine=None,
        science: ScienceConfig | None = None,
    ) -> None:
        self._engine = engine
        self._science = science or load_science_config()

    async def start_workout(
        self,
        *,
        sleep_hours: float,
        pre_readiness: int,
    ) -> BackendResult:
        return await self._execute(
            "workout_start",
            [
                "--sleep-hours",
                f"{sleep_hours:g}",
                "--pre-readiness",
                str(pre_readiness),
            ],
        )

    async def get_workout_status(self) -> BackendResult:
        return await self._execute("workout_status", [])

    async def get_profile_status(self) -> BackendResult:
        return await self._execute("profile_show", [])

    async def start_onboarding(self, *, reset: bool = False) -> BackendResult:
        argv: list[str] = []
        if reset:
            argv.append("--reset")
        return await self._execute("onboarding_start", argv)

    async def answer_onboarding(
        self,
        *,
        question_id: str,
        answer: str,
    ) -> BackendResult:
        return await self._execute(
            "onboarding_answer",
            ["--question", question_id, "--answer", answer],
        )

    async def complete_onboarding(self) -> BackendResult:
        return await self._execute("onboarding_complete", [])

    async def save_post_checkin(
        self,
        *,
        session_id: int,
        post_feeling: int,
    ) -> BackendResult:
        return await self._execute(
            "workout_post_checkin",
            [
                "--session-id",
                str(session_id),
                "--post-feeling",
                str(post_feeling),
            ],
        )

    async def _execute(self, intent: str, argv: list[str]) -> BackendResult:
        payload = await asyncio.to_thread(self._execute_sync, intent, argv)
        return BackendResult(
            stdout=str(payload["stdout"]),
            exit_code=int(payload["exit_code"]),
            data=dict(payload.get("data", {})),
        )

    def _execute_sync(self, intent: str, argv: list[str]) -> dict[str, object]:
        with get_session(self._engine) as session:
            return execute_intent(
                intent,
                argv,
                session=session,
                science=self._science,
            )


async def run(
    *,
    token: str | None = None,
    engine=None,
    science: ScienceConfig | None = None,
    openrouter_api_key: str | None = None,
    openrouter_model: str | None = None,
    state_db_path: str | None = None,
    use_persistent_state: bool = True,
) -> None:
    """Create the aiogram runtime, start the agent loop, and begin long polling."""
    resolved_token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not resolved_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    # Initialize state store based on configuration
    if use_persistent_state:
        db_path = state_db_path or os.environ.get("BOT_STATE_DB_PATH", "bot_state.db")
        try:
            state_store = SQLiteUserStateStore(db_path=db_path)
            logger.info("Using persistent state storage at {}", db_path)
        except Exception as e:
            logger.error("Failed to initialize persistent state store: {}", e)
            logger.warning("Falling back to in-memory state store")
            state_store = InMemoryUserStateStore()
    else:
        state_store = InMemoryUserStateStore()
        logger.info("Using in-memory state storage (data will be lost on restart)")

    bus = MessageBus()

    # Initialize Whisper transcriber for voice messages
    transcriber: WhisperTranscriber | None = None
    try:
        transcriber = WhisperTranscriber()
        logger.info("Whisper transcriber initialized successfully")
    except ValueError as e:
        logger.warning("Whisper transcriber not available: {}", e)
        logger.info("Voice messages will not be supported")
    except Exception as e:
        logger.error("Failed to initialize Whisper transcriber: {}", e)
        logger.info("Voice messages will not be supported")

    bot = Bot(token=resolved_token)
    dispatcher = Dispatcher()
    controller = TelegramBotController(
        bot=bot,
        backend=ApiBackendClient(engine=engine, science=science),
        bus=bus,
        state_store=state_store,
        transcriber=transcriber,
    )
    dispatcher.include_router(controller.router)

    llm_client = OpenRouterClient(
        api_key=openrouter_api_key,
        model=openrouter_model,
    )
    agent_loop = AgentLoop(bus=bus, llm_client=llm_client)
    agent_task = asyncio.create_task(agent_loop.run_loop(state_store))
    cleanup_task = asyncio.create_task(agent_loop.run_cleanup_loop())
    outbound_task = asyncio.create_task(controller.run_outbound_loop())

    try:
        await dispatcher.start_polling(bot)
    finally:
        agent_task.cancel()
        cleanup_task.cancel()
        outbound_task.cancel()
        await asyncio.gather(agent_task, cleanup_task, outbound_task, return_exceptions=True)
        await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

"""aiogram 3 transport adapter and deterministic check-in controller."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Protocol, Sequence

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from gym_coach_brain.bot.bus import InboundEvent, MessageBus, OutboundEvent, OutboundMessage
from gym_coach_brain.bot.channels.base import BaseChannel, ButtonSpec, TransportMessage
from gym_coach_brain.bot.speech import WhisperTranscriber, cleanup_audio_file, download_telegram_voice
from gym_coach_brain.bot.state import UserState, UserStateStore

SLEEP_OPTIONS = (5.0, 6.5, 7.5, 9.0)
READINESS_OPTIONS = (2, 5, 9)
POST_FEELING_OPTIONS = (2, 5, 9)

SLEEP_BUTTONS = tuple(
    ButtonSpec(label=f"{value:g}h", payload=f"sleep:{value:g}")
    for value in SLEEP_OPTIONS
)
READINESS_BUTTONS = tuple(
    ButtonSpec(label=str(value), payload=f"ready:{value}")
    for value in READINESS_OPTIONS
)
POST_FEELING_BUTTONS = tuple(
    ButtonSpec(label=str(value), payload=f"post:{value}")
    for value in POST_FEELING_OPTIONS
)


class SupportsSendMessage(Protocol):
    """Minimal bot protocol used by the transport adapter."""

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> object:
        ...


@dataclass(frozen=True, slots=True)
class BackendResult:
    """Normalized response from the backend API boundary."""

    stdout: str
    exit_code: int
    data: dict[str, object]

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class BackendClient(Protocol):
    """Narrow backend seam used by the Telegram transport layer."""

    async def start_workout(
        self,
        *,
        sleep_hours: float,
        pre_readiness: int,
    ) -> BackendResult:
        ...

    async def get_workout_status(self) -> BackendResult:
        ...

    async def save_post_checkin(
        self,
        *,
        session_id: int,
        post_feeling: int,
    ) -> BackendResult:
        ...


class TelegramChannel(BaseChannel):
    """Telegram adapter that normalizes inbound/outbound transport details."""

    def __init__(
        self,
        *,
        bot: SupportsSendMessage,
        chat_id: int,
        user_id: str,
        inbox: asyncio.Queue[TransportMessage],
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._user_id = user_id
        self._inbox = inbox

    @property
    def user_id(self) -> str:
        return self._user_id

    async def send(
        self,
        text: str,
        buttons: Sequence[ButtonSpec] = (),
    ) -> None:
        await self._bot.send_message(
            chat_id=self._chat_id,
            text=text,
            reply_markup=_build_keyboard(buttons),
        )

    async def receive(self) -> TransportMessage:
        return await self._inbox.get()

    async def ingest_text(self, text: str) -> TransportMessage:
        stripped = text.strip()
        command = None
        kind: str = "text"
        if stripped.startswith("/"):
            kind = "command"
            command = stripped.split()[0].split("@", 1)[0][1:]
        message = TransportMessage(
            user_id=self._user_id,
            chat_id=self._chat_id,
            kind=kind,
            text=stripped,
            command=command,
        )
        try:
            self._inbox.put_nowait(message)
        except asyncio.QueueFull:
            pass
        return message

    async def ingest_callback(self, callback_data: str) -> TransportMessage:
        message = TransportMessage(
            user_id=self._user_id,
            chat_id=self._chat_id,
            kind="callback",
            callback_data=callback_data,
        )
        try:
            self._inbox.put_nowait(message)
        except asyncio.QueueFull:
            pass
        return message


class TelegramBotController:
    """Registers aiogram 3 routes and runs the deterministic bot scaffold."""

    def __init__(
        self,
        *,
        bot: SupportsSendMessage,
        backend: BackendClient,
        bus: MessageBus,
        state_store: UserStateStore,
        transcriber: WhisperTranscriber | None = None,
    ) -> None:
        self._bot = bot
        self._backend = backend
        self._bus = bus
        self._state_store = state_store
        self._transcriber = transcriber
        self._inboxes: dict[str, asyncio.Queue[TransportMessage]] = {}
        self._chat_ids: dict[str, int] = {}
        self.router = Router(name="telegram-bot")
        self.router.message.register(self.handle_start_command, Command("start"))
        self.router.message.register(self.handle_workout_command, Command("workout"))
        self.router.message.register(self.handle_status_command, Command("status"))
        self.router.message.register(self.handle_stop_command, Command("stop"))
        self.router.callback_query.register(self.handle_callback_query)
        # Register voice message handler before text handler (more specific)
        self.router.message.register(self.handle_voice_message, lambda m: m.voice is not None)
        self.router.message.register(self.handle_text_message)

    async def handle_start_command(self, message: Message) -> None:
        channel = self._channel_from_message(message)
        state = self._state(channel.user_id)
        normalized = await channel.ingest_text(message.text or "/start")
        await self._bus.publish_inbound(
            InboundEvent(
                kind="user_message",
                user_id=channel.user_id,
                message=normalized,
                active_session_id=state.active_session_id,
            )
        )

    async def handle_workout_command(self, message: Message) -> None:
        channel = self._channel_from_message(message)
        state = self._state(channel.user_id)
        state.start_precheckin()
        await self._send_sleep_prompt(channel)

    async def handle_status_command(self, message: Message) -> None:
        channel = self._channel_from_message(message)
        state = self._state(channel.user_id)
        await channel.ingest_text(message.text or "/status")
        result = await self._backend.get_workout_status()
        if result.ok:
            session_id = result.data.get("session_id")
            if isinstance(session_id, int):
                state.active_session_id = session_id
        await channel.send(result.stdout)

    async def handle_stop_command(self, message: Message) -> None:
        channel = self._channel_from_message(message)
        state = self._state(channel.user_id)
        await channel.ingest_text(message.text or "/stop")
        active_session_id = state.active_session_id
        state.clear_pending()
        state.active_session_id = active_session_id
        await channel.send("Local bot state cleared. Active backend workout, if any, was left unchanged.")

    async def handle_text_message(self, message: Message) -> None:
        text = message.text or ""
        if not text:
            return

        channel = self._channel_from_message(message)
        normalized = await channel.ingest_text(text)
        if normalized.command in {"start", "workout", "status", "stop"}:
            return

        state = self._state(channel.user_id)
        if state.pending_checkin_sleep:
            await self._send_sleep_prompt(channel)
            return
        if state.pending_checkin_readiness:
            await self._send_readiness_prompt(channel)
            return
        if state.pending_postcheckin:
            await self._send_post_checkin_prompt(channel)
            return

        await self._bus.publish_inbound(
            InboundEvent(
                kind="user_message",
                user_id=channel.user_id,
                message=normalized,
                active_session_id=state.active_session_id,
            )
        )

    async def handle_voice_message(self, message: Message) -> None:
        """Handle voice messages by transcribing them and processing as text."""
        if not message.voice:
            return

        channel = self._channel_from_message(message)
        state = self._state(channel.user_id)

        # Check if transcriber is available
        if not self._transcriber:
            logger.warning("Voice message received but transcriber not configured")
            await channel.send(
                "Голосовые сообщения временно недоступны. Пожалуйста, отправь текстом."
            )
            return

        # Notify user that we're processing
        await channel.send("🎤 Обрабатываю голосовое сообщение...")

        temp_file: Path | None = None
        try:
            # Download voice file to temporary location
            temp_dir = Path(tempfile.gettempdir()) / "gym_coach_voice"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"voice_{message.voice.file_id}.ogg"

            await download_telegram_voice(
                bot=self._bot,
                file_id=message.voice.file_id,
                destination=temp_file,
            )

            # Transcribe the audio
            transcribed_text = await self._transcriber.transcribe_with_fallback(
                audio_file=temp_file,
                fallback_message="Не удалось распознать голосовое сообщение. Попробуй ещё раз или отправь текстом.",
            )

            logger.info(
                "Transcribed voice message from user {}: {}",
                channel.user_id,
                transcribed_text[:100],
            )

            # If transcription failed (returned fallback), send error and return
            if transcribed_text.startswith("Не удалось распознать"):
                await channel.send(transcribed_text)
                return

            # Process transcribed text through normal flow
            normalized = await channel.ingest_text(transcribed_text)

            # Check for deterministic flow states
            if state.pending_checkin_sleep:
                await self._send_sleep_prompt(channel)
                return
            if state.pending_checkin_readiness:
                await self._send_readiness_prompt(channel)
                return
            if state.pending_postcheckin:
                await self._send_post_checkin_prompt(channel)
                return

            # Send to agent loop
            await self._bus.publish_inbound(
                InboundEvent(
                    kind="user_message",
                    user_id=channel.user_id,
                    message=normalized,
                    active_session_id=state.active_session_id,
                )
            )

        except Exception as e:
            logger.error("Failed to process voice message: {}", e)
            await channel.send(
                "Произошла ошибка при обработке голосового сообщения. Попробуй ещё раз или отправь текстом."
            )

        finally:
            # Clean up temporary file
            if temp_file:
                cleanup_audio_file(temp_file)

    async def handle_callback_query(self, callback_query: CallbackQuery) -> None:
        message = callback_query.message
        if message is None or callback_query.data is None:
            return

        channel = self._channel_from_message(message, user_id=callback_query.from_user.id)
        normalized = await channel.ingest_callback(callback_query.data)
        await callback_query.answer()
        state = self._state(channel.user_id)

        if callback_query.data.startswith("sleep:"):
            await self._handle_sleep_callback(channel, state, normalized)
            return
        if callback_query.data.startswith("ready:"):
            await self._handle_readiness_callback(channel, state, normalized)
            return
        if callback_query.data.startswith("post:"):
            await self._handle_post_checkin_callback(channel, state, normalized)
            return

        await channel.send("Unsupported callback payload.")

    async def _handle_sleep_callback(
        self,
        channel: TelegramChannel,
        state: UserState,
        message: TransportMessage,
    ) -> None:
        if not state.pending_checkin_sleep:
            await self._send_sleep_prompt(channel)
            return

        sleep_hours = _parse_float_payload(message.callback_data, prefix="sleep:")
        if sleep_hours not in SLEEP_OPTIONS:
            await self._send_sleep_prompt(channel)
            return

        state.advance_to_readiness(sleep_hours)
        await self._send_readiness_prompt(channel)

    async def _handle_readiness_callback(
        self,
        channel: TelegramChannel,
        state: UserState,
        message: TransportMessage,
    ) -> None:
        if not state.pending_checkin_readiness or state.selected_sleep_hours is None:
            await self._send_sleep_prompt(channel)
            return

        readiness = _parse_int_payload(message.callback_data, prefix="ready:")
        if readiness not in READINESS_OPTIONS:
            await self._send_readiness_prompt(channel)
            return

        sleep_hours = state.selected_sleep_hours
        result = await self._backend.start_workout(
            sleep_hours=sleep_hours,
            pre_readiness=readiness,
        )
        if result.ok:
            session_id = result.data.get("session_id")
            state.clear_pending()
            if isinstance(session_id, int):
                state.active_session_id = session_id
            await self._bus.publish_inbound(
                InboundEvent(
                    kind="checkin_complete",
                    user_id=channel.user_id,
                    message=message,
                    active_session_id=state.active_session_id,
                    sleep_hours=sleep_hours,
                    pre_readiness=readiness,
                )
            )
        await channel.send(result.stdout)

    async def _handle_post_checkin_callback(
        self,
        channel: TelegramChannel,
        state: UserState,
        message: TransportMessage,
    ) -> None:
        if not state.pending_postcheckin or state.active_session_id is None:
            await self._send_post_checkin_prompt(channel)
            return

        post_feeling = _parse_int_payload(message.callback_data, prefix="post:")
        if post_feeling not in POST_FEELING_OPTIONS:
            await self._send_post_checkin_prompt(channel)
            return

        result = await self._backend.save_post_checkin(
            session_id=state.active_session_id,
            post_feeling=post_feeling,
        )
        if result.ok:
            state.pending_postcheckin = False
            await self._bus.publish_inbound(
                InboundEvent(
                    kind="post_checkin",
                    user_id=channel.user_id,
                    message=message,
                    active_session_id=state.active_session_id,
                    post_feeling=post_feeling,
                )
            )
        await channel.send(result.stdout)

    async def _send_sleep_prompt(self, channel: TelegramChannel) -> None:
        await channel.send(
            "Select sleep hours before the workout session starts.",
            buttons=SLEEP_BUTTONS,
        )

    async def _send_readiness_prompt(self, channel: TelegramChannel) -> None:
        await channel.send(
            "Select pre-workout readiness.",
            buttons=READINESS_BUTTONS,
        )

    async def _send_post_checkin_prompt(self, channel: TelegramChannel) -> None:
        await channel.send(
            "Select post-workout feeling.",
            buttons=POST_FEELING_BUTTONS,
        )

    async def run_outbound_loop(self) -> None:
        while True:
            event = await self._bus.consume_outbound()
            await self._deliver_outbound(event)

    async def _deliver_outbound(self, event: OutboundEvent | OutboundMessage) -> None:
        chat_id = self._chat_ids.get(event.user_id)
        if chat_id is None:
            return

        buttons = event.buttons if isinstance(event, OutboundEvent) else ()
        await self._bot.send_message(
            chat_id=chat_id,
            text=event.text,
            reply_markup=_build_keyboard(buttons),
        )

    def _channel_from_message(
        self,
        message: Message,
        *,
        user_id: int | None = None,
    ) -> TelegramChannel:
        normalized_user_id = str(user_id if user_id is not None else message.from_user.id)
        self._chat_ids[normalized_user_id] = message.chat.id
        inbox = self._inboxes.get(normalized_user_id)
        if inbox is None:
            inbox = asyncio.Queue(maxsize=1)
            self._inboxes[normalized_user_id] = inbox
        return TelegramChannel(
            bot=self._bot,
            chat_id=message.chat.id,
            user_id=normalized_user_id,
            inbox=inbox,
        )

    def _state(self, user_id: str) -> UserState:
        return self._state_store.get(user_id)


def _build_keyboard(buttons: Sequence[ButtonSpec]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for index, button in enumerate(buttons, start=1):
        row.append(
            InlineKeyboardButton(text=button.label, callback_data=button.payload)
        )
        if len(row) == 2 or index == len(buttons):
            inline_keyboard.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _parse_float_payload(value: str | None, *, prefix: str) -> float | None:
    if value is None or not value.startswith(prefix):
        return None
    try:
        return float(value.removeprefix(prefix))
    except ValueError:
        return None


def _parse_int_payload(value: str | None, *, prefix: str) -> int | None:
    if value is None or not value.startswith(prefix):
        return None
    try:
        return int(value.removeprefix(prefix))
    except ValueError:
        return None

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from aiogram.types import CallbackQuery, Message

from gym_coach_brain.bot.bus import MessageBus
from gym_coach_brain.bot.channels.base import ButtonSpec, TransportMessage
from gym_coach_brain.bot.channels.telegram import (
    BackendResult,
    SLEEP_BUTTONS,
    TelegramBotController,
    TelegramChannel,
)
from gym_coach_brain.bot.state import InMemoryUserStateStore


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> object:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
        }
        self.sent_messages.append(payload)
        return payload


class FakeBackend:
    def __init__(self) -> None:
        self.start_calls: list[tuple[float, int]] = []
        self.status_calls = 0
        self.post_calls: list[tuple[int, int]] = []

    async def start_workout(
        self,
        *,
        sleep_hours: float,
        pre_readiness: int,
    ) -> BackendResult:
        self.start_calls.append((sleep_hours, pre_readiness))
        return BackendResult(
            stdout="Workout created",
            exit_code=0,
            data={"session_id": 501},
        )

    async def get_workout_status(self) -> BackendResult:
        self.status_calls += 1
        return BackendResult(stdout="Active workout #501", exit_code=0, data={"session_id": 501})

    async def save_post_checkin(
        self,
        *,
        session_id: int,
        post_feeling: int,
    ) -> BackendResult:
        self.post_calls.append((session_id, post_feeling))
        return BackendResult(
            stdout="Post check-in saved",
            exit_code=0,
            data={"session_id": session_id, "post_feeling": post_feeling},
        )


@dataclass
class FakeMessage:
    text: str
    user_id: int = 42
    chat_id: int = 99

    def __post_init__(self) -> None:
        self.from_user = SimpleNamespace(id=self.user_id)
        self.chat = SimpleNamespace(id=self.chat_id)


@dataclass
class FakeCallbackQuery:
    data: str
    user_id: int = 42
    chat_id: int = 99

    def __post_init__(self) -> None:
        self.from_user = SimpleNamespace(id=self.user_id)
        self.message = FakeMessage(text="", user_id=self.user_id, chat_id=self.chat_id)
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


def _keyboard_payloads(reply_markup) -> list[str]:
    if reply_markup is None:
        return []
    return [
        button.callback_data
        for row in reply_markup.inline_keyboard
        for button in row
    ]


@pytest.mark.asyncio
async def test_channel_normalizes_callbacks_and_renders_buttons():
    bot = FakeBot()
    channel = TelegramChannel(
        bot=bot,
        chat_id=99,
        user_id="42",
        inbox=asyncio.Queue(),
    )

    await channel.send("Pick one", buttons=(ButtonSpec(label="A", payload="a:1"),))
    await channel.ingest_callback("sleep:7.5")
    message = await channel.receive()

    assert isinstance(message, TransportMessage)
    assert message.kind == "callback"
    assert message.callback_data == "sleep:7.5"
    assert _keyboard_payloads(bot.sent_messages[-1]["reply_markup"]) == ["a:1"]
    assert not isinstance(message, Message)
    assert not isinstance(message, CallbackQuery)


@pytest.mark.asyncio
async def test_workout_flow_advances_sleep_to_readiness_and_publishes_handoff():
    bot = FakeBot()
    backend = FakeBackend()
    bus = MessageBus()
    state_store = InMemoryUserStateStore()
    controller = TelegramBotController(
        bot=bot,
        backend=backend,
        bus=bus,
        state_store=state_store,
    )

    await controller.handle_workout_command(FakeMessage("/workout"))
    await controller.handle_callback_query(FakeCallbackQuery("sleep:7.5"))
    await controller.handle_callback_query(FakeCallbackQuery("ready:5"))

    state = state_store.get("42")
    event = await bus.consume_inbound()

    assert _keyboard_payloads(bot.sent_messages[0]["reply_markup"]) == [
        button.payload for button in SLEEP_BUTTONS
    ]
    assert backend.start_calls == [(7.5, 5)]
    assert state.pending_checkin_sleep is False
    assert state.pending_checkin_readiness is False
    assert state.selected_sleep_hours is None
    assert state.active_session_id == 501
    assert bot.sent_messages[-1]["text"] == "Workout created"
    assert event.kind == "checkin_complete"
    assert event.active_session_id == 501
    assert event.sleep_hours == 7.5
    assert event.pre_readiness == 5


@pytest.mark.asyncio
async def test_pending_text_repeats_keyboard_and_does_not_publish_bus_event():
    bot = FakeBot()
    backend = FakeBackend()
    bus = MessageBus()
    controller = TelegramBotController(
        bot=bot,
        backend=backend,
        bus=bus,
        state_store=InMemoryUserStateStore(),
    )

    await controller.handle_workout_command(FakeMessage("/workout"))
    await controller.handle_text_message(FakeMessage("hello"))

    assert backend.start_calls == []
    assert bus._inbound.empty()
    assert bot.sent_messages[-1]["text"] == "Select sleep hours before the workout session starts."
    assert _keyboard_payloads(bot.sent_messages[-1]["reply_markup"]) == [
        button.payload for button in SLEEP_BUTTONS
    ]


@pytest.mark.asyncio
async def test_post_checkin_uses_backend_seam_without_direct_db_access():
    bot = FakeBot()
    backend = FakeBackend()
    bus = MessageBus()
    state_store = InMemoryUserStateStore()
    controller = TelegramBotController(
        bot=bot,
        backend=backend,
        bus=bus,
        state_store=state_store,
    )
    state = state_store.get("42")
    state.active_session_id = 501
    state.pending_postcheckin = True

    await controller.handle_callback_query(FakeCallbackQuery("post:9"))
    event = await bus.consume_inbound()

    assert backend.post_calls == [(501, 9)]
    assert state.pending_postcheckin is False
    assert state.active_session_id == 501
    assert bot.sent_messages[-1]["text"] == "Post check-in saved"
    assert event.kind == "post_checkin"
    assert event.post_feeling == 9
    assert event.active_session_id == 501


@pytest.mark.asyncio
async def test_status_and_stop_commands_use_backend_and_only_clear_local_state():
    bot = FakeBot()
    backend = FakeBackend()
    state_store = InMemoryUserStateStore()
    controller = TelegramBotController(
        bot=bot,
        backend=backend,
        bus=MessageBus(),
        state_store=state_store,
    )
    state = state_store.get("42")
    state.pending_checkin_sleep = True
    state.pending_postcheckin = True
    state.selected_sleep_hours = 6.5
    state.active_session_id = 501

    await controller.handle_status_command(FakeMessage("/status"))
    await controller.handle_stop_command(FakeMessage("/stop"))

    assert backend.status_calls == 1
    assert bot.sent_messages[0]["text"] == "Active workout #501"
    assert state.pending_checkin_sleep is False
    assert state.pending_checkin_readiness is False
    assert state.pending_postcheckin is False
    assert state.selected_sleep_hours is None
    assert state.active_session_id == 501

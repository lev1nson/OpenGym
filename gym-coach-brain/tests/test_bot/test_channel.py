from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from aiogram.types import CallbackQuery, Message

from gym_coach_brain.bot.bus import MessageBus, OutboundEvent
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
        self.profile_exists = False
        self.onboarding_complete = False
        self.onboarding_questions = [
            "age",
            "experience_level",
            "goal",
            "bodyweight_kg",
            "equipment",
            "training_days_per_week",
            "training_split",
            "sleep_quality",
            "stress_level",
        ]
        self.onboarding_answers: list[tuple[str, str]] = []
        self.onboarding_start_calls = 0
        self.onboarding_complete_calls = 0

    async def get_profile_status(self) -> BackendResult:
        if not self.profile_exists:
            return BackendResult(
                stdout="Профиль не найден. Запустите onboarding_start для создания профиля.",
                exit_code=1,
                data={},
            )
        return BackendResult(
            stdout="Профиль найден",
            exit_code=0,
            data={
                "profile_exists": True,
                "onboarding_complete": self.onboarding_complete,
            },
        )

    async def start_onboarding(self, *, reset: bool = False) -> BackendResult:
        self.onboarding_start_calls += 1
        self.profile_exists = True
        self.onboarding_complete = False
        if reset:
            self.onboarding_answers.clear()
        return BackendResult(
            stdout="Вопрос 1/9: Сколько вам лет? (диапазон: 10-100)",
            exit_code=0,
            data={
                "current_question_id": self.onboarding_questions[0],
                "next_question_id": self.onboarding_questions[1],
                "onboarding_complete": False,
                "onboarding_ready_to_complete": False,
            },
        )

    async def answer_onboarding(
        self,
        *,
        question_id: str,
        answer: str,
    ) -> BackendResult:
        self.onboarding_answers.append((question_id, answer))
        current_index = self.onboarding_questions.index(question_id)
        next_index = current_index + 1
        if next_index < len(self.onboarding_questions):
            return BackendResult(
                stdout=f"Вопрос {next_index + 1}/9: next",
                exit_code=0,
                data={
                    "current_question_id": question_id,
                    "next_question_id": self.onboarding_questions[next_index],
                    "onboarding_complete": False,
                    "onboarding_ready_to_complete": False,
                },
            )
        return BackendResult(
            stdout="Все ответы приняты. Запустите onboarding_complete для завершения.",
            exit_code=0,
            data={
                "current_question_id": question_id,
                "next_question_id": None,
                "onboarding_complete": False,
                "onboarding_ready_to_complete": True,
            },
        )

    async def complete_onboarding(self) -> BackendResult:
        self.onboarding_complete_calls += 1
        self.profile_exists = True
        self.onboarding_complete = True
        return BackendResult(
            stdout="✅ Онбординг завершён!",
            exit_code=0,
            data={"profile_exists": True, "onboarding_complete": True},
        )

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
async def test_start_command_publishes_to_agent_bus():
    bot = FakeBot()
    backend = FakeBackend()
    bus = MessageBus()
    controller = TelegramBotController(
        bot=bot,
        backend=backend,
        bus=bus,
        state_store=InMemoryUserStateStore(),
    )

    await controller.handle_start_command(FakeMessage("/start"))
    event = await bus.consume_inbound()

    assert bot.sent_messages == []
    assert event.kind == "user_message"
    assert event.message.text == "/start"


@pytest.mark.asyncio
async def test_first_text_goes_to_agent_bus_without_transport_onboarding_gate():
    bot = FakeBot()
    backend = FakeBackend()
    bus = MessageBus()
    controller = TelegramBotController(
        bot=bot,
        backend=backend,
        bus=bus,
        state_store=InMemoryUserStateStore(),
    )

    await controller.handle_text_message(FakeMessage("привет"))
    event = await bus.consume_inbound()

    assert bot.sent_messages == []
    assert event.kind == "user_message"
    assert event.message.text == "привет"


@pytest.mark.asyncio
async def test_outbound_loop_delivers_agent_reply_back_to_same_chat():
    bot = FakeBot()
    backend = FakeBackend()
    bus = MessageBus()
    controller = TelegramBotController(
        bot=bot,
        backend=backend,
        bus=bus,
        state_store=InMemoryUserStateStore(),
    )

    await controller.handle_text_message(FakeMessage("привет", user_id=42, chat_id=99))
    outbound_task = asyncio.create_task(controller.run_outbound_loop())
    await bus.publish_outbound(OutboundEvent(user_id="42", text="Привет. Чем помочь?"))
    await asyncio.sleep(0)
    outbound_task.cancel()
    await asyncio.gather(outbound_task, return_exceptions=True)

    assert bot.sent_messages[-1]["chat_id"] == 99
    assert bot.sent_messages[-1]["text"] == "Привет. Чем помочь?"


@pytest.mark.asyncio
async def test_workout_flow_advances_sleep_to_readiness_and_publishes_handoff():
    bot = FakeBot()
    backend = FakeBackend()
    backend.profile_exists = True
    backend.onboarding_complete = True
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
    backend.profile_exists = True
    backend.onboarding_complete = True
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
    backend.profile_exists = True
    backend.onboarding_complete = True
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
    backend.profile_exists = True
    backend.onboarding_complete = True
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

from __future__ import annotations

from pathlib import Path

import pytest

from gym_coach_brain.bot.agent import AgentLoop
from gym_coach_brain.bot.bus import InboundEvent, InboundMessage, MessageBus
from gym_coach_brain.bot.channels.base import TransportMessage
from gym_coach_brain.bot.openrouter_client import LLMResponse, LLMToolCall
from gym_coach_brain.bot.state import UserState
from gym_coach_brain.bot.tools import ToolExecutionResult, apply_result_to_state


class SequencedLLMClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    async def create_response(self, *, messages, tools):
        self.calls.append(messages)
        if not self._responses:
            raise AssertionError("No response queued")
        return self._responses.pop(0)


class SequencedToolExecutor:
    def __init__(self, results):
        self._results = list(results)
        self.calls: list[str] = []

    def execute(self, *, tool_name, arguments_json, state, tool_call_id=None):
        del arguments_json, tool_call_id
        self.calls.append(tool_name)
        if not self._results:
            raise AssertionError("No result queued")
        result = self._results.pop(0)
        apply_result_to_state(state, result)
        return result


def _prompt_file(tmp_path: Path) -> Path:
    prompt_path = tmp_path / "system.md"
    prompt_path.write_text("Ты тренер.", encoding="utf-8")
    return prompt_path


@pytest.mark.asyncio
async def test_e2e_agent_loop_handles_workout_flow_handoffs(tmp_path: Path) -> None:
    bus = MessageBus()
    llm = SequencedLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id="1", name="workout_start", arguments="{}")],
            ),
            LLMResponse(content="Тренировка началась. Начни с первого упражнения.", tool_calls=[]),
            LLMResponse(
                content=None,
                tool_calls=[
                    LLMToolCall(
                        id="2",
                        name="workout_log_set",
                        arguments='{"exercise_id":11,"set_number":1,"weight_kg":80,"reps":8,"rir":2}',
                    )
                ],
            ),
            LLMResponse(content="Подход записал. Можешь делать следующий.", tool_calls=[]),
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id="3", name="workout_finish", arguments="{}")],
            ),
            LLMResponse(content="Тренировку завершил. Как самочувствие после сессии?", tool_calls=[]),
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id="4", name="workout_summary", arguments='{"session_id":77}')],
            ),
            LLMResponse(content="Итог: объём выполнен, восстановление держим под контролем.", tool_calls=[]),
        ]
    )
    tool_executor = SequencedToolExecutor(
        [
            ToolExecutionResult(
                name="workout_start",
                intent="workout_start",
                exit_code=0,
                stdout="1. Жим лёжа (id:11): 3x6-8 @ 80.0кг",
                argv=[],
                data={"session_id": 77},
            ),
            ToolExecutionResult(
                name="workout_log_set",
                intent="workout_log_set",
                exit_code=0,
                stdout="✅ Подход записан",
                argv=[],
                data={"session_id": 77},
            ),
            ToolExecutionResult(
                name="workout_finish",
                intent="workout_finish",
                exit_code=0,
                stdout="Тренировка завершена",
                argv=[],
                data={"session_id": 77},
            ),
            ToolExecutionResult(
                name="workout_summary",
                intent="workout_summary",
                exit_code=0,
                stdout="Итог тренировки",
                argv=[],
                data={"session_id": 77},
            ),
        ]
    )
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=tool_executor,
        prompt_path=_prompt_file(tmp_path),
    )
    state = UserState(
        pending_checkin_sleep=False,
        pending_checkin_readiness=False,
        current_stage="checkin_complete",
    )

    await bus.publish_inbound(InboundMessage(user_id="athlete", text="Поехали"))
    outbound = await loop.run_once(state)
    assert "Тренировка началась" in outbound.text
    assert state.active_session_id == 77
    assert state.known_exercise_ids["Жим лёжа"] == 11

    await bus.publish_inbound(InboundMessage(user_id="athlete", text="Сделал 8 повторений"))
    outbound = await loop.run_once(state)
    assert "Подход записал" in outbound.text

    await bus.publish_inbound(InboundMessage(user_id="athlete", text="Заканчиваем"))
    outbound = await loop.run_once(state)
    assert "Как самочувствие" in outbound.text
    assert state.pending_postcheckin is True
    assert state.current_stage == "post_workout_checkin"

    state.pending_postcheckin = False
    state.current_stage = "chat"
    await bus.publish_inbound(InboundMessage(user_id="athlete", text="Покажи итог"))
    outbound = await loop.run_once(state)
    assert "Итог" in outbound.text

    assert tool_executor.calls == [
        "workout_start",
        "workout_log_set",
        "workout_finish",
        "workout_summary",
    ]


@pytest.mark.asyncio
async def test_e2e_checkin_event_triggers_workout_start(tmp_path: Path) -> None:
    """InboundEvent(kind='checkin_complete') normalizes through _normalize_inbound and reaches the agent."""
    bus = MessageBus()
    llm = SequencedLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id="1", name="workout_start", arguments="{}")],
            ),
            LLMResponse(content="Тренировка началась!", tool_calls=[]),
        ]
    )
    tool_executor = SequencedToolExecutor(
        [
            ToolExecutionResult(
                name="workout_start",
                intent="workout_start",
                exit_code=0,
                stdout="1. Жим лёжа (id:11): 3x6-8 @ 80.0кг",
                argv=[],
                data={"session_id": 55},
            )
        ]
    )
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=tool_executor,
        prompt_path=_prompt_file(tmp_path),
    )
    state = UserState()

    transport_msg = TransportMessage(
        user_id="athlete",
        chat_id=999,
        kind="callback",
        callback_data="readiness:4",
    )
    event = InboundEvent(
        kind="checkin_complete",
        user_id="athlete",
        message=transport_msg,
        sleep_hours=7.5,
        pre_readiness=4,
    )
    await bus.publish_inbound(event)
    outbound = await loop.run_once(state)

    assert "Тренировка началась" in outbound.text
    assert tool_executor.calls == ["workout_start"]
    # Verify state updated from normalized event
    assert state.active_session_id == 55
    # Verify the LLM received the correct context — text should describe completed check-in.
    # messages list is mutated in-place so index 2 is always the initial user message
    # (0=system_prompt, 1=state_summary, 2=user_text).
    initial_user_msg = llm.calls[0][2]
    assert initial_user_msg["role"] == "user"
    assert "завершён" in initial_user_msg["content"]


@pytest.mark.asyncio
async def test_e2e_freeform_first_message_routes_into_onboarding_tools(tmp_path: Path) -> None:
    bus = MessageBus()
    llm = SequencedLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id="1", name="profile_show", arguments="{}")],
            ),
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id="2", name="onboarding_start", arguments="{}")],
            ),
            LLMResponse(
                content="Привет. Давай начнём с короткого онбординга. Сколько тебе лет?",
                tool_calls=[],
            ),
        ]
    )
    tool_executor = SequencedToolExecutor(
        [
            ToolExecutionResult(
                name="profile_show",
                intent="profile_show",
                exit_code=1,
                stdout="Профиль не найден. Запустите onboarding_start для создания профиля.",
                argv=[],
                data=None,
            ),
            ToolExecutionResult(
                name="onboarding_start",
                intent="onboarding_start",
                exit_code=0,
                stdout="Вопрос 1/9: Сколько вам лет? (диапазон: 10-100)",
                argv=[],
                data={
                    "profile_exists": True,
                    "onboarding_complete": False,
                    "onboarding_status": "in_progress",
                    "current_question_id": "age",
                    "next_question_id": "experience_level",
                    "onboarding_ready_to_complete": False,
                },
            ),
        ]
    )
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=tool_executor,
        prompt_path=_prompt_file(tmp_path),
    )
    state = UserState()

    await bus.publish_inbound(InboundMessage(user_id="athlete", text="привет"))
    outbound = await loop.run_once(state)

    assert "онбординга" in outbound.text
    assert tool_executor.calls == ["profile_show", "onboarding_start"]
    assert state.profile_exists is True
    assert state.onboarding_status == "in_progress"
    assert state.current_onboarding_question_id == "age"

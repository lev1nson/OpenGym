from __future__ import annotations

import json
from pathlib import Path

import pytest

from gym_coach_brain.bot.agent import ATHLETE_SAFE_FALLBACK, AgentLoop
from gym_coach_brain.bot.bus import InboundMessage, MessageBus
from gym_coach_brain.bot.openrouter_client import LLMResponse, LLMToolCall
from gym_coach_brain.bot.state import UserState
from gym_coach_brain.bot.tools import ToolExecutionResult


class FakeLLMClient:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict[str, object]]] = []

    async def create_response(self, *, messages, tools) -> LLMResponse:
        del tools
        self.calls.append(messages)
        if not self._responses:
            raise AssertionError("No more fake LLM responses queued")
        return self._responses.pop(0)


class FakeToolExecutor:
    def __init__(self, results: list[ToolExecutionResult]) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, str]] = []

    def execute(self, *, tool_name, arguments_json, state, tool_call_id=None) -> ToolExecutionResult:
        del state
        self.calls.append((tool_name, arguments_json))
        if not self._results:
            raise AssertionError("No more fake tool results queued")
        result = self._results.pop(0)
        result.tool_call_id = tool_call_id
        return result


def _prompt_file(tmp_path: Path, text: str = "Ты тренер.") -> Path:
    prompt_path = tmp_path / "system.md"
    prompt_path.write_text(text, encoding="utf-8")
    return prompt_path


@pytest.mark.asyncio
async def test_agent_executes_tool_and_returns_final_reply(tmp_path: Path) -> None:
    bus = MessageBus()
    await bus.publish_inbound(InboundMessage(user_id="42", text="Начинаем тренировку"))
    llm = FakeLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    LLMToolCall(
                        id="tool-1",
                        name="workout_start",
                        arguments="{}",
                    )
                ],
            ),
            LLMResponse(content="Погнали. Первая цель: разминочный сет на жим.", tool_calls=[]),
        ]
    )
    tool_executor = FakeToolExecutor(
        [
            ToolExecutionResult(
                name="workout_start",
                intent="workout_start",
                exit_code=0,
                stdout="1. Жим лёжа (id:11): 3x6-8 @ 80.0кг",
                argv=[],
                data={"session_id": 77},
            )
        ]
    )
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=tool_executor,
        prompt_path=_prompt_file(tmp_path),
    )

    outbound = await loop.run_once(UserState())

    assert outbound.text == "Погнали. Первая цель: разминочный сет на жим."
    assert tool_executor.calls == [("workout_start", "{}")]


@pytest.mark.asyncio
async def test_agent_handles_exit_code_1_user_error_path(tmp_path: Path) -> None:
    bus = MessageBus()
    await bus.publish_inbound(InboundMessage(user_id="42", text="Покажи итог"))
    llm = FakeLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    LLMToolCall(id="tool-1", name="workout_summary", arguments="{}"),
                ],
            ),
            LLMResponse(content="Пока нет завершённых тренировок. Сначала закончи текущую сессию.", tool_calls=[]),
        ]
    )
    tool_executor = FakeToolExecutor(
        [
            ToolExecutionResult(
                name="workout_summary",
                intent="workout_summary",
                exit_code=1,
                stdout="История завершённых тренировок пока пуста.",
                argv=[],
            )
        ]
    )
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=tool_executor,
        prompt_path=_prompt_file(tmp_path),
    )

    outbound = await loop.run_once(UserState())

    assert "нет завершённых тренировок" in outbound.text


@pytest.mark.asyncio
async def test_agent_handles_exit_code_2_system_error_immediately(tmp_path: Path) -> None:
    """exit_code=2 must return ATHLETE_SAFE_FALLBACK directly without querying LLM again."""
    bus = MessageBus()
    await bus.publish_inbound(InboundMessage(user_id="42", text="Покажи статус"))
    llm = FakeLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id="tool-1", name="workout_status", arguments="{}")],
            ),
            # Second response should NOT be consumed — loop must return fallback after exit_code=2
        ]
    )
    tool_executor = FakeToolExecutor(
        [
            ToolExecutionResult(
                name="workout_status",
                intent="workout_status",
                exit_code=2,
                stdout="System error: sqlite locked",
                argv=[],
            )
        ]
    )
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=tool_executor,
        prompt_path=_prompt_file(tmp_path),
    )

    outbound = await loop.run_once(UserState())

    assert outbound.text == ATHLETE_SAFE_FALLBACK
    # Only one LLM call — the fallback reply does NOT invoke LLM a second time
    assert len(llm.calls) == 1


def test_tool_executor_handles_malformed_backend_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from gym_coach_brain.bot.tools import ToolExecutor

    class CompletedProcess:
        stdout = "not-json"

    monkeypatch.setattr("gym_coach_brain.bot.tools.subprocess.run", lambda *args, **kwargs: CompletedProcess())
    executor = ToolExecutor()

    result = executor.execute(
        tool_name="workout_status",
        arguments_json="{}",
        state=UserState(),
        tool_call_id="tool-1",
    )

    assert result.exit_code == 2
    assert "malformed JSON" in result.stdout


@pytest.mark.asyncio
async def test_history_is_truncated_to_latest_turns(tmp_path: Path) -> None:
    bus = MessageBus()
    llm = FakeLLMClient([LLMResponse(content="Принято.", tool_calls=[]) for _ in range(25)])
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=FakeToolExecutor([]),
        prompt_path=_prompt_file(tmp_path),
        max_history_turns=3,
    )
    state = UserState()

    for index in range(4):
        await bus.publish_inbound(InboundMessage(user_id="u1", text=f"msg-{index}"))
        await loop.run_once(state)

    await bus.publish_inbound(InboundMessage(user_id="u1", text="msg-4"))
    await loop.run_once(state)
    last_call_messages = llm.calls[-1]
    prior_history = last_call_messages[2:-1]

    assert [message["content"] for message in prior_history] == [
        "msg-1",
        "Принято.",
        "msg-2",
        "Принято.",
        "msg-3",
        "Принято.",
    ]


@pytest.mark.asyncio
async def test_prompt_is_loaded_from_file(tmp_path: Path) -> None:
    prompt_path = _prompt_file(tmp_path, "Системный prompt из файла.")
    bus = MessageBus()
    await bus.publish_inbound(InboundMessage(user_id="42", text="Привет"))
    llm = FakeLLMClient([LLMResponse(content="Привет.", tool_calls=[])])
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=FakeToolExecutor([]),
        prompt_path=prompt_path,
    )

    await loop.run_once(UserState())

    assert llm.calls[0][0]["content"] == "Системный prompt из файла."


@pytest.mark.asyncio
async def test_agent_stops_at_max_iteration_cutoff(tmp_path: Path) -> None:
    bus = MessageBus()
    await bus.publish_inbound(InboundMessage(user_id="42", text="Старт"))
    llm = FakeLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[LLMToolCall(id=f"tool-{index}", name="workout_status", arguments="{}")],
            )
            for index in range(10)
        ]
    )
    tool_executor = FakeToolExecutor(
        [
            ToolExecutionResult(
                name="workout_status",
                intent="workout_status",
                exit_code=0,
                stdout=json.dumps({"noop": True}, ensure_ascii=False),
                argv=[],
            )
            for _ in range(10)
        ]
    )
    loop = AgentLoop(
        bus=bus,
        llm_client=llm,
        tool_executor=tool_executor,
        prompt_path=_prompt_file(tmp_path),
        max_iterations=10,
    )

    outbound = await loop.run_once(UserState())

    assert outbound.text == ATHLETE_SAFE_FALLBACK

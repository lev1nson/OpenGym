"""Bounded conversational agent loop for the workout coach."""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
from typing import Any

from loguru import logger

from gym_coach_brain.bot.bus import InboundEvent, InboundMessage, MessageBus, OutboundEvent
from gym_coach_brain.bot.openrouter_client import LLMClient
from gym_coach_brain.bot.state import UserState, UserStateStore
from gym_coach_brain.bot.tools import TOOL_SCHEMAS, ToolExecutionResult, ToolExecutor


DEFAULT_HISTORY_TURNS = 20
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_CONVERSATION_TIMEOUT_HOURS = 24
ATHLETE_SAFE_FALLBACK = (
    "Сейчас не получилось надёжно обработать сообщение. Попробуй ещё раз через минуту."
)
_RE_INTERNAL_ID = re.compile(r"\s*\(id:\d+\)")
_RE_TECHNICAL_FIELDS = re.compile(
    r"(exercise_id|exit_code|OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN)",
    re.IGNORECASE,
)


class AgentLoop:
    """Conversation loop that routes chat through OpenRouter and backend tools."""

    def __init__(
        self,
        *,
        bus: MessageBus,
        llm_client: LLMClient,
        tool_executor: ToolExecutor | None = None,
        prompt_path: str | Path | None = None,
        max_history_turns: int = DEFAULT_HISTORY_TURNS,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        conversation_timeout_hours: int | None = None,
    ) -> None:
        self.bus = bus
        self.llm_client = llm_client
        self.tool_executor = tool_executor or ToolExecutor()
        self.prompt_path = (
            Path(prompt_path)
            if prompt_path
            else Path(__file__).with_name("prompts") / "system.md"
        )
        self.max_history_turns = max_history_turns
        self.max_iterations = max_iterations
        
        # Conversation timeout configuration
        if conversation_timeout_hours is None:
            env_timeout = os.environ.get("CONVERSATION_TIMEOUT_HOURS")
            conversation_timeout_hours = (
                int(env_timeout) if env_timeout else DEFAULT_CONVERSATION_TIMEOUT_HOURS
            )
        self.conversation_timeout_hours = conversation_timeout_hours
        
        # History storage with timestamps
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.max_history_turns * 2)
        )
        self._last_activity: dict[str, datetime] = {}

    async def run_once(self, state: UserState) -> OutboundEvent:
        """Consume one inbound message, process it, and publish one outbound reply."""
        inbound = self._normalize_inbound(await self.bus.consume_inbound())
        outbound = await self.handle_inbound(inbound=inbound, state=state)
        await self.bus.publish_outbound(outbound)
        return outbound

    async def handle_inbound(self, *, inbound: InboundMessage, state: UserState) -> OutboundEvent:
        """Handle one inbound message and return the outbound reply."""
        history = self._history[inbound.user_id]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.load_system_prompt()},
            {"role": "system", "content": self._build_state_summary(state, inbound)},
            *list(history),
            {"role": "user", "content": inbound.text},
        ]

        for iteration in range(1, self.max_iterations + 1):
            try:
                response = await self.llm_client.create_response(
                    messages=list(messages),
                    tools=TOOL_SCHEMAS,
                )
            except Exception:
                logger.exception("OpenRouter request failed on iteration {}", iteration)
                return self._finalize_reply(
                    user_id=inbound.user_id,
                    user_text=inbound.text,
                    reply_text=ATHLETE_SAFE_FALLBACK,
                )

            if response.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.name,
                                    "arguments": tool_call.arguments,
                                },
                            }
                            for tool_call in response.tool_calls
                        ],
                    }
                )
                for tool_call in response.tool_calls:
                    result = self.tool_executor.execute(
                        tool_name=tool_call.name,
                        arguments_json=tool_call.arguments,
                        state=state,
                        tool_call_id=tool_call.id,
                    )
                    messages.append(self._tool_message(result))
                    if result.exit_code == 2:
                        logger.error(
                            "Tool {} returned system error (exit_code=2): {}",
                            result.name,
                            result.stdout,
                        )
                        return self._finalize_reply(
                            user_id=inbound.user_id,
                            user_text=inbound.text,
                            reply_text=ATHLETE_SAFE_FALLBACK,
                        )
                continue

            reply_text = self._sanitize_athlete_reply(response.content)
            if not reply_text:
                logger.error("Model returned empty final reply")
                reply_text = ATHLETE_SAFE_FALLBACK
            return self._finalize_reply(
                user_id=inbound.user_id,
                user_text=inbound.text,
                reply_text=reply_text,
            )

        logger.error(
            "Agent loop hit max_iterations={} for user {}",
            self.max_iterations,
            inbound.user_id,
        )
        return self._finalize_reply(
            user_id=inbound.user_id,
            user_text=inbound.text,
            reply_text=ATHLETE_SAFE_FALLBACK,
        )

    async def run_loop(self, state_store: UserStateStore) -> None:
        """Continuously consume bus events and dispatch replies. Run as a background task."""
        while True:
            try:
                inbound_raw = await self.bus.consume_inbound()
                inbound = self._normalize_inbound(inbound_raw)
                state = state_store.get(inbound.user_id)
                outbound = await self.handle_inbound(inbound=inbound, state=state)
                await self.bus.publish_outbound(outbound)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AgentLoop.run_loop iteration failed")

    def load_system_prompt(self) -> str:
        """Read the system prompt from disk so it remains versionable."""
        return self.prompt_path.read_text(encoding="utf-8").strip()

    def _build_state_summary(self, state: UserState, inbound: InboundMessage) -> str:
        summary = state.compact_summary()
        summary["transport_metadata"] = inbound.metadata
        return "Current user state:\n" + json.dumps(
            summary,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def _finalize_reply(self, *, user_id: str, user_text: str, reply_text: str) -> OutboundEvent:
        history = self._history[user_id]
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})
        # Update last activity timestamp
        self._last_activity[user_id] = datetime.now()
        return OutboundEvent(user_id=user_id, text=reply_text)

    def cleanup_stale_conversations(self) -> int:
        """
        Remove conversation history for users inactive beyond the timeout period.
        
        Returns:
            Number of conversations cleaned up.
        """
        if self.conversation_timeout_hours <= 0:
            return 0
            
        now = datetime.now()
        timeout_delta = timedelta(hours=self.conversation_timeout_hours)
        stale_users: list[str] = []
        
        for user_id, last_activity in self._last_activity.items():
            if now - last_activity > timeout_delta:
                stale_users.append(user_id)
        
        for user_id in stale_users:
            self._history.pop(user_id, None)
            self._last_activity.pop(user_id, None)
            logger.info(
                "Cleaned up stale conversation for user {} (inactive for {} hours)",
                user_id,
                self.conversation_timeout_hours,
            )
        
        return len(stale_users)

    async def run_cleanup_loop(self) -> None:
        """
        Background task that periodically cleans up stale conversations.
        Runs every hour.
        """
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                cleaned = self.cleanup_stale_conversations()
                if cleaned > 0:
                    logger.info("Cleanup task removed {} stale conversations", cleaned)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in cleanup loop")

    def _sanitize_athlete_reply(self, content: str | None) -> str:
        if not content:
            return ""

        sanitized = _RE_INTERNAL_ID.sub("", content)
        if _RE_TECHNICAL_FIELDS.search(sanitized):
            logger.warning("Suppressed technical assistant reply: {}", sanitized)
            return ATHLETE_SAFE_FALLBACK
        if sanitized.lstrip().startswith("{") and "\"intent\"" in sanitized:
            logger.warning("Suppressed raw JSON assistant reply")
            return ATHLETE_SAFE_FALLBACK
        return sanitized.strip()

    @staticmethod
    def _tool_message(result: ToolExecutionResult) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": result.tool_call_id,
            "name": result.name,
            "content": result.model_payload(),
        }

    def _normalize_inbound(self, inbound: InboundMessage | InboundEvent) -> InboundMessage:
        if isinstance(inbound, InboundMessage):
            return inbound

        metadata: dict[str, Any] = {
            "event_kind": inbound.kind,
            "active_session_id": inbound.active_session_id,
            "sleep_hours": inbound.sleep_hours,
            "pre_readiness": inbound.pre_readiness,
            "post_feeling": inbound.post_feeling,
            "transport_kind": inbound.message.kind,
        }
        if inbound.message.callback_data is not None:
            metadata["callback_data"] = inbound.message.callback_data

        if inbound.kind == "checkin_complete":
            text = (
                "Детерминированный pre-workout check-in завершён. "
                "Спортсмен готов начать тренировку."
            )
        elif inbound.kind == "post_checkin":
            text = (
                "Детерминированный post-workout check-in завершён. "
                "Учитывай это состояние в ответе."
            )
        else:
            text = inbound.message.text or inbound.message.callback_data or "Новое сообщение от спортсмена."

        return InboundMessage(user_id=inbound.user_id, text=text, metadata=metadata)

"""Typed asyncio-backed message bus for bot transport and agent orchestration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal

from gym_coach_brain.bot.channels.base import ButtonSpec, TransportMessage


InboundEventKind = Literal["user_message", "checkin_complete", "post_checkin"]


@dataclass(frozen=True, slots=True)
class InboundEvent:
    """Transport-agnostic inbound event for the future agent loop."""

    kind: InboundEventKind
    user_id: str
    message: TransportMessage
    active_session_id: int | None = None
    sleep_hours: float | None = None
    pre_readiness: int | None = None
    post_feeling: int | None = None

    @property
    def text(self) -> str:
        if self.message.text:
            return self.message.text
        if self.message.callback_data:
            return self.message.callback_data
        if self.message.command:
            return self.message.command
        return ""


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """Simpler inbound message used directly by the AgentLoop and its tests."""

    user_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutboundEvent:
    """Typed outbound payload for agent replies."""

    user_id: str
    text: str
    buttons: tuple[ButtonSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    """Simpler outbound message for direct agent tests."""

    user_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageBus:
    """Thin wrapper around separate inbound/outbound asyncio queues."""

    def __init__(self) -> None:
        self._inbound: asyncio.Queue[InboundEvent | InboundMessage] = asyncio.Queue()
        self._outbound: asyncio.Queue[OutboundEvent | OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, event: InboundEvent | InboundMessage) -> None:
        await self._inbound.put(event)

    async def consume_inbound(self) -> InboundEvent | InboundMessage:
        return await self._inbound.get()

    async def publish_outbound(self, event: OutboundEvent | OutboundMessage) -> None:
        await self._outbound.put(event)

    async def consume_outbound(self) -> OutboundEvent | OutboundMessage:
        return await self._outbound.get()

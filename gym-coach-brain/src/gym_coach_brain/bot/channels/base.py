"""Transport-neutral bot channel primitives."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Sequence


MessageKind = Literal["text", "command", "callback"]


@dataclass(frozen=True, slots=True)
class ButtonSpec:
    """Normalized button metadata independent of Telegram types."""

    label: str
    payload: str


@dataclass(frozen=True, slots=True)
class TransportMessage:
    """Normalized inbound message shape for the bot stack."""

    user_id: str
    chat_id: int
    kind: MessageKind
    text: str | None = None
    command: str | None = None
    callback_data: str | None = None


class BaseChannel(ABC):
    """Transport adapter contract shared by Telegram and future channels."""

    @property
    @abstractmethod
    def user_id(self) -> str:
        """Return the normalized user identifier."""

    @abstractmethod
    async def send(
        self,
        text: str,
        buttons: Sequence[ButtonSpec] = (),
    ) -> None:
        """Send a message through the underlying transport."""

    @abstractmethod
    async def receive(self) -> TransportMessage:
        """Receive the next normalized inbound message."""

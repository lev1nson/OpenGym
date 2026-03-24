"""OpenRouter client using the OpenAI-compatible chat completions surface."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Protocol

from openai import AsyncOpenAI


@dataclass(slots=True)
class LLMToolCall:
    """One tool call requested by the model."""

    id: str
    name: str
    arguments: str


@dataclass(slots=True)
class LLMResponse:
    """Normalized assistant message returned by the LLM client."""

    content: str | None
    tool_calls: list[LLMToolCall]


class LLMClient(Protocol):
    """Protocol for pluggable LLM clients."""

    async def create_response(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Request one assistant turn."""


class OpenRouterClient:
    """OpenRouter wrapper around the OpenAI-compatible chat completions API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 30.0,
        client: AsyncOpenAI | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not resolved_api_key:
            raise ValueError("OPENROUTER_API_KEY is required")

        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
        self._client = client or AsyncOpenAI(
            api_key=resolved_api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=timeout_seconds,
        )

    async def create_response(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        completion = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )
        if not completion.choices:
            raise ValueError("OpenRouter returned empty choices array")
        message = completion.choices[0].message
        tool_calls = [
            LLMToolCall(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=tool_call.function.arguments,
            )
            for tool_call in (message.tool_calls or [])
        ]
        return LLMResponse(content=message.content, tool_calls=tool_calls)

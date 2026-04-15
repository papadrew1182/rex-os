"""Provider-agnostic model client abstraction.

Session 1 scope: define the interface and ship a null/echo implementation
so the streaming endpoint is demoable without real credentials. Anthropic
is the default provider behind the abstraction — not hardwired into the
app.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class ModelMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ModelRequest:
    model_key: str
    messages: list[ModelMessage]
    system_prompt: str | None = None
    max_tokens: int = 1024
    metadata: dict[str, str] = field(default_factory=dict)


class ModelClient(Protocol):
    async def stream_completion(
        self, request: ModelRequest
    ) -> AsyncIterator[str]: ...

    async def complete(self, request: ModelRequest) -> str: ...


class EchoModelClient:
    """Deterministic stub client used when no provider is configured."""

    model_key = "echo"

    async def stream_completion(
        self, request: ModelRequest
    ) -> AsyncIterator[str]:
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            "",
        )
        reply = (
            f"(echo) You asked: {last_user}\n\n"
            "This stub response comes from the Session 1 AI spine. "
            "Wire a real provider via REX_AI_PROVIDER to replace it."
        )
        for chunk in _chunk_text(reply, size=24):
            yield chunk

    async def complete(self, request: ModelRequest) -> str:
        parts: list[str] = []
        async for chunk in self.stream_completion(request):
            parts.append(chunk)
        return "".join(parts)


class AnthropicModelClient:
    """Anthropic-backed client (default provider when credentials present).

    Not wired up in Session 1. The class exists so the selector can point
    at it and so Session 2/3 do not need to guess the interface.
    """

    def __init__(self, *, api_key: str, default_model: str = "claude-opus-4-6") -> None:
        self._api_key = api_key
        self.model_key = default_model

    async def stream_completion(
        self, request: ModelRequest
    ) -> AsyncIterator[str]:
        raise NotImplementedError(
            "AnthropicModelClient is a Session 1 placeholder. "
            "Set REX_AI_PROVIDER=echo until the SDK integration lands."
        )
        yield ""  # pragma: no cover — makes this an async generator

    async def complete(self, request: ModelRequest) -> str:
        raise NotImplementedError(
            "AnthropicModelClient is a Session 1 placeholder. "
            "Set REX_AI_PROVIDER=echo until the SDK integration lands."
        )


def get_model_client() -> ModelClient:
    """Resolve the active model client from environment."""
    provider = os.getenv("REX_AI_PROVIDER", "echo").lower()
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return EchoModelClient()
        return AnthropicModelClient(api_key=api_key)
    return EchoModelClient()


def _chunk_text(text: str, *, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]

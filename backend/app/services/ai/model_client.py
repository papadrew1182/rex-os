"""Provider-agnostic model client abstraction.

Session 1 ships two concrete providers:

* ``EchoModelClient`` — deterministic stub used as the default when
  ``REX_AI_PROVIDER`` is unset. Produces a chunked echo of the last
  user message so local development, tests, and CI all work without
  provider credentials.
* ``AnthropicModelClient`` — real streaming integration over the
  ``anthropic`` Python SDK. Activated with ``REX_AI_PROVIDER=anthropic``
  and ``ANTHROPIC_API_KEY=...``. Optional model override via
  ``REX_ANTHROPIC_MODEL`` (default: ``claude-sonnet-4-6``).

Failure semantics (per Session 1 charter): when the caller explicitly
asks for Anthropic but the SDK or API key are missing, we do NOT
silently degrade to echo. Instead, the first call into
``stream_completion`` raises ``ProviderNotConfigured`` — a structured
exception that ``chat_service`` catches and surfaces as a frozen
``error`` SSE event with a specific ``code``. This keeps the app
running (catalog/conversations endpoints still work) while making the
misconfiguration loud and actionable on any chat request.

The SDK import is lazy so environments that only use echo never need
to have ``anthropic`` installed. The helper ``_try_import_anthropic``
is a seam for hermetic tests to monkeypatch the import outcome.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol

DEFAULT_ANTHROPIC_MODEL: str = "claude-sonnet-4-6"


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
    # Phase 6: Anthropic tool_use schemas (already in tool_schema wire format).
    # Echo provider ignores this; Anthropic provider forwards it to the SDK.
    tools: list[dict[str, Any]] | None = None


class ModelClient(Protocol):
    async def stream_completion(
        self, request: ModelRequest
    ) -> AsyncIterator[str]: ...

    async def complete(self, request: ModelRequest) -> str: ...

    async def stream_events(
        self, request: ModelRequest
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields discriminated event dicts.

        Event shapes:
          * ``{"type": "text", "delta": "..."}`` — partial text chunk.
          * ``{"type": "tool_use", "id": "...", "name": "...", "input": {...}}``
            — emitted after the streamed tool_use block is fully assembled.

        Chat service fans these into SSE frames; tool_use events trigger
        ActionQueueService.enqueue.
        """
        ...


class ProviderNotConfigured(Exception):
    """Structured error raised when the selected provider cannot start.

    The ``code`` field is propagated verbatim onto the SSE ``error``
    event by ``chat_service.stream_chat``. Current codes:

    * ``anthropic_sdk_missing`` — ``REX_AI_PROVIDER=anthropic`` but the
      ``anthropic`` Python package is not installed in this environment
    * ``anthropic_api_key_missing`` — ``REX_AI_PROVIDER=anthropic`` but
      ``ANTHROPIC_API_KEY`` is unset or empty
    """

    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ── echo provider ──────────────────────────────────────────────────────────
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

    async def stream_events(
        self, request: ModelRequest
    ) -> AsyncIterator[dict[str, Any]]:
        """Echo client never emits tool_use — it only fans deltas through
        as ``{"type": "text", ...}`` events so the chat service can share
        one code path across providers."""
        async for chunk in self.stream_completion(request):
            yield {"type": "text", "delta": chunk}


# ── anthropic provider ─────────────────────────────────────────────────────
def _try_import_anthropic() -> Any | None:
    """Lazy import seam for hermetic tests.

    Returns the ``anthropic`` module if importable, otherwise ``None``.
    Tests monkeypatch this function to simulate a missing SDK without
    touching ``sys.modules``.
    """
    try:
        import anthropic  # noqa: PLC0415 — intentional lazy import
    except ImportError:
        return None
    return anthropic


class AnthropicModelClient:
    """Anthropic-backed client over the official ``anthropic`` SDK.

    The SDK client is constructed lazily on first use so that:
      * Constructing the dispatcher never blocks on provider config
        (catalog/conversations endpoints always work).
      * Tests can inject a fake client without touching sys.modules.
      * The ``ProviderNotConfigured`` error surface only fires when
        something actually tries to stream a chat, at which point
        ``chat_service`` converts it into a structured SSE event.
    """

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str | None = None,
        _client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self.model_key = default_model or os.getenv(
            "REX_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL
        )
        # ``_client`` is a test seam: tests construct a fake with the
        # same shape (``.messages.stream(...)`` returning an async
        # context manager whose ``text_stream`` iterates strings) and
        # pass it in to bypass the SDK import entirely.
        self._client: Any | None = _client

    # ── internals ─────────────────────────────────────────────────────────
    def _resolve_client(self) -> Any:
        if self._client is not None:
            return self._client

        anthropic_module = _try_import_anthropic()
        if anthropic_module is None:
            raise ProviderNotConfigured(
                code="anthropic_sdk_missing",
                message=(
                    "REX_AI_PROVIDER=anthropic requires the `anthropic` "
                    "Python package. Install it with `pip install anthropic` "
                    "or unset REX_AI_PROVIDER to fall back to the echo client."
                ),
            )

        if not self._api_key:
            raise ProviderNotConfigured(
                code="anthropic_api_key_missing",
                message=(
                    "REX_AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY "
                    "to be set. Set the key in the environment or unset "
                    "REX_AI_PROVIDER to fall back to the echo client."
                ),
            )

        self._client = anthropic_module.AsyncAnthropic(api_key=self._api_key)
        return self._client

    @staticmethod
    def _to_anthropic_messages(
        messages: list[ModelMessage],
    ) -> tuple[str | None, list[dict[str, str]]]:
        """Split the unified message list into (system, user/assistant).

        Anthropic's Messages API takes ``system`` as a top-level field
        and the rest as a flat alternating list. If multiple system
        entries exist we concatenate them with blank-line separators.
        """
        system_parts: list[str] = []
        convo: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue
            if m.role not in ("user", "assistant"):
                continue
            convo.append({"role": m.role, "content": m.content})
        system = "\n\n".join(system_parts) if system_parts else None
        return system, convo

    def _build_stream_kwargs(self, request: ModelRequest) -> dict[str, Any]:
        # Prefer the explicit request.system_prompt if present; the
        # chat_service always sets this so Anthropic receives the
        # canonical role + project context.
        system_from_messages, convo = self._to_anthropic_messages(request.messages)
        system = request.system_prompt or system_from_messages

        stream_kwargs: dict[str, Any] = {
            "model": self.model_key,
            "max_tokens": request.max_tokens,
            "messages": convo,
        }
        if system:
            stream_kwargs["system"] = system
        if request.tools:
            stream_kwargs["tools"] = request.tools
        return stream_kwargs

    # ── protocol impl ─────────────────────────────────────────────────────
    async def stream_completion(
        self, request: ModelRequest
    ) -> AsyncIterator[str]:
        client = self._resolve_client()
        stream_kwargs = self._build_stream_kwargs(request)

        async with client.messages.stream(**stream_kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text

    async def complete(self, request: ModelRequest) -> str:
        parts: list[str] = []
        async for chunk in self.stream_completion(request):
            parts.append(chunk)
        return "".join(parts)

    async def stream_events(
        self, request: ModelRequest
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream Anthropic text deltas, then emit any tool_use blocks.

        Implementation note: we iterate ``text_stream`` for incremental
        text rendering, then pull ``get_final_message()`` from the SDK.
        The SDK reassembles ``input_json_delta`` chunks into a dict for
        each ``tool_use`` content block, so we don't have to buffer
        partial JSON ourselves.
        """
        client = self._resolve_client()
        stream_kwargs = self._build_stream_kwargs(request)

        async with client.messages.stream(**stream_kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield {"type": "text", "delta": text}

            # After the text stream drains, the SDK has the full message
            # (including any tool_use blocks with their assembled input).
            try:
                final_message = await stream.get_final_message()
            except Exception:  # noqa: BLE001
                # If the SDK can't produce a final message, we've already
                # emitted everything we could. Fall silent so text-only
                # conversations still complete normally.
                return

            content = getattr(final_message, "content", None) or []
            for block in content:
                block_type = getattr(block, "type", None)
                if block_type != "tool_use":
                    continue
                yield {
                    "type": "tool_use",
                    "id": getattr(block, "id", None),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", None) or {},
                }


# ── selector ───────────────────────────────────────────────────────────────
def get_model_client() -> ModelClient:
    """Resolve the active model client from environment.

    * ``REX_AI_PROVIDER`` unset (or ``echo``) -> ``EchoModelClient``.
    * ``REX_AI_PROVIDER=anthropic`` -> ``AnthropicModelClient``. SDK
      and API-key presence are validated lazily on first stream call
      via ``ProviderNotConfigured`` so dispatcher construction never
      blocks on provider config.
    * Any other value -> ``EchoModelClient`` (typo-tolerance; the real
      expected failure mode is "user typed anthropec" and they will
      notice echo output immediately).
    """
    provider = os.getenv("REX_AI_PROVIDER", "echo").strip().lower()
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        return AnthropicModelClient(api_key=api_key)
    return EchoModelClient()


def _chunk_text(text: str, *, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


__all__ = [
    "DEFAULT_ANTHROPIC_MODEL",
    "AnthropicModelClient",
    "EchoModelClient",
    "ModelClient",
    "ModelMessage",
    "ModelRequest",
    "ProviderNotConfigured",
    "get_model_client",
]

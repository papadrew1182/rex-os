"""Hermetic tests for the optional Anthropic-backed model provider.

These tests never make network calls. They exercise:

* provider selection via ``REX_AI_PROVIDER``
* the ``ProviderNotConfigured`` error surface when the SDK or the API
  key are missing
* the streaming path with a stubbed SDK client whose ``text_stream``
  yields pre-baked deltas
* the chat service's SSE contract under both a healthy stub stream and
  a misconfigured provider

A real live Anthropic test would require an API key and network
access; it lives (if it exists at all) behind a separate marker and
is not part of this file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from main import app
from app.schemas.assistant import AssistantChatRequest, AssistantUser, PageContext
from app.schemas.catalog import CatalogResponse
from app.services.ai import model_client as mc
from app.services.ai.catalog_import import build_catalog_response_from_source
from app.services.ai.chat_service import ChatService
from app.services.ai.context_builder import ContextBuilder
from app.services.ai.followups import FollowupGenerator
from app.services.ai.model_client import (
    AnthropicModelClient,
    EchoModelClient,
    ModelMessage,
    ModelRequest,
    ProviderNotConfigured,
    get_model_client,
)
from tests._assistant_fakes import FakeChatRepository, FakeDispatcher


# ── fake anthropic SDK surface ────────────────────────────────────────────
class _FakeTextStream:
    """Async iterator of pre-baked text deltas, matching the shape of
    ``anthropic.AsyncStream.text_stream``."""

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = list(deltas)

    def __aiter__(self) -> "_FakeTextStream":
        return self

    async def __anext__(self) -> str:
        if not self._deltas:
            raise StopAsyncIteration
        return self._deltas.pop(0)


class _FakeAnthropicStreamContext:
    def __init__(self, deltas: list[str], captured: dict[str, Any]) -> None:
        self._deltas = deltas
        self._captured = captured
        self.text_stream = _FakeTextStream(deltas)

    async def __aenter__(self) -> "_FakeAnthropicStreamContext":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeMessages:
    def __init__(self, deltas: list[str], captured: dict[str, Any]) -> None:
        self._deltas = deltas
        self._captured = captured

    def stream(self, **kwargs: Any) -> _FakeAnthropicStreamContext:
        self._captured.update(kwargs)
        return _FakeAnthropicStreamContext(list(self._deltas), self._captured)


class _FakeAnthropicClient:
    def __init__(self, deltas: list[str]) -> None:
        self.deltas = deltas
        self.captured: dict[str, Any] = {}
        self.messages = _FakeMessages(self.deltas, self.captured)


# ── provider selection ───────────────────────────────────────────────────
def test_provider_selection_defaults_to_echo(monkeypatch):
    monkeypatch.delenv("REX_AI_PROVIDER", raising=False)
    client = get_model_client()
    assert isinstance(client, EchoModelClient)
    assert client.model_key == "echo"


def test_provider_selection_explicit_echo(monkeypatch):
    monkeypatch.setenv("REX_AI_PROVIDER", "echo")
    client = get_model_client()
    assert isinstance(client, EchoModelClient)


def test_provider_selection_anthropic_returns_anthropic_client(monkeypatch):
    monkeypatch.setenv("REX_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-for-tests")
    client = get_model_client()
    assert isinstance(client, AnthropicModelClient)
    # Dispatcher construction must succeed even when the SDK or key
    # are wrong — the error only surfaces on first stream call.
    assert client.model_key  # default model is set


def test_provider_selection_unknown_value_falls_back_to_echo(monkeypatch):
    """Unknown provider values are treated as typo-tolerance: we return
    echo (which is obviously wrong output at first chat) instead of
    raising at app construction time."""
    monkeypatch.setenv("REX_AI_PROVIDER", "anthropec")  # typo
    assert isinstance(get_model_client(), EchoModelClient)


def test_anthropic_model_key_respects_rex_anthropic_model(monkeypatch):
    monkeypatch.setenv("REX_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    monkeypatch.setenv("REX_ANTHROPIC_MODEL", "claude-opus-4-6")
    client = get_model_client()
    assert isinstance(client, AnthropicModelClient)
    assert client.model_key == "claude-opus-4-6"


# ── missing SDK / missing key → ProviderNotConfigured ───────────────────
async def test_missing_sdk_raises_provider_not_configured(monkeypatch):
    """When ``anthropic`` is not importable, stream_completion raises
    ``ProviderNotConfigured(code='anthropic_sdk_missing')``. The test
    simulates the missing SDK by monkeypatching the lazy-import helper."""
    monkeypatch.setattr(mc, "_try_import_anthropic", lambda: None)
    client = AnthropicModelClient(api_key="sk-fake")

    with pytest.raises(ProviderNotConfigured) as err:
        async for _ in client.stream_completion(
            ModelRequest(model_key="x", messages=[ModelMessage(role="user", content="hi")])
        ):
            pass
    assert err.value.code == "anthropic_sdk_missing"
    assert "pip install anthropic" in err.value.message


async def test_missing_api_key_raises_provider_not_configured(monkeypatch):
    """When the SDK is importable but the API key is missing,
    stream_completion raises ``ProviderNotConfigured`` with the
    ``anthropic_api_key_missing`` code."""
    # Simulate SDK present with a dummy module that has an
    # ``AsyncAnthropic`` attribute so _resolve_client gets past the
    # import check. The key-missing branch should still fire first.
    class _StubSDK:
        class AsyncAnthropic:
            def __init__(self, api_key: str) -> None:
                raise AssertionError("should not be constructed when key is missing")

    monkeypatch.setattr(mc, "_try_import_anthropic", lambda: _StubSDK)
    client = AnthropicModelClient(api_key="")  # empty key

    with pytest.raises(ProviderNotConfigured) as err:
        async for _ in client.stream_completion(
            ModelRequest(model_key="x", messages=[ModelMessage(role="user", content="hi")])
        ):
            pass
    assert err.value.code == "anthropic_api_key_missing"
    assert "ANTHROPIC_API_KEY" in err.value.message


async def test_missing_sdk_also_raises_on_complete(monkeypatch):
    monkeypatch.setattr(mc, "_try_import_anthropic", lambda: None)
    client = AnthropicModelClient(api_key="sk-fake")
    with pytest.raises(ProviderNotConfigured):
        await client.complete(
            ModelRequest(model_key="x", messages=[ModelMessage(role="user", content="hi")])
        )


# ── stubbed streaming path ──────────────────────────────────────────────
async def test_anthropic_streams_deltas_from_stubbed_client():
    """With a pre-wired fake SDK client, ``stream_completion`` yields
    every ``text_stream`` chunk and preserves order."""
    deltas = ["Hello ", "from ", "Claude ", "(stubbed)."]
    fake = _FakeAnthropicClient(deltas)

    client = AnthropicModelClient(
        api_key="sk-fake",
        default_model="claude-sonnet-4-6",
        _client=fake,
    )

    req = ModelRequest(
        model_key=client.model_key,
        system_prompt="You are a test system prompt.",
        messages=[
            ModelMessage(role="system", content="You are a test system prompt."),
            ModelMessage(role="user", content="say hi"),
            ModelMessage(role="assistant", content="(prior turn)"),
            ModelMessage(role="user", content="now really say hi"),
        ],
    )

    got: list[str] = []
    async for chunk in client.stream_completion(req):
        got.append(chunk)

    assert got == deltas

    # ``system`` on the request becomes the top-level system= on the
    # Anthropic API call, and the messages collection excludes system
    # roles but preserves user/assistant order.
    assert fake.captured["system"] == "You are a test system prompt."
    assert fake.captured["model"] == "claude-sonnet-4-6"
    assert fake.captured["max_tokens"] == 1024
    assert fake.captured["messages"] == [
        {"role": "user", "content": "say hi"},
        {"role": "assistant", "content": "(prior turn)"},
        {"role": "user", "content": "now really say hi"},
    ]


async def test_anthropic_complete_aggregates_deltas():
    deltas = ["one ", "two ", "three"]
    fake = _FakeAnthropicClient(deltas)
    client = AnthropicModelClient(api_key="sk-fake", _client=fake)

    result = await client.complete(
        ModelRequest(
            model_key=client.model_key,
            messages=[ModelMessage(role="user", content="x")],
        )
    )
    assert result == "one two three"


async def test_anthropic_skips_empty_deltas():
    """Empty text deltas from the SDK (interleaved with tool/start
    events) must not be yielded as empty SSE frames."""
    fake = _FakeAnthropicClient(["real ", "", "content"])
    client = AnthropicModelClient(api_key="sk-fake", _client=fake)
    got = [c async for c in client.stream_completion(
        ModelRequest(model_key="x", messages=[ModelMessage(role="user", content="hi")])
    )]
    assert got == ["real ", "content"]


# ── chat service SSE contract preservation ─────────────────────────────
async def _run_chat_stream(model_client) -> list[dict]:
    """Drive ``ChatService.stream_chat`` against an in-memory fake chat
    repo and return the decoded SSE events. Uses the real ChatService
    so any change to the event vocabulary would fail loudly."""
    chat_repo = FakeChatRepository()
    followups = FollowupGenerator()
    service = ChatService(
        chat_repo=chat_repo,
        model_client=model_client,
        followup_generator=followups,
    )

    user = AssistantUser(
        id=UUID("20000000-0000-4000-a000-000000000001"),
        email="u@test",
        full_name=None,
        primary_role_key="VP",
        role_keys=["VP"],
        legacy_role_aliases=["vp"],
        project_ids=[],
    )
    ctx_builder = ContextBuilder()
    context = ctx_builder.build_context(
        user=user,
        project_id=None,
        page_context=PageContext(route="/test"),
        system_prompt="You are a test system prompt.",
    )

    req = AssistantChatRequest(
        conversation_id=None,
        message="provider contract smoke",
        project_id=None,
        active_action_slug=None,
        mode="chat",
        params={},
        page_context=PageContext(route="/test"),
    )

    events: list[dict] = []
    async for frame in service.stream_chat(request=req, user=user, context=context):
        frame = frame.strip()
        if frame.startswith("data:"):
            events.append(json.loads(frame[5:].strip()))
    return events


async def test_chat_sse_vocabulary_unchanged_with_stubbed_anthropic():
    """When ChatService drives an AnthropicModelClient wired against a
    stubbed SDK that yields multiple deltas, the frozen SSE event
    vocabulary and ordering must be identical to the echo path."""
    fake = _FakeAnthropicClient(["Hello ", "from ", "stubbed Claude."])
    client = AnthropicModelClient(api_key="sk-fake", _client=fake)

    events = await _run_chat_stream(client)
    types = [e["type"] for e in events]

    for expected in (
        "conversation.created",
        "message.started",
        "message.delta",
        "followups.generated",
        "message.completed",
    ):
        assert expected in types, f"missing {expected}"

    assert types.index("conversation.created") < types.index("message.started")
    first_delta = types.index("message.delta")
    assert first_delta < types.index("followups.generated")
    assert first_delta < types.index("message.completed")

    # Every delta from the fake stream lands as a single SSE delta
    # event, in order.
    delta_payloads = [e["delta"] for e in events if e["type"] == "message.delta"]
    assert delta_payloads == ["Hello ", "from ", "stubbed Claude."]


async def test_chat_sse_emits_error_event_on_missing_sdk(monkeypatch):
    """When AnthropicModelClient raises ``ProviderNotConfigured`` on
    first stream call, the chat service must emit a structured
    ``error`` SSE event with the exception's ``code`` and then stop —
    no delta, no followups, no message.completed."""
    monkeypatch.setattr(mc, "_try_import_anthropic", lambda: None)
    client = AnthropicModelClient(api_key="sk-fake")

    events = await _run_chat_stream(client)
    types = [e["type"] for e in events]

    # Conversation is created and the user message is started BEFORE
    # the model is called, so both events appear even when the
    # provider is broken. That preserves "user message persists before
    # model execution" — the whole point of that contract.
    assert "conversation.created" in types
    assert "message.started" in types

    # Then the stream errors out with a structured code.
    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    err = error_events[0]
    assert err["code"] == "anthropic_sdk_missing"
    assert "pip install anthropic" in err["message"]

    # No followups, no completion, no delta — the stream stopped at
    # the error.
    assert "message.delta" not in types
    assert "followups.generated" not in types
    assert "message.completed" not in types


async def test_chat_sse_emits_error_event_on_missing_key(monkeypatch):
    class _StubSDK:
        class AsyncAnthropic:
            def __init__(self, api_key: str) -> None:
                raise AssertionError("should not be constructed when key is missing")

    monkeypatch.setattr(mc, "_try_import_anthropic", lambda: _StubSDK)
    client = AnthropicModelClient(api_key="")

    events = await _run_chat_stream(client)
    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["code"] == "anthropic_api_key_missing"


# ── router-level: echo path still works and SSE vocabulary unchanged ──
@pytest.fixture
def anthropic_provider_fresh_env(client):
    """Install a fresh FakeDispatcher so the echo-path contract tests
    stay hermetic even while this test file monkeypatches ``mc``."""
    response = CatalogResponse.model_validate(build_catalog_response_from_source())
    saved = getattr(app.state, "assistant_dispatcher", None)
    app.state.assistant_dispatcher = FakeDispatcher.build(response)
    try:
        yield client
    finally:
        if saved is None:
            if hasattr(app.state, "assistant_dispatcher"):
                delattr(app.state, "assistant_dispatcher")
        else:
            app.state.assistant_dispatcher = saved


async def test_echo_default_still_wires_through_router_unchanged(anthropic_provider_fresh_env):
    """Regression guard: after this packet adds Anthropic support, the
    default-echo path through the router must still produce the exact
    same frozen SSE vocabulary Session 3 was promised."""
    resp = await anthropic_provider_fresh_env.post(
        "/api/assistant/chat",
        json={
            "message": "regression guard",
            "page_context": {"route": "/regress"},
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events: list[dict] = []
    for frame in resp.text.split("\n\n"):
        frame = frame.strip()
        if frame.startswith("data:"):
            events.append(json.loads(frame[5:].strip()))

    types = [e["type"] for e in events]
    for expected in (
        "conversation.created",
        "message.started",
        "message.delta",
        "followups.generated",
        "message.completed",
    ):
        assert expected in types

"""Chat-service prompt-injection contract.

When a chat request carries ``active_action_slug`` matching a handler,
the chat service must invoke the dispatcher before building its
ModelRequest and append the handler's prompt_fragment to the system
prompt.

We verify this by mocking the model client so it captures what
system_prompt it was called with.

Adaptations vs. task spec:
* ``AssistantUser`` uses ``id``, ``primary_role_key``, ``role_keys``,
  ``legacy_role_aliases``, ``project_ids`` (no ``user_id``/``legacy_role``).
* ``ChatRepository`` exposes ``get_conversation``/``create_conversation``
  (not ``get_or_create_conversation``); chat_service also calls
  ``touch_conversation``.
* ``FollowupGenerator`` has ``.suggest(...)`` returning
  ``list[FollowupSuggestion]`` (no ``.build``).
* ``AssistantContext`` is the real dataclass; we build a real instance so
  chat_service's attribute access matches production.
* ``stream_completion`` is an async-generator function — calling it must
  return an async iterator directly (no await), so we patch it with a
  plain function returning an async generator instead of AsyncMock.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantUser,
    PageContext,
)
from app.services.ai.action_dispatcher import ActionDispatcher
from app.services.ai.actions.base import ActionResult
from app.services.ai.chat_service import ChatService
from app.services.ai.context_builder import AssistantContext
from app.services.ai.followups import FollowupSuggestion


# ── fakes ──────────────────────────────────────────────────────────────────

class _FakePoolAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_a):
        return None


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakePoolAcquireCtx(self._conn)


class _CaptureHandler:
    slug = "rfi_aging"

    def __init__(self):
        self.called_with = None

    async def run(self, ctx):
        self.called_with = ctx
        return ActionResult(
            stats={"total_open": 23, "oldest_days": 19},
            sample_rows=[],
            prompt_fragment=(
                "## Quick action data: rfi_aging\n\n"
                "Total open RFIs: 23\nOldest: 19 days\n"
            ),
        )


def _make_user() -> AssistantUser:
    return AssistantUser(
        id=uuid4(),
        email="t@t.com",
        full_name="Test",
        primary_role_key="VP",
        role_keys=["VP"],
        legacy_role_aliases=[],
        project_ids=[],
    )


def _make_context(system_prompt: str = "base system prompt") -> AssistantContext:
    return AssistantContext(
        user=_make_user(),
        project_id=None,
        page_context=PageContext(),
        system_prompt=system_prompt,
    )


def _make_chat_repo():
    chat_repo = MagicMock()
    conversation_id = uuid4()
    chat_repo.get_conversation = AsyncMock(return_value=None)
    chat_repo.create_conversation = AsyncMock(
        return_value={"id": conversation_id, "title": "New conversation"}
    )
    chat_repo.append_message = AsyncMock(return_value={"id": uuid4()})
    chat_repo.list_messages = AsyncMock(return_value=[])
    chat_repo.touch_conversation = AsyncMock(return_value=None)
    return chat_repo


# ── tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_service_appends_prompt_fragment_when_slug_present():
    captured: dict = {}

    def fake_stream(model_request):
        # stream_completion is an async-generator function — calling it must
        # return an async iterator directly, not a coroutine.
        captured["system_prompt"] = model_request.system_prompt
        captured["messages"] = list(model_request.messages)

        async def gen():
            yield "ok"

        return gen()

    model_client = MagicMock()
    model_client.model_key = "test-mock"
    model_client.stream_completion = fake_stream

    chat_repo = _make_chat_repo()

    handler = _CaptureHandler()
    dispatcher = ActionDispatcher(handlers=[handler])

    followup = MagicMock()
    followup.suggest = MagicMock(return_value=[FollowupSuggestion(label="sample")])

    pool = _FakePool(conn=MagicMock())

    svc = ChatService(
        chat_repo=chat_repo,
        model_client=model_client,
        followup_generator=followup,
        pool=pool,
        action_dispatcher=dispatcher,
    )

    user = _make_user()
    request = AssistantChatRequest(
        message="Show me RFI aging",
        active_action_slug="rfi_aging",
        params={},
        conversation_id=None,
        project_id=None,
        mode="chat",
    )
    context = _make_context()

    # Drain the stream so stream_completion is actually invoked.
    async for _chunk in svc.stream_chat(request=request, user=user, context=context):
        pass

    assert "system_prompt" in captured, "model_client was not invoked"
    sp = captured["system_prompt"]
    assert "base system prompt" in sp
    assert "Quick action data: rfi_aging" in sp
    assert "Total open RFIs: 23" in sp

    # The first ModelMessage is the system message — its content must also
    # carry the fragment (Anthropic picks up system-role messages from here).
    first_msg = captured["messages"][0]
    assert first_msg.role == "system"
    assert "Quick action data: rfi_aging" in first_msg.content

    # Handler saw the injected ActionContext.
    assert handler.called_with is not None
    assert handler.called_with.user_account_id == user.id


@pytest.mark.asyncio
async def test_chat_service_does_not_append_when_no_slug():
    captured: dict = {}

    def fake_stream(model_request):
        captured["system_prompt"] = model_request.system_prompt
        captured["messages"] = list(model_request.messages)

        async def gen():
            yield "ok"

        return gen()

    model_client = MagicMock()
    model_client.model_key = "test-mock"
    model_client.stream_completion = fake_stream

    chat_repo = _make_chat_repo()

    dispatcher = ActionDispatcher(handlers=[_CaptureHandler()])
    pool = _FakePool(conn=MagicMock())

    followup = MagicMock()
    followup.suggest = MagicMock(return_value=[])

    svc = ChatService(
        chat_repo=chat_repo,
        model_client=model_client,
        followup_generator=followup,
        pool=pool,
        action_dispatcher=dispatcher,
    )

    user = _make_user()
    request = AssistantChatRequest(
        message="hi",
        active_action_slug=None,
        params={},
        conversation_id=None,
        project_id=None,
        mode="chat",
    )
    context = _make_context()

    async for _ in svc.stream_chat(request=request, user=user, context=context):
        pass

    assert captured["system_prompt"] == "base system prompt"
    assert "Quick action data" not in captured["system_prompt"]
    first_msg = captured["messages"][0]
    assert first_msg.role == "system"
    assert first_msg.content == "base system prompt"


def _make_request_user_ctx(slug: str | None = None):
    """Shared boilerplate for building (request, user, context) triples."""
    user = _make_user()
    request = AssistantChatRequest(
        message="Show me RFI aging",
        active_action_slug=slug,
        params={},
        conversation_id=None,
        project_id=None,
        mode="chat",
    )
    ctx = _make_context()
    return request, user, ctx


@pytest.mark.asyncio
async def test_chat_service_degrades_gracefully_when_pool_acquire_fails():
    """If acquire() on the pool raises, the chat should still complete
    with the base system prompt — no user-visible failure."""
    captured: dict = {}

    def fake_stream(model_request):
        captured["system_prompt"] = model_request.system_prompt

        async def gen():
            yield "ok"

        return gen()

    model_client = MagicMock()
    model_client.model_key = "test-mock"
    model_client.stream_completion = fake_stream

    chat_repo = _make_chat_repo()

    dispatcher = ActionDispatcher(handlers=[_CaptureHandler()])

    class _BrokenPool:
        def acquire(self):
            raise RuntimeError("pool exhausted")

    followup = MagicMock()
    followup.suggest = MagicMock(return_value=[])

    svc = ChatService(
        chat_repo=chat_repo,
        model_client=model_client,
        followup_generator=followup,
        pool=_BrokenPool(),
        action_dispatcher=dispatcher,
    )

    request, user, ctx = _make_request_user_ctx(slug="rfi_aging")

    async for _ in svc.stream_chat(request=request, user=user, context=ctx):
        pass

    # Base prompt preserved; no fragment appended; no exception raised.
    assert captured["system_prompt"] == "base system prompt"
    assert "Quick action data" not in captured["system_prompt"]

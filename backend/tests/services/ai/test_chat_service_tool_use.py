"""Phase 6 Task 12 — chat_service intercepts LLM tool_use blocks.

When the model emits a ``tool_use`` event via ``stream_events``,
chat_service must:

1. Pass the registry's tool schemas on the outgoing ModelRequest so the
   model knows what's callable.
2. Buffer and forward text deltas as ``message.delta`` SSE frames.
3. Route every ``tool_use`` through ``ActionQueueService.enqueue``.
4. Emit ``action_auto_committed`` / ``action_proposed`` / ``action_failed``
   SSE frames based on the returned ``DispatchResult.status``.

All four behaviors are exercised here with a hermetic mock model that
replays a canned tool_use plus a text delta, and a fake queue service
that records its call args.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantUser,
    PageContext,
)
from app.services.ai.action_queue_service import DispatchResult
from app.services.ai.chat_service import ChatService
from app.services.ai.context_builder import AssistantContext
from app.services.ai.followups import FollowupSuggestion


# ── fakes ─────────────────────────────────────────────────────────────────

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


class _FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _FakeQueueSvc:
    """Records enqueue calls; returns a caller-configured DispatchResult."""

    def __init__(self, result: DispatchResult):
        self.enqueue_calls: list[dict] = []
        self._result = result

    async def enqueue(self, **kwargs):
        self.enqueue_calls.append(kwargs)
        return self._result


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


def _make_model_with_events(events: list[dict]):
    """Build a model_client double that yields canned events from
    ``stream_events`` and captures the ModelRequest it received.
    """
    captured: dict = {}

    def stream_events(request):
        captured["request"] = request

        async def gen():
            for ev in events:
                yield ev

        return gen()

    def stream_completion(request):
        # Fallback path — not used when list_tool_schemas is set, but
        # implemented so getattr(model, 'stream_completion') is safe.
        captured.setdefault("request", request)

        async def gen():
            for ev in events:
                if ev.get("type") == "text":
                    yield ev.get("delta", "")

        return gen()

    model = MagicMock()
    model.model_key = "test-mock"
    model.stream_events = stream_events
    model.stream_completion = stream_completion
    return model, captured


def _drain_sse(frames: list[str]) -> list[dict]:
    out: list[dict] = []
    for frame in frames:
        frame = frame.strip()
        if not frame.startswith("data:"):
            continue
        out.append(json.loads(frame[5:].strip()))
    return out


def _build_service(*, model, queue_svc, tool_schemas=None, pool=None):
    session = _FakeSession()

    def factory():
        return queue_svc, session

    chat_repo = _make_chat_repo()
    followup = MagicMock()
    followup.suggest = MagicMock(return_value=[FollowupSuggestion(label="ok")])

    svc = ChatService(
        chat_repo=chat_repo,
        model_client=model,
        followup_generator=followup,
        pool=pool or _FakePool(conn=MagicMock()),
        action_queue_service_factory=factory,
        list_tool_schemas=lambda: tool_schemas if tool_schemas is not None else [],
    )
    return svc, session, chat_repo


def _basic_request() -> AssistantChatRequest:
    return AssistantChatRequest(
        message="please create a task",
        active_action_slug=None,
        params={},
        conversation_id=None,
        project_id=None,
        mode="chat",
    )


# ── tests ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_use_auto_committed_emits_action_auto_committed_frame():
    tool_call_id = "toolu_abc123"
    action_id = uuid4()
    task_id = str(uuid4())

    events = [
        {"type": "text", "delta": "Creating the task now."},
        {
            "type": "tool_use",
            "id": tool_call_id,
            "name": "create_task",
            "input": {"title": "fix the thing", "project_id": str(uuid4())},
        },
    ]
    model, captured = _make_model_with_events(events)

    queue_svc = _FakeQueueSvc(
        DispatchResult(
            action_id=action_id,
            status="auto_committed",
            requires_approval=False,
            blast_radius={"audience": "internal", "scope_size": 1},
            result_payload={"task_id": task_id, "ok": True},
        )
    )

    tool_schemas = [{"name": "create_task", "description": "x", "input_schema": {}}]
    svc, session, _repo = _build_service(
        model=model, queue_svc=queue_svc, tool_schemas=tool_schemas,
    )

    user = _make_user()
    frames: list[str] = []
    async for frame in svc.stream_chat(
        request=_basic_request(), user=user, context=_make_context()
    ):
        frames.append(frame)
    events_out = _drain_sse(frames)

    # 1) Model was handed the tool schemas
    assert "request" in captured, "stream_events was not called"
    assert captured["request"].tools == tool_schemas

    # 2) Queue service was called exactly once with the right slug/args
    assert len(queue_svc.enqueue_calls) == 1
    call = queue_svc.enqueue_calls[0]
    assert call["tool_slug"] == "create_task"
    assert call["tool_args"]["title"] == "fix the thing"
    assert call["user_account_id"] == user.id
    assert call["requested_by_user_id"] == user.id

    # 3) SSE vocabulary includes message.delta AND action_auto_committed
    types = [e["type"] for e in events_out]
    assert "message.delta" in types
    assert "action_auto_committed" in types

    ac = next(e for e in events_out if e["type"] == "action_auto_committed")
    assert ac["action_id"] == str(action_id)
    assert ac["tool_slug"] == "create_task"
    assert ac["result"] == {"task_id": task_id, "ok": True}

    # 4) Session was closed after the tool_use dispatch
    assert session.closed is True


@pytest.mark.asyncio
async def test_tool_use_pending_approval_emits_action_proposed_frame():
    action_id = uuid4()
    events = [
        {
            "type": "tool_use",
            "id": "toolu_xyz",
            "name": "answer_rfi",
            "input": {"rfi_id": str(uuid4()), "response": "approved as submitted"},
        },
    ]
    model, _ = _make_model_with_events(events)

    queue_svc = _FakeQueueSvc(
        DispatchResult(
            action_id=action_id,
            status="pending_approval",
            requires_approval=True,
            blast_radius={"audience": "external", "scope_size": 1},
            reasons=["will notify someone outside Rex Construction"],
        )
    )

    svc, _session, _repo = _build_service(
        model=model, queue_svc=queue_svc,
        tool_schemas=[{"name": "answer_rfi", "description": "x", "input_schema": {}}],
    )

    frames: list[str] = []
    async for frame in svc.stream_chat(
        request=_basic_request(), user=_make_user(), context=_make_context()
    ):
        frames.append(frame)
    events_out = _drain_sse(frames)

    ap = next((e for e in events_out if e["type"] == "action_proposed"), None)
    assert ap is not None, f"missing action_proposed; got types={[e['type'] for e in events_out]}"
    assert ap["action_id"] == str(action_id)
    assert ap["tool_slug"] == "answer_rfi"
    assert ap["status"] == "pending_approval"
    assert ap["reasons"] == ["will notify someone outside Rex Construction"]
    assert ap["blast_radius"] == {"audience": "external", "scope_size": 1}

    # Verify tool_args is present and matches the input passed to enqueue
    assert "tool_args" in ap, f"action_proposed frame missing tool_args: {ap}"
    assert isinstance(ap["tool_args"], dict)
    assert ap["tool_args"] == {"rfi_id": events[0]["input"]["rfi_id"], "response": "approved as submitted"}


@pytest.mark.asyncio
async def test_tool_use_handler_failure_emits_action_failed_frame():
    action_id = uuid4()
    events = [
        {
            "type": "tool_use",
            "id": "toolu_fail",
            "name": "create_task",
            "input": {"title": "t"},
        },
    ]
    model, _ = _make_model_with_events(events)

    queue_svc = _FakeQueueSvc(
        DispatchResult(
            action_id=action_id,
            status="failed",
            requires_approval=False,
            blast_radius={"audience": "internal"},
            error_excerpt="ValueError: project_id required",
        )
    )

    svc, _session, _repo = _build_service(
        model=model, queue_svc=queue_svc,
        tool_schemas=[{"name": "create_task", "description": "x", "input_schema": {}}],
    )

    frames: list[str] = []
    async for frame in svc.stream_chat(
        request=_basic_request(), user=_make_user(), context=_make_context()
    ):
        frames.append(frame)
    events_out = _drain_sse(frames)

    fail = next((e for e in events_out if e["type"] == "action_failed"), None)
    assert fail is not None
    assert fail["action_id"] == str(action_id)
    assert fail["tool_slug"] == "create_task"
    assert "project_id required" in fail["error"]


@pytest.mark.asyncio
async def test_no_tool_use_events_does_not_call_queue_service():
    """Regression: a plain text-only model response must not enqueue
    anything. The tool_use interception branch only fires on tool_use
    events."""
    events = [
        {"type": "text", "delta": "just words, no tools"},
    ]
    model, _ = _make_model_with_events(events)

    queue_svc = _FakeQueueSvc(
        DispatchResult(
            action_id=uuid4(), status="auto_committed",
            requires_approval=False, blast_radius={},
        )
    )

    svc, _session, _repo = _build_service(
        model=model, queue_svc=queue_svc,
        tool_schemas=[{"name": "create_task", "description": "x", "input_schema": {}}],
    )

    frames: list[str] = []
    async for frame in svc.stream_chat(
        request=_basic_request(), user=_make_user(), context=_make_context()
    ):
        frames.append(frame)
    events_out = _drain_sse(frames)

    assert len(queue_svc.enqueue_calls) == 0
    types = [e["type"] for e in events_out]
    # SSE vocabulary intact: delta + followups + completed
    assert "message.delta" in types
    assert "followups.generated" in types
    assert "message.completed" in types
    # None of the new Phase 6 action frames
    assert not any(t.startswith("action_") for t in types)


@pytest.mark.asyncio
async def test_multiple_tool_use_events_fan_out_to_multiple_enqueues():
    """If the model emits two tool_use blocks in one turn, each one must
    produce its own enqueue + SSE frame."""
    events = [
        {"type": "text", "delta": "Batch incoming."},
        {
            "type": "tool_use", "id": "t1", "name": "create_task",
            "input": {"title": "a"},
        },
        {
            "type": "tool_use", "id": "t2", "name": "create_task",
            "input": {"title": "b"},
        },
    ]
    model, _ = _make_model_with_events(events)

    queue_svc = _FakeQueueSvc(
        DispatchResult(
            action_id=uuid4(), status="auto_committed",
            requires_approval=False, blast_radius={"audience": "internal"},
            result_payload={"ok": True},
        )
    )

    svc, _session, _repo = _build_service(
        model=model, queue_svc=queue_svc,
        tool_schemas=[{"name": "create_task", "description": "x", "input_schema": {}}],
    )

    frames: list[str] = []
    async for frame in svc.stream_chat(
        request=_basic_request(), user=_make_user(), context=_make_context()
    ):
        frames.append(frame)
    events_out = _drain_sse(frames)

    assert len(queue_svc.enqueue_calls) == 2
    assert queue_svc.enqueue_calls[0]["tool_args"] == {"title": "a"}
    assert queue_svc.enqueue_calls[1]["tool_args"] == {"title": "b"}

    ac = [e for e in events_out if e["type"] == "action_auto_committed"]
    assert len(ac) == 2

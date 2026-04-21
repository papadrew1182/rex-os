"""ActionQueueService — enqueue, commit, undo, discard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.ai.action_queue_service import (
    ActionQueueService,
    DispatchResult,
    UNDO_WINDOW_SECONDS,
)
from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import (
    ActionContext, ActionResult, ActionSpec,
)


def _spec(slug="test_tool", fires_external=False, will_approve=False,
          with_compensator=False):
    async def classify(args, ctx):
        return BlastRadius(
            audience='external' if will_approve else 'internal',
            fires_external_effect=fires_external,
            financial_dollar_amount=None,
            scope_size=1,
        )

    async def handler(ctx):
        return ActionResult(result_payload={"ok": True, "slug": slug})

    async def compensator(original_result, ctx):
        return ActionResult(result_payload={"reversed": True})

    return ActionSpec(
        slug=slug,
        tool_schema={
            "description": "test",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        classify=classify,
        handler=handler,
        fires_external_effect=fires_external,
        compensator=compensator if with_compensator else None,
    )


class _FakeRepo:
    def __init__(self):
        self.rows: dict = {}
        self.calls: list = []

    async def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        self.rows[kwargs["id"]] = {**kwargs, "created_at": datetime.now(timezone.utc)}

    async def get(self, action_id):
        return self.rows.get(action_id)

    async def update_status(self, *, action_id, status, **kwargs):
        self.calls.append(("update_status", {"id": action_id, "status": status, **kwargs}))
        if action_id in self.rows:
            self.rows[action_id]["status"] = status
            if kwargs.get("committed_at"):
                self.rows[action_id]["committed_at"] = datetime.now(timezone.utc)
            if kwargs.get("undone_at"):
                self.rows[action_id]["undone_at"] = datetime.now(timezone.utc)
            if kwargs.get("error_excerpt") is not None:
                self.rows[action_id]["error_excerpt"] = kwargs["error_excerpt"]
            if kwargs.get("result_payload") is not None:
                self.rows[action_id]["result_payload"] = kwargs["result_payload"]


class _FakeConn:
    pass


def _ctx_builder():
    return lambda user_id: ClassifyContext(conn=_FakeConn(), user_account_id=user_id)


def _make_service(spec):
    repo = _FakeRepo()
    svc = ActionQueueService(
        repo=repo,
        get_tool_by_slug=lambda slug: spec if slug == spec.slug else None,
        build_classify_ctx=_ctx_builder(),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )
    return svc, repo


@pytest.mark.asyncio
async def test_enqueue_auto_commits_when_no_approval_needed():
    svc, repo = _make_service(_spec(slug="test_tool"))
    user_id = uuid4()
    result = await svc.enqueue(
        conn=_FakeConn(),
        user_account_id=user_id,
        requested_by_user_id=user_id,
        conversation_id=None,
        message_id=None,
        tool_slug="test_tool",
        tool_args={"foo": "bar"},
    )
    assert isinstance(result, DispatchResult)
    assert result.status == "auto_committed"
    assert result.requires_approval is False
    assert result.result_payload == {"ok": True, "slug": "test_tool"}


@pytest.mark.asyncio
async def test_enqueue_queues_for_approval_when_required():
    svc, repo = _make_service(_spec(slug="danger_tool", will_approve=True))
    user_id = uuid4()
    result = await svc.enqueue(
        conn=_FakeConn(),
        user_account_id=user_id,
        requested_by_user_id=user_id,
        conversation_id=None,
        message_id=None,
        tool_slug="danger_tool",
        tool_args={},
    )
    assert result.status == "pending_approval"
    assert result.requires_approval is True
    assert result.result_payload is None


@pytest.mark.asyncio
async def test_commit_approved_action_runs_handler():
    svc, repo = _make_service(_spec(slug="approval_tool", will_approve=True))
    user_id = uuid4()
    enq = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="approval_tool", tool_args={},
    )
    commit = await svc.commit(
        conn=_FakeConn(), action_id=enq.action_id,
    )
    assert commit.status == "committed"
    assert commit.result_payload == {"ok": True, "slug": "approval_tool"}


@pytest.mark.asyncio
async def test_discard_marks_dismissed_without_running_handler():
    svc, repo = _make_service(_spec(slug="x", will_approve=True))
    user_id = uuid4()
    enq = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="x", tool_args={},
    )
    result = await svc.discard(action_id=enq.action_id)
    assert result.status == "dismissed"


@pytest.mark.asyncio
async def test_handler_failure_marks_failed_with_error_excerpt():
    async def raising_handler(ctx):
        raise RuntimeError("simulated failure")

    spec = _spec(slug="flaky")
    spec.handler = raising_handler
    svc, repo = _make_service(spec)
    user_id = uuid4()
    result = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="flaky", tool_args={},
    )
    assert result.status == "failed"
    assert result.error_excerpt is not None
    assert "simulated failure" in result.error_excerpt


@pytest.mark.asyncio
async def test_undo_marks_undone_within_window():
    svc, repo = _make_service(_spec(slug="undoable", with_compensator=True))
    user_id = uuid4()
    enq = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="undoable", tool_args={},
    )
    # It's auto_committed now — immediately undo
    undo = await svc.undo(conn=_FakeConn(), action_id=enq.action_id)
    assert undo.status == "undone"


@pytest.mark.asyncio
async def test_undo_rejects_outside_window():
    svc, repo = _make_service(_spec(slug="undoable", with_compensator=True))
    user_id = uuid4()
    enq = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="undoable", tool_args={},
    )
    # Manually age the committed_at past the window
    repo.rows[enq.action_id]["committed_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=UNDO_WINDOW_SECONDS + 5)
    )
    undo = await svc.undo(conn=_FakeConn(), action_id=enq.action_id)
    assert undo.status == "auto_committed"  # unchanged — outside window
    assert "undo window expired" in (undo.error_excerpt or "")

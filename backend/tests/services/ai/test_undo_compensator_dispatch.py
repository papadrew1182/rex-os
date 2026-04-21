"""ActionQueueService.undo() dispatches the tool's compensator as a new
correction row and flips the original to 'undone'."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.ai.action_queue_service import ActionQueueService, UNDO_WINDOW_SECONDS
from app.services.ai.actions.blast_radius import BlastRadius
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


def _mk_spec(slug, compensator):
    async def _classify(a, c):
        return BlastRadius('internal', False, None, 1)
    async def _handler(c):
        return ActionResult(result_payload={})
    return ActionSpec(
        slug=slug, tool_schema={}, classify=_classify, handler=_handler,
        compensator=compensator,
    )


@pytest.mark.asyncio
async def test_undo_with_compensator_inserts_correction_row_and_flips_original():
    original_id = uuid4()
    user_id = uuid4()
    seen_args = {}

    async def _comp(original_result, ctx):
        seen_args["original_result"] = original_result
        return ActionResult(result_payload={"reversed": True})

    repo = MagicMock()
    repo.get = AsyncMock(return_value={
        "id": original_id, "status": "auto_committed",
        "committed_at": datetime.now(timezone.utc),
        "requires_approval": False,
        "blast_radius": {"audience": "internal"},
        "tool_slug": "create_task",
        "user_account_id": user_id,
        "conversation_id": None, "message_id": None,
        "result_payload": {"task_id": "abc"},
    })
    repo.insert = AsyncMock(return_value=None)
    repo.update_status = AsyncMock(return_value=None)

    spec = _mk_spec("create_task", _comp)
    svc = ActionQueueService(
        repo=repo,
        get_tool_by_slug=lambda s: spec,
        build_classify_ctx=lambda u: MagicMock(user_account_id=u),
        build_action_ctx=lambda conn, u, args, aid:
            ActionContext(conn=conn, user_account_id=u, args=args, action_id=aid),
    )

    result = await svc.undo(conn=MagicMock(), action_id=original_id)

    assert seen_args["original_result"] == {"task_id": "abc"}
    repo.insert.assert_awaited_once()
    insert_kwargs = repo.insert.await_args.kwargs
    assert insert_kwargs["tool_slug"] == "create_task__undo"
    assert insert_kwargs["correction_of_id"] == original_id
    assert insert_kwargs["committed_at_now"] is True
    statuses = [c.kwargs.get("status") for c in repo.update_status.await_args_list]
    assert "committed" in statuses
    assert "undone" in statuses
    assert result.status == "undone"


@pytest.mark.asyncio
async def test_undo_without_compensator_returns_failure():
    original_id = uuid4()
    repo = MagicMock()
    repo.get = AsyncMock(return_value={
        "id": original_id, "status": "auto_committed",
        "committed_at": datetime.now(timezone.utc),
        "requires_approval": False, "blast_radius": {},
        "tool_slug": "answer_rfi",
        "user_account_id": uuid4(),
        "conversation_id": None, "message_id": None,
        "result_payload": {},
    })
    spec = _mk_spec("answer_rfi", None)
    svc = ActionQueueService(
        repo=repo, get_tool_by_slug=lambda s: spec,
        build_classify_ctx=lambda u: MagicMock(),
        build_action_ctx=lambda *a, **k: MagicMock(),
    )
    result = await svc.undo(conn=MagicMock(), action_id=original_id)
    assert result.status != "undone"
    assert "not undoable" in (result.error_excerpt or "").lower()


@pytest.mark.asyncio
async def test_undo_outside_window_returns_failure():
    original_id = uuid4()
    long_ago = datetime.now(timezone.utc) - timedelta(seconds=UNDO_WINDOW_SECONDS + 10)
    repo = MagicMock()
    repo.get = AsyncMock(return_value={
        "id": original_id, "status": "auto_committed",
        "committed_at": long_ago,
        "requires_approval": False, "blast_radius": {},
        "tool_slug": "create_task",
        "user_account_id": uuid4(),
        "conversation_id": None, "message_id": None,
        "result_payload": {},
    })
    async def _comp(orig, ctx):
        return ActionResult(result_payload={})
    spec = _mk_spec("create_task", _comp)
    svc = ActionQueueService(
        repo=repo, get_tool_by_slug=lambda s: spec,
        build_classify_ctx=lambda u: MagicMock(),
        build_action_ctx=lambda *a, **k: MagicMock(),
    )
    result = await svc.undo(conn=MagicMock(), action_id=original_id)
    assert "expired" in (result.error_excerpt or "").lower()


@pytest.mark.asyncio
async def test_undo_compensator_failure_marks_correction_failed_keeps_original():
    original_id = uuid4()
    repo = MagicMock()
    repo.get = AsyncMock(return_value={
        "id": original_id, "status": "auto_committed",
        "committed_at": datetime.now(timezone.utc),
        "requires_approval": False, "blast_radius": {},
        "tool_slug": "create_task",
        "user_account_id": uuid4(),
        "conversation_id": None, "message_id": None,
        "result_payload": {"task_id": "abc"},
    })
    repo.insert = AsyncMock(return_value=None)
    repo.update_status = AsyncMock(return_value=None)

    async def _comp(orig, ctx):
        raise RuntimeError("compensator blew up")

    spec = _mk_spec("create_task", _comp)
    svc = ActionQueueService(
        repo=repo, get_tool_by_slug=lambda s: spec,
        build_classify_ctx=lambda u: MagicMock(user_account_id=u),
        build_action_ctx=lambda conn, u, args, aid:
            ActionContext(conn=conn, user_account_id=u, args=args, action_id=aid),
    )
    result = await svc.undo(conn=MagicMock(), action_id=original_id)
    statuses = [c.kwargs.get("status") for c in repo.update_status.await_args_list]
    assert "failed" in statuses
    assert "undone" not in statuses
    assert result.status == "failed"
    assert "blew up" in (result.error_excerpt or "")

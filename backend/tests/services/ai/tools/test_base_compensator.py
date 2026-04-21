"""ActionSpec must accept an optional compensator; ActionContext must
expose original_result for compensators to read."""
from __future__ import annotations

from uuid import uuid4

from app.services.ai.actions.blast_radius import BlastRadius
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


async def _classify(args, ctx):
    return BlastRadius(
        audience='internal', fires_external_effect=False,
        financial_dollar_amount=None, scope_size=1,
    )


async def _handler(ctx):
    return ActionResult(result_payload={"ok": True})


async def _compensate(original_result, ctx):
    return ActionResult(result_payload={"reversed": True})


def test_actionspec_compensator_defaults_to_none():
    spec = ActionSpec(
        slug="test", tool_schema={}, classify=_classify, handler=_handler,
    )
    assert spec.compensator is None


def test_actionspec_accepts_compensator():
    spec = ActionSpec(
        slug="test", tool_schema={}, classify=_classify, handler=_handler,
        compensator=_compensate,
    )
    assert spec.compensator is _compensate


def test_actioncontext_original_result_defaults_to_none():
    ctx = ActionContext(
        conn=None, user_account_id=uuid4(), args={}, action_id=uuid4(),
    )
    assert ctx.original_result is None


def test_actioncontext_accepts_original_result():
    payload = {"task_id": "abc", "prior_status": "open"}
    ctx = ActionContext(
        conn=None, user_account_id=uuid4(), args={}, action_id=uuid4(),
        original_result=payload,
    )
    assert ctx.original_result == payload

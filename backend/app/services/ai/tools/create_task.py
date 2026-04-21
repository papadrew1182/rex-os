# backend/app/services/ai/tools/create_task.py
"""create_task — STUB. Real implementation lands in Task 6."""
from __future__ import annotations

from app.services.ai.tools.base import (
    ActionContext, ActionResult, ActionSpec,
)
from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext


async def _classify(args, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    raise NotImplementedError(
        f"create_task handler not yet implemented; see Phase 6 plan Task 6"
    )


SPEC = ActionSpec(
    slug="create_task",
    tool_schema={
        "description": "STUB",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
)


__all__ = ["SPEC"]

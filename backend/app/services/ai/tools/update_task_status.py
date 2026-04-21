# backend/app/services/ai/tools/update_task_status.py
"""update_task_status — updates rex.tasks.status. Auto-pass always."""
from __future__ import annotations

from uuid import UUID

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Update the status of a task. Single-row internal mutation. "
        "Always auto-approves."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "UUID of rex.tasks row."},
            "status": {
                "type": "string",
                "description": "New status (open|in_progress|blocked|complete|cancelled).",
            },
        },
        "required": ["task_id", "status"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    task_uuid = UUID(str(ctx.args["task_id"]))
    new_status = str(ctx.args["status"])
    row = await ctx.conn.fetchrow(
        "SELECT status FROM rex.tasks WHERE id = $1::uuid",
        task_uuid,
    )
    if row is None:
        raise ValueError(f"task {task_uuid} not found")
    prev = row["status"]
    await ctx.conn.execute(
        "UPDATE rex.tasks SET status = $1, updated_at = now() "
        "WHERE id = $2::uuid",
        new_status, task_uuid,
    )
    return ActionResult(result_payload={
        "task_id": str(task_uuid),
        "previous_status": prev,
        "new_status": new_status,
    })


SPEC = ActionSpec(
    slug="update_task_status",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
)

__all__ = ["SPEC"]

# backend/app/services/ai/tools/create_note.py
"""create_note — free-form note persisted to rex.notes.

Always auto-approves: a private/internal note has no external audience,
fires no external effect, has no financial weight, and touches a single
row. The classifier therefore returns the smallest possible BlastRadius.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Create a free-form note attached to a project or standalone. "
        "Always auto-approves. Use for quick annotations, follow-up "
        "reminders, or when the user says 'note that X'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Note body (markdown OK)."},
            "project_id": {
                "type": "string",
                "description": "UUID of rex.projects. Optional.",
            },
        },
        "required": ["content"],
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
    note_id = uuid4()
    project = ctx.args.get("project_id")
    await ctx.conn.execute(
        """
        INSERT INTO rex.notes (id, project_id, user_account_id, content, created_at, updated_at)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, now(), now())
        """,
        note_id,
        UUID(str(project)) if project else None,
        ctx.user_account_id,
        ctx.args["content"],
    )
    return ActionResult(result_payload={
        "note_id": str(note_id),
        "content": ctx.args["content"],
        "project_id": str(project) if project else None,
    })


async def _compensator(original_result: dict, ctx: ActionContext) -> ActionResult:
    note_id = UUID(str(original_result["note_id"]))
    await ctx.conn.execute(
        "DELETE FROM rex.notes WHERE id = $1::uuid", note_id,
    )
    return ActionResult(result_payload={
        "compensated": "create_note",
        "note_id": str(note_id),
    })


SPEC = ActionSpec(
    slug="create_note",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
    compensator=_compensator,
)

__all__ = ["SPEC"]

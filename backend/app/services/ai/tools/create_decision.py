# backend/app/services/ai/tools/create_decision.py
"""create_decision — INSERT rex.pending_decisions. Auto-pass internal.
60s undo via compensator (DELETE by id).

`raised_by` is auto-populated from ctx.user_account_id by looking up
rex.user_accounts.person_id. If the user has no linked person record
(shouldn't happen in practice), raised_by is left NULL."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


PRIORITIES = ['low', 'medium', 'high', 'critical']


TOOL_SCHEMA = {
    "description": (
        "Flag an open question that needs to be decided on a project. "
        "Internal auto-pass with 60s undo. Creates a rex.pending_decisions "
        "row; does not record a decision already made."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "title": {"type": "string", "description": "The question, as a headline."},
            "description": {"type": "string"},
            "priority": {"type": "string", "enum": PRIORITIES},
            "blocks_description": {"type": "string", "description": "Optional: what downstream work is blocked."},
            "due_date": {"type": "string", "description": "ISO date (optional)."},
            "decision_maker_id": {"type": "string", "description": "UUID of rex.people (optional)."},
        },
        "required": ["project_id", "title"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


def _parse_date(v):
    if v is None:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


async def _handler(ctx: ActionContext) -> ActionResult:
    args = ctx.args
    decision_id = uuid4()
    project_id = UUID(str(args["project_id"]))
    raised_by = await ctx.conn.fetchval(
        "SELECT person_id FROM rex.user_accounts WHERE id = $1::uuid",
        ctx.user_account_id,
    )
    decision_maker = args.get("decision_maker_id")
    await ctx.conn.execute(
        """
        INSERT INTO rex.pending_decisions (
            id, project_id, title, description,
            priority, status, blocks_description, due_date,
            decision_maker_id, raised_by, raised_at,
            created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3, $4,
            $5, 'open', $6, $7::date,
            $8::uuid, $9::uuid, now(),
            now(), now()
        )
        """,
        decision_id, project_id,
        str(args["title"]), args.get("description"),
        str(args.get("priority") or "medium"),
        args.get("blocks_description"),
        _parse_date(args.get("due_date")),
        UUID(str(decision_maker)) if decision_maker else None,
        raised_by,
    )
    return ActionResult(result_payload={
        "decision_id": str(decision_id),
        "title": str(args["title"]),
        "project_id": str(project_id),
        "priority": str(args.get("priority") or "medium"),
    })


async def _compensator(original_result: dict, ctx: ActionContext) -> ActionResult:
    decision_id = UUID(str(original_result["decision_id"]))
    await ctx.conn.execute(
        "DELETE FROM rex.pending_decisions WHERE id = $1::uuid", decision_id,
    )
    return ActionResult(result_payload={
        "compensated": "create_decision",
        "decision_id": str(decision_id),
    })


SPEC = ActionSpec(
    slug="create_decision",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
    compensator=_compensator,
)

__all__ = ["SPEC"]

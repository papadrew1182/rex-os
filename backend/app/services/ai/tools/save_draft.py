# backend/app/services/ai/tools/save_draft.py
"""save_draft — INSERT rex.correspondence as a draft email. Auto-pass
always (no external audience until status transitions to 'sent')."""
from __future__ import annotations

from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Save a draft email for later review or sending. Inserts a row "
        "in rex.correspondence with type='email' and status='draft'. "
        "No external effect; the email is NOT sent. Always auto-approves."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "UUID of rex.projects row."},
            "subject": {"type": "string", "description": "Email subject line."},
            "body": {"type": "string", "description": "Email body (plain text or markdown)."},
            "to_person_id": {"type": "string", "description": "UUID of rex.people recipient. Optional."},
            "from_person_id": {"type": "string", "description": "UUID of rex.people sender. Optional."},
        },
        "required": ["project_id", "subject", "body"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal', fires_external_effect=False,
        financial_dollar_amount=None, scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    project_id = UUID(str(ctx.args["project_id"]))
    corr_id = uuid4()
    # Generate a unique correspondence_number per project. Use uuid suffix
    # to avoid concurrency issues with MAX+1 sequences.
    corr_number = f"DRAFT-{uuid4().hex[:8]}"
    to_pid = ctx.args.get("to_person_id")
    from_pid = ctx.args.get("from_person_id")
    await ctx.conn.execute(
        """
        INSERT INTO rex.correspondence (
            id, project_id, correspondence_number, subject,
            correspondence_type, status, body, from_person_id, to_person_id,
            created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3, $4, 'email', 'draft', $5,
            $6::uuid, $7::uuid, now(), now()
        )
        """,
        corr_id, project_id, corr_number, ctx.args["subject"],
        ctx.args["body"],
        UUID(str(from_pid)) if from_pid else None,
        UUID(str(to_pid)) if to_pid else None,
    )
    return ActionResult(result_payload={
        "correspondence_id": str(corr_id),
        "correspondence_number": corr_number,
        "project_id": str(project_id),
        "subject": ctx.args["subject"],
    })


async def _compensator(original_result: dict, ctx: ActionContext) -> ActionResult:
    corr_id = UUID(str(original_result["correspondence_id"]))
    await ctx.conn.execute(
        "DELETE FROM rex.correspondence WHERE id = $1::uuid", corr_id,
    )
    return ActionResult(result_payload={
        "compensated": "save_draft",
        "correspondence_id": str(corr_id),
    })


SPEC = ActionSpec(
    slug="save_draft",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
    compensator=_compensator,
)

__all__ = ["SPEC"]

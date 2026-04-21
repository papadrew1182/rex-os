# backend/app/services/ai/tools/save_meeting_packet.py
"""save_meeting_packet — UPDATE rex.meetings.packet_url. Auto-pass always.
Compensator restores the prior packet_url captured in result_payload."""
from __future__ import annotations

from uuid import UUID

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Attach or update the packet URL (meeting minutes PDF, agenda "
        "bundle, etc.) on an existing meeting. Single-row internal "
        "mutation. Always auto-approves."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "meeting_id": {"type": "string", "description": "UUID of rex.meetings row."},
            "packet_url": {"type": "string", "description": "URL of the packet document."},
        },
        "required": ["meeting_id", "packet_url"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal', fires_external_effect=False,
        financial_dollar_amount=None, scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    meeting_id = UUID(str(ctx.args["meeting_id"]))
    new_url = str(ctx.args["packet_url"])
    row = await ctx.conn.fetchrow(
        "SELECT packet_url FROM rex.meetings WHERE id = $1::uuid",
        meeting_id,
    )
    if row is None:
        raise ValueError(f"meeting {meeting_id} not found")
    prior = row["packet_url"]
    await ctx.conn.execute(
        "UPDATE rex.meetings SET packet_url = $1, updated_at = now() "
        "WHERE id = $2::uuid",
        new_url, meeting_id,
    )
    return ActionResult(result_payload={
        "meeting_id": str(meeting_id),
        "prior_packet_url": prior,
        "new_packet_url": new_url,
    })


async def _compensator(original_result: dict, ctx: ActionContext) -> ActionResult:
    meeting_id = UUID(str(original_result["meeting_id"]))
    prior = original_result.get("prior_packet_url")
    await ctx.conn.execute(
        "UPDATE rex.meetings SET packet_url = $1, updated_at = now() "
        "WHERE id = $2::uuid",
        prior, meeting_id,
    )
    return ActionResult(result_payload={
        "compensated": "save_meeting_packet",
        "meeting_id": str(meeting_id),
        "restored_packet_url": prior,
    })


SPEC = ActionSpec(
    slug="save_meeting_packet",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
    compensator=_compensator,
)

__all__ = ["SPEC"]

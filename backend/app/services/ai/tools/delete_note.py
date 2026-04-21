# backend/app/services/ai/tools/delete_note.py
"""delete_note — DELETE rex.notes after full-row snapshot.
Compensator re-INSERTs from the snapshot."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Delete a note by id. Single-row internal deletion. Always "
        "auto-approves. Full row snapshot is captured for the 60s undo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "note_id": {"type": "string", "description": "UUID of rex.notes row to delete."},
        },
        "required": ["note_id"],
    },
}


def _serialize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if v is None:
            out[k] = None
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, (int, bool, float)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal', fires_external_effect=False,
        financial_dollar_amount=None, scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    note_id = UUID(str(ctx.args["note_id"]))
    row = await ctx.conn.fetchrow(
        "SELECT * FROM rex.notes WHERE id = $1::uuid", note_id,
    )
    if row is None:
        raise ValueError(f"note {note_id} not found")
    snapshot = _serialize_row(dict(row))
    await ctx.conn.execute(
        "DELETE FROM rex.notes WHERE id = $1::uuid", note_id,
    )
    return ActionResult(result_payload={
        "note_id": str(note_id),
        "snapshot": snapshot,
    })


async def _compensator(original_result: dict, ctx: ActionContext) -> ActionResult:
    snap = original_result["snapshot"]
    await ctx.conn.execute(
        """
        INSERT INTO rex.notes (
            id, project_id, user_account_id, content, created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4, $5::text::timestamptz, now()
        )
        """,
        UUID(snap["id"]),
        UUID(snap["project_id"]) if snap.get("project_id") else None,
        UUID(snap["user_account_id"]),
        snap["content"],
        snap.get("created_at"),
    )
    return ActionResult(result_payload={
        "compensated": "delete_note",
        "note_id": snap["id"],
    })


SPEC = ActionSpec(
    slug="delete_note",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
    compensator=_compensator,
)

__all__ = ["SPEC"]

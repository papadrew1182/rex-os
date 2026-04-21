# backend/app/services/ai/tools/delete_task.py
"""delete_task — DELETE rex.tasks after full-row snapshot.
Compensator re-INSERTs from the snapshot."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Delete a task by id. Single-row internal deletion. Always "
        "auto-approves. Full row snapshot is captured for the 60s undo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "UUID of rex.tasks row to delete."},
        },
        "required": ["task_id"],
    },
}


def _serialize_row(row: dict) -> dict:
    """Convert asyncpg Record → JSON-serializable dict. datetimes and dates
    become ISO strings; UUIDs become str; primitives pass through."""
    out = {}
    for k, v in row.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (datetime, date)):
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
    task_id = UUID(str(ctx.args["task_id"]))
    row = await ctx.conn.fetchrow(
        "SELECT * FROM rex.tasks WHERE id = $1::uuid", task_id,
    )
    if row is None:
        raise ValueError(f"task {task_id} not found")
    snapshot = _serialize_row(dict(row))
    await ctx.conn.execute(
        "DELETE FROM rex.tasks WHERE id = $1::uuid", task_id,
    )
    return ActionResult(result_payload={
        "task_id": str(task_id),
        "snapshot": snapshot,
    })


async def _compensator(original_result: dict, ctx: ActionContext) -> ActionResult:
    snap = original_result["snapshot"]
    await ctx.conn.execute(
        """
        INSERT INTO rex.tasks (
            id, project_id, task_number, title, description, status,
            priority, category, assigned_to, assigned_company_id,
            due_date, completed_date, created_by, created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3::int, $4, $5, $6, $7, $8,
            $9::uuid, $10::uuid, $11::date, $12::date,
            $13::uuid, $14::text::timestamptz, now()
        )
        """,
        UUID(snap["id"]),
        UUID(snap["project_id"]),
        int(snap["task_number"]),
        snap["title"],
        snap.get("description"),
        snap["status"],
        snap["priority"],
        snap.get("category"),
        UUID(snap["assigned_to"]) if snap.get("assigned_to") else None,
        UUID(snap["assigned_company_id"]) if snap.get("assigned_company_id") else None,
        date.fromisoformat(snap["due_date"]) if snap.get("due_date") else None,
        date.fromisoformat(snap["completed_date"]) if snap.get("completed_date") else None,
        UUID(snap["created_by"]) if snap.get("created_by") else None,
        snap.get("created_at"),  # asyncpg accepts ISO string via ::timestamptz cast
    )
    return ActionResult(result_payload={
        "compensated": "delete_task",
        "task_id": snap["id"],
    })


SPEC = ActionSpec(
    slug="delete_task",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
    compensator=_compensator,
)

__all__ = ["SPEC"]

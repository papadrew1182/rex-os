# backend/app/services/ai/tools/create_task.py
"""create_task — creates a task in rex.tasks. Auto-pass when assignee
is internal or self; approval required when assignee is external."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import (
    BlastRadius, ClassifyContext,
)
from app.services.ai.tools.base import (
    ActionContext, ActionResult, ActionSpec,
)


TOOL_SCHEMA = {
    "description": (
        "Create a new internal task assigned to a person. Returns the "
        "task_id. Use this when the user asks to track work, make a "
        "checklist item, or assign a follow-up."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short (1-sentence) description of the task.",
            },
            "description": {
                "type": "string",
                "description": "Optional longer description. Markdown OK.",
            },
            "assignee_person_id": {
                "type": "string",
                "description": "UUID of rex.people row to assign to. Optional — defaults to requester (self).",
            },
            "project_id": {
                "type": "string",
                "description": "UUID of rex.projects row. Required by schema; caller should resolve project context.",
            },
            "due_date": {
                "type": "string",
                "description": "ISO date (YYYY-MM-DD). Optional; defaults to 7 days out.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Defaults to medium.",
            },
        },
        "required": ["title"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    """Internal when assignee is internal person OR self. External otherwise."""
    assignee_raw = args.get("assignee_person_id")
    if assignee_raw is None:
        return BlastRadius(
            audience='internal',
            fires_external_effect=False,
            financial_dollar_amount=None,
            scope_size=1,
        )
    try:
        assignee_id = UUID(str(assignee_raw))
    except ValueError:
        return BlastRadius(
            audience='external',
            fires_external_effect=False,
            financial_dollar_amount=None,
            scope_size=1,
        )
    is_internal = await ctx.is_internal_person(assignee_id)
    return BlastRadius(
        audience='internal' if is_internal else 'external',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    args = ctx.args
    task_id = uuid4()
    assignee = args.get("assignee_person_id")
    project = args.get("project_id")
    priority = args.get("priority") or "medium"
    due_raw = args.get("due_date")
    if due_raw is None:
        due = date.today() + timedelta(days=7)
    elif isinstance(due_raw, date):
        due = due_raw
    else:
        due = date.fromisoformat(str(due_raw))

    if project is None:
        raise ValueError("create_task requires project_id (rex.tasks.project_id is NOT NULL)")

    project_uuid = UUID(str(project))

    # Compute next task_number per project.
    next_num = await ctx.conn.fetchval(
        "SELECT COALESCE(MAX(task_number), 0) + 1 FROM rex.tasks "
        "WHERE project_id = $1::uuid",
        project_uuid,
    )

    await ctx.conn.execute(
        """
        INSERT INTO rex.tasks
            (id, project_id, task_number, title, description, status,
             priority, assigned_to, due_date, created_at, updated_at)
        VALUES (
            $1::uuid,
            $2::uuid,
            $3::int,
            $4, $5, 'open',
            $6,
            $7::uuid,
            $8::date,
            now(), now()
        )
        """,
        task_id,
        project_uuid,
        int(next_num),
        args["title"],
        args.get("description"),
        priority,
        UUID(str(assignee)) if assignee else None,
        due,
    )
    return ActionResult(result_payload={
        "task_id": str(task_id),
        "task_number": int(next_num),
        "title": args["title"],
        "project_id": str(project_uuid),
        "assignee_person_id": str(assignee) if assignee else None,
    })


SPEC = ActionSpec(
    slug="create_task",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
)

__all__ = ["SPEC"]

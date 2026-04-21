# backend/app/services/ai/tools/create_alert.py
"""create_alert — INSERT rex.notifications. Auto-pass always."""
from __future__ import annotations

from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


DOMAINS = ['foundation', 'schedule', 'field_ops', 'financials',
           'document_management', 'closeout', 'system']
SEVERITIES = ['info', 'warning', 'critical', 'success']


TOOL_SCHEMA = {
    "description": (
        "Create an alert / in-app notification for a user. Inserts a "
        "row in rex.notifications. Always auto-approves (internal only)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "user_account_id": {"type": "string", "description": "UUID of the recipient rex.user_accounts row."},
            "domain": {"type": "string", "enum": DOMAINS, "description": "Which product domain the alert belongs to."},
            "notification_type": {"type": "string", "description": "Free-text type slug (e.g. 'rfi_overdue', 'schedule_drift')."},
            "severity": {"type": "string", "enum": SEVERITIES, "description": "Defaults to 'info'."},
            "title": {"type": "string", "description": "Alert headline."},
            "body": {"type": "string", "description": "Optional longer body."},
            "project_id": {"type": "string", "description": "UUID of rex.projects row. Optional."},
        },
        "required": ["user_account_id", "domain", "notification_type", "title"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal', fires_external_effect=False,
        financial_dollar_amount=None, scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    notif_id = uuid4()
    args = ctx.args
    project_id = args.get("project_id")
    await ctx.conn.execute(
        """
        INSERT INTO rex.notifications (
            id, user_account_id, project_id, domain, notification_type,
            severity, title, body, created_at, metadata
        ) VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, now(),
            '{}'::jsonb
        )
        """,
        notif_id,
        UUID(str(args["user_account_id"])),
        UUID(str(project_id)) if project_id else None,
        str(args["domain"]),
        str(args["notification_type"]),
        str(args.get("severity") or "info"),
        str(args["title"]),
        args.get("body"),
    )
    return ActionResult(result_payload={
        "notification_id": str(notif_id),
        "user_account_id": str(args["user_account_id"]),
        "title": str(args["title"]),
    })


async def _compensator(original_result: dict, ctx: ActionContext) -> ActionResult:
    notif_id = UUID(str(original_result["notification_id"]))
    await ctx.conn.execute(
        "DELETE FROM rex.notifications WHERE id = $1::uuid", notif_id,
    )
    return ActionResult(result_payload={
        "compensated": "create_alert",
        "notification_id": str(notif_id),
    })


SPEC = ActionSpec(
    slug="create_alert",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
    compensator=_compensator,
)

__all__ = ["SPEC"]

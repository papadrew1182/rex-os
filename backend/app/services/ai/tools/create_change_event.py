# backend/app/services/ai/tools/create_change_event.py
"""create_change_event — INSERT rex.change_events. Approval-required
financial instrument (fires_external_effect=True always forces approval).
No compensator — reversing a committed change event is a Phase 6c
'Send correction' action, not a 60s undo."""
from __future__ import annotations

from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


CHANGE_REASONS = ['owner_change', 'design_change', 'unforeseen', 'allowance', 'contingency']
EVENT_TYPES = ['tbd', 'allowance', 'contingency', 'owner_change', 'transfer']
SCOPES = ['in_scope', 'out_of_scope', 'tbd']


TOOL_SCHEMA = {
    "description": (
        "Open a new change event on a project. Financial instrument — "
        "always requires approval regardless of dollar amount."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "UUID of rex.projects."},
            "event_number": {"type": "string", "description": "CE number (text, unique per project)."},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "change_reason": {"type": "string", "enum": CHANGE_REASONS},
            "event_type": {"type": "string", "enum": EVENT_TYPES},
            "scope": {"type": "string", "enum": SCOPES},
            "estimated_amount": {"type": "number", "description": "USD. Defaults to 0."},
            "rfi_id": {"type": "string"},
            "prime_contract_id": {"type": "string"},
        },
        "required": ["project_id", "event_number", "title", "change_reason", "event_type"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    amount = args.get("estimated_amount")
    return BlastRadius(
        audience='internal',
        fires_external_effect=True,
        financial_dollar_amount=float(amount) if amount is not None else 0.0,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    args = ctx.args
    ce_id = uuid4()
    project_id = UUID(str(args["project_id"]))
    rfi_id = args.get("rfi_id")
    prime_contract_id = args.get("prime_contract_id")
    await ctx.conn.execute(
        """
        INSERT INTO rex.change_events (
            id, project_id, event_number, title, description,
            status, change_reason, event_type, scope, estimated_amount,
            rfi_id, prime_contract_id, created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3, $4, $5,
            'open', $6, $7, $8, $9::numeric,
            $10::uuid, $11::uuid, now(), now()
        )
        """,
        ce_id, project_id,
        str(args["event_number"]), str(args["title"]), args.get("description"),
        str(args["change_reason"]), str(args["event_type"]),
        str(args.get("scope") or "tbd"),
        float(args.get("estimated_amount") or 0),
        UUID(str(rfi_id)) if rfi_id else None,
        UUID(str(prime_contract_id)) if prime_contract_id else None,
    )
    return ActionResult(result_payload={
        "change_event_id": str(ce_id),
        "event_number": str(args["event_number"]),
        "title": str(args["title"]),
        "project_id": str(project_id),
    })


SPEC = ActionSpec(
    slug="create_change_event",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=True,
    compensator=None,
)

__all__ = ["SPEC"]

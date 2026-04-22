# backend/app/services/ai/tools/create_pco.py
"""create_pco — INSERT rex.potential_change_orders. Approval-required
financial instrument."""
from __future__ import annotations

from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Create a Potential Change Order under a change event and "
        "commitment. Financial instrument — always requires approval."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "change_event_id": {"type": "string", "description": "UUID of rex.change_events."},
            "commitment_id": {"type": "string", "description": "UUID of rex.commitments."},
            "pco_number": {"type": "string"},
            "title": {"type": "string"},
            "amount": {"type": "number"},
            "cost_code_id": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["change_event_id", "commitment_id", "pco_number", "title"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    amount = args.get("amount")
    return BlastRadius(
        audience='internal',
        fires_external_effect=True,
        financial_dollar_amount=float(amount) if amount is not None else 0.0,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    args = ctx.args
    pco_id = uuid4()
    cost_code_id = args.get("cost_code_id")
    await ctx.conn.execute(
        """
        INSERT INTO rex.potential_change_orders (
            id, change_event_id, commitment_id, pco_number, title,
            status, amount, cost_code_id, description, created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4, $5,
            'draft', $6::numeric, $7::uuid, $8, now(), now()
        )
        """,
        pco_id,
        UUID(str(args["change_event_id"])),
        UUID(str(args["commitment_id"])),
        str(args["pco_number"]), str(args["title"]),
        float(args.get("amount") or 0),
        UUID(str(cost_code_id)) if cost_code_id else None,
        args.get("description"),
    )
    return ActionResult(result_payload={
        "pco_id": str(pco_id),
        "pco_number": str(args["pco_number"]),
        "title": str(args["title"]),
    })


SPEC = ActionSpec(
    slug="create_pco",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=True,
    compensator=None,
)

__all__ = ["SPEC"]

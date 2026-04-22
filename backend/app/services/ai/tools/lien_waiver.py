# backend/app/services/ai/tools/lien_waiver.py
"""lien_waiver — INSERT rex.lien_waivers. Approval-required financial
instrument."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


WAIVER_TYPES = ['conditional_progress', 'unconditional_progress',
                'conditional_final', 'unconditional_final']


TOOL_SCHEMA = {
    "description": (
        "Record a lien waiver under a pay application. Financial "
        "instrument — always requires approval."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "payment_application_id": {"type": "string"},
            "vendor_id": {"type": "string"},
            "waiver_type": {"type": "string", "enum": WAIVER_TYPES},
            "through_date": {"type": "string", "description": "ISO date."},
            "amount": {"type": "number"},
            "notes": {"type": "string"},
        },
        "required": ["payment_application_id", "vendor_id", "waiver_type", "through_date"],
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


def _parse_date(v):
    if v is None:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


async def _handler(ctx: ActionContext) -> ActionResult:
    args = ctx.args
    lw_id = uuid4()
    await ctx.conn.execute(
        """
        INSERT INTO rex.lien_waivers (
            id, payment_application_id, vendor_id, waiver_type,
            status, amount, through_date, notes,
            created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4,
            'pending', $5::numeric, $6::date, $7,
            now(), now()
        )
        """,
        lw_id,
        UUID(str(args["payment_application_id"])),
        UUID(str(args["vendor_id"])),
        str(args["waiver_type"]),
        float(args.get("amount") or 0),
        _parse_date(args["through_date"]),
        args.get("notes"),
    )
    return ActionResult(result_payload={
        "lien_waiver_id": str(lw_id),
        "waiver_type": str(args["waiver_type"]),
        "amount": float(args.get("amount") or 0),
    })


SPEC = ActionSpec(
    slug="lien_waiver",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=True,
    compensator=None,
)

__all__ = ["SPEC"]

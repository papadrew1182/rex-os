# backend/app/services/ai/tools/pay_application.py
"""pay_application — INSERT rex.payment_applications. Approval-required
financial instrument."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Draft a pay application for a commitment in a given billing "
        "period. Financial instrument — always requires approval."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "commitment_id": {"type": "string"},
            "billing_period_id": {"type": "string"},
            "pay_app_number": {"type": "integer"},
            "period_start": {"type": "string", "description": "ISO date."},
            "period_end": {"type": "string", "description": "ISO date."},
            "this_period_amount": {"type": "number"},
            "total_completed": {"type": "number"},
            "retention_held": {"type": "number"},
            "retention_released": {"type": "number"},
            "net_payment_due": {"type": "number"},
        },
        "required": ["commitment_id", "billing_period_id", "pay_app_number", "period_start", "period_end"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    amount = args.get("this_period_amount")
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
    pa_id = uuid4()
    await ctx.conn.execute(
        """
        INSERT INTO rex.payment_applications (
            id, commitment_id, billing_period_id, pay_app_number,
            status, period_start, period_end,
            this_period_amount, total_completed, retention_held,
            retention_released, net_payment_due,
            created_at, updated_at
        ) VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4::int,
            'draft', $5::date, $6::date,
            $7::numeric, $8::numeric, $9::numeric,
            $10::numeric, $11::numeric,
            now(), now()
        )
        """,
        pa_id,
        UUID(str(args["commitment_id"])),
        UUID(str(args["billing_period_id"])),
        int(args["pay_app_number"]),
        _parse_date(args["period_start"]),
        _parse_date(args["period_end"]),
        float(args.get("this_period_amount") or 0),
        float(args.get("total_completed") or 0),
        float(args.get("retention_held") or 0),
        float(args.get("retention_released") or 0),
        float(args.get("net_payment_due") or 0),
    )
    return ActionResult(result_payload={
        "pay_application_id": str(pa_id),
        "pay_app_number": int(args["pay_app_number"]),
        "this_period_amount": float(args.get("this_period_amount") or 0),
    })


SPEC = ActionSpec(
    slug="pay_application",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=True,
    compensator=None,
)

__all__ = ["SPEC"]

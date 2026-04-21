# backend/app/services/ai/tools/answer_rfi.py
"""answer_rfi — approval-required tool. Fires Procore API call to close
the RFI officially, then updates rex.rfis to match.

Handler contract: call Procore FIRST. If it fails, rex.rfis stays
unchanged so we don't produce a spurious "answered" state. If Procore
succeeds but the rex.rfis UPDATE fails afterward, the Procore side is
now ahead of Rex OS — the next Procore webhook reconcile corrects it.
"""
from __future__ import annotations

from uuid import UUID

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec
from app.services.ai.tools.procore_api import ProcoreClient


TOOL_SCHEMA = {
    "description": (
        "Post an official answer to an RFI and close it in Procore. "
        "Requires approval (fires external effect). Handler updates "
        "rex.rfis AND calls Procore's API in-band."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "rfi_id": {"type": "string", "description": "UUID of rex.rfis row."},
            "answer_text": {"type": "string", "description": "The official answer text."},
        },
        "required": ["rfi_id", "answer_text"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',
        fires_external_effect=True,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    rfi_uuid = UUID(str(ctx.args["rfi_id"]))
    answer_text = str(ctx.args["answer_text"])

    row = await ctx.conn.fetchrow(
        "SELECT external_id FROM rex.connector_mappings "
        "WHERE rex_table = 'rex.rfis' AND rex_id = $1::uuid "
        "AND connector = 'procore' AND source_table = 'procore.rfis' "
        "LIMIT 1",
        rfi_uuid,
    )
    if row is None:
        raise ValueError(
            f"rex.rfis/{rfi_uuid} has no Procore source_link — cannot write back"
        )
    procore_id = int(row["external_id"])

    client = ProcoreClient.from_env()
    try:
        procore_response = await client.answer_rfi(
            rfi_procore_id=procore_id, answer_text=answer_text,
        )
    finally:
        await client.close()

    # Update rex.rfis to match — only if Procore accepted.
    # Schema: status CHECK allows 'answered'; answered_date is nullable date.
    await ctx.conn.execute(
        "UPDATE rex.rfis "
        "SET answer = $1, status = 'answered', "
        "    answered_date = CURRENT_DATE, updated_at = now() "
        "WHERE id = $2::uuid",
        answer_text, rfi_uuid,
    )

    return ActionResult(result_payload={
        "rfi_id": str(rfi_uuid),
        "procore_id": procore_id,
        "answer_text": answer_text,
        "procore_response": procore_response,
    })


SPEC = ActionSpec(
    slug="answer_rfi",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=True,
)

__all__ = ["SPEC"]

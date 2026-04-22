"""create_pco — INSERT rex.potential_change_orders. Approval-required
financial instrument; no compensator."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_pco import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_parent():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    ce_id = uuid4()
    commitment_id = uuid4()
    company_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    proj_number = f"PCO-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'PCO Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.companies (id, name, company_type) "
            "VALUES ($1::uuid, $2, 'subcontractor')",
            company_id, f"PCO Sub {uuid4().hex[:6]}",
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'PC', 'Seeder', $2, 'internal')",
            person_id, f"pco-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"pco-u-{user_id}@t.invalid",
        )
        await conn.execute(
            """
            INSERT INTO rex.commitments (id, project_id, vendor_id, commitment_number,
                                          title, contract_type, status, original_value)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'Test commitment',
                    'subcontract', 'executed', 100000)
            """,
            commitment_id, proj_id, company_id, f"CM-{uuid4().hex[:6]}",
        )
        await conn.execute(
            """
            INSERT INTO rex.change_events (id, project_id, event_number, title,
                                            change_reason, event_type, scope, estimated_amount, status)
            VALUES ($1::uuid, $2::uuid, 'CE-PCO-1', 'Parent CE',
                    'owner_change', 'owner_change', 'in_scope', 15000, 'open')
            """,
            ce_id, proj_id,
        )
        yield {
            "project_id": proj_id,
            "change_event_id": ce_id,
            "commitment_id": commitment_id,
            "user_id": user_id,
        }
    finally:
        await conn.execute("DELETE FROM rex.potential_change_orders WHERE change_event_id = $1::uuid", ce_id)
        await conn.execute("DELETE FROM rex.change_events WHERE id = $1::uuid", ce_id)
        await conn.execute("DELETE FROM rex.commitments WHERE id = $1::uuid", commitment_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.execute("DELETE FROM rex.companies WHERE id = $1::uuid", company_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_approval_required(seeded_parent):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_parent["user_id"])
        br = await SPEC.classify({
            "change_event_id": str(seeded_parent["change_event_id"]),
            "commitment_id": str(seeded_parent["commitment_id"]),
            "pco_number": "PCO-7",
            "title": "Added scope",
            "amount": 8000,
        }, ctx)
        assert br.requires_approval() is True
        assert br.financial_dollar_amount == 8000.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_pco(seeded_parent):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_parent["user_id"],
            args={
                "change_event_id": str(seeded_parent["change_event_id"]),
                "commitment_id": str(seeded_parent["commitment_id"]),
                "pco_number": "PCO-42",
                "title": "Add glulam beam",
                "amount": 18400,
                "description": "Per architect RFI-12.",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT pco_number, title, status, amount FROM rex.potential_change_orders "
            "WHERE id = $1::uuid",
            UUID(result.result_payload["pco_id"]),
        )
        assert row["pco_number"] == "PCO-42"
        assert row["title"] == "Add glulam beam"
        assert row["status"] == "draft"
        assert float(row["amount"]) == 18400.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_spec_has_no_compensator():
    assert SPEC.compensator is None

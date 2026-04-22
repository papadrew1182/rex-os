"""lien_waiver — INSERT rex.lien_waivers. Approval-required financial
instrument; no compensator."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.lien_waiver import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_chain():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    company_id = uuid4()
    commitment_id = uuid4()
    billing_period_id = uuid4()
    pay_app_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    proj_number = f"LW-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Lien Waiver Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.companies (id, name, company_type) "
            "VALUES ($1::uuid, $2, 'subcontractor')",
            company_id, f"LW Sub {uuid4().hex[:6]}",
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'LW', 'Seeder', $2, 'internal')",
            person_id, f"lw-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"lw-u-{user_id}@t.invalid",
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
        # rex.billing_periods uses start_date / end_date / due_date
        await conn.execute(
            """
            INSERT INTO rex.billing_periods (id, project_id, period_number,
                                              start_date, end_date, due_date, status)
            VALUES ($1::uuid, $2::uuid, 1, $3::date, $4::date, $5::date, 'open')
            """,
            billing_period_id, proj_id,
            date(2026, 4, 1), date(2026, 4, 30), date(2026, 5, 10),
        )
        # rex.payment_applications uses period_start / period_end
        await conn.execute(
            """
            INSERT INTO rex.payment_applications (
                id, commitment_id, billing_period_id, pay_app_number, status,
                period_start, period_end, this_period_amount, net_payment_due)
            VALUES ($1::uuid, $2::uuid, $3::uuid, 1, 'draft',
                    $4::date, $5::date, 45000, 40500)
            """,
            pay_app_id, commitment_id, billing_period_id,
            date(2026, 4, 1), date(2026, 4, 30),
        )
        yield {
            "payment_application_id": pay_app_id,
            "vendor_id": company_id,
            "user_id": user_id,
        }
    finally:
        await conn.execute("DELETE FROM rex.lien_waivers WHERE payment_application_id = $1::uuid", pay_app_id)
        await conn.execute("DELETE FROM rex.payment_applications WHERE id = $1::uuid", pay_app_id)
        await conn.execute("DELETE FROM rex.billing_periods WHERE id = $1::uuid", billing_period_id)
        await conn.execute("DELETE FROM rex.commitments WHERE id = $1::uuid", commitment_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.execute("DELETE FROM rex.companies WHERE id = $1::uuid", company_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_approval_required(seeded_chain):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_chain["user_id"])
        br = await SPEC.classify({
            "payment_application_id": str(seeded_chain["payment_application_id"]),
            "vendor_id": str(seeded_chain["vendor_id"]),
            "waiver_type": "conditional_progress",
            "through_date": "2026-04-30",
            "amount": 45000,
        }, ctx)
        assert br.requires_approval() is True
        assert br.financial_dollar_amount == 45000.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_lien_waiver(seeded_chain):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_chain["user_id"],
            args={
                "payment_application_id": str(seeded_chain["payment_application_id"]),
                "vendor_id": str(seeded_chain["vendor_id"]),
                "waiver_type": "conditional_progress",
                "through_date": "2026-04-30",
                "amount": 45000,
                "notes": "Received 4/28.",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT waiver_type, status, amount FROM rex.lien_waivers "
            "WHERE id = $1::uuid",
            UUID(result.result_payload["lien_waiver_id"]),
        )
        assert row["waiver_type"] == "conditional_progress"
        assert row["status"] == "pending"
        assert float(row["amount"]) == 45000.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_spec_has_no_compensator():
    assert SPEC.compensator is None

"""pay_application — INSERT rex.payment_applications. Approval-required
financial instrument; no compensator."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.pay_application import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_parent():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    company_id = uuid4()
    commitment_id = uuid4()
    billing_period_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    proj_number = f"PA-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Pay App Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.companies (id, name, company_type) "
            "VALUES ($1::uuid, $2, 'subcontractor')",
            company_id, f"PA Sub {uuid4().hex[:6]}",
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'PA', 'Seeder', $2, 'internal')",
            person_id, f"pa-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"pa-u-{user_id}@t.invalid",
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
            INSERT INTO rex.billing_periods (id, project_id, period_number,
                                              start_date, end_date, due_date, status)
            VALUES ($1::uuid, $2::uuid, 1, $3::date, $4::date, $5::date, 'open')
            """,
            billing_period_id, proj_id, date(2026, 4, 1), date(2026, 4, 30), date(2026, 5, 10),
        )
        yield {
            "commitment_id": commitment_id,
            "billing_period_id": billing_period_id,
            "user_id": user_id,
        }
    finally:
        await conn.execute("DELETE FROM rex.payment_applications WHERE commitment_id = $1::uuid", commitment_id)
        await conn.execute("DELETE FROM rex.billing_periods WHERE id = $1::uuid", billing_period_id)
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
            "commitment_id": str(seeded_parent["commitment_id"]),
            "billing_period_id": str(seeded_parent["billing_period_id"]),
            "pay_app_number": 4,
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "this_period_amount": 45000,
        }, ctx)
        assert br.requires_approval() is True
        assert br.financial_dollar_amount == 45000.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_pay_app(seeded_parent):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_parent["user_id"],
            args={
                "commitment_id": str(seeded_parent["commitment_id"]),
                "billing_period_id": str(seeded_parent["billing_period_id"]),
                "pay_app_number": 4,
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
                "this_period_amount": 45000,
                "total_completed": 45000,
                "retention_held": 4500,
                "retention_released": 0,
                "net_payment_due": 40500,
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT pay_app_number, status, this_period_amount, retention_held, net_payment_due "
            "FROM rex.payment_applications WHERE id = $1::uuid",
            UUID(result.result_payload["pay_application_id"]),
        )
        assert row["pay_app_number"] == 4
        assert row["status"] == "draft"
        assert float(row["this_period_amount"]) == 45000.0
        assert float(row["retention_held"]) == 4500.0
        assert float(row["net_payment_due"]) == 40500.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_spec_has_no_compensator():
    assert SPEC.compensator is None

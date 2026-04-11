"""Billing period and project billing summary tests."""

import uuid
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Bill-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _commitment(c: AsyncClient, project_id: str) -> str:
    r = await c.post("/api/commitments/", json={
        "project_id": project_id, "vendor_id": COMPANY_REX,
        "commitment_number": f"SC-{_uid()}", "title": f"Sub-{_uid()}",
        "contract_type": "subcontract",
    })
    return r.json()["id"]


async def _billing_period(c: AsyncClient, project_id: str, period: int) -> str:
    r = await c.post("/api/billing-periods/", json={
        "project_id": project_id, "period_number": period,
        "start_date": "2025-01-01", "end_date": "2025-01-31", "due_date": "2025-02-10",
    })
    return r.json()["id"]


async def _pay_app(c: AsyncClient, commitment_id: str, billing_period_id: str, **kw) -> dict:
    p = {
        "commitment_id": commitment_id, "billing_period_id": billing_period_id,
        "pay_app_number": int(_uid()[:4], 16),
        "period_start": "2025-01-01", "period_end": "2025-01-31",
        "this_period_amount": 10000,
    }
    p.update(kw)
    r = await c.post("/api/payment-applications/", json=p)
    assert r.status_code == 201
    return r.json()


# ── Billing period summary ──────────────────────────────────────────────────

async def test_billing_period_summary_with_pay_apps(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(client, pid)
    bp = await _billing_period(client, pid, int(_uid()[:4], 16))

    await _pay_app(client, cm, bp, this_period_amount=10000, status="approved")
    await _pay_app(client, cm, bp, this_period_amount=15000, status="paid")
    await _pay_app(client, cm, bp, this_period_amount=5000, status="draft")

    r = await client.get(f"/api/billing-periods/{bp}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_period_id"] == bp
    assert body["pay_app_count"] == 3
    assert body["total_this_period_amount"] == 30000
    assert body["total_approved_amount"] == 10000
    assert body["total_paid_amount"] == 15000
    assert body["counts_by_status"]["approved"] == 1
    assert body["counts_by_status"]["paid"] == 1
    assert body["counts_by_status"]["draft"] == 1


async def test_billing_period_summary_no_pay_apps(client: AsyncClient):
    pid = await _project(client)
    bp = await _billing_period(client, pid, int(_uid()[:4], 16))

    r = await client.get(f"/api/billing-periods/{bp}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["pay_app_count"] == 0
    assert body["total_this_period_amount"] == 0
    assert body["counts_by_status"] == {}


async def test_billing_period_summary_404(client: AsyncClient):
    r = await client.get(f"/api/billing-periods/{BOGUS_UUID}/summary")
    assert r.status_code == 404


# ── Project billing summary ─────────────────────────────────────────────────

async def test_project_billing_summary(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(client, pid)
    bp1 = await _billing_period(client, pid, int(_uid()[:4], 16))
    bp2 = await _billing_period(client, pid, int(_uid()[:4], 16))

    await _pay_app(client, cm, bp1, this_period_amount=10000, status="paid")
    await _pay_app(client, cm, bp2, this_period_amount=20000, status="approved")

    r = await client.get(f"/api/projects/{pid}/billing-periods/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_periods"] == 2
    assert body["grand_total_this_period"] == 30000
    assert body["grand_total_paid"] == 10000
    assert len(body["periods"]) == 2

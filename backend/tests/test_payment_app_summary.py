"""Payment application summary tests."""

import uuid
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"PayApp-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _commitment(c: AsyncClient, pid: str) -> dict:
    r = await c.post("/api/commitments/", json={
        "project_id": pid, "vendor_id": COMPANY_REX,
        "commitment_number": f"SC-{_uid()}", "title": f"Sub-{_uid()}",
        "contract_type": "subcontract",
    })
    return r.json()


async def _billing_period(c: AsyncClient, pid: str) -> dict:
    r = await c.post("/api/billing-periods/", json={
        "project_id": pid, "period_number": int(_uid()[:4], 16),
        "start_date": "2025-01-01", "end_date": "2025-01-31", "due_date": "2025-02-10",
    })
    return r.json()


async def _pay_app(c: AsyncClient, cm_id: str, bp_id: str) -> dict:
    r = await c.post("/api/payment-applications/", json={
        "commitment_id": cm_id, "billing_period_id": bp_id,
        "pay_app_number": int(_uid()[:4], 16),
        "period_start": "2025-01-01", "period_end": "2025-01-31",
        "this_period_amount": 12000, "retention_held": 1200,
        "net_payment_due": 10800,
    })
    return r.json()


async def test_pay_app_summary_with_links(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(client, pid)
    bp = await _billing_period(client, pid)
    pa = await _pay_app(client, cm["id"], bp["id"])

    r = await client.get(f"/api/payment-applications/{pa['id']}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["payment_application_id"] == pa["id"]
    assert body["this_period_amount"] == 12000
    assert body["retention_held"] == 1200
    assert body["commitment_id"] == cm["id"]
    assert body["commitment_number"] == cm["commitment_number"]
    assert body["vendor_id"] == COMPANY_REX
    assert body["billing_period_id"] == bp["id"]
    assert body["billing_period_number"] == bp["period_number"]
    assert body["lien_waiver_count"] == 0
    assert body["lien_waivers_by_status"] == {}


async def test_pay_app_summary_with_lien_waivers(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(client, pid)
    bp = await _billing_period(client, pid)
    pa = await _pay_app(client, cm["id"], bp["id"])

    # Add 2 lien waivers, different statuses
    await client.post("/api/lien-waivers/", json={
        "payment_application_id": pa["id"], "vendor_id": COMPANY_REX,
        "waiver_type": "conditional_progress", "amount": 12000,
        "through_date": "2025-01-31", "status": "received",
    })
    await client.post("/api/lien-waivers/", json={
        "payment_application_id": pa["id"], "vendor_id": COMPANY_REX,
        "waiver_type": "unconditional_progress", "amount": 12000,
        "through_date": "2025-01-31", "status": "approved",
    })

    r = await client.get(f"/api/payment-applications/{pa['id']}/summary")
    body = r.json()
    assert body["lien_waiver_count"] == 2
    assert body["lien_waivers_by_status"]["received"] == 1
    assert body["lien_waivers_by_status"]["approved"] == 1


async def test_pay_app_summary_404(client: AsyncClient):
    r = await client.get(f"/api/payment-applications/{BOGUS_UUID}/summary")
    assert r.status_code == 404

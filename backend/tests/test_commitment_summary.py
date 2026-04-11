"""Commitment summary read model tests (PCO/CCO/links/pay apps)."""

import uuid
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"CommSum-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _commitment(c: AsyncClient, pid: str, **kw) -> dict:
    p = {
        "project_id": pid, "vendor_id": COMPANY_REX,
        "commitment_number": f"SC-{_uid()}", "title": f"Sub-{_uid()}",
        "contract_type": "subcontract",
    }
    p.update(kw)
    r = await c.post("/api/commitments/", json=p)
    return r.json()


async def _change_event(c: AsyncClient, pid: str) -> dict:
    r = await c.post("/api/change-events/", json={
        "project_id": pid, "event_number": f"CE-{_uid()}",
        "title": f"CE-{_uid()}", "change_reason": "owner_change", "event_type": "owner_change",
    })
    return r.json()


async def _pco(c: AsyncClient, ce_id: str, cm_id: str, amount: float, status: str = "draft") -> dict:
    r = await c.post("/api/potential-change-orders/", json={
        "change_event_id": ce_id, "commitment_id": cm_id,
        "pco_number": f"PCO-{_uid()}", "title": f"PCO-{_uid()}",
        "amount": amount, "status": status,
    })
    return r.json()


async def _cco(c: AsyncClient, cm_id: str, total: float, status: str = "draft") -> dict:
    r = await c.post("/api/commitment-change-orders/", json={
        "commitment_id": cm_id, "cco_number": f"CCO-{_uid()}",
        "title": f"CCO-{_uid()}", "total_amount": total, "status": status,
    })
    return r.json()


async def test_commitment_summary_basic_values(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(
        client, pid,
        original_value=100000,
    )
    # Patch in approved_cos / revised etc
    await client.patch(f"/api/commitments/{cm['id']}", json={
        "approved_cos": 5000, "revised_value": 105000,
        "invoiced_to_date": 50000, "remaining_to_invoice": 55000,
    })

    r = await client.get(f"/api/commitments/{cm['id']}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["original_value"] == 100000
    assert body["approved_cos"] == 5000
    assert body["revised_value"] == 105000
    assert body["invoiced_to_date"] == 50000
    assert body["remaining_to_invoice"] == 55000
    assert body["pco_count"] == 0
    assert body["cco_count"] == 0
    assert body["pay_app_count"] == 0


async def test_commitment_summary_with_pcos(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(client, pid)
    ce = await _change_event(client, pid)

    await _pco(client, ce["id"], cm["id"], amount=2000, status="approved")
    await _pco(client, ce["id"], cm["id"], amount=3500, status="pending")
    await _pco(client, ce["id"], cm["id"], amount=1500, status="rejected")

    r = await client.get(f"/api/commitments/{cm['id']}/summary")
    body = r.json()
    assert body["pco_count"] == 3
    assert body["pco_total_amount"] == 7000
    assert body["pco_counts_by_status"]["approved"] == 1
    assert body["pco_counts_by_status"]["pending"] == 1
    assert body["pco_counts_by_status"]["rejected"] == 1


async def test_commitment_summary_with_ccos_and_links(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(client, pid)
    ce = await _change_event(client, pid)

    pco = await _pco(client, ce["id"], cm["id"], amount=5000)
    cco = await _cco(client, cm["id"], total=5000, status="executed")

    # Link PCO to CCO
    await client.post("/api/pco-cco-links/", json={"pco_id": pco["id"], "cco_id": cco["id"]})

    r = await client.get(f"/api/commitments/{cm['id']}/summary")
    body = r.json()
    assert body["pco_count"] == 1
    assert body["cco_count"] == 1
    assert body["cco_total_amount"] == 5000
    assert body["cco_counts_by_status"]["executed"] == 1
    assert body["linked_pco_to_cco_count"] == 1


async def test_commitment_summary_with_pay_apps(client: AsyncClient):
    pid = await _project(client)
    cm = await _commitment(client, pid)
    bp = await client.post("/api/billing-periods/", json={
        "project_id": pid, "period_number": int(_uid()[:4], 16),
        "start_date": "2025-01-01", "end_date": "2025-01-31", "due_date": "2025-02-10",
    })
    bp_id = bp.json()["id"]

    await client.post("/api/payment-applications/", json={
        "commitment_id": cm["id"], "billing_period_id": bp_id,
        "pay_app_number": int(_uid()[:4], 16),
        "period_start": "2025-01-01", "period_end": "2025-01-31",
        "this_period_amount": 10000,
    })
    await client.post("/api/payment-applications/", json={
        "commitment_id": cm["id"], "billing_period_id": bp_id,
        "pay_app_number": int(_uid()[:4], 16),
        "period_start": "2025-01-01", "period_end": "2025-01-31",
        "this_period_amount": 8000,
    })

    r = await client.get(f"/api/commitments/{cm['id']}/summary")
    body = r.json()
    assert body["pay_app_count"] == 2


async def test_commitment_summary_no_changes(client: AsyncClient):
    """Commitment with no PCOs/CCOs/pay apps returns zeros cleanly."""
    pid = await _project(client)
    cm = await _commitment(client, pid)
    r = await client.get(f"/api/commitments/{cm['id']}/summary")
    body = r.json()
    assert body["pco_count"] == 0
    assert body["pco_total_amount"] == 0
    assert body["cco_count"] == 0
    assert body["cco_total_amount"] == 0
    assert body["linked_pco_to_cco_count"] == 0
    assert body["pay_app_count"] == 0


async def test_commitment_summary_404(client: AsyncClient):
    r = await client.get(f"/api/commitments/{BOGUS_UUID}/summary")
    assert r.status_code == 404

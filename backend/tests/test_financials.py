"""Financials domain smoke tests.

Uses seeded Bishop Modern project and Rex Construction company.
Builds a dependency chain: cost_code -> budget_line_item -> budget_snapshot,
commitment -> commitment_line_item, change_event -> PCO -> CCO -> link,
billing_period -> payment_application -> lien_waiver.
"""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


# ── Shared helpers ───────────────────────────────────────────────────────────

async def _cost_code(c: AsyncClient, **kw) -> dict:
    p = {"project_id": PROJECT_BISHOP, "code": f"CC-{_uid()}", "name": f"Code-{_uid()}", "cost_type": "labor"}
    p.update(kw)
    r = await c.post("/api/cost-codes/", json=p)
    assert r.status_code == 201, r.text
    return r.json()

async def _commitment(c: AsyncClient, **kw) -> dict:
    p = {"project_id": PROJECT_BISHOP, "vendor_id": COMPANY_REX, "commitment_number": f"SC-{_uid()}", "title": f"Sub-{_uid()}", "contract_type": "subcontract"}
    p.update(kw)
    r = await c.post("/api/commitments/", json=p)
    assert r.status_code == 201, r.text
    return r.json()

async def _prime(c: AsyncClient, **kw) -> dict:
    p = {"project_id": PROJECT_BISHOP, "contract_number": f"PC-{_uid()}", "title": f"Prime-{_uid()}"}
    p.update(kw)
    r = await c.post("/api/prime-contracts/", json=p)
    assert r.status_code == 201, r.text
    return r.json()

async def _billing_period(c: AsyncClient, **kw) -> dict:
    n = int(_uid()[:4], 16)
    p = {"project_id": PROJECT_BISHOP, "period_number": n, "start_date": "2025-01-01", "end_date": "2025-01-31", "due_date": "2025-02-10"}
    p.update(kw)
    r = await c.post("/api/billing-periods/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Cost Codes
# ═══════════════════════════════════════════════════════════════════════════

async def test_cost_code_crud(client: AsyncClient):
    cc = await _cost_code(client)
    r = await client.get(f"/api/cost-codes/{cc['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/cost-codes/{cc['id']}", json={"name": "Patched"})
    assert r.status_code == 200
    assert r.json()["name"] == "Patched"

async def test_cost_code_self_ref(client: AsyncClient):
    parent = await _cost_code(client, code=f"P-{_uid()}", cost_type="material")
    child = await _cost_code(client, code=f"C-{_uid()}", parent_id=parent["id"])
    assert child["parent_id"] == parent["id"]

async def test_list_cost_codes(client: AsyncClient):
    r = await client.get(f"/api/cost-codes/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_cost_code_duplicate_409(client: AsyncClient):
    code = f"DUP-{_uid()}"
    await _cost_code(client, code=code)
    r = await client.post("/api/cost-codes/", json={"project_id": PROJECT_BISHOP, "code": code, "name": "Dup", "cost_type": "labor"})
    assert r.status_code == 409

async def test_cost_code_invalid_type(client: AsyncClient):
    r = await client.post("/api/cost-codes/", json={"project_id": PROJECT_BISHOP, "code": "BAD", "name": "Bad", "cost_type": "bogus"})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Budget Line Items + Snapshots
# ═══════════════════════════════════════════════════════════════════════════

async def test_budget_line_item_crud(client: AsyncClient):
    cc = await _cost_code(client)
    r = await client.post("/api/budget-line-items/", json={"project_id": PROJECT_BISHOP, "cost_code_id": cc["id"], "original_budget": 50000})
    assert r.status_code == 201
    bli_id = r.json()["id"]
    r = await client.get(f"/api/budget-line-items/{bli_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/budget-line-items/{bli_id}", json={"revised_budget": 55000})
    assert r.status_code == 200

async def test_budget_line_item_bad_fk(client: AsyncClient):
    r = await client.post("/api/budget-line-items/", json={"project_id": PROJECT_BISHOP, "cost_code_id": BOGUS_UUID})
    assert r.status_code == 422

async def test_list_budget_line_items(client: AsyncClient):
    r = await client.get(f"/api/budget-line-items/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_budget_snapshot_crud(client: AsyncClient):
    cc = await _cost_code(client)
    bli = await client.post("/api/budget-line-items/", json={"project_id": PROJECT_BISHOP, "cost_code_id": cc["id"], "original_budget": 10000})
    bli_id = bli.json()["id"]
    snap_date = f"2099-{(int(_uid()[:2],16)%12)+1:02d}-{(int(_uid()[:2],16)%28)+1:02d}"
    r = await client.post("/api/budget-snapshots/", json={"project_id": PROJECT_BISHOP, "budget_line_item_id": bli_id, "snapshot_date": snap_date, "revised_budget": 10000, "projected_cost": 9500, "over_under": 500, "committed_costs": 8000})
    assert r.status_code == 201
    r = await client.get(f"/api/budget-snapshots/{r.json()['id']}")
    assert r.status_code == 200

async def test_budget_snapshot_duplicate_409(client: AsyncClient):
    cc = await _cost_code(client)
    bli = await client.post("/api/budget-line-items/", json={"project_id": PROJECT_BISHOP, "cost_code_id": cc["id"]})
    bli_id = bli.json()["id"]
    payload = {"project_id": PROJECT_BISHOP, "budget_line_item_id": bli_id, "snapshot_date": "2098-01-01", "revised_budget": 0, "projected_cost": 0, "over_under": 0, "committed_costs": 0}
    r1 = await client.post("/api/budget-snapshots/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/budget-snapshots/", json=payload)
    assert r2.status_code == 409

async def test_list_budget_snapshots(client: AsyncClient):
    r = await client.get("/api/budget-snapshots/")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Prime Contracts
# ═══════════════════════════════════════════════════════════════════════════

async def test_prime_contract_crud(client: AsyncClient):
    pc = await _prime(client)
    r = await client.get(f"/api/prime-contracts/{pc['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/prime-contracts/{pc['id']}", json={"status": "executed"})
    assert r.status_code == 200
    assert r.json()["status"] == "executed"

async def test_list_prime_contracts(client: AsyncClient):
    r = await client.get(f"/api/prime-contracts/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Commitments + Line Items
# ═══════════════════════════════════════════════════════════════════════════

async def test_commitment_crud(client: AsyncClient):
    cm = await _commitment(client)
    r = await client.get(f"/api/commitments/{cm['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/commitments/{cm['id']}", json={"status": "executed"})
    assert r.status_code == 200

async def test_list_commitments(client: AsyncClient):
    r = await client.get(f"/api/commitments/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_commitment_line_item_crud(client: AsyncClient):
    cm = await _commitment(client)
    cc = await _cost_code(client)
    r = await client.post("/api/commitment-line-items/", json={"commitment_id": cm["id"], "cost_code_id": cc["id"], "description": f"Line-{_uid()}", "amount": 25000})
    assert r.status_code == 201
    li_id = r.json()["id"]
    r = await client.get(f"/api/commitment-line-items/{li_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/commitment-line-items/{li_id}", json={"amount": 27500})
    assert r.status_code == 200

async def test_list_commitment_line_items(client: AsyncClient):
    r = await client.get("/api/commitment-line-items/")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Change Events + PCOs + CCOs + Links
# ═══════════════════════════════════════════════════════════════════════════

async def test_change_event_crud(client: AsyncClient):
    r = await client.post("/api/change-events/", json={"project_id": PROJECT_BISHOP, "event_number": f"CE-{_uid()}", "title": f"CE-{_uid()}", "change_reason": "owner_change", "event_type": "owner_change"})
    assert r.status_code == 201
    ce_id = r.json()["id"]
    r = await client.get(f"/api/change-events/{ce_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/change-events/{ce_id}", json={"status": "approved"})
    assert r.status_code == 200

async def test_list_change_events(client: AsyncClient):
    r = await client.get(f"/api/change-events/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_change_event_invalid_reason(client: AsyncClient):
    r = await client.post("/api/change-events/", json={"project_id": PROJECT_BISHOP, "event_number": "BAD", "title": "Bad", "change_reason": "bogus", "event_type": "tbd"})
    assert r.status_code == 422

async def test_pco_crud(client: AsyncClient):
    cm = await _commitment(client)
    ce = await client.post("/api/change-events/", json={"project_id": PROJECT_BISHOP, "event_number": f"CE-{_uid()}", "title": "PCO Test CE", "change_reason": "design_change", "event_type": "tbd"})
    ce_id = ce.json()["id"]
    r = await client.post("/api/potential-change-orders/", json={"change_event_id": ce_id, "commitment_id": cm["id"], "pco_number": f"PCO-{_uid()}", "title": f"PCO-{_uid()}", "amount": 5000})
    assert r.status_code == 201
    pco_id = r.json()["id"]
    r = await client.get(f"/api/potential-change-orders/{pco_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/potential-change-orders/{pco_id}", json={"status": "approved"})
    assert r.status_code == 200

async def test_cco_crud(client: AsyncClient):
    cm = await _commitment(client)
    r = await client.post("/api/commitment-change-orders/", json={"commitment_id": cm["id"], "cco_number": f"CCO-{_uid()}", "title": f"CCO-{_uid()}", "total_amount": 5000})
    assert r.status_code == 201
    cco_id = r.json()["id"]
    r = await client.get(f"/api/commitment-change-orders/{cco_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/commitment-change-orders/{cco_id}", json={"status": "executed"})
    assert r.status_code == 200

async def test_pco_cco_link(client: AsyncClient):
    cm = await _commitment(client)
    ce = await client.post("/api/change-events/", json={"project_id": PROJECT_BISHOP, "event_number": f"CE-{_uid()}", "title": "Link CE", "change_reason": "unforeseen", "event_type": "tbd"})
    pco = await client.post("/api/potential-change-orders/", json={"change_event_id": ce.json()["id"], "commitment_id": cm["id"], "pco_number": f"PCO-{_uid()}", "title": "Link PCO"})
    cco = await client.post("/api/commitment-change-orders/", json={"commitment_id": cm["id"], "cco_number": f"CCO-{_uid()}", "title": "Link CCO"})
    r = await client.post("/api/pco-cco-links/", json={"pco_id": pco.json()["id"], "cco_id": cco.json()["id"]})
    assert r.status_code == 201
    link_id = r.json()["id"]
    r = await client.get(f"/api/pco-cco-links/{link_id}")
    assert r.status_code == 200

async def test_pco_cco_link_duplicate_409(client: AsyncClient):
    cm = await _commitment(client)
    ce = await client.post("/api/change-events/", json={"project_id": PROJECT_BISHOP, "event_number": f"CE-{_uid()}", "title": "Dup Link CE", "change_reason": "allowance", "event_type": "allowance"})
    pco = await client.post("/api/potential-change-orders/", json={"change_event_id": ce.json()["id"], "commitment_id": cm["id"], "pco_number": f"PCO-{_uid()}", "title": "Dup PCO"})
    cco = await client.post("/api/commitment-change-orders/", json={"commitment_id": cm["id"], "cco_number": f"CCO-{_uid()}", "title": "Dup CCO"})
    payload = {"pco_id": pco.json()["id"], "cco_id": cco.json()["id"]}
    r1 = await client.post("/api/pco-cco-links/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/pco-cco-links/", json=payload)
    assert r2.status_code == 409

async def test_list_pco_cco_links(client: AsyncClient):
    r = await client.get("/api/pco-cco-links/")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Billing Periods + Direct Costs + Pay Apps + Lien Waivers
# ═══════════════════════════════════════════════════════════════════════════

async def test_billing_period_crud(client: AsyncClient):
    bp = await _billing_period(client)
    r = await client.get(f"/api/billing-periods/{bp['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/billing-periods/{bp['id']}", json={"status": "locked"})
    assert r.status_code == 200

async def test_list_billing_periods(client: AsyncClient):
    r = await client.get(f"/api/billing-periods/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_billing_period_duplicate_409(client: AsyncClient):
    pn = int(_uid()[:4], 16)
    payload = {"project_id": PROJECT_BISHOP, "period_number": pn, "start_date": "2097-01-01", "end_date": "2097-01-31", "due_date": "2097-02-10"}
    r1 = await client.post("/api/billing-periods/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/billing-periods/", json=payload)
    assert r2.status_code == 409

async def test_direct_cost_crud(client: AsyncClient):
    cc = await _cost_code(client)
    r = await client.post("/api/direct-costs/", json={"project_id": PROJECT_BISHOP, "cost_code_id": cc["id"], "description": f"DC-{_uid()}", "amount": 1500, "direct_cost_date": "2025-03-15", "payment_method": "check"})
    assert r.status_code == 201
    dc_id = r.json()["id"]
    r = await client.get(f"/api/direct-costs/{dc_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/direct-costs/{dc_id}", json={"amount": 1600})
    assert r.status_code == 200

async def test_list_direct_costs(client: AsyncClient):
    r = await client.get(f"/api/direct-costs/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_payment_application_crud(client: AsyncClient):
    cm = await _commitment(client)
    bp = await _billing_period(client)
    r = await client.post("/api/payment-applications/", json={"commitment_id": cm["id"], "billing_period_id": bp["id"], "pay_app_number": int(_uid()[:4],16), "period_start": "2025-01-01", "period_end": "2025-01-31", "this_period_amount": 10000})
    assert r.status_code == 201
    pa_id = r.json()["id"]
    r = await client.get(f"/api/payment-applications/{pa_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/payment-applications/{pa_id}", json={"status": "submitted"})
    assert r.status_code == 200

async def test_list_payment_applications(client: AsyncClient):
    r = await client.get("/api/payment-applications/")
    assert r.status_code == 200

async def test_lien_waiver_crud(client: AsyncClient):
    cm = await _commitment(client)
    bp = await _billing_period(client)
    pa = await client.post("/api/payment-applications/", json={"commitment_id": cm["id"], "billing_period_id": bp["id"], "pay_app_number": int(_uid()[:4],16), "period_start": "2025-02-01", "period_end": "2025-02-28"})
    r = await client.post("/api/lien-waivers/", json={"payment_application_id": pa.json()["id"], "vendor_id": COMPANY_REX, "waiver_type": "conditional_progress", "amount": 10000, "through_date": "2025-02-28"})
    assert r.status_code == 201
    lw_id = r.json()["id"]
    r = await client.get(f"/api/lien-waivers/{lw_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/lien-waivers/{lw_id}", json={"status": "received", "received_date": "2025-03-01"})
    assert r.status_code == 200
    assert r.json()["status"] == "received"

async def test_list_lien_waivers(client: AsyncClient):
    r = await client.get("/api/lien-waivers/")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════

async def test_not_found_404(client: AsyncClient):
    for path in ["/api/cost-codes/", "/api/commitments/", "/api/payment-applications/"]:
        r = await client.get(f"{path}{BOGUS_UUID}")
        assert r.status_code == 404, f"{path} should 404"

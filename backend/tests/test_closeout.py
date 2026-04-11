"""Closeout & Warranty domain smoke tests.

Uses seeded Bishop Modern project and Rex Construction company.
Builds: template -> template_items, checklist -> checklist_items,
warranty -> claims -> alerts, completion_milestones.
"""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _template(c: AsyncClient, **kw) -> dict:
    p = {"name": f"Tmpl-{_uid()}", "project_type": "all"}
    p.update(kw)
    r = await c.post("/api/closeout-templates/", json=p)
    assert r.status_code == 201, r.text
    return r.json()

async def _checklist(c: AsyncClient, **kw) -> dict:
    p = {"project_id": PROJECT_BISHOP}
    p.update(kw)
    r = await c.post("/api/closeout-checklists/", json=p)
    assert r.status_code == 201, r.text
    return r.json()

async def _warranty(c: AsyncClient, **kw) -> dict:
    p = {"project_id": PROJECT_BISHOP, "company_id": COMPANY_REX,
         "scope_description": f"Warranty-{_uid()}", "warranty_type": "standard",
         "duration_months": 12, "start_date": "2025-06-01", "expiration_date": "2026-06-01"}
    p.update(kw)
    r = await c.post("/api/warranties/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Templates
# ═══════════════════════════════════════════════════════════════════════════

async def test_closeout_template_crud(client: AsyncClient):
    t = await _template(client)
    r = await client.get(f"/api/closeout-templates/{t['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/closeout-templates/{t['id']}", json={"name": "Patched"})
    assert r.status_code == 200
    assert r.json()["name"] == "Patched"

async def test_list_closeout_templates(client: AsyncClient):
    r = await client.get("/api/closeout-templates/")
    assert r.status_code == 200
    assert len(r.json()) >= 3  # 3 seeded

async def test_closeout_template_invalid_type(client: AsyncClient):
    r = await client.post("/api/closeout-templates/", json={"name": "Bad", "project_type": "bogus"})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Template Items
# ═══════════════════════════════════════════════════════════════════════════

async def test_closeout_template_item_crud(client: AsyncClient):
    t = await _template(client)
    r = await client.post("/api/closeout-template-items/", json={
        "template_id": t["id"], "category": "documentation", "item_number": 1,
        "name": f"Item-{_uid()}", "default_assignee_role": "lead_super",
    })
    assert r.status_code == 201
    iid = r.json()["id"]
    r = await client.get(f"/api/closeout-template-items/{iid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/closeout-template-items/{iid}", json={"name": "Updated Item"})
    assert r.status_code == 200

async def test_list_closeout_template_items(client: AsyncClient):
    r = await client.get("/api/closeout-template-items/")
    assert r.status_code == 200

async def test_template_item_bad_fk(client: AsyncClient):
    r = await client.post("/api/closeout-template-items/", json={
        "template_id": BOGUS_UUID, "category": "general", "item_number": 1, "name": "Bad",
    })
    assert r.status_code == 422

async def test_template_item_invalid_category(client: AsyncClient):
    t = await _template(client)
    r = await client.post("/api/closeout-template-items/", json={
        "template_id": t["id"], "category": "bogus", "item_number": 1, "name": "Bad",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Checklists
# ═══════════════════════════════════════════════════════════════════════════

async def test_closeout_checklist_crud(client: AsyncClient):
    cl = await _checklist(client)
    r = await client.get(f"/api/closeout-checklists/{cl['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/closeout-checklists/{cl['id']}", json={"total_items": 34})
    assert r.status_code == 200
    assert r.json()["total_items"] == 34

async def test_list_closeout_checklists(client: AsyncClient):
    r = await client.get(f"/api/closeout-checklists/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Checklist Items
# ═══════════════════════════════════════════════════════════════════════════

async def test_closeout_checklist_item_crud(client: AsyncClient):
    cl = await _checklist(client)
    r = await client.post("/api/closeout-checklist-items/", json={
        "checklist_id": cl["id"], "category": "mep", "item_number": 1,
        "name": f"CheckItem-{_uid()}",
    })
    assert r.status_code == 201
    ciid = r.json()["id"]
    r = await client.get(f"/api/closeout-checklist-items/{ciid}")
    assert r.status_code == 200
    assert r.json()["status"] == "not_started"
    r = await client.patch(f"/api/closeout-checklist-items/{ciid}", json={"status": "complete"})
    assert r.status_code == 200
    assert r.json()["status"] == "complete"

async def test_list_closeout_checklist_items(client: AsyncClient):
    r = await client.get("/api/closeout-checklist-items/")
    assert r.status_code == 200

async def test_checklist_item_invalid_status(client: AsyncClient):
    cl = await _checklist(client)
    r = await client.post("/api/closeout-checklist-items/", json={
        "checklist_id": cl["id"], "category": "general", "item_number": 1,
        "name": "Bad", "status": "bogus",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Warranties
# ═══════════════════════════════════════════════════════════════════════════

async def test_warranty_crud(client: AsyncClient):
    w = await _warranty(client)
    r = await client.get(f"/api/warranties/{w['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/warranties/{w['id']}", json={"is_letter_received": True})
    assert r.status_code == 200
    assert r.json()["is_letter_received"] is True

async def test_list_warranties(client: AsyncClient):
    r = await client.get(f"/api/warranties/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_warranty_invalid_type(client: AsyncClient):
    r = await client.post("/api/warranties/", json={
        "project_id": PROJECT_BISHOP, "company_id": COMPANY_REX,
        "scope_description": "Bad", "warranty_type": "bogus",
        "duration_months": 12, "start_date": "2025-01-01", "expiration_date": "2026-01-01",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Warranty Claims
# ═══════════════════════════════════════════════════════════════════════════

async def test_warranty_claim_crud(client: AsyncClient):
    w = await _warranty(client)
    r = await client.post("/api/warranty-claims/", json={
        "warranty_id": w["id"], "claim_number": int(_uid()[:4], 16),
        "title": f"Claim-{_uid()}", "description": "Leak in unit 201",
        "reported_date": "2025-09-01",
    })
    assert r.status_code == 201
    cid = r.json()["id"]
    r = await client.get(f"/api/warranty-claims/{cid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/warranty-claims/{cid}", json={"status": "resolved", "resolved_date": "2025-09-15"})
    assert r.status_code == 200

async def test_list_warranty_claims(client: AsyncClient):
    r = await client.get("/api/warranty-claims/")
    assert r.status_code == 200

async def test_warranty_claim_bad_fk(client: AsyncClient):
    r = await client.post("/api/warranty-claims/", json={
        "warranty_id": BOGUS_UUID, "claim_number": 1,
        "title": "Bad", "description": "Bad", "reported_date": "2025-01-01",
    })
    assert r.status_code in (404, 422)  # write-scope resolves parent first → 404


# ═══════════════════════════════════════════════════════════════════════════
# Warranty Alerts
# ═══════════════════════════════════════════════════════════════════════════

async def test_warranty_alert_crud(client: AsyncClient):
    w = await _warranty(client)
    r = await client.post("/api/warranty-alerts/", json={
        "warranty_id": w["id"], "alert_type": "90_day", "alert_date": "2026-03-01",
    })
    assert r.status_code == 201
    aid = r.json()["id"]
    r = await client.get(f"/api/warranty-alerts/{aid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/warranty-alerts/{aid}", json={"is_sent": True})
    assert r.status_code == 200
    assert r.json()["is_sent"] is True

async def test_list_warranty_alerts(client: AsyncClient):
    r = await client.get("/api/warranty-alerts/")
    assert r.status_code == 200

async def test_warranty_alert_invalid_type(client: AsyncClient):
    w = await _warranty(client)
    r = await client.post("/api/warranty-alerts/", json={
        "warranty_id": w["id"], "alert_type": "bogus", "alert_date": "2026-01-01",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Completion Milestones
# ═══════════════════════════════════════════════════════════════════════════

async def test_completion_milestone_crud(client: AsyncClient):
    # Create a fresh project to avoid unique constraint on (project_id, milestone_type)
    proj = await client.post("/api/projects/", json={"name": f"Milestone-Proj-{_uid()}", "status": "active"})
    pid = proj.json()["id"]
    r = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "rough_in",
        "milestone_name": "Rough-In Complete",
    })
    assert r.status_code == 201
    mid = r.json()["id"]
    r = await client.get(f"/api/completion-milestones/{mid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/completion-milestones/{mid}", json={"status": "achieved", "is_evidence_complete": True})
    assert r.status_code == 200
    assert r.json()["status"] == "achieved"

async def test_list_completion_milestones(client: AsyncClient):
    r = await client.get(f"/api/completion-milestones/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200
    assert len(r.json()) >= 6  # 6 seeded for Bishop Modern (multifamily)

async def test_completion_milestone_duplicate_409(client: AsyncClient):
    proj = await client.post("/api/projects/", json={"name": f"Dup-MS-{_uid()}", "status": "active"})
    pid = proj.json()["id"]
    payload = {"project_id": pid, "milestone_type": "tco", "milestone_name": "TCO"}
    r1 = await client.post("/api/completion-milestones/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/completion-milestones/", json=payload)
    assert r2.status_code == 409

async def test_completion_milestone_invalid_type(client: AsyncClient):
    r = await client.post("/api/completion-milestones/", json={
        "project_id": PROJECT_BISHOP, "milestone_type": "bogus", "milestone_name": "Bad",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════

async def test_not_found_404(client: AsyncClient):
    for path in ["/api/closeout-templates/", "/api/warranties/", "/api/completion-milestones/"]:
        r = await client.get(f"{path}{BOGUS_UUID}")
        assert r.status_code == 404, f"{path} should 404"

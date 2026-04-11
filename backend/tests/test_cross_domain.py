"""Cross-domain integration tests.

Proves FK relationships work across domain boundaries.
Each test creates data in one domain and references it from another.
"""

from httpx import AsyncClient
from tests.helpers import PROJECT_BISHOP, COMPANY_REX, PERSON_ROBERTS, BOGUS_UUID, uid


# ── Shared builders ──────────────────────────────────────────────────────────

async def _schedule(c: AsyncClient) -> dict:
    r = await c.post("/api/schedules/", json={"project_id": PROJECT_BISHOP, "name": f"XD-Sched-{uid()}", "schedule_type": "master", "start_date": "2025-01-01"})
    assert r.status_code == 201
    return r.json()

async def _activity(c: AsyncClient, schedule_id: str) -> dict:
    r = await c.post("/api/schedule-activities/", json={"schedule_id": schedule_id, "name": f"XD-Act-{uid()}", "activity_type": "task", "start_date": "2025-01-06", "end_date": "2025-01-10"})
    assert r.status_code == 201
    return r.json()

async def _cost_code(c: AsyncClient) -> dict:
    r = await c.post("/api/cost-codes/", json={"project_id": PROJECT_BISHOP, "code": f"XD-{uid()}", "name": f"Code-{uid()}", "cost_type": "labor"})
    assert r.status_code == 201
    return r.json()

async def _commitment(c: AsyncClient) -> dict:
    r = await c.post("/api/commitments/", json={"project_id": PROJECT_BISHOP, "vendor_id": COMPANY_REX, "commitment_number": f"XD-SC-{uid()}", "title": f"XD-Sub-{uid()}", "contract_type": "subcontract"})
    assert r.status_code == 201
    return r.json()

async def _drawing_area(c: AsyncClient) -> dict:
    r = await c.post("/api/drawing-areas/", json={"project_id": PROJECT_BISHOP, "name": f"XD-Area-{uid()}"})
    assert r.status_code == 201
    return r.json()

async def _drawing(c: AsyncClient, area_id: str) -> dict:
    r = await c.post("/api/drawings/", json={"project_id": PROJECT_BISHOP, "drawing_area_id": area_id, "drawing_number": f"XD-{uid()}", "title": f"XD-Dwg-{uid()}", "discipline": "architectural"})
    assert r.status_code == 201
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Field Ops -> Schedule: inspection with valid activity_id
# ═══════════════════════════════════════════════════════════════════════════

async def test_inspection_with_schedule_activity(client: AsyncClient):
    sched = await _schedule(client)
    act = await _activity(client, sched["id"])
    r = await client.post("/api/inspections/", json={
        "project_id": PROJECT_BISHOP, "inspection_number": f"XD-INS-{uid()}",
        "title": f"XD-Insp-{uid()}", "inspection_type": "municipal",
        "scheduled_date": "2025-06-01", "activity_id": act["id"],
    })
    assert r.status_code == 201
    assert r.json()["activity_id"] == act["id"]


# ═══════════════════════════════════════════════════════════════════════════
# Doc Mgmt -> Schedule + Financials: submittal with activity + cost_code
# ═══════════════════════════════════════════════════════════════════════════

async def test_submittal_with_schedule_and_cost_code(client: AsyncClient):
    sched = await _schedule(client)
    act = await _activity(client, sched["id"])
    cc = await _cost_code(client)
    r = await client.post("/api/submittals/", json={
        "project_id": PROJECT_BISHOP, "submittal_number": f"XD-SUB-{uid()}",
        "title": f"XD-Submittal-{uid()}", "submittal_type": "shop_drawing",
        "schedule_activity_id": act["id"], "cost_code_id": cc["id"],
    })
    assert r.status_code == 201
    body = r.json()
    assert body["schedule_activity_id"] == act["id"]
    assert body["cost_code_id"] == cc["id"]


# ═══════════════════════════════════════════════════════════════════════════
# Doc Mgmt -> Financials + Drawings: RFI with drawing + cost_code
# ═══════════════════════════════════════════════════════════════════════════

async def test_rfi_with_drawing_and_cost_code(client: AsyncClient):
    area = await _drawing_area(client)
    dwg = await _drawing(client, area["id"])
    cc = await _cost_code(client)
    r = await client.post("/api/rfis/", json={
        "project_id": PROJECT_BISHOP, "rfi_number": f"XD-RFI-{uid()}",
        "subject": f"XD-Subject-{uid()}", "question": "Per which spec section?",
        "drawing_id": dwg["id"], "cost_code_id": cc["id"],
    })
    assert r.status_code == 201
    body = r.json()
    assert body["drawing_id"] == dwg["id"]
    assert body["cost_code_id"] == cc["id"]


# ═══════════════════════════════════════════════════════════════════════════
# Closeout -> Financials: warranty with commitment + cost_code
# ═══════════════════════════════════════════════════════════════════════════

async def test_warranty_with_commitment_and_cost_code(client: AsyncClient):
    cm = await _commitment(client)
    cc = await _cost_code(client)
    r = await client.post("/api/warranties/", json={
        "project_id": PROJECT_BISHOP, "company_id": COMPANY_REX,
        "scope_description": f"XD-Warranty-{uid()}", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-06-01", "expiration_date": "2026-06-01",
        "commitment_id": cm["id"], "cost_code_id": cc["id"],
    })
    assert r.status_code == 201
    body = r.json()
    assert body["commitment_id"] == cm["id"]
    assert body["cost_code_id"] == cc["id"]


# ═══════════════════════════════════════════════════════════════════════════
# Closeout: milestone duplicate (project_id, milestone_type) -> 409
# ═══════════════════════════════════════════════════════════════════════════

async def test_milestone_duplicate_cross_domain(client: AsyncClient):
    proj = await client.post("/api/projects/", json={"name": f"XD-Proj-{uid()}", "status": "active"})
    pid = proj.json()["id"]
    payload = {"project_id": pid, "milestone_type": "tco", "milestone_name": "TCO"}
    r1 = await client.post("/api/completion-milestones/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/completion-milestones/", json=payload)
    assert r2.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# Doc Mgmt: attachment metadata CRUD with real project
# ═══════════════════════════════════════════════════════════════════════════

async def test_attachment_metadata_crud(client: AsyncClient):
    # Create an RFI to use as source
    rfi = await client.post("/api/rfis/", json={
        "project_id": PROJECT_BISHOP, "rfi_number": f"XD-RFI-ATT-{uid()}",
        "subject": "Attachment test", "question": "See attached?",
    })
    rfi_id = rfi.json()["id"]

    r = await client.post("/api/attachments/", json={
        "project_id": PROJECT_BISHOP, "source_type": "rfi", "source_id": rfi_id,
        "filename": f"spec-{uid()}.pdf", "file_size": 2048,
        "content_type": "application/pdf",
        "storage_url": f"https://r2.example.com/{uid()}.pdf",
        "storage_key": f"attachments/{uid()}",
    })
    assert r.status_code == 201
    att = r.json()
    assert att["source_type"] == "rfi"
    assert att["source_id"] == rfi_id

    # Verify list filter by source
    r = await client.get(f"/api/attachments/?source_type=rfi&source_id={rfi_id}")
    assert r.status_code == 200
    assert any(a["id"] == att["id"] for a in r.json())


# ═══════════════════════════════════════════════════════════════════════════
# Closeout: checklist item with valid assigned person + company
# ═══════════════════════════════════════════════════════════════════════════

async def test_checklist_item_with_assignments(client: AsyncClient):
    cl = await client.post("/api/closeout-checklists/", json={"project_id": PROJECT_BISHOP})
    cl_id = cl.json()["id"]

    r = await client.post("/api/closeout-checklist-items/", json={
        "checklist_id": cl_id, "category": "general", "item_number": 1,
        "name": f"XD-Item-{uid()}", "assigned_company_id": COMPANY_REX,
        "assigned_person_id": PERSON_ROBERTS,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["assigned_company_id"] == COMPANY_REX
    assert body["assigned_person_id"] == PERSON_ROBERTS


# ═══════════════════════════════════════════════════════════════════════════
# Foundation: filter consistency
# ═══════════════════════════════════════════════════════════════════════════

async def test_foundation_filters(client: AsyncClient):
    """Verify new Foundation filters work."""
    r = await client.get(f"/api/projects/?status=active")
    assert r.status_code == 200
    assert all(p["status"] == "active" for p in r.json())

    r = await client.get(f"/api/people/?role_type=internal")
    assert r.status_code == 200
    assert all(p["role_type"] == "internal" for p in r.json())

    r = await client.get(f"/api/project-members/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200
    assert all(m["project_id"] == PROJECT_BISHOP for m in r.json())

    r = await client.get(f"/api/connector-mappings/?connector=procore")
    assert r.status_code == 200
    assert all(m["connector"] == "procore" for m in r.json())

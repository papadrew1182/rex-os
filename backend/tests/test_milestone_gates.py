"""Milestone gate evaluation tests.

Tests the read-only gate evaluation helper on completion milestones.
"""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
TEMPLATE_STANDARD = "a0000001-0000-0000-0000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Gate-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _milestone(c: AsyncClient, project_id: str, mtype: str = "rough_in") -> dict:
    r = await c.post("/api/completion-milestones/", json={
        "project_id": project_id, "milestone_type": mtype,
        "milestone_name": f"MS-{_uid()}", "scheduled_date": "2025-08-01",
    })
    assert r.status_code == 201
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Full pass scenario
# ═══════════════════════════════════════════════════════════════════════════

async def test_gates_full_pass(client: AsyncClient):
    """Achieved + evidence complete + 100% checklist = all pass."""
    pid = await _project(client)
    ms = await _milestone(client, pid)

    # Certify
    await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS, "actual_date": "2025-08-01",
    })
    # Mark evidence complete
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={
        "all_items_complete": True,
    })
    # Create a 100% checklist
    cl = await client.post("/api/closeout-checklists/", json={"project_id": pid, "total_items": 10, "completed_items": 10, "percent_complete": 100})
    assert cl.status_code == 201

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    assert r.status_code == 200
    body = r.json()
    assert body["gate_status"] == "pass"
    assert body["summary_message"] == "All gates passed"

    codes = {g["code"] for g in body["gate_results"]}
    assert "certified" in codes
    assert "evidence_complete" in codes
    assert "closeout_checklist" in codes


# ═══════════════════════════════════════════════════════════════════════════
# Failure scenarios
# ═══════════════════════════════════════════════════════════════════════════

async def test_gates_not_achieved_fails(client: AsyncClient):
    """Milestone not certified -> certified gate fails."""
    pid = await _project(client)
    ms = await _milestone(client, pid)

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    body = r.json()
    assert body["gate_status"] == "fail"

    cert_gate = next(g for g in body["gate_results"] if g["code"] == "certified")
    assert cert_gate["status"] == "fail"


async def test_gates_evidence_incomplete_fails(client: AsyncClient):
    """Evidence not confirmed -> evidence gate fails."""
    pid = await _project(client)
    ms = await _milestone(client, pid)

    # Certify but don't confirm evidence
    await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
    })

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    body = r.json()
    assert body["gate_status"] == "fail"

    ev_gate = next(g for g in body["gate_results"] if g["code"] == "evidence_complete")
    assert ev_gate["status"] == "fail"


async def test_gates_no_checklist_warning(client: AsyncClient):
    """No closeout checklist on project -> warning."""
    pid = await _project(client)
    ms = await _milestone(client, pid)

    await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={"certified_by": PERSON_ROBERTS})
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={"all_items_complete": True})

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    body = r.json()

    cl_gate = next(g for g in body["gate_results"] if g["code"] == "closeout_checklist")
    assert cl_gate["status"] == "warning"
    assert "No closeout checklist" in cl_gate["detail"]


async def test_gates_partial_checklist_warning(client: AsyncClient):
    """Checklist at 90% -> warning."""
    pid = await _project(client)
    ms = await _milestone(client, pid)

    await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={"certified_by": PERSON_ROBERTS})
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={"all_items_complete": True})
    await client.post("/api/closeout-checklists/", json={"project_id": pid, "total_items": 10, "completed_items": 9, "percent_complete": 90})

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    body = r.json()

    cl_gate = next(g for g in body["gate_results"] if g["code"] == "closeout_checklist")
    assert cl_gate["status"] == "warning"
    assert body["gate_status"] == "warning"


async def test_gates_low_checklist_fails(client: AsyncClient):
    """Checklist at 50% -> fail."""
    pid = await _project(client)
    ms = await _milestone(client, pid)

    await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={"certified_by": PERSON_ROBERTS})
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={"all_items_complete": True})
    await client.post("/api/closeout-checklists/", json={"project_id": pid, "total_items": 10, "completed_items": 5, "percent_complete": 50})

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    body = r.json()
    assert body["gate_status"] == "fail"


# ═══════════════════════════════════════════════════════════════════════════
# Holdback-specific + gate_conditions metadata
# ═══════════════════════════════════════════════════════════════════════════

async def test_gates_holdback_with_warranty_clear(client: AsyncClient):
    """Holdback release with warranties but no claims -> warranty gate pass."""
    pid = await _project(client)
    ms = await _milestone(client, pid, mtype="holdback_release")

    await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={"certified_by": PERSON_ROBERTS})
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={"all_items_complete": True})
    await client.post("/api/closeout-checklists/", json={"project_id": pid, "total_items": 1, "completed_items": 1, "percent_complete": 100})

    # Create a warranty with no claims
    await client.post("/api/warranties/", json={
        "project_id": pid, "company_id": COMPANY_REX,
        "scope_description": "Roofing", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01",
    })

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    body = r.json()

    w_gate = next(g for g in body["gate_results"] if g["code"] == "warranty_status")
    assert w_gate["status"] == "pass"


async def test_gates_holdback_with_claimed_warranty(client: AsyncClient):
    """Holdback release with a claimed warranty -> warranty gate fail."""
    pid = await _project(client)
    ms = await _milestone(client, pid, mtype="holdback_release")

    await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={"certified_by": PERSON_ROBERTS})
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={"all_items_complete": True})
    await client.post("/api/closeout-checklists/", json={"project_id": pid, "total_items": 1, "completed_items": 1, "percent_complete": 100})

    w = await client.post("/api/warranties/", json={
        "project_id": pid, "company_id": COMPANY_REX,
        "scope_description": "HVAC", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01", "status": "claimed",
    })

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-gates")
    body = r.json()

    w_gate = next(g for g in body["gate_results"] if g["code"] == "warranty_status")
    assert w_gate["status"] == "fail"
    assert body["gate_status"] == "fail"


async def test_gates_surfaces_gate_conditions_metadata(client: AsyncClient):
    """Seeded holdback_release milestone has gate_conditions in evidence_requirements."""
    # Use seeded Bishop Modern holdback_release
    r = await client.get(f"/api/completion-milestones/?project_id={PROJECT_BISHOP}&milestone_type=holdback_release")
    milestones = r.json()
    assert len(milestones) >= 1
    ms_id = milestones[0]["id"]

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()

    meta_gates = [g for g in body["gate_results"] if g["code"].startswith("evidence_gate:")]
    assert len(meta_gates) >= 3  # seeded holdback has 4 gate_conditions
    assert all(g["status"] == "not_applicable" for g in meta_gates)


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════

async def test_gates_bad_milestone_404(client: AsyncClient):
    r = await client.post(f"/api/completion-milestones/{BOGUS_UUID}/evaluate-gates")
    assert r.status_code == 404

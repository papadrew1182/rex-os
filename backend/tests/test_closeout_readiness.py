"""Project closeout readiness summary tests."""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
TEMPLATE_STANDARD = "a0000001-0000-0000-0000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]

async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Ready-{_uid()}", "status": "active"})
    return r.json()["id"]


async def test_bad_project_404(client: AsyncClient):
    r = await client.get(f"/api/projects/{BOGUS_UUID}/closeout-readiness")
    assert r.status_code == 404


async def test_no_artifacts_not_started(client: AsyncClient):
    """Project with no checklists, milestones, or warranties -> not_started."""
    pid = await _project(client)
    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["overall_status"] == "not_started"
    assert body["checklist_summary"]["checklist_count"] == 0
    assert body["milestone_summary"]["total_milestones"] == 0
    assert body["warranty_summary"]["total_warranties"] == 0
    assert body["holdback_release"]["exists"] is False


async def test_full_pass_scenario(client: AsyncClient):
    """Project with 100% checklist + all milestones achieved + evidence + no warranty claims -> pass."""
    pid = await _project(client)

    # Checklist at 100%
    await client.post("/api/closeout-checklists/", json={
        "project_id": pid, "total_items": 10, "completed_items": 10, "percent_complete": 100,
    })

    # One milestone achieved + evidence complete
    ms = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "substantial_completion",
        "milestone_name": "Substantial Completion",
    })
    ms_id = ms.json()["id"]
    await client.post(f"/api/completion-milestones/{ms_id}/evaluate-evidence", json={"all_items_complete": True})
    await client.post(f"/api/completion-milestones/{ms_id}/certify", json={"certified_by": PERSON_ROBERTS})

    # Holdback release achieved + evidence + checklist pass
    hb = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "holdback_release",
        "milestone_name": "Holdback Release",
    })
    hb_id = hb.json()["id"]
    await client.post(f"/api/completion-milestones/{hb_id}/evaluate-evidence", json={"all_items_complete": True})
    await client.post(f"/api/completion-milestones/{hb_id}/certify", json={"certified_by": PERSON_ROBERTS})

    # Add a clean warranty so holdback warranty gate passes
    await client.post("/api/warranties/", json={
        "project_id": pid, "company_id": COMPANY_REX,
        "scope_description": "Roofing", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01",
    })

    # Add a closed punch item so punch_aging gate passes
    await client.post("/api/punch-items/", json={
        "project_id": pid, "punch_number": 1,
        "title": "Closed punch", "status": "closed",
    })

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert body["overall_status"] == "pass"
    assert body["checklist_summary"]["best_percent_complete"] == 100
    assert body["milestone_summary"]["achieved_count"] == 2
    assert body["holdback_release"]["exists"] is True
    assert body["holdback_release"]["gate_status"] == "pass"


async def test_partial_checklist_warning(client: AsyncClient):
    """85% checklist -> warning."""
    pid = await _project(client)
    await client.post("/api/closeout-checklists/", json={
        "project_id": pid, "total_items": 20, "completed_items": 17, "percent_complete": 85,
    })
    ms = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "tco", "milestone_name": "TCO",
    })

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert body["overall_status"] in ("warning", "fail")  # warning from checklist + pending milestone
    assert any("85%" in i["message"] for i in body["open_issues"])


async def test_failed_holdback_gates_fail(client: AsyncClient):
    """Holdback release with uncertified milestone -> fail in gates -> overall fail."""
    pid = await _project(client)
    await client.post("/api/closeout-checklists/", json={
        "project_id": pid, "total_items": 10, "completed_items": 10, "percent_complete": 100,
    })
    # Create holdback but don't certify
    await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "holdback_release",
        "milestone_name": "Holdback Release",
    })

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert body["overall_status"] == "fail"
    assert body["holdback_release"]["gate_status"] == "fail"


async def test_claimed_warranty_fail(client: AsyncClient):
    """Claimed warranty shows in warranty summary and causes fail/warning."""
    pid = await _project(client)
    # Need a milestone to avoid not_started
    await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "tco", "milestone_name": "TCO",
    })
    await client.post("/api/warranties/", json={
        "project_id": pid, "company_id": COMPANY_REX,
        "scope_description": "Claimed warranty", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01", "status": "claimed",
    })

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert body["warranty_summary"]["claimed_count"] == 1
    assert body["overall_status"] == "fail"
    assert any("claim" in i["message"].lower() for i in body["open_issues"])


async def test_response_includes_all_sections(client: AsyncClient):
    """Verify response shape has all expected keys."""
    pid = await _project(client)
    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert "project_id" in body
    assert "project_name" in body
    assert "overall_status" in body
    assert "summary_message" in body
    assert "checklist_summary" in body
    assert "milestone_summary" in body
    assert "holdback_release" in body
    assert "warranty_summary" in body
    assert "open_issues" in body


async def test_milestone_summary_detail(client: AsyncClient):
    """Milestone summary includes per-milestone detail."""
    pid = await _project(client)
    await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "rough_in", "milestone_name": "Rough-In",
    })
    await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "tco", "milestone_name": "TCO",
    })

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert body["milestone_summary"]["total_milestones"] == 2
    types = {m["milestone_type"] for m in body["milestone_summary"]["milestones"]}
    assert types == {"rough_in", "tco"}


async def test_open_issues_populated(client: AsyncClient):
    """Open issues contain actionable messages for pending milestones."""
    pid = await _project(client)
    await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "rough_in", "milestone_name": "Rough-In",
    })

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert len(body["open_issues"]) >= 1
    assert any("pending" in i["message"].lower() for i in body["open_issues"])

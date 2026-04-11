"""Milestone certification workflow tests.

Uses seeded Bishop Modern milestones and seeded people.
"""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _fresh_milestone(c: AsyncClient, **kw) -> dict:
    """Create a fresh milestone on a new project to avoid seeded data conflicts."""
    proj = await c.post("/api/projects/", json={"name": f"Cert-{_uid()}", "status": "active"})
    pid = proj.json()["id"]
    payload = {
        "project_id": pid, "milestone_type": "rough_in",
        "milestone_name": "Rough-In Complete", "scheduled_date": "2025-08-01",
    }
    payload.update(kw)
    r = await c.post("/api/completion-milestones/", json=payload)
    assert r.status_code == 201
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Certification
# ═══════════════════════════════════════════════════════════════════════════

async def test_certify_sets_status_achieved(client: AsyncClient):
    ms = await _fresh_milestone(client)
    assert ms["status"] == "pending"

    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "achieved"
    assert body["certified_by"] == PERSON_ROBERTS


async def test_certify_stores_actual_date(client: AsyncClient):
    ms = await _fresh_milestone(client)
    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
        "actual_date": "2025-08-05",
    })
    assert r.status_code == 200
    assert r.json()["actual_date"] == "2025-08-05"


async def test_certify_computes_variance(client: AsyncClient):
    """When scheduled_date and actual_date are both present, variance_days is computed."""
    ms = await _fresh_milestone(client, scheduled_date="2025-08-01")
    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
        "actual_date": "2025-08-05",
    })
    assert r.status_code == 200

    # Fetch full record to check variance
    r2 = await client.get(f"/api/completion-milestones/{ms['id']}")
    assert r2.json()["variance_days"] == 4  # 4 days late


async def test_certify_with_notes(client: AsyncClient):
    ms = await _fresh_milestone(client)
    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
        "notes": "Certified after VP site walk.",
    })
    assert r.status_code == 200
    assert r.json()["notes"] == "Certified after VP site walk."


async def test_certify_bad_milestone_404(client: AsyncClient):
    r = await client.post(f"/api/completion-milestones/{BOGUS_UUID}/certify", json={
        "certified_by": PERSON_ROBERTS,
    })
    assert r.status_code == 404


async def test_certify_bad_person_422(client: AsyncClient):
    ms = await _fresh_milestone(client)
    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": BOGUS_UUID,
    })
    assert r.status_code == 422
    assert "person" in r.json()["detail"].lower()


async def test_certify_with_evidence_incomplete_shows_warning(client: AsyncClient):
    """Certifying when evidence is incomplete succeeds but returns a warning flag."""
    ms = await _fresh_milestone(client)
    assert ms["is_evidence_complete"] is False

    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "achieved"
    assert body["evidence_incomplete_warning"] is True


async def test_certify_with_evidence_complete_no_warning(client: AsyncClient):
    """Certifying when evidence is complete does not show a warning."""
    ms = await _fresh_milestone(client)

    # Mark evidence complete first
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={
        "all_items_complete": True,
    })

    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
    })
    assert r.status_code == 200
    assert r.json()["evidence_incomplete_warning"] is None


async def test_patch_does_not_auto_certify(client: AsyncClient):
    """PATCH on milestone fields does not accidentally set status=achieved or certified_by."""
    ms = await _fresh_milestone(client)
    r = await client.patch(f"/api/completion-milestones/{ms['id']}", json={
        "notes": "Updated via PATCH",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["certified_by"] is None


async def test_certify_preserves_existing_actual_date(client: AsyncClient):
    """Certifying without providing actual_date keeps existing one."""
    ms = await _fresh_milestone(client)

    # Set actual_date via PATCH first
    await client.patch(f"/api/completion-milestones/{ms['id']}", json={
        "actual_date": "2025-07-28",
    })

    r = await client.post(f"/api/completion-milestones/{ms['id']}/certify", json={
        "certified_by": PERSON_ROBERTS,
    })
    assert r.status_code == 200
    assert r.json()["actual_date"] == "2025-07-28"

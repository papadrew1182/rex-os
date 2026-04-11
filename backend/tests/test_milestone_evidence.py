"""Completion milestone evidence helper tests.

Uses seeded Bishop Modern milestones (multifamily: 6 milestones with evidence JSONB).
"""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _get_seeded_milestone(c: AsyncClient, milestone_type: str) -> dict:
    """Fetch a seeded milestone from Bishop Modern by type."""
    r = await c.get(f"/api/completion-milestones/?project_id={PROJECT_BISHOP}&milestone_type={milestone_type}")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1, f"No seeded milestone found for type={milestone_type}"
    return data[0]


# ═══════════════════════════════════════════════════════════════════════════
# Evidence checklist view
# ═══════════════════════════════════════════════════════════════════════════

async def test_evidence_checklist_returns_parsed_items(client: AsyncClient):
    """Seeded foundation_podium milestone has 3 checklist items."""
    ms = await _get_seeded_milestone(client, "foundation_podium")
    r = await client.get(f"/api/completion-milestones/{ms['id']}/evidence-checklist")
    assert r.status_code == 200
    body = r.json()

    assert body["milestone_id"] == ms["id"]
    assert body["milestone_type"] == "foundation_podium"
    assert body["milestone_name"] == "Foundation / Podium"
    assert body["is_evidence_complete"] is False
    assert len(body["checklist"]) == 3

    # Verify item structure
    items = body["checklist"]
    sources = {i["source"] for i in items}
    assert "inspections" in sources
    assert "photos" in sources
    assert "schedule" in sources


async def test_evidence_checklist_includes_payout(client: AsyncClient):
    """Seeded milestones have payout_percent and holdback_percent."""
    ms = await _get_seeded_milestone(client, "foundation_podium")
    r = await client.get(f"/api/completion-milestones/{ms['id']}/evidence-checklist")
    body = r.json()
    assert body["payout_percent"] == 20
    assert body["holdback_percent"] == 10


async def test_evidence_checklist_with_gate_conditions(client: AsyncClient):
    """Holdback release milestone has gate_conditions."""
    ms = await _get_seeded_milestone(client, "holdback_release")
    r = await client.get(f"/api/completion-milestones/{ms['id']}/evidence-checklist")
    body = r.json()
    assert body["gate_conditions"] is not None
    assert len(body["gate_conditions"]) >= 3
    assert body["trigger_condition"] is not None


async def test_evidence_checklist_null_requirements(client: AsyncClient):
    """Milestone with null evidence_requirements returns safe empty structure."""
    # Create a milestone with no evidence_requirements
    proj = await client.post("/api/projects/", json={"name": f"EvidNull-{_uid()}", "status": "active"})
    pid = proj.json()["id"]
    ms = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "tco", "milestone_name": "TCO",
    })
    ms_id = ms.json()["id"]

    r = await client.get(f"/api/completion-milestones/{ms_id}/evidence-checklist")
    assert r.status_code == 200
    body = r.json()
    assert body["checklist"] == []
    assert body["payout_percent"] is None
    assert body["gate_conditions"] is None


async def test_evidence_checklist_not_found(client: AsyncClient):
    r = await client.get(f"/api/completion-milestones/{BOGUS_UUID}/evidence-checklist")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Evaluate evidence
# ═══════════════════════════════════════════════════════════════════════════

async def test_evaluate_evidence_complete(client: AsyncClient):
    """Setting all_items_complete=true marks is_evidence_complete=true."""
    ms = await _get_seeded_milestone(client, "topped_out")
    assert ms["is_evidence_complete"] is False

    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={
        "all_items_complete": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["is_evidence_complete"] is True

    # Verify persisted
    r2 = await client.get(f"/api/completion-milestones/{ms['id']}")
    assert r2.json()["is_evidence_complete"] is True


async def test_evaluate_evidence_incomplete(client: AsyncClient):
    """Setting all_items_complete=false marks is_evidence_complete=false."""
    ms = await _get_seeded_milestone(client, "topped_out")

    # First set it to true
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={
        "all_items_complete": True,
    })

    # Then set it back to false
    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={
        "all_items_complete": False,
    })
    assert r.status_code == 200
    assert r.json()["is_evidence_complete"] is False


async def test_evaluate_evidence_with_notes(client: AsyncClient):
    """Notes are saved alongside the evidence evaluation."""
    ms = await _get_seeded_milestone(client, "sheetrock_prime")
    r = await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={
        "all_items_complete": True,
        "notes": "All evidence verified by Andrew Roberts on site walk.",
    })
    assert r.status_code == 200
    assert r.json()["notes"] == "All evidence verified by Andrew Roberts on site walk."

    # Verify note persisted
    r2 = await client.get(f"/api/completion-milestones/{ms['id']}")
    assert "Andrew Roberts" in r2.json()["notes"]


async def test_evaluate_evidence_not_found(client: AsyncClient):
    r = await client.post(f"/api/completion-milestones/{BOGUS_UUID}/evaluate-evidence", json={
        "all_items_complete": True,
    })
    assert r.status_code == 404


async def test_patch_preserves_evidence_flag(client: AsyncClient):
    """PATCH does not reset is_evidence_complete unless explicitly set."""
    ms = await _get_seeded_milestone(client, "first_turnover_tco")

    # Set evidence complete via workflow
    await client.post(f"/api/completion-milestones/{ms['id']}/evaluate-evidence", json={
        "all_items_complete": True,
    })

    # PATCH something else (status)
    r = await client.patch(f"/api/completion-milestones/{ms['id']}", json={
        "status": "achieved",
    })
    assert r.status_code == 200
    assert r.json()["is_evidence_complete"] is True  # preserved
    assert r.json()["status"] == "achieved"

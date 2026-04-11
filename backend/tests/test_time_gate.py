"""Time-based milestone gate evaluation tests.

Tests the time_elapsed gate for holdback_release milestones with trigger conditions
like 45_days_post_final_co and 45_days_post_opening.
"""

import uuid
from datetime import date, timedelta
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"TimeGate-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _holdback_with_trigger(
    c: AsyncClient,
    project_id: str,
    trigger: str,
    *,
    own_actual: date | None = None,
) -> str:
    """Create a holdback_release milestone with a specific trigger_condition in JSONB."""
    payload = {
        "project_id": project_id,
        "milestone_type": "holdback_release",
        "milestone_name": "Holdback Release",
        "evidence_requirements": {
            "checklist": [],
            "trigger_condition": trigger,
            "payout_percent": 10,
            "holdback_percent": 0,
        },
    }
    if own_actual:
        payload["actual_date"] = own_actual.isoformat()
    r = await c.post("/api/completion-milestones/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _final_co(c: AsyncClient, project_id: str, actual_date: date) -> str:
    r = await c.post("/api/completion-milestones/", json={
        "project_id": project_id,
        "milestone_type": "final_co",
        "milestone_name": "Final CO",
        "actual_date": actual_date.isoformat(),
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _get_time_gate(body: dict) -> dict | None:
    return next((g for g in body["gate_results"] if g["code"] == "time_elapsed"), None)


# ═══════════════════════════════════════════════════════════════════════════
# 45_days_post_final_co
# ═══════════════════════════════════════════════════════════════════════════

async def test_final_co_older_than_45_days_pass(client: AsyncClient):
    pid = await _project(client)
    # Final CO 60 days ago
    await _final_co(client, pid, date.today() - timedelta(days=60))
    ms_id = await _holdback_with_trigger(client, pid, "45_days_post_final_co")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate is not None
    assert gate["status"] == "pass"
    assert "60 days elapsed" in gate["detail"]
    assert "Final CO actual date" in gate["detail"]


async def test_final_co_exactly_45_days_pass(client: AsyncClient):
    """Boundary: exactly 45 days elapsed -> pass."""
    pid = await _project(client)
    await _final_co(client, pid, date.today() - timedelta(days=45))
    ms_id = await _holdback_with_trigger(client, pid, "45_days_post_final_co")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate["status"] == "pass"


async def test_final_co_less_than_45_days_fail(client: AsyncClient):
    pid = await _project(client)
    await _final_co(client, pid, date.today() - timedelta(days=10))
    ms_id = await _holdback_with_trigger(client, pid, "45_days_post_final_co")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate["status"] == "fail"
    assert "10 days elapsed" in gate["detail"]


async def test_final_co_missing_actual_date_warning(client: AsyncClient):
    """No final_co milestone on project -> warning with explicit detail."""
    pid = await _project(client)
    ms_id = await _holdback_with_trigger(client, pid, "45_days_post_final_co")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate["status"] == "warning"
    assert "Base date missing" in gate["detail"]


async def test_final_co_exists_but_no_actual_date_warning(client: AsyncClient):
    """Final CO milestone exists but has no actual_date -> warning."""
    pid = await _project(client)
    # Create final_co without actual_date
    await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "final_co", "milestone_name": "Final CO",
    })
    ms_id = await _holdback_with_trigger(client, pid, "45_days_post_final_co")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate["status"] == "warning"


# ═══════════════════════════════════════════════════════════════════════════
# 45_days_post_opening
# ═══════════════════════════════════════════════════════════════════════════

async def test_opening_older_than_45_days_pass(client: AsyncClient):
    pid = await _project(client)
    ms_id = await _holdback_with_trigger(
        client, pid, "45_days_post_opening",
        own_actual=date.today() - timedelta(days=50),
    )

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate["status"] == "pass"
    assert "50 days elapsed" in gate["detail"]


async def test_opening_less_than_45_days_fail(client: AsyncClient):
    pid = await _project(client)
    ms_id = await _holdback_with_trigger(
        client, pid, "45_days_post_opening",
        own_actual=date.today() - timedelta(days=20),
    )

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate["status"] == "fail"
    assert "20 days elapsed" in gate["detail"]


async def test_opening_no_own_actual_warning(client: AsyncClient):
    pid = await _project(client)
    ms_id = await _holdback_with_trigger(client, pid, "45_days_post_opening")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    gate = _get_time_gate(r.json())
    assert gate["status"] == "warning"
    assert "Base date missing" in gate["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# No trigger -> no time gate
# ═══════════════════════════════════════════════════════════════════════════

async def test_no_trigger_no_time_gate(client: AsyncClient):
    """Holdback without trigger_condition in JSONB -> no time_elapsed gate."""
    pid = await _project(client)
    r = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "holdback_release",
        "milestone_name": "Holdback", "evidence_requirements": {"checklist": []},
    })
    ms_id = r.json()["id"]

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    codes = {g["code"] for g in r.json()["gate_results"]}
    assert "time_elapsed" not in codes


async def test_unknown_trigger_no_gate(client: AsyncClient):
    """Unknown trigger string -> no time gate (don't fabricate)."""
    pid = await _project(client)
    ms_id = await _holdback_with_trigger(client, pid, "bogus_trigger_xyz")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    codes = {g["code"] for g in r.json()["gate_results"]}
    assert "time_elapsed" not in codes


# ═══════════════════════════════════════════════════════════════════════════
# Readiness summary integration
# ═══════════════════════════════════════════════════════════════════════════

async def test_readiness_reflects_time_gate_fail(client: AsyncClient):
    """Project readiness summary reflects a failing time gate via holdback."""
    pid = await _project(client)
    await _final_co(client, pid, date.today() - timedelta(days=5))
    ms_id = await _holdback_with_trigger(client, pid, "45_days_post_final_co")

    # Make everything else clean so only the time gate fails
    await client.post(f"/api/completion-milestones/{ms_id}/certify", json={"certified_by": PERSON_ROBERTS})
    await client.post(f"/api/completion-milestones/{ms_id}/evaluate-evidence", json={"all_items_complete": True})
    await client.post("/api/closeout-checklists/", json={
        "project_id": pid, "total_items": 10, "completed_items": 10, "percent_complete": 100,
    })
    await client.post("/api/warranties/", json={
        "project_id": pid, "company_id": COMPANY_REX,
        "scope_description": "Clean", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01",
    })
    await client.post("/api/punch-items/", json={
        "project_id": pid, "punch_number": 1, "title": "Closed", "status": "closed",
    })

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert body["holdback_release"]["gate_status"] == "fail"
    assert body["overall_status"] == "fail"

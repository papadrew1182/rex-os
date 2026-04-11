"""Punch aging gate evaluation tests.

Tests the punch_aging gate added to evaluate_milestone_gates() for holdback_release milestones.
"""

import uuid
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Punch-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _holdback_milestone(c: AsyncClient, project_id: str) -> str:
    r = await c.post("/api/completion-milestones/", json={
        "project_id": project_id, "milestone_type": "holdback_release",
        "milestone_name": "Holdback Release",
    })
    return r.json()["id"]


async def _punch(c: AsyncClient, project_id: str, *, status: str = "open", days_open: int | None = None) -> dict:
    """Create a punch item. days_open must be set after create (schema default behavior)."""
    r = await c.post("/api/punch-items/", json={
        "project_id": project_id, "punch_number": int(_uid()[:4], 16),
        "title": f"Punch-{_uid()}", "status": status,
    })
    assert r.status_code == 201
    pid = r.json()["id"]
    if days_open is not None:
        r2 = await c.patch(f"/api/punch-items/{pid}", json={"days_open": days_open})
        assert r2.status_code == 200
    return r.json() if days_open is None else r2.json()


# ═══════════════════════════════════════════════════════════════════════════
# Punch aging gate
# ═══════════════════════════════════════════════════════════════════════════

async def test_no_punch_items_warning(client: AsyncClient):
    """Holdback with no punch items -> punch_aging gate is warning."""
    pid = await _project(client)
    ms_id = await _holdback_milestone(client, pid)

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    gate = next(g for g in body["gate_results"] if g["code"] == "punch_aging")
    assert gate["status"] == "warning"
    assert "No punch items" in gate["detail"]


async def test_all_punch_closed_pass(client: AsyncClient):
    """All punch items closed -> punch_aging pass."""
    pid = await _project(client)
    ms_id = await _holdback_milestone(client, pid)

    await _punch(client, pid, status="closed")
    await _punch(client, pid, status="closed")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    gate = next(g for g in body["gate_results"] if g["code"] == "punch_aging")
    assert gate["status"] == "pass"
    assert "2 punch item(s) closed" in gate["detail"]


async def test_moderate_open_punch_warning(client: AsyncClient):
    """A few open punch items with low aging -> warning."""
    pid = await _project(client)
    ms_id = await _holdback_milestone(client, pid)

    # 3 open items, all recent (days_open=5)
    await _punch(client, pid, status="open", days_open=5)
    await _punch(client, pid, status="open", days_open=8)
    await _punch(client, pid, status="open", days_open=3)

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    gate = next(g for g in body["gate_results"] if g["code"] == "punch_aging")
    assert gate["status"] == "warning"
    assert "3 open item(s)" in gate["detail"]
    assert "avg age" in gate["detail"]


async def test_severe_aging_fail_too_many_items(client: AsyncClient):
    """More than 10 open punch items -> fail."""
    pid = await _project(client)
    ms_id = await _holdback_milestone(client, pid)

    for _ in range(11):
        await _punch(client, pid, status="open", days_open=5)

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    gate = next(g for g in body["gate_results"] if g["code"] == "punch_aging")
    assert gate["status"] == "fail"
    assert "11 open item(s)" in gate["detail"]


async def _backdate_punch(punch_id: str, days_ago: int):
    """Backdate a punch_item's created_at via raw SQL.

    Required because the gate evaluator computes days_open from created_at at read time.
    """
    import db as legacy_db
    pool = await legacy_db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE rex.punch_items SET created_at = NOW() - ($1 || ' days')::interval WHERE id = $2::uuid",
            str(days_ago), punch_id,
        )


async def test_severe_aging_fail_avg_too_high(client: AsyncClient):
    """Average age > 21 days -> fail."""
    pid = await _project(client)
    ms_id = await _holdback_milestone(client, pid)

    p1 = await _punch(client, pid, status="open")
    p2 = await _punch(client, pid, status="open")
    p3 = await _punch(client, pid, status="open")
    await _backdate_punch(p1["id"], 25)
    await _backdate_punch(p2["id"], 30)
    await _backdate_punch(p3["id"], 40)

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    gate = next(g for g in body["gate_results"] if g["code"] == "punch_aging")
    assert gate["status"] == "fail"


async def test_severe_aging_fail_aged_over_10_percent(client: AsyncClient):
    """More than 10% of open items aged >30 days -> fail."""
    pid = await _project(client)
    ms_id = await _holdback_milestone(client, pid)

    # 4 items, 1 aged >30 (25% of items)
    p1 = await _punch(client, pid, status="open")
    p2 = await _punch(client, pid, status="open")
    p3 = await _punch(client, pid, status="open")
    p4 = await _punch(client, pid, status="open")
    await _backdate_punch(p1["id"], 5)
    await _backdate_punch(p2["id"], 8)
    await _backdate_punch(p3["id"], 10)
    await _backdate_punch(p4["id"], 45)

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    gate = next(g for g in body["gate_results"] if g["code"] == "punch_aging")
    assert gate["status"] == "fail"
    assert "1 item(s) > 30 days" in gate["detail"]


async def test_non_holdback_milestone_no_punch_gate(client: AsyncClient):
    """Non-holdback milestones don't get the punch_aging gate."""
    pid = await _project(client)
    r = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "tco", "milestone_name": "TCO",
    })
    ms_id = r.json()["id"]

    # Add a bunch of open punch items that would fail a holdback
    for _ in range(15):
        await _punch(client, pid, status="open", days_open=40)

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    codes = {g["code"] for g in body["gate_results"]}
    assert "punch_aging" not in codes


# ═══════════════════════════════════════════════════════════════════════════
# Readiness summary integration
# ═══════════════════════════════════════════════════════════════════════════

async def test_readiness_summary_reflects_punch_fail(client: AsyncClient):
    """Project closeout readiness reflects failed punch aging via holdback gates."""
    pid = await _project(client)
    ms_id = await _holdback_milestone(client, pid)

    # Set up a "clean" scenario otherwise
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
    # But punch aging is bad
    for _ in range(12):
        await _punch(client, pid, status="open", days_open=15)

    r = await client.get(f"/api/projects/{pid}/closeout-readiness")
    body = r.json()
    assert body["holdback_release"]["exists"] is True
    assert body["holdback_release"]["gate_status"] == "fail"
    assert body["overall_status"] == "fail"

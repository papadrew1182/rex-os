"""Punch aging helper tests — read-time computation and refresh endpoints."""

import uuid
from datetime import date, timedelta
from httpx import AsyncClient

BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"PunchAge-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _punch(c: AsyncClient, project_id: str, **kw) -> dict:
    p = {
        "project_id": project_id, "punch_number": int(_uid()[:4], 16),
        "title": f"Punch-{_uid()}", "status": "open",
    }
    p.update(kw)
    r = await c.post("/api/punch-items/", json=p)
    assert r.status_code == 201
    return r.json()


# ── Single refresh ──────────────────────────────────────────────────────────

async def test_refresh_open_punch_sets_days_open(client: AsyncClient):
    """Open punch with no days_open gets computed value (0 since just created)."""
    pid = await _project(client)
    p = await _punch(client, pid, status="open")
    assert p["days_open"] is None  # not set on create

    r = await client.post(f"/api/punch-items/{p['id']}/refresh-aging")
    assert r.status_code == 200
    assert r.json()["days_open"] == 0


async def test_refresh_closed_punch_uses_closed_date(client: AsyncClient):
    """Closed punch with closed_date computes days_open from created_at to closed_date."""
    pid = await _project(client)
    p = await _punch(client, pid, status="open")
    # Patch to closed with closed_date today
    await client.patch(f"/api/punch-items/{p['id']}", json={
        "status": "closed", "closed_date": date.today().isoformat(),
    })

    r = await client.post(f"/api/punch-items/{p['id']}/refresh-aging")
    assert r.status_code == 200
    assert r.json()["days_open"] == 0  # created today, closed today


async def test_refresh_bad_id_404(client: AsyncClient):
    r = await client.post(f"/api/punch-items/{BOGUS_UUID}/refresh-aging")
    assert r.status_code == 404


# ── Bulk refresh ────────────────────────────────────────────────────────────

async def test_bulk_refresh_aging(client: AsyncClient):
    pid = await _project(client)
    await _punch(client, pid, status="open")
    await _punch(client, pid, status="open")
    await _punch(client, pid, status="closed", closed_date=date.today().isoformat())

    r = await client.post(f"/api/punch-items/refresh-aging?project_id={pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["total_punch_items"] == 3
    assert body["updated_count"] == 3  # all start with None days_open


# ── Gate evaluator now uses computed days_open ──────────────────────────────

async def test_gate_evaluator_uses_computed_days_open(client: AsyncClient):
    """Gate evaluator should use compute_punch_days_open at read time, not stored value."""
    pid = await _project(client)
    # Create holdback milestone
    ms = await client.post("/api/completion-milestones/", json={
        "project_id": pid, "milestone_type": "holdback_release",
        "milestone_name": "Holdback",
    })
    ms_id = ms.json()["id"]

    # Create open punch with no days_open set
    await _punch(client, pid, status="open")
    await _punch(client, pid, status="open")

    r = await client.post(f"/api/completion-milestones/{ms_id}/evaluate-gates")
    body = r.json()
    gate = next(g for g in body["gate_results"] if g["code"] == "punch_aging")
    # Should be warning (2 fresh open items), not pass — proves it's seeing the items
    assert gate["status"] == "warning"
    assert "2 open item(s)" in gate["detail"]
    # avg age should be 0 (just created), not None
    assert "avg age 0" in gate["detail"] or "avg age 0.0" in gate["detail"]

"""Submittal aging helper tests."""

import uuid
from datetime import date, datetime, timedelta, timezone
from httpx import AsyncClient

BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"SubAging-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _submittal(c: AsyncClient, project_id: str, **kw) -> dict:
    p = {
        "project_id": project_id, "submittal_number": f"SUB-{_uid()}",
        "title": "Test Sub", "submittal_type": "shop_drawing",
    }
    p.update(kw)
    r = await c.post("/api/submittals/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


async def test_open_submittal_aging(client: AsyncClient):
    pid = await _project(client)
    s = await _submittal(client, pid, status="pending")

    r = await client.get(f"/api/submittals/{s['id']}/aging")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["is_open"] is True
    assert body["days_open"] == 0


async def test_overdue_submittal_flagged(client: AsyncClient):
    pid = await _project(client)
    past = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
    s = await _submittal(client, pid, status="submitted", due_date=past)

    r = await client.get(f"/api/submittals/{s['id']}/aging")
    body = r.json()
    assert body["is_overdue"] is True
    assert body["days_overdue"] == 7


async def test_required_on_site_countdown(client: AsyncClient):
    pid = await _project(client)
    future = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
    s = await _submittal(client, pid, status="submitted", required_on_site=future)

    r = await client.get(f"/api/submittals/{s['id']}/aging")
    body = r.json()
    assert body["days_to_required_onsite"] == 30


async def test_submittal_aging_404(client: AsyncClient):
    r = await client.get(f"/api/submittals/{BOGUS_UUID}/aging")
    assert r.status_code == 404


async def test_project_submittal_aging_summary(client: AsyncClient):
    pid = await _project(client)
    await _submittal(client, pid, status="pending")
    overdue = (datetime.now(timezone.utc).date() - timedelta(days=14)).isoformat()
    await _submittal(client, pid, status="submitted", due_date=overdue)
    approved = await _submittal(client, pid, status="submitted")
    await client.patch(f"/api/submittals/{approved['id']}", json={
        "status": "approved", "approved_date": datetime.now(timezone.utc).date().isoformat(),
    })

    r = await client.get(f"/api/projects/{pid}/submittal-aging")
    assert r.status_code == 200
    body = r.json()
    assert body["total_submittals"] == 3
    assert body["open_count"] == 2
    assert body["overdue_count"] == 1
    assert len(body["items"]) == 3

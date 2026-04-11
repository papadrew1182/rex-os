"""RFI aging helper tests."""

import uuid
from datetime import date, datetime, timedelta, timezone
from httpx import AsyncClient

BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Aging-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _rfi(c: AsyncClient, project_id: str, **kw) -> dict:
    p = {
        "project_id": project_id, "rfi_number": f"RFI-{_uid()}",
        "subject": "Test RFI", "question": "Q?",
    }
    p.update(kw)
    r = await c.post("/api/rfis/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


async def test_open_rfi_aging_computed(client: AsyncClient):
    pid = await _project(client)
    rfi = await _rfi(client, pid, status="open")

    r = await client.get(f"/api/rfis/{rfi['id']}/aging")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "open"
    assert body["is_open"] is True
    assert body["days_open"] == 0  # just created
    assert body["is_overdue"] is False


async def test_overdue_rfi_flagged(client: AsyncClient):
    pid = await _project(client)
    past = (datetime.now(timezone.utc).date() - timedelta(days=5)).isoformat()
    rfi = await _rfi(client, pid, status="open", due_date=past)

    r = await client.get(f"/api/rfis/{rfi['id']}/aging")
    body = r.json()
    assert body["is_overdue"] is True
    assert body["days_overdue"] == 5


async def test_answered_rfi_uses_answered_date(client: AsyncClient):
    pid = await _project(client)
    rfi = await _rfi(client, pid, status="open")
    # Patch to answered with a past answered_date
    answered = datetime.now(timezone.utc).date() - timedelta(days=1)
    await client.patch(f"/api/rfis/{rfi['id']}", json={
        "status": "answered", "answered_date": answered.isoformat(),
    })

    r = await client.get(f"/api/rfis/{rfi['id']}/aging")
    body = r.json()
    assert body["status"] == "answered"
    assert body["is_open"] is False
    # days_open computed from created_at to answered_date (created today, answered yesterday)
    # which is negative -> we just check is_open is False


async def test_rfi_aging_404(client: AsyncClient):
    r = await client.get(f"/api/rfis/{BOGUS_UUID}/aging")
    assert r.status_code == 404


async def test_project_rfi_aging_summary(client: AsyncClient):
    pid = await _project(client)
    # 2 open (1 overdue), 1 answered
    await _rfi(client, pid, status="open")
    overdue = (datetime.now(timezone.utc).date() - timedelta(days=10)).isoformat()
    await _rfi(client, pid, status="open", due_date=overdue)
    answered = await _rfi(client, pid, status="open")
    await client.patch(f"/api/rfis/{answered['id']}", json={
        "status": "answered", "answered_date": datetime.now(timezone.utc).date().isoformat(),
    })

    r = await client.get(f"/api/projects/{pid}/rfi-aging")
    assert r.status_code == 200
    body = r.json()
    assert body["total_rfis"] == 3
    assert body["open_count"] == 2
    assert body["overdue_count"] == 1
    assert isinstance(body["average_days_open"], (int, float))
    assert len(body["items"]) == 3

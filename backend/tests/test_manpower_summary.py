"""Daily log + manpower aggregation tests."""

import uuid
from datetime import date, timedelta
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"MP-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _company(c: AsyncClient) -> str:
    r = await c.post("/api/companies/", json={
        "name": f"Sub-{_uid()}", "company_type": "subcontractor",
    })
    return r.json()["id"]


async def _daily_log(c: AsyncClient, project_id: str, log_date: date) -> dict:
    r = await c.post("/api/daily-logs/", json={
        "project_id": project_id, "log_date": log_date.isoformat(),
        "weather_summary": "sunny",
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _manpower(c: AsyncClient, daily_log_id: str, company_id: str, workers: int, hours: float):
    r = await c.post("/api/manpower-entries/", json={
        "daily_log_id": daily_log_id, "company_id": company_id,
        "worker_count": workers, "hours": hours,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _unique_date(offset: int = 0) -> date:
    """Generate a unique far-future date to avoid daily_logs unique constraint collisions."""
    h = int(_uid(), 16)
    return date(5000 + (h % 1000), ((h >> 12) % 12) + 1, ((h >> 8) % 28) + 1) + timedelta(days=offset)


# ── Daily log summary ───────────────────────────────────────────────────────

async def test_daily_log_summary_with_manpower(client: AsyncClient):
    pid = await _project(client)
    cid_a = await _company(client)
    cid_b = await _company(client)
    log = await _daily_log(client, pid, _unique_date())
    await _manpower(client, log["id"], cid_a, workers=5, hours=40)
    await _manpower(client, log["id"], cid_b, workers=3, hours=24)

    r = await client.get(f"/api/daily-logs/{log['id']}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["manpower_entry_count"] == 2
    assert body["total_worker_count"] == 8
    assert body["total_hours"] == 64
    assert body["company_count"] == 2
    assert body["weather_summary"] == "sunny"


async def test_daily_log_summary_no_manpower(client: AsyncClient):
    pid = await _project(client)
    log = await _daily_log(client, pid, _unique_date())
    r = await client.get(f"/api/daily-logs/{log['id']}/summary")
    body = r.json()
    assert body["manpower_entry_count"] == 0
    assert body["total_worker_count"] == 0
    assert body["total_hours"] == 0


async def test_daily_log_summary_404(client: AsyncClient):
    r = await client.get(f"/api/daily-logs/{BOGUS_UUID}/summary")
    assert r.status_code == 404


# ── Project manpower summary ────────────────────────────────────────────────

async def test_project_manpower_summary_basic(client: AsyncClient):
    pid = await _project(client)
    cid = await _company(client)

    log1 = await _daily_log(client, pid, _unique_date())
    log2 = await _daily_log(client, pid, _unique_date())
    await _manpower(client, log1["id"], cid, workers=5, hours=40)
    await _manpower(client, log2["id"], cid, workers=7, hours=56)

    r = await client.get(f"/api/projects/{pid}/manpower-summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_logs"] == 2
    assert body["logs_with_manpower"] == 2
    assert body["total_worker_count"] == 12
    assert body["total_hours"] == 96
    assert body["average_workers_per_log"] == 6.0
    assert len(body["by_company"]) == 1
    assert body["by_company"][0]["worker_count"] == 12


async def test_project_manpower_summary_date_filter(client: AsyncClient):
    pid = await _project(client)
    cid = await _company(client)

    early = date(5500, 1, 1)
    mid = date(5500, 6, 1)
    late = date(5500, 12, 1)

    log_e = await _daily_log(client, pid, early)
    log_m = await _daily_log(client, pid, mid)
    log_l = await _daily_log(client, pid, late)
    await _manpower(client, log_e["id"], cid, workers=2, hours=16)
    await _manpower(client, log_m["id"], cid, workers=4, hours=32)
    await _manpower(client, log_l["id"], cid, workers=8, hours=64)

    # Filter to mid only
    r = await client.get(
        f"/api/projects/{pid}/manpower-summary"
        f"?date_from=5500-04-01&date_to=5500-08-31"
    )
    body = r.json()
    assert body["total_logs"] == 1
    assert body["total_worker_count"] == 4


async def test_project_manpower_summary_empty(client: AsyncClient):
    pid = await _project(client)
    r = await client.get(f"/api/projects/{pid}/manpower-summary")
    body = r.json()
    assert body["total_logs"] == 0
    assert body["total_worker_count"] == 0
    assert body["by_company"] == []

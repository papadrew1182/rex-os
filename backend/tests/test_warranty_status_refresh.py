"""Warranty auto-status transitions tests."""

import uuid
from datetime import date, timedelta
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"WStatus-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _warranty(c: AsyncClient, project_id: str, **kw) -> dict:
    p = {
        "project_id": project_id, "company_id": COMPANY_REX,
        "scope_description": f"Scope-{_uid()}", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01",
    }
    p.update(kw)
    r = await c.post("/api/warranties/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


# ── Single warranty refresh ─────────────────────────────────────────────────

async def test_refresh_active_far_from_expiration(client: AsyncClient):
    pid = await _project(client)
    # Expiration 1 year in the future
    far = (date.today() + timedelta(days=365)).isoformat()
    w = await _warranty(client, pid, start_date=date.today().isoformat(),
                        expiration_date=far)

    r = await client.post(f"/api/warranties/{w['id']}/refresh-status")
    assert r.status_code == 200
    assert r.json()["status"] == "active"


async def test_refresh_to_expiring_soon(client: AsyncClient):
    pid = await _project(client)
    # Expiration in 60 days -> within 90-day window
    soon = (date.today() + timedelta(days=60)).isoformat()
    w = await _warranty(client, pid, start_date=(date.today() - timedelta(days=305)).isoformat(),
                        expiration_date=soon)

    r = await client.post(f"/api/warranties/{w['id']}/refresh-status")
    assert r.status_code == 200
    assert r.json()["status"] == "expiring_soon"


async def test_refresh_to_expired(client: AsyncClient):
    pid = await _project(client)
    # Expiration in the past
    past = (date.today() - timedelta(days=10)).isoformat()
    w = await _warranty(client, pid, start_date=(date.today() - timedelta(days=400)).isoformat(),
                        expiration_date=past)

    r = await client.post(f"/api/warranties/{w['id']}/refresh-status")
    assert r.status_code == 200
    assert r.json()["status"] == "expired"


async def test_claimed_status_preserved(client: AsyncClient):
    """Claimed warranties are never auto-overridden by refresh."""
    pid = await _project(client)
    past = (date.today() - timedelta(days=10)).isoformat()
    w = await _warranty(client, pid, start_date=(date.today() - timedelta(days=400)).isoformat(),
                        expiration_date=past, status="claimed")

    r = await client.post(f"/api/warranties/{w['id']}/refresh-status")
    assert r.status_code == 200
    assert r.json()["status"] == "claimed"


async def test_refresh_bad_id_404(client: AsyncClient):
    r = await client.post(f"/api/warranties/{BOGUS_UUID}/refresh-status")
    assert r.status_code == 404


# ── Bulk refresh ────────────────────────────────────────────────────────────

async def test_bulk_refresh_counts(client: AsyncClient):
    pid = await _project(client)
    # 1 active, 1 expiring, 1 expired, 1 claimed
    await _warranty(client, pid, start_date=date.today().isoformat(),
                    expiration_date=(date.today() + timedelta(days=365)).isoformat())
    await _warranty(client, pid, start_date=(date.today() - timedelta(days=305)).isoformat(),
                    expiration_date=(date.today() + timedelta(days=60)).isoformat())
    await _warranty(client, pid, start_date=(date.today() - timedelta(days=400)).isoformat(),
                    expiration_date=(date.today() - timedelta(days=10)).isoformat())
    await _warranty(client, pid, start_date=(date.today() - timedelta(days=400)).isoformat(),
                    expiration_date=(date.today() - timedelta(days=10)).isoformat(),
                    status="claimed")

    r = await client.post(f"/api/warranties/refresh-statuses?project_id={pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["total_warranties"] == 4
    assert body["by_status"]["active"] == 1
    assert body["by_status"]["expiring_soon"] == 1
    assert body["by_status"]["expired"] == 1
    assert body["by_status"]["claimed"] == 1

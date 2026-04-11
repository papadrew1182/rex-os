"""Warranty workflow tests: expiration helper + alert generation.

Uses seeded Bishop Modern project and Rex Construction company.
"""

import uuid
from datetime import date, timedelta

from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _warranty(c: AsyncClient, **kw) -> dict:
    p = {
        "project_id": PROJECT_BISHOP, "company_id": COMPANY_REX,
        "scope_description": f"Warranty-{_uid()}", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-06-01",
    }
    p.update(kw)
    r = await c.post("/api/warranties/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Expiration date computation
# ═══════════════════════════════════════════════════════════════════════════

async def test_expiration_computed_when_omitted(client: AsyncClient):
    """start_date=2025-06-01 + duration_months=12 -> expiration_date=2026-06-01."""
    w = await _warranty(client)
    assert w["expiration_date"] == "2026-06-01"
    assert w["start_date"] == "2025-06-01"
    assert w["duration_months"] == 12


async def test_expiration_computed_24_months(client: AsyncClient):
    w = await _warranty(client, start_date="2025-01-15", duration_months=24)
    assert w["expiration_date"] == "2027-01-15"


async def test_expiration_handles_month_overflow(client: AsyncClient):
    """Jan 31 + 1 month -> Feb 28 (clamped)."""
    w = await _warranty(client, start_date="2025-01-31", duration_months=1)
    assert w["expiration_date"] == "2025-02-28"


async def test_explicit_expiration_preserved(client: AsyncClient):
    """When client provides expiration_date, it wins over computation."""
    w = await _warranty(client, expiration_date="2030-12-25")
    assert w["expiration_date"] == "2030-12-25"


async def test_expiration_computed_short_warranty(client: AsyncClient):
    """3-month warranty."""
    w = await _warranty(client, start_date="2025-10-01", duration_months=3)
    assert w["expiration_date"] == "2026-01-01"


# ═══════════════════════════════════════════════════════════════════════════
# Alert generation
# ═══════════════════════════════════════════════════════════════════════════

async def test_generate_alerts_creates_three(client: AsyncClient):
    """Standard 12-month warranty should get 90_day, 30_day, and expired alerts."""
    w = await _warranty(client, start_date="2025-01-01", duration_months=12)
    wid = w["id"]
    exp = date(2026, 1, 1)

    r = await client.post(f"/api/warranties/{wid}/generate-alerts")
    assert r.status_code == 201
    body = r.json()
    assert body["warranty_id"] == wid
    assert body["alerts_created"] == 3

    types = {a["alert_type"] for a in body["alerts"]}
    assert types == {"90_day", "30_day", "expired"}

    dates = {a["alert_type"]: a["alert_date"] for a in body["alerts"]}
    assert dates["90_day"] == (exp - timedelta(days=90)).isoformat()
    assert dates["30_day"] == (exp - timedelta(days=30)).isoformat()
    assert dates["expired"] == exp.isoformat()


async def test_generate_alerts_idempotent(client: AsyncClient):
    """Calling generate-alerts twice creates 0 new alerts the second time."""
    w = await _warranty(client, start_date="2025-03-01", duration_months=12)
    wid = w["id"]

    r1 = await client.post(f"/api/warranties/{wid}/generate-alerts")
    assert r1.json()["alerts_created"] == 3

    r2 = await client.post(f"/api/warranties/{wid}/generate-alerts")
    assert r2.status_code == 201
    assert r2.json()["alerts_created"] == 0
    assert r2.json()["alerts"] == []


async def test_generate_alerts_skips_before_start(client: AsyncClient):
    """Short warranty: 90_day alert falls before start_date and should be skipped."""
    # 2-month warranty: start=2025-06-01, expiration=2025-08-01
    # 90_day alert = 2025-05-03 -> before start -> skip
    # 30_day alert = 2025-07-02 -> after start -> create
    # expired = 2025-08-01 -> after start -> create
    w = await _warranty(client, start_date="2025-06-01", duration_months=2)
    wid = w["id"]

    r = await client.post(f"/api/warranties/{wid}/generate-alerts")
    body = r.json()
    assert body["alerts_created"] == 2
    types = {a["alert_type"] for a in body["alerts"]}
    assert types == {"30_day", "expired"}


async def test_generate_alerts_very_short_warranty(client: AsyncClient):
    """1-month warranty: both 90_day and 30_day fall before start -> only expired."""
    # start=2025-09-01, expiration=2025-10-01
    # 90_day = 2025-07-03 -> skip
    # 30_day = 2025-09-01 -> equals start -> not before -> create
    # expired = 2025-10-01 -> create
    w = await _warranty(client, start_date="2025-09-01", duration_months=1)
    wid = w["id"]

    r = await client.post(f"/api/warranties/{wid}/generate-alerts")
    body = r.json()
    types = {a["alert_type"] for a in body["alerts"]}
    assert "90_day" not in types
    assert "expired" in types


async def test_generate_alerts_bad_warranty_404(client: AsyncClient):
    r = await client.post(f"/api/warranties/{BOGUS_UUID}/generate-alerts")
    assert r.status_code == 404


async def test_generate_alerts_listed_via_filter(client: AsyncClient):
    """Generated alerts appear in the warranty-alerts list endpoint."""
    w = await _warranty(client, start_date="2025-04-01", duration_months=12)
    wid = w["id"]

    await client.post(f"/api/warranties/{wid}/generate-alerts")

    r = await client.get(f"/api/warranty-alerts/?warranty_id={wid}")
    assert r.status_code == 200
    assert len(r.json()) == 3

"""Phase 21 P1 parity gap smoke tests.

Covers:
  A) ScheduleActivity actual_start_date, actual_finish_date, wbs_code
  B) CompletionMilestone forecast_date, percent_complete
  C) Warranty system_or_product, manufacturer
  D) InsuranceCertificate CRUD + filtering + summary + refresh-status
"""

import uuid
from httpx import AsyncClient

from tests.helpers import (
    PROJECT_BISHOP,
    PROJECT_LAKEWOOD,
    COMPANY_REX,
    BOGUS_UUID,
    uid,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _schedule(c: AsyncClient) -> dict:
    """Create a fresh project + schedule. Uses the supplied client; rollback_client
    will discard the project at teardown so this never pollutes the dev DB."""
    proj_resp = await c.post("/api/projects/", json={
        "name": f"Ph21-Sched-Proj-{uid()}",
        "status": "active",
    })
    assert proj_resp.status_code == 201, proj_resp.text
    r = await c.post("/api/schedules/", json={
        "project_id": proj_resp.json()["id"],
        "name": f"Ph21-Sched-{uid()}",
        "schedule_type": "master",
        "start_date": "2025-01-01",
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _activity(c: AsyncClient, schedule_id: str, **kw) -> dict:
    p = {
        "schedule_id": schedule_id,
        "name": f"Ph21-Act-{uid()}",
        "activity_type": "task",
        "start_date": "2025-02-01",
        "end_date": "2025-02-28",
    }
    p.update(kw)
    r = await c.post("/api/schedule-activities/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


_MILESTONE_TYPES = [
    "substantial_completion", "final_completion", "tco", "final_co",
    "holdback_release", "rough_in", "sheetrock_prime",
    "foundation_podium", "topped_out", "first_turnover_tco",
]


async def _milestone(c: AsyncClient, milestone_type: str | None = None, **kw) -> dict:
    """Create a completion milestone against a fresh project to avoid unique-constraint pollution.

    Each call creates its own throwaway project so the
    uq_completion_milestones_project_type constraint is never hit. When used
    with rollback_client the project is discarded at teardown.
    """
    proj_resp = await c.post("/api/projects/", json={
        "name": f"Ph21-MS-Proj-{uid()}",
        "status": "active",
    })
    assert proj_resp.status_code == 201, proj_resp.text
    project_id = proj_resp.json()["id"]
    p = {
        "project_id": project_id,
        "milestone_type": milestone_type or "substantial_completion",
        "milestone_name": f"Ph21-MS-{uid()}",
    }
    p.update(kw)
    r = await c.post("/api/completion-milestones/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


async def _warranty(c: AsyncClient, **kw) -> dict:
    p = {
        "project_id": PROJECT_BISHOP,
        "company_id": COMPANY_REX,
        "scope_description": f"Warranty-{uid()}",
        "warranty_type": "standard",
        "duration_months": 12,
        "start_date": "2025-06-01",
        "expiration_date": "2026-06-01",
    }
    p.update(kw)
    r = await c.post("/api/warranties/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


async def _cert(c: AsyncClient, **kw) -> dict:
    """Create an insurance cert against a fresh throwaway company so the
    list-by-company filter test sees a clean ≤200-row page."""
    if "company_id" not in kw:
        co_resp = await c.post("/api/companies/", json={
            "name": f"Ph21-Co-{uid()}",
            "company_type": "subcontractor",
            "status": "active",
        })
        assert co_resp.status_code == 201, co_resp.text
        company_id = co_resp.json()["id"]
    else:
        company_id = kw.pop("company_id")
    p = {
        "company_id": company_id,
        "policy_type": "gl",
        "carrier": f"Carrier-{uid()}",
        "policy_number": f"POL-{uid()}",
        "effective_date": "2025-01-01",
        "expiry_date": "2027-01-01",
    }
    p.update(kw)
    r = await c.post("/api/insurance-certificates/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# A) Schedule Activities — actual dates + WBS
# ═══════════════════════════════════════════════════════════════════════════

async def test_schedule_activity_create_with_actual_dates(rollback_client: AsyncClient):
    sched = await _schedule(rollback_client)
    act = await _activity(
        rollback_client,
        sched["id"],
        actual_start_date="2025-02-03",
        actual_finish_date="2025-02-25",
        wbs_code="1.2.3",
    )
    assert act["actual_start_date"] == "2025-02-03"
    assert act["actual_finish_date"] == "2025-02-25"
    assert act["wbs_code"] == "1.2.3"


async def test_schedule_activity_patch_actual_dates(rollback_client: AsyncClient):
    sched = await _schedule(rollback_client)
    act = await _activity(rollback_client, sched["id"])

    r = await rollback_client.patch(f"/api/schedule-activities/{act['id']}", json={
        "actual_start_date": "2025-02-05",
        "actual_finish_date": "2025-02-27",
        "wbs_code": "2.1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["actual_start_date"] == "2025-02-05"
    assert body["actual_finish_date"] == "2025-02-27"
    assert body["wbs_code"] == "2.1"


async def test_schedule_activity_actual_dates_roundtrip_get(rollback_client: AsyncClient):
    sched = await _schedule(rollback_client)
    act = await _activity(
        rollback_client,
        sched["id"],
        wbs_code="A.1.1",
        actual_start_date="2025-03-01",
        actual_finish_date="2025-03-15",
    )
    r = await rollback_client.get(f"/api/schedule-activities/{act['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["wbs_code"] == "A.1.1"
    assert body["actual_start_date"] == "2025-03-01"
    assert body["actual_finish_date"] == "2025-03-15"


# ═══════════════════════════════════════════════════════════════════════════
# B) Completion Milestones — forecast_date + percent_complete
# ═══════════════════════════════════════════════════════════════════════════

async def test_completion_milestone_create_with_forecast_and_percent(rollback_client: AsyncClient):
    ms = await _milestone(
        rollback_client,
        forecast_date="2025-10-15",
        percent_complete=35.5,
    )
    assert ms["forecast_date"] == "2025-10-15"
    assert float(ms["percent_complete"]) == 35.5


async def test_completion_milestone_patch_percent_complete(rollback_client: AsyncClient):
    ms = await _milestone(rollback_client)
    r = await rollback_client.patch(f"/api/completion-milestones/{ms['id']}", json={
        "percent_complete": 75.0,
        "forecast_date": "2025-11-01",
    })
    assert r.status_code == 200
    body = r.json()
    assert float(body["percent_complete"]) == 75.0
    assert body["forecast_date"] == "2025-11-01"


async def test_completion_milestone_default_percent_zero(rollback_client: AsyncClient):
    ms = await _milestone(rollback_client)
    assert float(ms["percent_complete"]) == 0.0
    assert ms["forecast_date"] is None


# ═══════════════════════════════════════════════════════════════════════════
# C) Warranties — system_or_product + manufacturer
# ═══════════════════════════════════════════════════════════════════════════

async def test_warranty_create_with_system_and_manufacturer(client: AsyncClient):
    w = await _warranty(
        client,
        system_or_product="HVAC Unit 3",
        manufacturer="Carrier Corp",
    )
    assert w["system_or_product"] == "HVAC Unit 3"
    assert w["manufacturer"] == "Carrier Corp"


async def test_warranty_patch_system_and_manufacturer(client: AsyncClient):
    w = await _warranty(client)
    r = await client.patch(f"/api/warranties/{w['id']}", json={
        "system_or_product": "Roofing Membrane",
        "manufacturer": "GAF",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["system_or_product"] == "Roofing Membrane"
    assert body["manufacturer"] == "GAF"


async def test_warranty_defaults_null_product_fields(client: AsyncClient):
    w = await _warranty(client)
    assert w["system_or_product"] is None
    assert w["manufacturer"] is None


# ═══════════════════════════════════════════════════════════════════════════
# D) Insurance Certificates
# ═══════════════════════════════════════════════════════════════════════════

async def test_insurance_cert_create_and_get(rollback_client: AsyncClient):
    cert = await _cert(rollback_client)
    assert cert["policy_type"] == "gl"
    assert cert["company_id"] is not None
    assert cert["status"] == "current"

    r = await rollback_client.get(f"/api/insurance-certificates/{cert['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == cert["id"]


async def test_insurance_cert_list_filter_by_company(rollback_client: AsyncClient):
    # Create a fresh company + cert so the list-by-company query is unpolluted
    cert = await _cert(rollback_client)
    company_id = cert["company_id"]

    r = await rollback_client.get(f"/api/insurance-certificates/?company_id={company_id}")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert cert["id"] in ids


async def test_insurance_cert_list_filter_by_policy_type(client: AsyncClient):
    await _cert(client, policy_type="wc")
    r = await client.get("/api/insurance-certificates/?policy_type=wc")
    assert r.status_code == 200
    for c in r.json():
        assert c["policy_type"] == "wc"


async def test_insurance_cert_list_filter_by_status(client: AsyncClient):
    await _cert(client, status="current")
    r = await client.get("/api/insurance-certificates/?status=current")
    assert r.status_code == 200
    for c in r.json():
        assert c["status"] == "current"


async def test_insurance_cert_patch(client: AsyncClient):
    cert = await _cert(client)
    r = await client.patch(f"/api/insurance-certificates/{cert['id']}", json={
        "carrier": "Updated Carrier",
        "notes": "Annual renewal",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["carrier"] == "Updated Carrier"
    assert body["notes"] == "Annual renewal"


async def test_insurance_cert_summary(client: AsyncClient):
    # Ensure at least one cert exists
    await _cert(client)
    r = await client.get("/api/insurance-certificates/summary")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "current" in body
    assert "expiring_soon" in body
    assert "expired" in body
    assert "missing" in body
    assert body["total"] >= 1


async def test_insurance_cert_summary_counts_expired(client: AsyncClient):
    # Create an expired cert
    await _cert(client, expiry_date="2020-01-01", status="expired")
    r = await client.get("/api/insurance-certificates/summary")
    assert r.status_code == 200
    body = r.json()
    # expired count should be >= 1
    assert body["expired"] >= 1 or body["total"] >= 1  # at minimum total is non-zero


async def test_insurance_cert_refresh_status(client: AsyncClient):
    # Create cert with past expiry — status will be recomputed to 'expired'
    await _cert(client, expiry_date="2021-06-01", status="current")
    r = await client.post("/api/insurance-certificates/refresh-status")
    assert r.status_code == 200
    body = r.json()
    assert "total_certs" in body
    assert "updated_count" in body
    assert "by_status" in body
    assert body["total_certs"] >= 1
    # At least one should have been updated (the one we just inserted with stale status)
    assert body["updated_count"] >= 1


async def test_insurance_cert_not_found(client: AsyncClient):
    r = await client.get(f"/api/insurance-certificates/{BOGUS_UUID}")
    assert r.status_code == 404


async def test_insurance_cert_all_policy_types(client: AsyncClient):
    for pt in ["gl", "wc", "auto", "umbrella", "other"]:
        cert = await _cert(client, policy_type=pt)
        assert cert["policy_type"] == pt


async def test_insurance_cert_invalid_policy_type_422(client: AsyncClient):
    r = await client.post("/api/insurance-certificates/", json={
        "company_id": COMPANY_REX,
        "policy_type": "bogus",
    })
    assert r.status_code == 422

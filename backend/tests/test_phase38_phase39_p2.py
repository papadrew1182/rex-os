"""Phase 38 + 39 P2 parity batch smoke tests.

Covers:
  A) ScheduleActivity start_variance_days, finish_variance_days, free_float_days
  B) Project latitude / longitude persistence
  C) Company mobile_phone + website persistence
  D) Observation contributing_behavior + contributing_condition
  E) CloseoutChecklistItem spec_division + spec_section
  F) OmManual CRUD (POST, GET, PATCH)
  G) OmManual list filter by project_id
"""

import pytest
from httpx import AsyncClient

from tests.helpers import (
    COMPANY_REX,
    PROJECT_BISHOP,
    uid,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _project(c: AsyncClient, **kw) -> dict:
    p = {"name": f"P38-Proj-{uid()}", "status": "active"}
    p.update(kw)
    r = await c.post("/api/projects/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


async def _company(c: AsyncClient, **kw) -> dict:
    p = {"name": f"P38-Co-{uid()}", "company_type": "subcontractor", "status": "active"}
    p.update(kw)
    r = await c.post("/api/companies/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


async def _schedule(c: AsyncClient, project_id: str) -> dict:
    r = await c.post("/api/schedules/", json={
        "project_id": project_id,
        "name": f"P38-Sched-{uid()}",
        "schedule_type": "master",
        "start_date": "2025-01-01",
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _activity(c: AsyncClient, schedule_id: str, **kw) -> dict:
    p = {
        "schedule_id": schedule_id,
        "name": f"P38-Act-{uid()}",
        "activity_type": "task",
        "start_date": "2025-03-01",
        "end_date": "2025-03-31",
    }
    p.update(kw)
    r = await c.post("/api/schedule-activities/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


async def _checklist(c: AsyncClient, project_id: str) -> dict:
    r = await c.post("/api/closeout-checklists/", json={
        "project_id": project_id,
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _checklist_item(c: AsyncClient, checklist_id: str, **kw) -> dict:
    p = {
        "checklist_id": checklist_id,
        "category": "general",
        "item_number": 1,
        "name": f"P38-Item-{uid()}",
    }
    p.update(kw)
    r = await c.post("/api/closeout-checklist-items/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# A) ScheduleActivity — start_variance_days, finish_variance_days, free_float_days
# ═══════════════════════════════════════════════════════════════════════════

async def test_schedule_activity_start_finish_variance_free_float(rollback_client: AsyncClient):
    proj = await _project(rollback_client)
    sched = await _schedule(rollback_client, proj["id"])
    act = await _activity(
        rollback_client,
        sched["id"],
        start_variance_days=3,
        finish_variance_days=-2,
        free_float_days=5,
    )
    assert act["start_variance_days"] == 3
    assert act["finish_variance_days"] == -2
    assert act["free_float_days"] == 5

    # Verify round-trip via GET
    r = await rollback_client.get(f"/api/schedule-activities/{act['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["start_variance_days"] == 3
    assert body["finish_variance_days"] == -2
    assert body["free_float_days"] == 5


# ═══════════════════════════════════════════════════════════════════════════
# B) Project — latitude / longitude
# ═══════════════════════════════════════════════════════════════════════════

async def test_project_lat_lng_persistence(rollback_client: AsyncClient):
    proj = await _project(rollback_client, latitude=34.052235, longitude=-118.243683)
    assert float(proj["latitude"]) == pytest.approx(34.052235, rel=1e-4)
    assert float(proj["longitude"]) == pytest.approx(-118.243683, rel=1e-4)

    r = await rollback_client.get(f"/api/projects/{proj['id']}")
    assert r.status_code == 200
    body = r.json()
    assert float(body["latitude"]) == pytest.approx(34.052235, rel=1e-4)
    assert float(body["longitude"]) == pytest.approx(-118.243683, rel=1e-4)


# ═══════════════════════════════════════════════════════════════════════════
# C) Company — mobile_phone + website
# ═══════════════════════════════════════════════════════════════════════════

async def test_company_mobile_website_persistence(rollback_client: AsyncClient):
    co = await _company(
        rollback_client,
        mobile_phone="555-867-5309",
        website="https://example-rex.com",
    )
    assert co["mobile_phone"] == "555-867-5309"
    assert co["website"] == "https://example-rex.com"

    r = await rollback_client.get(f"/api/companies/{co['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["mobile_phone"] == "555-867-5309"
    assert body["website"] == "https://example-rex.com"


# ═══════════════════════════════════════════════════════════════════════════
# D) Observation — contributing_behavior + contributing_condition
# ═══════════════════════════════════════════════════════════════════════════

async def test_observation_contributing_fields(rollback_client: AsyncClient):
    r = await rollback_client.post("/api/observations/", json={
        "project_id": PROJECT_BISHOP,
        "observation_number": abs(hash(uid())) % 100000,
        "title": f"P38-Obs-{uid()}",
        "observation_type": "safety",
        "description": "Test observation for P38/39",
        "contributing_behavior": "Improper PPE usage",
        "contributing_condition": "Slippery surface",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["contributing_behavior"] == "Improper PPE usage"
    assert body["contributing_condition"] == "Slippery surface"

    r2 = await rollback_client.get(f"/api/observations/{body['id']}")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["contributing_behavior"] == "Improper PPE usage"
    assert body2["contributing_condition"] == "Slippery surface"


# ═══════════════════════════════════════════════════════════════════════════
# E) CloseoutChecklistItem — spec_division + spec_section
# ═══════════════════════════════════════════════════════════════════════════

async def test_closeout_checklist_item_spec_fields(rollback_client: AsyncClient):
    proj = await _project(rollback_client)
    cl = await _checklist(rollback_client, proj["id"])
    item = await _checklist_item(
        rollback_client,
        cl["id"],
        spec_division="03",
        spec_section="03 30 00",
    )
    assert item["spec_division"] == "03"
    assert item["spec_section"] == "03 30 00"

    r = await rollback_client.get(f"/api/closeout-checklist-items/{item['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["spec_division"] == "03"
    assert body["spec_section"] == "03 30 00"


# ═══════════════════════════════════════════════════════════════════════════
# F) OmManual CRUD
# ═══════════════════════════════════════════════════════════════════════════

async def test_om_manual_crud(rollback_client: AsyncClient):
    proj = await _project(rollback_client)

    # POST
    r = await rollback_client.post("/api/om-manuals/", json={
        "project_id": proj["id"],
        "spec_section": "23 05 00",
        "spec_title": "HVAC Basic Materials and Methods",
        "required_count": 3,
        "received_count": 1,
        "status": "partial",
        "vendor_company_id": COMPANY_REX,
        "notes": "Waiting on 2 more copies",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["spec_section"] == "23 05 00"
    assert body["spec_title"] == "HVAC Basic Materials and Methods"
    assert body["required_count"] == 3
    assert body["received_count"] == 1
    assert body["status"] == "partial"
    assert body["notes"] == "Waiting on 2 more copies"
    row_id = body["id"]

    # GET
    r2 = await rollback_client.get(f"/api/om-manuals/{row_id}")
    assert r2.status_code == 200
    assert r2.json()["spec_section"] == "23 05 00"

    # PATCH — change status to received
    r3 = await rollback_client.patch(f"/api/om-manuals/{row_id}", json={
        "received_count": 3,
        "status": "received",
    })
    assert r3.status_code == 200
    body3 = r3.json()
    assert body3["received_count"] == 3
    assert body3["status"] == "received"


# ═══════════════════════════════════════════════════════════════════════════
# G) OmManual list filter by project_id
# ═══════════════════════════════════════════════════════════════════════════

async def test_om_manual_list_filter_by_project(rollback_client: AsyncClient):
    proj = await _project(rollback_client)
    project_id = proj["id"]

    # Create 2 om_manuals for the same project
    for i, section in enumerate(["01 10 00", "02 20 00"]):
        r = await rollback_client.post("/api/om-manuals/", json={
            "project_id": project_id,
            "spec_section": section,
            "required_count": 1,
        })
        assert r.status_code == 201, r.text

    # List filtered by project_id
    r = await rollback_client.get(f"/api/om-manuals/?project_id={project_id}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    sections = {item["spec_section"] for item in items}
    assert sections == {"01 10 00", "02 20 00"}


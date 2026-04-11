"""Schedule domain smoke tests.

Requires a running PostgreSQL with seeded rex_os database.
Tests create their own schedule data under the seeded Bishop Modern project.
Each test uses unique names via _uid() to avoid cross-run collisions.
"""

import uuid

from httpx import AsyncClient

# Seeded project from foundation bootstrap
PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _create_schedule(client: AsyncClient, **overrides) -> dict:
    payload = {
        "project_id": PROJECT_BISHOP,
        "name": f"Sched-{_uid()}",
        "schedule_type": "master",
        "start_date": "2025-01-01",
    }
    payload.update(overrides)
    r = await client.post("/api/schedules/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _create_activity(client: AsyncClient, schedule_id: str, **overrides) -> dict:
    payload = {
        "schedule_id": schedule_id,
        "name": f"Act-{_uid()}",
        "activity_type": "task",
        "start_date": "2025-01-06",
        "end_date": "2025-01-10",
        "duration_days": 5,
    }
    payload.update(overrides)
    r = await client.post("/api/schedule-activities/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Schedules
# ═══════════════════════════════════════════════════════════════════════════

async def test_create_schedule(client: AsyncClient):
    data = await _create_schedule(client)
    assert data["project_id"] == PROJECT_BISHOP
    assert data["schedule_type"] == "master"
    assert data["status"] == "active"


async def test_list_schedules(client: AsyncClient):
    r = await client.get("/api/schedules/")
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_list_schedules_filter_project(client: AsyncClient):
    sched = await _create_schedule(client)
    r = await client.get(f"/api/schedules/?project_id={PROJECT_BISHOP}&limit=2000")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert sched["id"] in ids


async def test_get_schedule(client: AsyncClient):
    sched = await _create_schedule(client)
    r = await client.get(f"/api/schedules/{sched['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == sched["id"]


async def test_get_schedule_not_found(client: AsyncClient):
    r = await client.get(f"/api/schedules/{BOGUS_UUID}")
    assert r.status_code == 404


async def test_patch_schedule(client: AsyncClient):
    sched = await _create_schedule(client)
    r = await client.patch(f"/api/schedules/{sched['id']}", json={
        "name": f"Patched-{_uid()}",
        "status": "draft",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "draft"


async def test_create_schedule_bad_fk(client: AsyncClient):
    r = await client.post("/api/schedules/", json={
        "project_id": BOGUS_UUID,
        "name": "Bad FK",
        "schedule_type": "master",
        "start_date": "2025-01-01",
    })
    assert r.status_code == 422


async def test_create_schedule_invalid_type(client: AsyncClient):
    """Pydantic Literal rejects invalid schedule_type before hitting the DB."""
    r = await client.post("/api/schedules/", json={
        "project_id": PROJECT_BISHOP,
        "name": "Bad Type",
        "schedule_type": "invalid_type",
        "start_date": "2025-01-01",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Schedule Activities
# ═══════════════════════════════════════════════════════════════════════════

async def test_create_activity(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    assert act["schedule_id"] == sched["id"]
    assert act["activity_type"] == "task"


async def test_list_activities(client: AsyncClient):
    sched = await _create_schedule(client)
    await _create_activity(client, sched["id"])
    await _create_activity(client, sched["id"])
    r = await client.get(f"/api/schedule-activities/?schedule_id={sched['id']}")
    assert r.status_code == 200
    assert len(r.json()) >= 2


async def test_list_activities_filter_type(client: AsyncClient):
    sched = await _create_schedule(client)
    await _create_activity(client, sched["id"], activity_type="milestone",
                           start_date="2025-03-01", end_date="2025-03-01")
    await _create_activity(client, sched["id"])
    r = await client.get(f"/api/schedule-activities/?schedule_id={sched['id']}&activity_type=milestone")
    assert r.status_code == 200
    assert all(a["activity_type"] == "milestone" for a in r.json())


async def test_get_activity(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    r = await client.get(f"/api/schedule-activities/{act['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == act["id"]


async def test_patch_activity(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    r = await client.patch(f"/api/schedule-activities/{act['id']}", json={
        "percent_complete": 50,
        "is_critical": True,
    })
    assert r.status_code == 200
    assert r.json()["percent_complete"] == 50
    assert r.json()["is_critical"] is True


async def test_activity_self_reference(client: AsyncClient):
    sched = await _create_schedule(client)
    parent = await _create_activity(client, sched["id"], activity_type="section")
    child = await _create_activity(client, sched["id"], parent_id=parent["id"])
    assert child["parent_id"] == parent["id"]


async def test_activity_bad_schedule_fk(client: AsyncClient):
    r = await client.post("/api/schedule-activities/", json={
        "schedule_id": BOGUS_UUID,
        "name": "Bad FK",
        "activity_type": "task",
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
    })
    # Sprint J: write-scope resolves parent schedule first → 404 for bogus FK
    assert r.status_code in (404, 422)


async def test_activity_invalid_type(client: AsyncClient):
    sched = await _create_schedule(client)
    r = await client.post("/api/schedule-activities/", json={
        "schedule_id": sched["id"],
        "name": "Bad Type",
        "activity_type": "invalid",
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Activity Links
# ═══════════════════════════════════════════════════════════════════════════

async def test_create_activity_link(client: AsyncClient):
    sched = await _create_schedule(client)
    a = await _create_activity(client, sched["id"])
    b = await _create_activity(client, sched["id"],
                               start_date="2025-01-13", end_date="2025-01-17")
    r = await client.post("/api/activity-links/", json={
        "schedule_id": sched["id"],
        "from_activity_id": a["id"],
        "to_activity_id": b["id"],
        "link_type": "fs",
        "lag_days": 2,
    })
    assert r.status_code == 201
    assert r.json()["link_type"] == "fs"
    assert r.json()["lag_days"] == 2


async def test_list_activity_links(client: AsyncClient):
    r = await client.get("/api/activity-links/")
    assert r.status_code == 200


async def test_get_activity_link(client: AsyncClient):
    sched = await _create_schedule(client)
    a = await _create_activity(client, sched["id"])
    b = await _create_activity(client, sched["id"],
                               start_date="2025-02-01", end_date="2025-02-05")
    link = await client.post("/api/activity-links/", json={
        "schedule_id": sched["id"],
        "from_activity_id": a["id"],
        "to_activity_id": b["id"],
    })
    r = await client.get(f"/api/activity-links/{link.json()['id']}")
    assert r.status_code == 200


async def test_activity_link_bad_fk(client: AsyncClient):
    sched = await _create_schedule(client)
    a = await _create_activity(client, sched["id"])
    r = await client.post("/api/activity-links/", json={
        "schedule_id": sched["id"],
        "from_activity_id": a["id"],
        "to_activity_id": BOGUS_UUID,
    })
    assert r.status_code == 422


async def test_activity_link_invalid_type(client: AsyncClient):
    sched = await _create_schedule(client)
    a = await _create_activity(client, sched["id"])
    b = await _create_activity(client, sched["id"],
                               start_date="2025-02-01", end_date="2025-02-05")
    r = await client.post("/api/activity-links/", json={
        "schedule_id": sched["id"],
        "from_activity_id": a["id"],
        "to_activity_id": b["id"],
        "link_type": "invalid",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Schedule Constraints
# ═══════════════════════════════════════════════════════════════════════════

async def test_create_schedule_constraint(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    r = await client.post("/api/schedule-constraints/", json={
        "activity_id": act["id"],
        "constraint_type": "rfi_pending",
        "source_type": "rfi",
        "severity": "yellow",
    })
    assert r.status_code == 201
    assert r.json()["status"] == "active"


async def test_list_schedule_constraints(client: AsyncClient):
    r = await client.get("/api/schedule-constraints/")
    assert r.status_code == 200


async def test_get_schedule_constraint(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    created = await client.post("/api/schedule-constraints/", json={
        "activity_id": act["id"],
        "constraint_type": "permit_pending",
        "source_type": "permit",
        "severity": "red",
    })
    r = await client.get(f"/api/schedule-constraints/{created.json()['id']}")
    assert r.status_code == 200
    assert r.json()["severity"] == "red"


async def test_patch_schedule_constraint(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    created = await client.post("/api/schedule-constraints/", json={
        "activity_id": act["id"],
        "constraint_type": "material_lead",
        "source_type": "commitment",
        "severity": "green",
    })
    r = await client.patch(f"/api/schedule-constraints/{created.json()['id']}", json={
        "status": "resolved",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


async def test_constraint_invalid_type(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    r = await client.post("/api/schedule-constraints/", json={
        "activity_id": act["id"],
        "constraint_type": "invalid",
        "source_type": "rfi",
        "severity": "red",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Schedule Snapshots
# ═══════════════════════════════════════════════════════════════════════════

async def test_create_schedule_snapshot(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    r = await client.post("/api/schedule-snapshots/", json={
        "activity_id": act["id"],
        "snapshot_date": "2025-01-10",
        "start_date": "2025-01-06",
        "end_date": "2025-01-10",
        "percent_complete": 100,
    })
    assert r.status_code == 201
    assert r.json()["percent_complete"] == 100


async def test_list_schedule_snapshots(client: AsyncClient):
    r = await client.get("/api/schedule-snapshots/")
    assert r.status_code == 200


async def test_get_schedule_snapshot(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    created = await client.post("/api/schedule-snapshots/", json={
        "activity_id": act["id"],
        "snapshot_date": "2025-02-14",
        "start_date": "2025-01-06",
        "end_date": "2025-01-10",
    })
    r = await client.get(f"/api/schedule-snapshots/{created.json()['id']}")
    assert r.status_code == 200


async def test_duplicate_snapshot_returns_409(client: AsyncClient):
    sched = await _create_schedule(client)
    act = await _create_activity(client, sched["id"])
    payload = {
        "activity_id": act["id"],
        "snapshot_date": "2025-03-01",
        "start_date": "2025-01-06",
        "end_date": "2025-01-10",
    }
    r1 = await client.post("/api/schedule-snapshots/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/schedule-snapshots/", json=payload)
    assert r2.status_code == 409


async def test_snapshot_bad_activity_fk(client: AsyncClient):
    r = await client.post("/api/schedule-snapshots/", json={
        "activity_id": BOGUS_UUID,
        "snapshot_date": "2025-04-01",
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
    })
    assert r.status_code in (404, 422)  # write-scope resolves parent first → 404

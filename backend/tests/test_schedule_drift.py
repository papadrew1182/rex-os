"""Schedule drift summary + project schedule health tests."""

import uuid
from httpx import AsyncClient

PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Drift-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _schedule(c: AsyncClient, project_id: str) -> dict:
    r = await c.post("/api/schedules/", json={
        "project_id": project_id, "name": f"Sched-{_uid()}",
        "schedule_type": "master", "start_date": "2025-01-01",
    })
    return r.json()


async def _activity(c: AsyncClient, schedule_id: str, **kw) -> dict:
    p = {
        "schedule_id": schedule_id, "name": f"Act-{_uid()}",
        "activity_type": "task", "start_date": "2025-01-06", "end_date": "2025-01-10",
    }
    p.update(kw)
    r = await c.post("/api/schedule-activities/", json=p)
    return r.json()


async def test_drift_summary_empty_schedule(client: AsyncClient):
    pid = await _project(client)
    sched = await _schedule(client, pid)
    r = await client.get(f"/api/schedules/{sched['id']}/drift-summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_activities"] == 0
    assert body["critical_count"] == 0
    assert body["average_variance_days"] == 0
    assert body["worst_variance_activity"] is None
    assert body["constraints_by_severity"] == {"green": 0, "yellow": 0, "red": 0}


async def test_drift_summary_with_activities_and_variance(client: AsyncClient):
    pid = await _project(client)
    sched = await _schedule(client, pid)
    a1 = await _activity(client, sched["id"], is_critical=True, percent_complete=100, variance_days=2)
    a2 = await _activity(client, sched["id"], is_critical=True, percent_complete=50, variance_days=5)
    a3 = await _activity(client, sched["id"], percent_complete=0, variance_days=-1)

    r = await client.get(f"/api/schedules/{sched['id']}/drift-summary")
    body = r.json()
    assert body["total_activities"] == 3
    assert body["critical_count"] == 2
    assert body["completed_count"] == 1
    assert body["positive_variance_count"] == 2
    assert body["negative_variance_count"] == 1
    assert body["average_variance_days"] == 2.0  # (2+5-1)/3
    assert body["worst_variance_activity"]["variance_days"] == 5


async def test_drift_summary_with_constraints(client: AsyncClient):
    pid = await _project(client)
    sched = await _schedule(client, pid)
    act = await _activity(client, sched["id"])

    await client.post("/api/schedule-constraints/", json={
        "activity_id": act["id"], "constraint_type": "rfi_pending",
        "source_type": "rfi", "severity": "yellow",
    })
    await client.post("/api/schedule-constraints/", json={
        "activity_id": act["id"], "constraint_type": "permit_pending",
        "source_type": "permit", "severity": "red",
    })

    r = await client.get(f"/api/schedules/{sched['id']}/drift-summary")
    body = r.json()
    assert body["active_constraint_count"] == 2
    assert body["constraints_by_severity"]["yellow"] == 1
    assert body["constraints_by_severity"]["red"] == 1


async def test_drift_summary_with_snapshots(client: AsyncClient):
    pid = await _project(client)
    sched = await _schedule(client, pid)
    a1 = await _activity(client, sched["id"])
    a2 = await _activity(client, sched["id"])

    await client.post("/api/schedule-snapshots/", json={
        "activity_id": a1["id"], "snapshot_date": "2025-01-15",
        "start_date": "2025-01-06", "end_date": "2025-01-10",
    })
    await client.post("/api/schedule-snapshots/", json={
        "activity_id": a2["id"], "snapshot_date": "2025-01-15",
        "start_date": "2025-01-06", "end_date": "2025-01-10",
    })

    r = await client.get(f"/api/schedules/{sched['id']}/drift-summary")
    assert r.json()["snapshot_coverage_count"] == 2


async def test_drift_summary_404(client: AsyncClient):
    r = await client.get(f"/api/schedules/{BOGUS_UUID}/drift-summary")
    assert r.status_code == 404


# ── Project schedule health ─────────────────────────────────────────────────

async def test_project_schedule_health_no_schedules(client: AsyncClient):
    pid = await _project(client)
    r = await client.get(f"/api/projects/{pid}/schedule-health")
    assert r.status_code == 200
    body = r.json()
    assert body["schedule_count"] == 0
    assert body["health_status"] == "not_started"


async def test_project_schedule_health_with_red_constraint(client: AsyncClient):
    pid = await _project(client)
    sched = await _schedule(client, pid)
    act = await _activity(client, sched["id"])
    await client.post("/api/schedule-constraints/", json={
        "activity_id": act["id"], "constraint_type": "permit_pending",
        "source_type": "permit", "severity": "red",
    })

    r = await client.get(f"/api/projects/{pid}/schedule-health")
    body = r.json()
    assert body["schedule_count"] == 1
    assert body["health_status"] == "fail"
    assert body["constraints_by_severity"]["red"] == 1


async def test_project_schedule_health_clean_pass(client: AsyncClient):
    pid = await _project(client)
    sched = await _schedule(client, pid)
    await _activity(client, sched["id"], percent_complete=100)

    r = await client.get(f"/api/projects/{pid}/schedule-health")
    body = r.json()
    assert body["health_status"] == "pass"
    assert body["completed_count"] == 1

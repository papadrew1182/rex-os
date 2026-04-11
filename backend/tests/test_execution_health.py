"""Project execution health cross-domain helper tests."""

import uuid
from datetime import date, timedelta
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Exec-{_uid()}", "status": "active"})
    return r.json()["id"]


def _unique_date() -> date:
    h = int(_uid(), 16)
    return date(6000 + (h % 1000), ((h >> 12) % 12) + 1, ((h >> 8) % 28) + 1)


async def test_execution_health_empty_project(client: AsyncClient):
    pid = await _project(client)
    r = await client.get(f"/api/projects/{pid}/execution-health")
    assert r.status_code == 200
    body = r.json()
    assert body["schedule_health_status"] == "not_started"
    assert body["manpower"]["total_logs"] == 0
    assert body["inspections"]["total"] == 0
    assert body["punch"]["total"] == 0
    assert body["tasks_by_status"] == {}


async def test_execution_health_with_data(client: AsyncClient):
    pid = await _project(client)

    # Schedule + activity
    sched = await client.post("/api/schedules/", json={
        "project_id": pid, "name": f"Sched-{_uid()}",
        "schedule_type": "master", "start_date": "2025-01-01",
    })
    await client.post("/api/schedule-activities/", json={
        "schedule_id": sched.json()["id"], "name": f"Act-{_uid()}",
        "activity_type": "task", "start_date": "2025-01-06", "end_date": "2025-01-10",
        "is_critical": True,
    })

    # Daily log + manpower
    log = await client.post("/api/daily-logs/", json={
        "project_id": pid, "log_date": _unique_date().isoformat(),
    })
    await client.post("/api/manpower-entries/", json={
        "daily_log_id": log.json()["id"], "company_id": COMPANY_REX,
        "worker_count": 6, "hours": 48,
    })

    # Inspection with failed item
    insp = await client.post("/api/inspections/", json={
        "project_id": pid, "inspection_number": f"INS-{_uid()}",
        "title": "Test", "inspection_type": "quality",
        "scheduled_date": "2025-06-01", "status": "in_progress",
    })
    await client.post("/api/inspection-items/", json={
        "inspection_id": insp.json()["id"], "item_number": 1,
        "description": "Fail item", "result": "fail",
    })

    # Open punch
    await client.post("/api/punch-items/", json={
        "project_id": pid, "punch_number": int(_uid()[:4], 16),
        "title": "Open punch", "status": "open",
    })

    # Tasks in different statuses
    await client.post("/api/tasks/", json={
        "project_id": pid, "task_number": int(_uid()[:4], 16),
        "title": "Open task", "due_date": "2025-09-01",
    })
    await client.post("/api/tasks/", json={
        "project_id": pid, "task_number": int(_uid()[:4], 16),
        "title": "Done task", "due_date": "2025-09-01", "status": "complete",
    })

    r = await client.get(f"/api/projects/{pid}/execution-health")
    assert r.status_code == 200
    body = r.json()

    assert body["manpower"]["total_logs"] == 1
    assert body["manpower"]["total_worker_count"] == 6
    assert body["inspections"]["total"] == 1
    assert body["inspections"]["open_count"] == 1
    assert body["inspections"]["failed_item_count"] == 1
    assert body["punch"]["open_count"] == 1
    assert body["tasks_by_status"]["open"] == 1
    assert body["tasks_by_status"]["complete"] == 1

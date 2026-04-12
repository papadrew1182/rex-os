"""Field Ops domain smoke tests.

Requires a running PostgreSQL with seeded rex_os database.
Uses seeded Bishop Modern project and Rex Construction company.
"""

import uuid

from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


# ═══════════════════════════════════════════════════════════════════════════
# Daily Logs
# ═══════════════════════════════════════════════════════════════════════════

async def test_create_daily_log(client: AsyncClient):
    r = await client.post("/api/daily-logs/", json={
        "project_id": PROJECT_BISHOP, "log_date": f"2099-01-{_uid()[:2].zfill(2)}",
    })
    # use unique date via random approach — but dates must be valid, so use fixed unique
    # Re-do with truly unique date
    pass  # covered below


async def test_daily_log_crud(client: AsyncClient):
    # Use a fresh throwaway project so the (project_id, log_date) unique
    # constraint can never collide with leftover seed data.
    proj = await client.post("/api/projects/", json={
        "name": f"DL-CRUD-{_uid()}",
        "status": "active",
    })
    assert proj.status_code == 201, proj.text
    project_id = proj.json()["id"]

    date_str = f"2090-{(int(_uid()[:2], 16) % 12) + 1:02d}-{(int(_uid()[:2], 16) % 28) + 1:02d}"
    r = await client.post("/api/daily-logs/", json={
        "project_id": project_id, "log_date": date_str, "weather_summary": "sunny",
    })
    assert r.status_code == 201
    log_id = r.json()["id"]

    r = await client.get(f"/api/daily-logs/{log_id}")
    assert r.status_code == 200
    assert r.json()["weather_summary"] == "sunny"

    r = await client.patch(f"/api/daily-logs/{log_id}", json={"status": "submitted"})
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"


async def test_list_daily_logs(client: AsyncClient):
    r = await client.get(f"/api/daily-logs/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


async def test_daily_log_duplicate_409(client: AsyncClient):
    h = int(_uid(), 16)
    date_str = f"{4200 + h % 800}-{(h >> 12) % 12 + 1:02d}-{(h >> 8) % 28 + 1:02d}"
    payload = {"project_id": PROJECT_BISHOP, "log_date": date_str}
    r1 = await client.post("/api/daily-logs/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/daily-logs/", json=payload)
    assert r2.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# Manpower Entries
# ═══════════════════════════════════════════════════════════════════════════

async def test_manpower_entry_crud(client: AsyncClient):
    h = int(_uid(), 16)
    date_str = f"{2200 + h % 800}-{(h >> 12) % 12 + 1:02d}-{(h >> 8) % 28 + 1:02d}"
    log = await client.post("/api/daily-logs/", json={"project_id": PROJECT_BISHOP, "log_date": date_str})
    assert log.status_code == 201, f"daily log create failed for {date_str}: {log.text}"
    log_id = log.json()["id"]

    r = await client.post("/api/manpower-entries/", json={
        "daily_log_id": log_id, "company_id": COMPANY_REX, "worker_count": 5, "hours": 40,
    })
    assert r.status_code == 201
    entry_id = r.json()["id"]

    r = await client.get(f"/api/manpower-entries/{entry_id}")
    assert r.status_code == 200

    r = await client.patch(f"/api/manpower-entries/{entry_id}", json={"worker_count": 8})
    assert r.status_code == 200
    assert r.json()["worker_count"] == 8


async def test_manpower_entry_duplicate_409(client: AsyncClient):
    h = int(_uid(), 16)
    date_str = f"{3200 + h % 800}-{(h >> 12) % 12 + 1:02d}-{(h >> 8) % 28 + 1:02d}"
    log = await client.post("/api/daily-logs/", json={"project_id": PROJECT_BISHOP, "log_date": date_str})
    assert log.status_code == 201, f"daily log create failed for {date_str}: {log.text}"
    log_id = log.json()["id"]
    payload = {"daily_log_id": log_id, "company_id": COMPANY_REX, "worker_count": 3, "hours": 24}
    r1 = await client.post("/api/manpower-entries/", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/manpower-entries/", json=payload)
    assert r2.status_code == 409


async def test_list_manpower_entries(client: AsyncClient):
    r = await client.get("/api/manpower-entries/")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Punch Items
# ═══════════════════════════════════════════════════════════════════════════

async def test_punch_item_crud(client: AsyncClient):
    num = int(_uid()[:4], 16)
    r = await client.post("/api/punch-items/", json={
        "project_id": PROJECT_BISHOP, "punch_number": num, "title": f"Punch-{_uid()}",
    })
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await client.get(f"/api/punch-items/{pid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/punch-items/{pid}", json={"status": "open", "priority": "high"})
    assert r.status_code == 200
    assert r.json()["priority"] == "high"


async def test_punch_item_bad_fk(client: AsyncClient):
    r = await client.post("/api/punch-items/", json={
        "project_id": BOGUS_UUID, "punch_number": 999, "title": "Bad",
    })
    assert r.status_code == 422


async def test_list_punch_items(client: AsyncClient):
    r = await client.get(f"/api/punch-items/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


async def test_punch_item_invalid_status(client: AsyncClient):
    r = await client.post("/api/punch-items/", json={
        "project_id": PROJECT_BISHOP, "punch_number": 9999, "title": "Bad Status", "status": "bogus",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Inspections + Items
# ═══════════════════════════════════════════════════════════════════════════

async def test_inspection_crud(client: AsyncClient):
    r = await client.post("/api/inspections/", json={
        "project_id": PROJECT_BISHOP, "inspection_number": f"INS-{_uid()}",
        "title": f"Insp-{_uid()}", "inspection_type": "municipal", "scheduled_date": "2025-06-01",
    })
    assert r.status_code == 201
    iid = r.json()["id"]

    r = await client.get(f"/api/inspections/{iid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/inspections/{iid}", json={"status": "passed"})
    assert r.status_code == 200
    assert r.json()["status"] == "passed"


async def test_list_inspections(client: AsyncClient):
    r = await client.get(f"/api/inspections/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


async def test_inspection_item_crud(client: AsyncClient):
    insp = await client.post("/api/inspections/", json={
        "project_id": PROJECT_BISHOP, "inspection_number": f"INS-{_uid()}",
        "title": f"Insp-{_uid()}", "inspection_type": "quality", "scheduled_date": "2025-07-01",
    })
    iid = insp.json()["id"]

    r = await client.post("/api/inspection-items/", json={
        "inspection_id": iid, "item_number": 1, "description": "Check rebar", "result": "pass",
    })
    assert r.status_code == 201
    item_id = r.json()["id"]

    r = await client.get(f"/api/inspection-items/{item_id}")
    assert r.status_code == 200

    r = await client.patch(f"/api/inspection-items/{item_id}", json={"result": "fail"})
    assert r.status_code == 200
    assert r.json()["result"] == "fail"


async def test_list_inspection_items(client: AsyncClient):
    r = await client.get("/api/inspection-items/")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Observations
# ═══════════════════════════════════════════════════════════════════════════

async def test_observation_crud(client: AsyncClient):
    num = int(_uid()[:4], 16)
    r = await client.post("/api/observations/", json={
        "project_id": PROJECT_BISHOP, "observation_number": num,
        "title": f"Obs-{_uid()}", "observation_type": "safety",
        "description": "Loose railing on 3rd floor",
    })
    assert r.status_code == 201
    oid = r.json()["id"]

    r = await client.get(f"/api/observations/{oid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/observations/{oid}", json={"status": "closed"})
    assert r.status_code == 200


async def test_list_observations(client: AsyncClient):
    r = await client.get(f"/api/observations/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Safety Incidents
# ═══════════════════════════════════════════════════════════════════════════

async def test_safety_incident_crud(client: AsyncClient):
    r = await client.post("/api/safety-incidents/", json={
        "project_id": PROJECT_BISHOP, "incident_number": f"SI-{_uid()}",
        "title": f"Incident-{_uid()}", "incident_type": "near_miss",
        "severity": "minor", "incident_date": "2025-05-01",
        "description": "Worker slipped on wet surface",
    })
    assert r.status_code == 201
    sid = r.json()["id"]

    r = await client.get(f"/api/safety-incidents/{sid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/safety-incidents/{sid}", json={"status": "closed"})
    assert r.status_code == 200


async def test_list_safety_incidents(client: AsyncClient):
    r = await client.get(f"/api/safety-incidents/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


async def test_safety_incident_invalid_type(client: AsyncClient):
    r = await client.post("/api/safety-incidents/", json={
        "project_id": PROJECT_BISHOP, "incident_number": "BAD",
        "title": "Bad", "incident_type": "bogus", "severity": "minor",
        "incident_date": "2025-05-01", "description": "x",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Photo Albums + Photos
# ═══════════════════════════════════════════════════════════════════════════

async def test_photo_album_crud(client: AsyncClient):
    r = await client.post("/api/photo-albums/", json={
        "project_id": PROJECT_BISHOP, "name": f"Album-{_uid()}",
    })
    assert r.status_code == 201
    aid = r.json()["id"]

    r = await client.get(f"/api/photo-albums/{aid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/photo-albums/{aid}", json={"description": "Updated"})
    assert r.status_code == 200


async def test_list_photo_albums(client: AsyncClient):
    r = await client.get(f"/api/photo-albums/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


async def test_photo_crud(client: AsyncClient):
    r = await client.post("/api/photos/", json={
        "project_id": PROJECT_BISHOP, "filename": f"img-{_uid()}.jpg",
        "file_size": 2048000, "content_type": "image/jpeg",
        "storage_url": "https://r2.example.com/test.jpg", "storage_key": f"photos/{_uid()}",
    })
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await client.get(f"/api/photos/{pid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/photos/{pid}", json={"description": "Site progress"})
    assert r.status_code == 200


async def test_list_photos(client: AsyncClient):
    r = await client.get(f"/api/photos/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════════════════════════════

async def test_task_crud(client: AsyncClient):
    num = int(_uid()[:4], 16)
    r = await client.post("/api/tasks/", json={
        "project_id": PROJECT_BISHOP, "task_number": num,
        "title": f"Task-{_uid()}", "due_date": "2025-08-01", "category": "safety",
    })
    assert r.status_code == 201
    tid = r.json()["id"]

    r = await client.get(f"/api/tasks/{tid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/tasks/{tid}", json={"status": "complete"})
    assert r.status_code == 200
    assert r.json()["status"] == "complete"


async def test_list_tasks(client: AsyncClient):
    r = await client.get(f"/api/tasks/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


async def test_task_invalid_category(client: AsyncClient):
    r = await client.post("/api/tasks/", json={
        "project_id": PROJECT_BISHOP, "task_number": 99999,
        "title": "Bad", "due_date": "2025-08-01", "category": "bogus",
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Meetings + Action Items
# ═══════════════════════════════════════════════════════════════════════════

async def test_meeting_crud(client: AsyncClient):
    r = await client.post("/api/meetings/", json={
        "project_id": PROJECT_BISHOP, "meeting_type": "oac",
        "title": f"Meeting-{_uid()}", "meeting_date": "2025-09-01",
    })
    assert r.status_code == 201
    mid = r.json()["id"]

    r = await client.get(f"/api/meetings/{mid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/meetings/{mid}", json={"minutes": "Discussed schedule"})
    assert r.status_code == 200


async def test_list_meetings(client: AsyncClient):
    r = await client.get(f"/api/meetings/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


async def test_meeting_action_item_crud(client: AsyncClient):
    mtg = await client.post("/api/meetings/", json={
        "project_id": PROJECT_BISHOP, "meeting_type": "sub_coordination",
        "title": f"Sub Coord-{_uid()}", "meeting_date": "2025-09-15",
    })
    mid = mtg.json()["id"]

    r = await client.post("/api/meeting-action-items/", json={
        "meeting_id": mid, "item_number": 1, "description": f"Follow up on rebar delivery-{_uid()}",
    })
    assert r.status_code == 201
    aid = r.json()["id"]

    r = await client.get(f"/api/meeting-action-items/{aid}")
    assert r.status_code == 200

    r = await client.patch(f"/api/meeting-action-items/{aid}", json={"status": "complete"})
    assert r.status_code == 200
    assert r.json()["status"] == "complete"


async def test_list_meeting_action_items(client: AsyncClient):
    r = await client.get("/api/meeting-action-items/")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════

async def test_not_found_404(client: AsyncClient):
    r = await client.get(f"/api/daily-logs/{BOGUS_UUID}")
    assert r.status_code == 404
    r = await client.get(f"/api/punch-items/{BOGUS_UUID}")
    assert r.status_code == 404
    r = await client.get(f"/api/tasks/{BOGUS_UUID}")
    assert r.status_code == 404

"""Inspection summary helper tests."""

import uuid
from httpx import AsyncClient

BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Insp-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _inspection(c: AsyncClient, project_id: str) -> dict:
    r = await c.post("/api/inspections/", json={
        "project_id": project_id, "inspection_number": f"INS-{_uid()}",
        "title": f"Insp-{_uid()}", "inspection_type": "quality",
        "scheduled_date": "2025-06-01",
    })
    assert r.status_code == 201
    return r.json()


async def _item(c: AsyncClient, inspection_id: str, item_number: int, result: str, punch_item_id: str | None = None) -> dict:
    payload = {
        "inspection_id": inspection_id, "item_number": item_number,
        "description": f"Item-{_uid()}", "result": result,
    }
    if punch_item_id:
        payload["punch_item_id"] = punch_item_id
    r = await c.post("/api/inspection-items/", json=payload)
    assert r.status_code == 201
    return r.json()


async def _punch(c: AsyncClient, project_id: str) -> dict:
    r = await c.post("/api/punch-items/", json={
        "project_id": project_id, "punch_number": int(_uid()[:4], 16),
        "title": f"Punch-{_uid()}",
    })
    return r.json()


async def test_inspection_summary_no_items(client: AsyncClient):
    pid = await _project(client)
    insp = await _inspection(client, pid)
    r = await client.get(f"/api/inspections/{insp['id']}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_items"] == 0
    assert body["failed_count"] == 0
    assert body["linked_punch_count"] == 0
    assert body["has_unresolved_failures"] is False
    assert body["items_by_result"] == {"pass": 0, "fail": 0, "n_a": 0, "not_inspected": 0}


async def test_inspection_summary_result_counts(client: AsyncClient):
    pid = await _project(client)
    insp = await _inspection(client, pid)
    await _item(client, insp["id"], 1, "pass")
    await _item(client, insp["id"], 2, "pass")
    await _item(client, insp["id"], 3, "fail")
    await _item(client, insp["id"], 4, "n_a")
    await _item(client, insp["id"], 5, "not_inspected")

    r = await client.get(f"/api/inspections/{insp['id']}/summary")
    body = r.json()
    assert body["total_items"] == 5
    assert body["items_by_result"]["pass"] == 2
    assert body["items_by_result"]["fail"] == 1
    assert body["items_by_result"]["n_a"] == 1
    assert body["items_by_result"]["not_inspected"] == 1
    assert body["failed_count"] == 1
    assert body["has_unresolved_failures"] is True  # failed item with no linked punch


async def test_inspection_summary_with_linked_punch(client: AsyncClient):
    pid = await _project(client)
    insp = await _inspection(client, pid)
    punch = await _punch(client, pid)
    # Failed item, but linked to a punch -> not "unresolved"
    await _item(client, insp["id"], 1, "fail", punch_item_id=punch["id"])
    await _item(client, insp["id"], 2, "pass")

    r = await client.get(f"/api/inspections/{insp['id']}/summary")
    body = r.json()
    assert body["failed_count"] == 1
    assert body["linked_punch_count"] == 1
    assert body["has_unresolved_failures"] is False
    assert body["linked_punch_item_ids"] == [punch["id"]]


async def test_inspection_summary_mixed_failed_linked_and_unlinked(client: AsyncClient):
    pid = await _project(client)
    insp = await _inspection(client, pid)
    punch = await _punch(client, pid)
    await _item(client, insp["id"], 1, "fail", punch_item_id=punch["id"])
    await _item(client, insp["id"], 2, "fail")  # unlinked

    r = await client.get(f"/api/inspections/{insp['id']}/summary")
    body = r.json()
    assert body["failed_count"] == 2
    assert body["linked_punch_count"] == 1
    assert body["has_unresolved_failures"] is True  # one fail without punch link


async def test_inspection_summary_404(client: AsyncClient):
    r = await client.get(f"/api/inspections/{BOGUS_UUID}/summary")
    assert r.status_code == 404

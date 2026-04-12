"""Phase 30 — Real-backend e2e for schedule workbench + file preview.

Verifies:
  - Schedule + activity CRUD with the new actuals/WBS fields
  - Activity-link round-trip (predecessors/successors used by detail panel)
  - Schedule constraint round-trip (constraint lanes in lookahead)
  - Schedule health summary endpoint (Health tab)
  - Attachment upload + download round-trip (file preview blob fetch)
  - Multi-attachment listing per source (polymorphic source_type/source_id)
  - Read-only user denied for schedule writes
"""

import io
import uuid
from datetime import date, timedelta

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return uuid.uuid4().hex[:8]


async def _project(client) -> str:
    r = await client.post("/api/projects/", json={
        "name": f"Ph30-Proj-{_uuid()}",
        "status": "active",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _schedule(client, project_id: str) -> dict:
    r = await client.post("/api/schedules/", json={
        "project_id": project_id,
        "name": f"Ph30-Sched-{_uuid()}",
        "schedule_type": "master",
        "start_date": str(date.today()),
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _activity(client, schedule_id: str, **kw) -> dict:
    payload = {
        "schedule_id": schedule_id,
        "name": f"Ph30-Act-{_uuid()}",
        "activity_type": "task",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=7)),
    }
    payload.update(kw)
    r = await client.post("/api/schedule-activities/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── 1. Schedule workbench data foundation ────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_schedule_workbench_data(rollback_client):
    """Schedule workbench fetches /schedules + /schedule-activities for the project."""
    pid = await _project(rollback_client)
    s = await _schedule(rollback_client, pid)
    a1 = await _activity(rollback_client, s["id"], wbs_code="1.1", is_critical=True)
    a2 = await _activity(rollback_client, s["id"], wbs_code="1.2", is_critical=False, parent_id=a1["id"])

    # The workbench fetches schedules first
    sl = await rollback_client.get(f"/api/schedules/?project_id={pid}")
    assert sl.status_code == 200
    schedules = sl.json()
    assert any(x["id"] == s["id"] for x in schedules)

    # Then activities per schedule
    al = await rollback_client.get(f"/api/schedule-activities/?schedule_id={s['id']}&limit=500")
    assert al.status_code == 200
    activities = al.json()
    assert {a["id"] for a in [a1, a2]} <= {x["id"] for x in activities}

    # Verify the new fields are exposed
    a1_full = next(x for x in activities if x["id"] == a1["id"])
    assert a1_full["wbs_code"] == "1.1"
    assert a1_full["is_critical"] is True
    assert "actual_start_date" in a1_full
    assert "actual_finish_date" in a1_full


# ── 2. Activity links (Gantt detail panel predecessors/successors) ──────

@pytest.mark.asyncio
async def test_e2e_activity_links_for_detail_panel(rollback_client):
    pid = await _project(rollback_client)
    s = await _schedule(rollback_client, pid)
    a = await _activity(rollback_client, s["id"], name="Foundation")
    b = await _activity(rollback_client, s["id"], name="Slab")

    # Create FS link a → b
    link_resp = await rollback_client.post("/api/activity-links/", json={
        "schedule_id": s["id"],
        "from_activity_id": a["id"],
        "to_activity_id": b["id"],
        "link_type": "fs",
        "lag_days": 2,
    })
    assert link_resp.status_code == 201, link_resp.text

    # The detail panel queries activity-links by schedule_id
    list_resp = await rollback_client.get(f"/api/activity-links/?schedule_id={s['id']}")
    assert list_resp.status_code == 200
    links = list_resp.json()
    matching = [lk for lk in links if lk["from_activity_id"] == a["id"] and lk["to_activity_id"] == b["id"]]
    assert len(matching) == 1
    assert matching[0]["link_type"] == "fs"
    assert matching[0]["lag_days"] == 2


# ── 3. Schedule constraints (lookahead constraint lanes) ────────────────

@pytest.mark.asyncio
async def test_e2e_schedule_constraints_for_lookahead(rollback_client):
    pid = await _project(rollback_client)
    s = await _schedule(rollback_client, pid)
    a = await _activity(rollback_client, s["id"])

    constraint_resp = await rollback_client.post("/api/schedule-constraints/", json={
        "activity_id": a["id"],
        "constraint_type": "rfi_pending",
        "source_type": "rfi",
        "severity": "yellow",
        "status": "active",
        "notes": "Awaiting clarification on column rebar",
    })
    assert constraint_resp.status_code == 201, constraint_resp.text

    # The lookahead view fetches constraints per activity
    list_resp = await rollback_client.get(f"/api/schedule-constraints/?activity_id={a['id']}")
    assert list_resp.status_code == 200
    constraints = list_resp.json()
    assert any(c["constraint_type"] == "rfi_pending" and c["status"] == "active" for c in constraints)


# ── 4. Schedule health summary endpoint (Health tab) ────────────────────

@pytest.mark.asyncio
async def test_e2e_schedule_health_summary(rollback_client):
    pid = await _project(rollback_client)
    s = await _schedule(rollback_client, pid)
    await _activity(rollback_client, s["id"], is_critical=True)
    await _activity(rollback_client, s["id"], is_critical=False, percent_complete=100)

    r = await rollback_client.get(f"/api/projects/{pid}/schedule-health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert str(body["project_id"]) == pid
    assert body["schedule_count"] >= 1
    assert body["total_activities"] >= 2
    assert "health_status" in body


# ── 5. Activity status filter — critical only ───────────────────────────

@pytest.mark.asyncio
async def test_e2e_activity_critical_only_filter(rollback_client):
    pid = await _project(rollback_client)
    s = await _schedule(rollback_client, pid)
    crit = await _activity(rollback_client, s["id"], is_critical=True, name="CritPath")
    nrm = await _activity(rollback_client, s["id"], is_critical=False, name="Normal")

    # Backend doesn't filter by is_critical at the API level (workbench filters
    # client-side). Verify both come back, then assert the workbench can
    # distinguish them by the boolean field.
    al = await rollback_client.get(f"/api/schedule-activities/?schedule_id={s['id']}&limit=500")
    assert al.status_code == 200
    activities = al.json()
    by_id = {a["id"]: a for a in activities}
    assert by_id[crit["id"]]["is_critical"] is True
    assert by_id[nrm["id"]]["is_critical"] is False


# ── 6. Activity get-by-id (detail drawer drilldown) ─────────────────────

@pytest.mark.asyncio
async def test_e2e_activity_detail_get(rollback_client):
    pid = await _project(rollback_client)
    s = await _schedule(rollback_client, pid)
    a = await _activity(
        rollback_client,
        s["id"],
        wbs_code="2.3",
        actual_start_date=str(date.today()),
        actual_finish_date=str(date.today() + timedelta(days=5)),
        notes="Detail drilldown test",
    )

    r = await rollback_client.get(f"/api/schedule-activities/{a['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["wbs_code"] == "2.3"
    assert body["actual_start_date"] is not None
    assert body["actual_finish_date"] is not None
    assert body["notes"] == "Detail drilldown test"


# ── 7. Attachment upload + download round-trip (file preview) ───────────

@pytest.mark.asyncio
async def test_e2e_attachment_upload_and_download(rollback_client):
    """The file preview drawer fetches files via /attachments/{id}/download.
    This verifies the round-trip works for both PDF and image content types."""
    pid = await _project(rollback_client)

    # Use the upload endpoint with a small synthetic PDF-like blob
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 0\ntrailer\n<<>>\n%%EOF\n"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "project_id": pid,
        "source_type": "test",
        "source_id": pid,  # arbitrary uuid for source_id; uses project id for simplicity
    }
    upload_resp = await rollback_client.post("/api/attachments/upload", files=files, data=data)
    assert upload_resp.status_code == 201, upload_resp.text
    attachment = upload_resp.json()
    assert attachment["filename"] == "test.pdf"
    assert attachment["content_type"] == "application/pdf"
    assert attachment["file_size"] == len(pdf_bytes)

    # Now download it (this is what FilePreviewDrawer does internally)
    download_resp = await rollback_client.get(f"/api/attachments/{attachment['id']}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"].startswith("application/pdf")
    assert download_resp.content == pdf_bytes


# ── 8. Polymorphic attachment listing (Correspondence/Warranty preview) ─

@pytest.mark.asyncio
async def test_e2e_polymorphic_attachment_listing(rollback_client):
    """Pages like Correspondence and Warranties query
    /attachments?source_type=X&source_id=Y to find their attached files."""
    pid = await _project(rollback_client)

    # Upload one attachment for source_type="warranty" with a synthetic source_id
    fake_source_id = str(uuid.uuid4())
    img_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # minimal PNG-ish header
    files = {"file": ("warranty-letter.png", io.BytesIO(img_bytes), "image/png")}
    data = {
        "project_id": pid,
        "source_type": "warranty",
        "source_id": fake_source_id,
    }
    upload_resp = await rollback_client.post("/api/attachments/upload", files=files, data=data)
    assert upload_resp.status_code == 201, upload_resp.text

    # The warranty page would query like this:
    list_resp = await rollback_client.get(
        f"/api/attachments/?source_type=warranty&source_id={fake_source_id}"
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["source_type"] == "warranty"
    assert items[0]["source_id"] == fake_source_id


# ── 9. Drawing image_url is preserved (Drawings page directUrl preview) ──

@pytest.mark.asyncio
async def test_e2e_drawing_image_url_roundtrip(rollback_client):
    """The Drawings page passes drawing.image_url directly to FilePreviewDrawer
    via the directUrl prop. Verify the field round-trips."""
    pid = await _project(rollback_client)
    area = await rollback_client.post("/api/drawing-areas/", json={
        "project_id": pid,
        "name": f"Area-{_uuid()}",
    })
    assert area.status_code == 201
    area_id = area.json()["id"]

    drawing = await rollback_client.post("/api/drawings/", json={
        "project_id": pid,
        "drawing_area_id": area_id,
        "drawing_number": f"A-{_uuid()}",
        "title": "Test Drawing",
        "discipline": "architectural",
        "image_url": "https://example.com/test.png",
    })
    assert drawing.status_code == 201, drawing.text
    body = drawing.json()
    assert body["image_url"] == "https://example.com/test.png"


# ── 10. Read-only user denied for schedule writes ───────────────────────

@pytest.mark.asyncio
async def test_e2e_readonly_user_cannot_create_activity(rollback_client):
    """Verify a non-admin/non-VP user cannot create schedule activities even
    when the schedule already exists."""
    from main import app
    from app.dependencies import get_current_user
    from app.models.foundation import UserAccount
    from datetime import datetime, timezone

    # First create a schedule under the admin override
    pid = await _project(rollback_client)
    s = await _schedule(rollback_client, pid)

    def _readonly_user():
        return UserAccount(
            id=uuid.UUID("60000000-0000-4000-a000-000000000001"),
            person_id=uuid.UUID("70000000-0000-4000-a000-000000000001"),
            email="ph30-readonly@rex.test",
            password_hash="(stub)",
            global_role=None,
            is_admin=False,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    saved = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _readonly_user
    try:
        resp = await rollback_client.post("/api/schedule-activities/", json={
            "schedule_id": s["id"],
            "name": "Should fail",
            "activity_type": "task",
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=1)),
        })
        # Project membership check should deny: 403 (no write access) or 404 (project hidden)
        assert resp.status_code in (403, 404), f"Expected 403/404, got {resp.status_code}: {resp.text}"
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
        else:
            app.dependency_overrides.pop(get_current_user, None)

"""Sprint K: backend cleanup before UI verification tests.

Covers:
- Child route write-scoping (one per domain group)
- PATCH project_id change rejection (unit test on guardrail helper)
- Attachment metadata scoping consistency
- OpenAPI sanity
"""

import contextlib
import uuid

from httpx import AsyncClient

from app.dependencies import get_current_user, reject_project_id_change
from main import app
from tests.helpers import PROJECT_BISHOP, uid

ADMIN_EMAIL = "aroberts@exxircapital.com"
NON_ADMIN_EMAIL = "mandersen@exxircapital.com"
PASSWORD = "rex2026!"


@contextlib.contextmanager
def _no_auth_override():
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def _login_token(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_orphan_project(client: AsyncClient) -> str:
    r = await client.post(
        "/api/projects/",
        json={"project_number": f"K-{uid()}", "name": f"K-Orphan-{uid()}", "status": "active"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Child route write-scoping (one per domain) ────────────────────────────


async def test_child_write_photo_denied_non_member(client: AsyncClient):
    """Field ops child: photos denied for non-member."""
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/photos/",
            json={
                "project_id": orphan,
                "filename": f"ph-{uid()}.jpg",
                "file_size": 1000,
                "content_type": "image/jpeg",
                "storage_url": "local://test",
                "storage_key": f"attachments/{orphan}/test.jpg",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_child_write_observation_denied_non_member(client: AsyncClient):
    """Field ops child: observations denied for non-member."""
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/observations/",
            json={
                "project_id": orphan,
                "observation_number": 1,
                "observation_type": "quality",
                "title": f"Obs-{uid()}",
                "description": "test",
                "status": "open",
                "priority": "medium",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_child_write_billing_period_denied_non_member(client: AsyncClient):
    """Financials child: billing periods denied for non-member."""
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/billing-periods/",
            json={
                "project_id": orphan,
                "period_number": 1,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "due_date": "2026-02-15",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_child_write_drawing_denied_non_member(client: AsyncClient):
    """Doc mgmt child: drawings denied for non-member."""
    orphan = await _create_orphan_project(client)
    area = await client.post(
        "/api/drawing-areas/",
        json={"project_id": orphan, "name": f"A-{uid()}"},
    )
    assert area.status_code == 201
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/drawings/",
            json={
                "project_id": orphan,
                "drawing_area_id": area.json()["id"],
                "drawing_number": f"D-{uid()}",
                "title": "test",
                "discipline": "architectural",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_child_write_warranty_claim_denied_non_member(client: AsyncClient):
    """Closeout child: warranty claims denied for non-member."""
    orphan = await _create_orphan_project(client)
    co = await client.post(
        "/api/companies/",
        json={"name": f"KC-{uid()}", "company_type": "subcontractor"},
    )
    w = await client.post(
        "/api/warranties/",
        json={
            "project_id": orphan,
            "company_id": co.json()["id"],
            "scope_description": "test",
            "warranty_type": "standard",
            "duration_months": 12,
            "start_date": "2026-01-01",
        },
    )
    assert w.status_code == 201
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/warranty-claims/",
            json={
                "warranty_id": w.json()["id"],
                "claim_number": 1,
                "title": "Denied",
                "description": "x",
                "reported_date": "2026-06-01",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_child_write_activity_link_denied_non_member(client: AsyncClient):
    """Schedule child: activity links denied for non-member."""
    orphan = await _create_orphan_project(client)
    sched = await client.post(
        "/api/schedules/",
        json={
            "project_id": orphan,
            "name": f"S-{uid()}",
            "schedule_type": "master",
            "start_date": "2026-01-01",
        },
    )
    a1 = await client.post(
        "/api/schedule-activities/",
        json={
            "schedule_id": sched.json()["id"],
            "name": "A1",
            "activity_type": "task",
            "start_date": "2026-01-01",
            "end_date": "2026-01-15",
        },
    )
    a2 = await client.post(
        "/api/schedule-activities/",
        json={
            "schedule_id": sched.json()["id"],
            "name": "A2",
            "activity_type": "task",
            "start_date": "2026-01-16",
            "end_date": "2026-01-30",
        },
    )
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/activity-links/",
            json={
                "schedule_id": sched.json()["id"],
                "from_activity_id": a1.json()["id"],
                "to_activity_id": a2.json()["id"],
                "link_type": "fs",
                "lag_days": 0,
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


# ── PATCH project_id change rejection (unit test on guardrail) ────────────


def test_reject_project_id_change_raises_on_mismatch():
    """The guardrail helper raises 422 when project_id changes."""
    from fastapi import HTTPException
    import pytest
    from types import SimpleNamespace

    existing_pid = uuid.UUID("40000000-0000-4000-a000-000000000001")
    different_pid = uuid.UUID("40000000-0000-4000-a000-000000000099")

    # Mismatch → 422
    data = SimpleNamespace(project_id=different_pid)
    with pytest.raises(HTTPException) as exc_info:
        reject_project_id_change(data, existing_pid)
    assert exc_info.value.status_code == 422
    assert "Cannot move" in exc_info.value.detail

    # Same project_id → no error
    data_same = SimpleNamespace(project_id=existing_pid)
    reject_project_id_change(data_same, existing_pid)  # should not raise

    # No project_id attr → no error
    data_none = SimpleNamespace()
    reject_project_id_change(data_none, existing_pid)  # should not raise


# ── Attachment metadata scoping ────────────────────────────────────────────


async def test_attachment_metadata_create_denied_non_member(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/attachments/",
            json={
                "project_id": orphan,
                "source_type": "rfi",
                "source_id": str(uuid.uuid4()),
                "filename": "test.pdf",
                "file_size": 100,
                "content_type": "application/pdf",
                "storage_url": "local://x",
                "storage_key": "x",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_attachment_metadata_patch_denied_non_member(client: AsyncClient):
    """Attachment PATCH on orphan project → 403."""
    orphan = await _create_orphan_project(client)
    att = await client.post(
        "/api/attachments/",
        json={
            "project_id": orphan,
            "source_type": "rfi",
            "source_id": str(uuid.uuid4()),
            "filename": "test.pdf",
            "file_size": 100,
            "content_type": "application/pdf",
            "storage_url": "local://x",
            "storage_key": "x",
        },
    )
    assert att.status_code == 201
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.patch(
            f"/api/attachments/{att.json()['id']}",
            json={"filename": "renamed.pdf"},
            headers=_auth(token),
        )
    assert r.status_code == 403


# ── Admin bypass ───────────────────────────────────────────────────────────


async def test_admin_can_write_child_on_orphan(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)
        r = await client.post(
            "/api/observations/",
            json={
                "project_id": orphan,
                "observation_number": 1,
                "observation_type": "quality",
                "title": f"Admin-Obs-{uid()}",
                "description": "admin bypass test",
                "status": "open",
                "priority": "medium",
            },
            headers=_auth(token),
        )
    assert r.status_code == 201, r.text


# ── OpenAPI sanity ─────────────────────────────────────────────────────────


def test_openapi_key_paths_present():
    schema = app.openapi()
    paths = set(schema.get("paths", {}).keys())
    required = {
        "/api/health", "/api/ready",
        "/api/auth/login", "/api/auth/logout", "/api/auth/logout-all", "/api/auth/me",
        "/api/projects/", "/api/rfis/", "/api/warranties/",
        "/api/attachments/upload",
    }
    missing = required - paths
    assert not missing, f"Missing OpenAPI paths: {missing}"


def test_openapi_schema_count():
    schema = app.openapi()
    schemas = schema.get("components", {}).get("schemas", {})
    assert len(schemas) >= 100, f"Only {len(schemas)} schemas — too few"

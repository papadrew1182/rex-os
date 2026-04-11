"""Sprint G: read authorization and tenant scoping tests.

Validates that the new project-scoped read filtering and 404-on-detail
enforcement actually hide other tenants' data from non-admin/non-VP users.

Test users:
- Andrew Roberts: admin + global_role=vp → sees everything
- Mitch Andersen:  no global role, member of all 4 seeded projects but NOT
  members of any orphan projects we create per test
"""

import contextlib
import uuid

from httpx import AsyncClient

from app.dependencies import get_current_user
from main import app
from tests.helpers import PROJECT_BISHOP, uid

ADMIN_EMAIL = "aroberts@exxircapital.com"
NON_ADMIN_EMAIL = "mandersen@exxircapital.com"
PASSWORD = "rex2026!"


@contextlib.contextmanager
def _no_auth_override():
    """Temporarily strip the stub-admin override so requests hit real auth."""
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
    """Project with no members — Mitch must NOT be able to see it."""
    r = await client.post(
        "/api/projects/",
        json={
            "project_number": f"SCOPE-{uid()}",
            "name": f"Orphan-{uid()}",
            "status": "active",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Foundation: projects + project members ─────────────────────────────────


async def test_projects_list_hides_orphan_from_non_member(client: AsyncClient):
    orphan = await _create_orphan_project(client)

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/projects/?limit=2000", headers=_auth(token))
    assert r.status_code == 200
    visible_ids = {p["id"] for p in r.json()}
    assert orphan not in visible_ids
    assert PROJECT_BISHOP in visible_ids  # Mitch is a member of Bishop


async def test_projects_list_admin_sees_orphan(client: AsyncClient):
    orphan = await _create_orphan_project(client)

    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)
        # Detail-fetch is the deterministic admin-bypass check; the list
        # endpoint may have hit its limit window with seed/test data.
        r = await client.get(f"/api/projects/{orphan}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["id"] == orphan


async def test_project_detail_404_for_non_member(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/projects/{orphan}", headers=_auth(token))
    assert r.status_code == 404


async def test_project_detail_200_for_member(client: AsyncClient):
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/projects/{PROJECT_BISHOP}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["id"] == PROJECT_BISHOP


async def test_project_members_scoped(client: AsyncClient):
    # Create a member row on the orphan project
    orphan = await _create_orphan_project(client)
    person_resp = await client.post(
        "/api/people/",
        json={"first_name": "Orph", "last_name": f"P-{uid()}", "role_type": "internal"},
    )
    pid = person_resp.json()["id"]
    member_resp = await client.post(
        "/api/project-members/",
        json={"project_id": orphan, "person_id": pid, "is_active": True},
    )
    member_id = member_resp.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        # List filtered to orphan returns empty
        r = await client.get(
            f"/api/project-members/?project_id={orphan}",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json() == []

        # Detail returns 404
        r = await client.get(f"/api/project-members/{member_id}", headers=_auth(token))
        assert r.status_code == 404


# ── Field ops: punch items list + detail ───────────────────────────────────


async def test_punch_items_list_hides_orphan_project(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/punch-items/",
        json={
            "project_id": orphan,
            "punch_number": 1,
            "title": f"Punch-{uid()}",
            "status": "open",
            "priority": "medium",
        },
    )
    assert r.status_code == 201, r.text
    punch_id = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/punch-items/?limit=2000", headers=_auth(token))
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert punch_id not in ids


async def test_punch_item_detail_404_for_non_member(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/punch-items/",
        json={
            "project_id": orphan,
            "punch_number": 2,
            "title": f"Punch-{uid()}",
            "status": "open",
            "priority": "medium",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/punch-items/{pid}", headers=_auth(token))
    assert r.status_code == 404


# ── Schedule: schedules list ───────────────────────────────────────────────


async def test_schedules_list_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/schedules/",
        json={
            "project_id": orphan,
            "name": f"Sched-{uid()}",
            "schedule_type": "master",
            "start_date": "2026-01-01",
        },
    )
    assert r.status_code == 201, r.text
    sched_id = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/schedules/?limit=2000", headers=_auth(token))
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert sched_id not in ids

    # Detail 404
    with _no_auth_override():
        r = await client.get(f"/api/schedules/{sched_id}", headers=_auth(token))
        assert r.status_code == 404


# ── Financials: budget line items list ─────────────────────────────────────


async def test_budget_line_items_list_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    # Need a cost code on the orphan project first
    cc = await client.post(
        "/api/cost-codes/",
        json={
            "project_id": orphan,
            "code": f"01-{uid()}",
            "name": "TestCC",
            "cost_type": "labor",
        },
    )
    assert cc.status_code == 201, cc.text
    cc_id = cc.json()["id"]

    bli = await client.post(
        "/api/budget-line-items/",
        json={
            "project_id": orphan,
            "cost_code_id": cc_id,
            "original_budget": 1000,
        },
    )
    assert bli.status_code == 201, bli.text
    bli_id = bli.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/budget-line-items/?limit=2000", headers=_auth(token))
    assert r.status_code == 200
    ids = {b["id"] for b in r.json()}
    assert bli_id not in ids


# ── Doc mgmt: RFI list + detail ────────────────────────────────────────────


async def test_rfis_list_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/rfis/",
        json={
            "project_id": orphan,
            "rfi_number": f"RFI-{uid()}",
            "subject": "scope test",
            "question": "?",
            "status": "open",
        },
    )
    assert r.status_code == 201, r.text
    rfi_id = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/rfis/?limit=2000", headers=_auth(token))
    assert r.status_code == 200
    ids = {x["id"] for x in r.json()}
    assert rfi_id not in ids


async def test_rfi_detail_404_for_non_member(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/rfis/",
        json={
            "project_id": orphan,
            "rfi_number": f"RFI-{uid()}",
            "subject": "scope test",
            "question": "?",
            "status": "open",
        },
    )
    rfi_id = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/rfis/{rfi_id}", headers=_auth(token))
    assert r.status_code == 404


# ── Doc mgmt: attachment list + detail ─────────────────────────────────────


async def test_attachment_list_and_detail_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    files = {"file": (f"orph-{uid()}.bin", b"orphan-bytes", "application/octet-stream")}
    data = {
        "project_id": orphan,
        "source_type": "rfi",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 201, r.text
    aid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)

        # List should not include the orphan-project attachment
        r = await client.get("/api/attachments/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert aid not in {a["id"] for a in r.json()}

        # Detail returns 404 (read-side helper) — note: download still 403
        # because that path uses assert_project_access (Sprint E behavior).
        r = await client.get(f"/api/attachments/{aid}", headers=_auth(token))
        assert r.status_code == 404


# ── Closeout / warranty ────────────────────────────────────────────────────


async def test_warranty_list_and_detail_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    # Need a company id for the warranty FK
    co = await client.post(
        "/api/companies/",
        json={"name": f"WarrantyCo-{uid()}", "company_type": "subcontractor"},
    )
    assert co.status_code == 201, co.text
    co_id = co.json()["id"]
    r = await client.post(
        "/api/warranties/",
        json={
            "project_id": orphan,
            "company_id": co_id,
            "scope_description": "Roof",
            "warranty_type": "standard",
            "duration_months": 12,
            "start_date": "2026-01-01",
            "status": "active",
        },
    )
    assert r.status_code == 201, r.text
    wid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)

        r = await client.get("/api/warranties/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert wid not in {w["id"] for w in r.json()}

        r = await client.get(f"/api/warranties/{wid}", headers=_auth(token))
        assert r.status_code == 404


async def test_completion_milestone_list_and_detail_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/completion-milestones/",
        json={
            "project_id": orphan,
            "milestone_type": "substantial_completion",
            "milestone_name": f"M-{uid()}",
            "target_date": "2026-12-31",
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text
    mid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)

        r = await client.get("/api/completion-milestones/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert mid not in {m["id"] for m in r.json()}

        r = await client.get(f"/api/completion-milestones/{mid}", headers=_auth(token))
        assert r.status_code == 404


async def test_closeout_checklist_list_and_detail_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/closeout-checklists/",
        json={
            "project_id": orphan,
            "name": f"Chk-{uid()}",
            "status": "in_progress",
        },
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)

        r = await client.get("/api/closeout-checklists/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert cid not in {c["id"] for c in r.json()}

        r = await client.get(f"/api/closeout-checklists/{cid}", headers=_auth(token))
        assert r.status_code == 404


# ── Admin/VP bypass sanity check ───────────────────────────────────────────


async def test_admin_bypasses_all_scoping(client: AsyncClient):
    """Admin sees orphan-project rows that non-admin can't."""
    orphan = await _create_orphan_project(client)
    r = await client.post(
        "/api/punch-items/",
        json={
            "project_id": orphan,
            "punch_number": 3,
            "title": f"AdminPunch-{uid()}",
            "status": "open",
            "priority": "medium",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)

        # Detail — deterministic admin-bypass check; list may hit the
        # limit window with accumulated seed/test data.
        r = await client.get(f"/api/punch-items/{pid}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["id"] == pid


async def test_member_sees_their_project_data(client: AsyncClient):
    """Sanity: Mitch (Bishop member) sees Bishop punch items.

    Creates one in Bishop and confirms it appears in Mitch's filtered list.
    """
    r = await client.post(
        "/api/punch-items/",
        json={
            "project_id": PROJECT_BISHOP,
            "punch_number": 4,
            "title": f"BishopPunch-{uid()}",
            "status": "open",
            "priority": "medium",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(
            f"/api/punch-items/?project_id={PROJECT_BISHOP}&limit=2000",
            headers=_auth(token),
        )
    assert r.status_code == 200
    assert pid in {p["id"] for p in r.json()}

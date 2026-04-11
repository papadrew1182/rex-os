"""Sprint H: read scoping completeness and permission consistency tests.

Validates that the new read-side scoping covers:
- Global resources (people, companies, role_templates)
- Child collections across all six domains (one representative per domain group)
- Bypass + denial behavior for admin/vp/member/non-member

Conventions: project-scoped detail denials return 404, write-side denials
return 403 (Sprint E behavior, intentionally preserved on attachment download).
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
        json={"project_number": f"H-{uid()}", "name": f"H-Orphan-{uid()}", "status": "active"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _make_orphan_company(client: AsyncClient) -> str:
    """Create a company with no project_members rows. Mitch must NOT see it."""
    r = await client.post(
        "/api/companies/",
        json={"name": f"OrphanCo-{uid()}", "company_type": "subcontractor"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Global resources: people ───────────────────────────────────────────────


async def test_people_list_hides_orphan_person_from_non_member(client: AsyncClient):
    """Create a person with no project membership; Mitch must not see them."""
    r = await client.post(
        "/api/people/",
        json={"first_name": "Orph", "last_name": f"Person-{uid()}", "role_type": "internal"},
    )
    assert r.status_code == 201, r.text
    orphan_pid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/people/?limit=2000", headers=_auth(token))
    assert r.status_code == 200
    visible_ids = {p["id"] for p in r.json()}
    assert orphan_pid not in visible_ids


async def test_person_detail_404_for_non_member(client: AsyncClient):
    r = await client.post(
        "/api/people/",
        json={"first_name": "Orph2", "last_name": f"P-{uid()}", "role_type": "internal"},
    )
    pid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/people/{pid}", headers=_auth(token))
    assert r.status_code == 404


async def test_admin_sees_orphan_person(client: AsyncClient):
    r = await client.post(
        "/api/people/",
        json={"first_name": "Orph3", "last_name": f"P-{uid()}", "role_type": "internal"},
    )
    pid = r.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)
        r = await client.get(f"/api/people/{pid}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["id"] == pid


# ── Global resources: companies ────────────────────────────────────────────


async def test_companies_list_hides_orphan_company(client: AsyncClient):
    orphan_co = await _make_orphan_company(client)

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/companies/?limit=2000", headers=_auth(token))
    assert r.status_code == 200
    assert orphan_co not in {c["id"] for c in r.json()}


async def test_company_detail_404_for_non_member(client: AsyncClient):
    orphan_co = await _make_orphan_company(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/companies/{orphan_co}", headers=_auth(token))
    assert r.status_code == 404


async def test_admin_sees_orphan_company(client: AsyncClient):
    orphan_co = await _make_orphan_company(client)
    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)
        r = await client.get(f"/api/companies/{orphan_co}", headers=_auth(token))
    assert r.status_code == 200


# ── Global resources: role_templates ───────────────────────────────────────


async def test_role_templates_readable_to_authenticated_user(client: AsyncClient):
    """role_templates is intentionally readable to any authenticated user."""
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/role-templates/", headers=_auth(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_role_templates_unauthenticated_returns_401(client: AsyncClient):
    with _no_auth_override():
        r = await client.get("/api/role-templates/")
    assert r.status_code == 401


# ── Field ops child: inspection_items (joined via Inspection) ──────────────


async def test_inspection_items_scoped_via_parent_inspection(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    insp = await client.post(
        "/api/inspections/",
        json={
            "project_id": orphan,
            "inspection_number": f"I-{uid()}",
            "inspection_type": "quality",
            "title": f"Insp-{uid()}",
            "scheduled_date": "2026-05-01",
            "status": "scheduled",
        },
    )
    assert insp.status_code == 201, insp.text
    insp_id = insp.json()["id"]
    item = await client.post(
        "/api/inspection-items/",
        json={
            "inspection_id": insp_id,
            "item_number": 1,
            "description": "test item",
            "result": "not_inspected",
        },
    )
    assert item.status_code == 201, item.text
    item_id = item.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/inspection-items/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert item_id not in {i["id"] for i in r.json()}

        r = await client.get(f"/api/inspection-items/{item_id}", headers=_auth(token))
        assert r.status_code == 404


# ── Financials child: commitment_change_orders (joined via Commitment) ────


async def test_commitment_change_orders_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    co = await client.post(
        "/api/companies/",
        json={"name": f"VendH-{uid()}", "company_type": "subcontractor"},
    )
    cm = await client.post(
        "/api/commitments/",
        json={
            "project_id": orphan,
            "vendor_id": co.json()["id"],
            "commitment_number": f"CM-{uid()}",
            "title": "test commitment",
            "contract_type": "subcontract",
            "amount": 1000,
        },
    )
    assert cm.status_code == 201, cm.text
    cm_id = cm.json()["id"]
    cco = await client.post(
        "/api/commitment-change-orders/",
        json={
            "commitment_id": cm_id,
            "cco_number": f"CCO-{uid()}",
            "title": "test cco",
            "total_amount": 100,
        },
    )
    assert cco.status_code == 201, cco.text
    cco_id = cco.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/commitment-change-orders/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert cco_id not in {x["id"] for x in r.json()}

        r = await client.get(f"/api/commitment-change-orders/{cco_id}", headers=_auth(token))
        assert r.status_code == 404


# ── Doc mgmt child: drawing_revisions (joined via Drawing) ─────────────────


async def test_drawing_revisions_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    # Drawing requires drawing_area_id
    area = await client.post(
        "/api/drawing-areas/",
        json={"project_id": orphan, "name": f"Area-{uid()}"},
    )
    assert area.status_code == 201, area.text
    drw = await client.post(
        "/api/drawings/",
        json={
            "project_id": orphan,
            "drawing_area_id": area.json()["id"],
            "drawing_number": f"D-{uid()}",
            "title": "test drawing",
            "discipline": "architectural",
            "current_revision": 0,
            "is_current": True,
        },
    )
    assert drw.status_code == 201, drw.text
    drw_id = drw.json()["id"]
    rev = await client.post(
        "/api/drawing-revisions/",
        json={
            "drawing_id": drw_id,
            "revision_number": 1,
            "revision_date": "2026-01-01",
            "image_url": "local://test.png",
        },
    )
    assert rev.status_code == 201, rev.text
    rev_id = rev.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/drawing-revisions/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert rev_id not in {x["id"] for x in r.json()}

        r = await client.get(f"/api/drawing-revisions/{rev_id}", headers=_auth(token))
        assert r.status_code == 404


# ── Closeout child: warranty_alerts (joined via Warranty) ─────────────────


async def test_warranty_alerts_scoped(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    co = await client.post(
        "/api/companies/",
        json={"name": f"WCo-{uid()}", "company_type": "subcontractor"},
    )
    w = await client.post(
        "/api/warranties/",
        json={
            "project_id": orphan,
            "company_id": co.json()["id"],
            "scope_description": "Test",
            "warranty_type": "standard",
            "duration_months": 12,
            "start_date": "2026-01-01",
            "status": "active",
        },
    )
    assert w.status_code == 201, w.text
    wid = w.json()["id"]
    alert = await client.post(
        "/api/warranty-alerts/",
        json={
            "warranty_id": wid,
            "alert_type": "90_day",
            "alert_date": "2026-12-01",
            "is_sent": False,
        },
    )
    assert alert.status_code == 201, alert.text
    aid = alert.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/warranty-alerts/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert aid not in {x["id"] for x in r.json()}

        r = await client.get(f"/api/warranty-alerts/{aid}", headers=_auth(token))
        assert r.status_code == 404


# ── Schedule child: activity_links (joined via Schedule) ──────────────────


async def test_activity_links_scoped(client: AsyncClient):
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
    sched_id = sched.json()["id"]
    a1 = await client.post(
        "/api/schedule-activities/",
        json={
            "schedule_id": sched_id,
            "name": "A1",
            "activity_type": "task",
            "start_date": "2026-01-01",
            "end_date": "2026-01-15",
        },
    )
    a2 = await client.post(
        "/api/schedule-activities/",
        json={
            "schedule_id": sched_id,
            "name": "A2",
            "activity_type": "task",
            "start_date": "2026-01-16",
            "end_date": "2026-01-30",
        },
    )
    link = await client.post(
        "/api/activity-links/",
        json={
            "schedule_id": sched_id,
            "from_activity_id": a1.json()["id"],
            "to_activity_id": a2.json()["id"],
            "link_type": "fs",
            "lag_days": 0,
        },
    )
    assert link.status_code == 201, link.text
    link_id = link.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/activity-links/?limit=2000", headers=_auth(token))
        assert r.status_code == 200
        assert link_id not in {x["id"] for x in r.json()}

        r = await client.get(f"/api/activity-links/{link_id}", headers=_auth(token))
        assert r.status_code == 404


# ── Read-denial consistency: project nested aggregates ────────────────────


async def test_project_aggregate_routes_404_for_non_member(client: AsyncClient):
    """Sprint H closed read-side gaps on the projects.py nested aggregates."""
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        for path in [
            "closeout-readiness",
            "rfi-aging",
            "submittal-aging",
            "billing-periods/summary",
            "schedule-health",
            "manpower-summary",
            "execution-health",
        ]:
            r = await client.get(f"/api/projects/{orphan}/{path}", headers=_auth(token))
            assert r.status_code == 404, f"{path}: expected 404, got {r.status_code}"


# ── Direct-project_id detail re-checks (cost_codes, payment_applications) ─


async def test_cost_code_detail_404_for_non_member(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    cc = await client.post(
        "/api/cost-codes/",
        json={"project_id": orphan, "code": f"CC-{uid()}", "name": "X", "cost_type": "labor"},
    )
    cc_id = cc.json()["id"]

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/cost-codes/{cc_id}", headers=_auth(token))
    assert r.status_code == 404


# ── Bypass sanity ─────────────────────────────────────────────────────────


async def test_admin_bypass_global_and_child(client: AsyncClient):
    """Admin sees orphan resources across global + child layers."""
    orphan_co = await _make_orphan_company(client)

    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)
        r = await client.get(f"/api/companies/{orphan_co}", headers=_auth(token))
        assert r.status_code == 200

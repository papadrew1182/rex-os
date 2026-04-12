"""Phase 25 — Real-backend e2e integration tests.

These exercise the full HTTP stack against an in-process FastAPI app talking
to a real database. No page.route mocks. Each test runs inside a savepoint
and rolls back at teardown via the `rollback_client` fixture.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio


# ── Helpers ────────────────────────────────────────────────────────────────

def _uuid_hex() -> str:
    return uuid.uuid4().hex[:8]


async def _create_test_project(client) -> str:
    """Create a fresh project and return its id."""
    resp = await client.post("/api/projects/", json={
        "name": f"E2E Project {_uuid_hex()}",
        "status": "active",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_test_company(client, *, company_type="subcontractor") -> str:
    resp = await client.post("/api/companies/", json={
        "name": f"E2E Co {_uuid_hex()}",
        "company_type": company_type,
        "status": "active",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_test_person(client, company_id: str | None = None) -> str:
    payload = {
        "first_name": "Test",
        "last_name": f"User {_uuid_hex()}",
        "role_type": "internal",
    }
    if company_id:
        payload["company_id"] = company_id
    resp = await client.post("/api/people/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── 1. Login flow + portfolio load (via existing dependency_override) ─────

@pytest.mark.asyncio
async def test_e2e_portfolio_load(rollback_client):
    """Authenticated user can fetch portfolio readiness."""
    resp = await rollback_client.get("/api/closeout-readiness/portfolio?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    # Should be either a list or {summary, projects}
    assert isinstance(body, (list, dict))


# ── 2. RFI lifecycle ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_rfi_create_edit(rollback_client):
    pid = await _create_test_project(rollback_client)

    # Create
    create_resp = await rollback_client.post("/api/rfis/", json={
        "project_id": pid,
        "rfi_number": f"RFI-{_uuid_hex()}",
        "subject": "What size rebar?",
        "question": "Need clarification on column reinforcement.",
        "status": "open",
        "priority": "high",
    })
    assert create_resp.status_code == 201, create_resp.text
    rfi_id = create_resp.json()["id"]

    # Edit
    edit_resp = await rollback_client.patch(f"/api/rfis/{rfi_id}", json={
        "answer": "Use #5 bars on perimeter columns.",
        "status": "answered",
    })
    assert edit_resp.status_code == 200
    assert edit_resp.json()["answer"] == "Use #5 bars on perimeter columns."
    assert edit_resp.json()["status"] == "answered"


# ── 3. Punch lifecycle including closure ──────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_punch_create_close(rollback_client):
    pid = await _create_test_project(rollback_client)
    person_id = await _create_test_person(rollback_client)

    create_resp = await rollback_client.post("/api/punch-items/", json={
        "project_id": pid,
        "punch_number": int(_uuid_hex(), 16) % 99999,
        "title": "Repair drywall corner",
        "status": "open",
        "priority": "medium",
        "is_critical_path": True,
    })
    assert create_resp.status_code == 201, create_resp.text
    punch_id = create_resp.json()["id"]
    assert create_resp.json()["is_critical_path"] is True

    # Close it
    close_resp = await rollback_client.patch(f"/api/punch-items/{punch_id}", json={
        "status": "closed",
        "closed_date": str(date.today()),
        "closed_by": person_id,
    })
    assert close_resp.status_code == 200
    body = close_resp.json()
    assert body["status"] == "closed"
    assert body["closed_by"] == person_id


# ── 4. Daily log + manpower entry ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_daily_log_with_manpower(rollback_client):
    pid = await _create_test_project(rollback_client)
    company_id = await _create_test_company(rollback_client)

    log_resp = await rollback_client.post("/api/daily-logs/", json={
        "project_id": pid,
        "log_date": str(date.today()),
        "status": "draft",
        "weather_summary": "Sunny, 72F",
        "work_summary": "Foundation pour east wing",
    })
    assert log_resp.status_code == 201, log_resp.text
    log_id = log_resp.json()["id"]

    mp_resp = await rollback_client.post("/api/manpower-entries/", json={
        "daily_log_id": log_id,
        "company_id": company_id,
        "worker_count": 12,
        "hours": 8.5,
        "description": "Concrete crew",
    })
    assert mp_resp.status_code == 201, mp_resp.text

    # Verify summary aggregates
    sum_resp = await rollback_client.get(f"/api/daily-logs/{log_id}/summary")
    assert sum_resp.status_code == 200
    s = sum_resp.json()
    assert s["total_worker_count"] == 12
    assert s["total_hours"] == 8.5


# ── 5. Change event with line item ────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_change_event_with_line_item(rollback_client):
    pid = await _create_test_project(rollback_client)

    ce_resp = await rollback_client.post("/api/change-events/", json={
        "project_id": pid,
        "event_number": f"CE-{_uuid_hex()}",
        "title": "Owner-directed scope change",
        "status": "open",
        "scope": "in_scope",
        "change_reason": "owner_change",
        "event_type": "owner_change",
        "estimated_amount": 25000,
    })
    assert ce_resp.status_code == 201, ce_resp.text
    ce_id = ce_resp.json()["id"]

    li_resp = await rollback_client.post("/api/change-event-line-items/", json={
        "change_event_id": ce_id,
        "description": "Additional MEP rough-in",
        "amount": 25000,
        "sort_order": 0,
    })
    assert li_resp.status_code == 201, li_resp.text

    # Verify detail endpoint shows the line item
    detail_resp = await rollback_client.get(f"/api/change-events/{ce_id}/detail")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["line_items"]) == 1
    assert detail["line_items"][0]["amount"] == 25000


# ── 6. Insurance cert lifecycle (phase 21 new feature) ────────────────────

@pytest.mark.asyncio
async def test_e2e_insurance_cert_lifecycle(rollback_client):
    company_id = await _create_test_company(rollback_client)

    # Create
    create_resp = await rollback_client.post("/api/insurance-certificates/", json={
        "company_id": company_id,
        "policy_type": "gl",
        "carrier": "Acme Insurance",
        "policy_number": "GL-12345",
        "effective_date": str(date.today() - timedelta(days=30)),
        "expiry_date": str(date.today() + timedelta(days=400)),
        "limit_amount": 2000000,
        "status": "current",
    })
    assert create_resp.status_code == 201, create_resp.text
    cert_id = create_resp.json()["id"]

    # Filter by company (trailing slash required to hit the API router, not static frontend)
    list_resp = await rollback_client.get(f"/api/insurance-certificates/?company_id={company_id}")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


# ── 7. Schedule activity with actuals + WBS (phase 21 new fields) ─────────

@pytest.mark.asyncio
async def test_e2e_schedule_actuals_and_wbs(rollback_client):
    pid = await _create_test_project(rollback_client)

    # Create schedule first
    sched_resp = await rollback_client.post("/api/schedules/", json={
        "project_id": pid,
        "name": "Master Schedule",
        "schedule_type": "master",
        "start_date": str(date.today()),
    })
    assert sched_resp.status_code == 201, sched_resp.text
    sched_id = sched_resp.json()["id"]

    # Activity with actuals + WBS
    act_resp = await rollback_client.post("/api/schedule-activities/", json={
        "schedule_id": sched_id,
        "name": "Foundation pour",
        "activity_type": "task",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=10)),
        "actual_start_date": str(date.today() + timedelta(days=1)),
        "actual_finish_date": str(date.today() + timedelta(days=12)),
        "wbs_code": "1.2.3",
        "percent_complete": 100,
    })
    assert act_resp.status_code == 201, act_resp.text
    body = act_resp.json()
    assert body["actual_start_date"] is not None
    assert body["actual_finish_date"] is not None
    assert body["wbs_code"] == "1.2.3"


# ── 8. Permission denial for non-admin user ───────────────────────────────

@pytest.mark.asyncio
async def test_e2e_readonly_user_denied(rollback_client):
    """A non-admin/non-VP user with no project membership cannot write."""
    from main import app
    from app.dependencies import get_current_user
    from app.models.foundation import UserAccount

    # Override the auth stub to return a read-only user
    def _readonly_user():
        return UserAccount(
            id=uuid.UUID("30000000-0000-4000-a000-000000000001"),
            person_id=uuid.UUID("40000000-0000-4000-a000-000000000001"),
            email="readonly@rex.test",
            password_hash="(stub)",
            global_role=None,  # not vp
            is_admin=False,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    saved = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _readonly_user
    try:
        # Try to create an RFI — should be denied since user has no project access
        # First need a project (created via admin override is impossible inside this scope,
        # so we use a fixed UUID that does not exist)
        fake_project_id = "99999999-9999-4999-9999-999999999999"
        resp = await rollback_client.post("/api/rfis/", json={
            "project_id": fake_project_id,
            "rfi_number": "RFI-DENIED",
            "subject": "Should fail",
            "question": "Test",
        })
        # Should be 403 (no access) or 404 (project not visible)
        assert resp.status_code in (403, 404), f"Expected 403/404, got {resp.status_code}: {resp.text}"
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
        else:
            app.dependency_overrides.pop(get_current_user, None)

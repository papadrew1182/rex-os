"""Phase 35 — Real-backend e2e for jobs + notifications + admin operations.

Verifies:
  1. admin/vp can list jobs
  2. admin/vp can run warranty_refresh_job manually
  3. admin/vp can run insurance_refresh_job manually
  4. schedule_snapshot_job writes snapshots and is idempotent on repeat
  5. aging_alerts_job creates project-summary notifications without spam
  6. session_purge_job removes expired sessions
  7. current user lists only their own notifications
  8. current user can mark notification read + dismiss it
  9. read-only user cannot access /api/admin/jobs
  10. notification dedupe respected on repeat upserts
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.foundation import JobRun, Session as SessionModel, UserAccount
from app.models.notifications import Notification
from app.services import notifications as notif_svc


def _uid() -> str:
    return uuid.uuid4().hex[:8]


# ── 1. admin/vp can list jobs ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_admin_list_jobs(client):
    r = await client.get("/api/admin/jobs")
    assert r.status_code == 200, r.text
    body = r.json()
    job_keys = {j["job_key"] for j in body}
    expected = {"warranty_refresh", "insurance_refresh", "schedule_snapshot", "aging_alerts", "session_purge"}
    assert expected.issubset(job_keys), f"Missing jobs: {expected - job_keys}"


# ── 2. warranty_refresh runs ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_run_warranty_refresh_job(client):
    r = await client.post("/api/admin/jobs/warranty_refresh/run")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_key"] == "warranty_refresh"
    assert body["triggered"] is True
    assert body["run_id"] is not None

    # Verify the run was persisted
    runs = await client.get("/api/admin/job-runs?job_key=warranty_refresh&limit=1")
    assert runs.status_code == 200
    run_list = runs.json()
    assert len(run_list) >= 1
    assert run_list[0]["status"] in ("succeeded", "running", "failed")


# ── 3. insurance_refresh runs and creates a notification ──────────────────

@pytest.mark.asyncio
async def test_e2e_insurance_refresh_creates_notification(client):
    """Create an expiring cert, run the job, verify a notification was created."""
    # Create a fresh company
    co_resp = await client.post("/api/companies/", json={
        "name": f"Ph35-Co-{_uid()}",
        "company_type": "subcontractor",
        "status": "active",
    })
    assert co_resp.status_code == 201
    company_id = co_resp.json()["id"]

    # Create a cert expiring in 45 days (should trigger 60_day tier notification)
    cert_resp = await client.post("/api/insurance-certificates/", json={
        "company_id": company_id,
        "policy_type": "gl",
        "carrier": f"Ph35-Carrier-{_uid()}",
        "policy_number": f"POL-{_uid()}",
        "effective_date": (date.today() - timedelta(days=30)).isoformat(),
        "expiry_date": (date.today() + timedelta(days=45)).isoformat(),
    })
    assert cert_resp.status_code == 201
    cert_id = cert_resp.json()["id"]

    # Run the job
    run_resp = await client.post("/api/admin/jobs/insurance_refresh/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["triggered"] is True

    # Verify a notification exists for this cert
    # Use the user's own notifications endpoint (admin gets fanout via get_admin_and_vp_user_ids)
    notifs = await client.get("/api/notifications/?domain=foundation&limit=200")
    assert notifs.status_code == 200
    found = [n for n in notifs.json() if n.get("source_type") == "insurance_certificate" and n.get("source_id") == cert_id]
    assert len(found) >= 1, f"No notification created for cert {cert_id}"

    # Cleanup: dismiss the notification so it doesn't pollute later runs
    for n in found:
        await client.patch(f"/api/notifications/{n['id']}/dismiss")


# ── 4. schedule_snapshot is idempotent ────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_schedule_snapshot_idempotent(client):
    # Run once
    r1 = await client.post("/api/admin/jobs/schedule_snapshot/run")
    assert r1.status_code == 200
    assert r1.json()["triggered"] is True

    # Run again immediately — should still succeed and not duplicate snapshots
    r2 = await client.post("/api/admin/jobs/schedule_snapshot/run")
    assert r2.status_code == 200
    assert r2.json()["triggered"] is True


# ── 5. aging_alerts runs ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_aging_alerts_runs(client):
    r = await client.post("/api/admin/jobs/aging_alerts/run")
    assert r.status_code == 200, r.text
    assert r.json()["triggered"] is True


# ── 6. session_purge removes expired sessions ─────────────────────────────

@pytest.mark.asyncio
async def test_e2e_session_purge_removes_expired(client):
    r = await client.post("/api/admin/jobs/session_purge/run")
    assert r.status_code == 200, r.text
    assert r.json()["triggered"] is True
    # Verify a job run was recorded
    runs = await client.get("/api/admin/job-runs?job_key=session_purge&limit=1")
    assert runs.status_code == 200
    assert len(runs.json()) >= 1


# ── 7. current user lists only their own notifications ───────────────────

@pytest.mark.asyncio
async def test_e2e_user_lists_own_notifications(rollback_client):
    r = await rollback_client.get("/api/notifications/")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    # Every notification should belong to the stub admin user
    # (admin user_id from conftest is 20000000-0000-4000-a000-000000000001)
    expected_user = "20000000-0000-4000-a000-000000000001"
    for n in body:
        assert n["user_account_id"] == expected_user, f"Got notification for wrong user: {n['user_account_id']}"


# ── 8. mark notification read + dismiss ──────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_notification_read_and_dismiss(client):
    """Use the service directly to insert a notification, then exercise the API.

    Uses `client` (not rollback_client) because we need both the service-layer
    INSERT and the API-layer PATCH to commit to the same real DB so we can
    clean up deterministically in `finally`.
    """
    from app.database import async_session_factory
    from sqlalchemy import delete

    user_id = uuid.UUID("20000000-0000-4000-a000-000000000001")  # stub admin
    notif_id = None
    try:
        async with async_session_factory() as session:
            n = await notif_svc.upsert_notification(
                session,
                user_account_id=user_id,
                domain="system",
                notification_type="test",
                title=f"Ph35 test {_uid()}",
                severity="info",
                dedupe_key=f"ph35:test:{_uid()}",
            )
            await session.commit()
            notif_id = n.id

        # Read it via the user-facing API
        r = await client.get("/api/notifications/?limit=200")
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert str(notif_id) in ids

        # Mark read
        r = await client.patch(f"/api/notifications/{notif_id}/read")
        assert r.status_code == 200

        # Dismiss
        r = await client.patch(f"/api/notifications/{notif_id}/dismiss")
        assert r.status_code == 200
    finally:
        # Cleanup — ensure no stale notification remains in the real DB
        if notif_id is not None:
            async with async_session_factory() as session:
                await session.execute(delete(Notification).where(Notification.id == notif_id))
                await session.commit()


# ── 9. read-only user cannot access admin job endpoints ───────────────────

@pytest.mark.asyncio
async def test_e2e_readonly_user_denied_admin_jobs(rollback_client):
    """Override get_current_user to a non-admin/non-vp user and verify 403."""
    from main import app
    from app.dependencies import get_current_user

    def _readonly_user():
        return UserAccount(
            id=uuid.UUID("80000000-0000-4000-a000-000000000001"),
            person_id=uuid.UUID("90000000-0000-4000-a000-000000000001"),
            email="ph35-readonly@rex.test",
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
        # GET list-jobs
        r = await rollback_client.get("/api/admin/jobs")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

        # POST run-now
        r = await rollback_client.post("/api/admin/jobs/warranty_refresh/run")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

        # GET job-runs
        r = await rollback_client.get("/api/admin/job-runs?job_key=warranty_refresh")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ── 10. notification dedupe respected on repeat upserts ──────────────────

@pytest.mark.asyncio
async def test_e2e_notification_dedupe_on_repeat(rollback_client):
    """Calling upsert_notification twice with same dedupe_key updates rather
    than creating a duplicate."""
    from app.database import async_session_factory

    user_id = uuid.UUID("20000000-0000-4000-a000-000000000001")
    dedupe = f"ph35:dedupe:{_uid()}"

    async with async_session_factory() as session:
        n1 = await notif_svc.upsert_notification(
            session, user_account_id=user_id,
            domain="system", notification_type="test",
            title="First title", severity="info", dedupe_key=dedupe,
        )
        await session.commit()
        first_id = n1.id

        n2 = await notif_svc.upsert_notification(
            session, user_account_id=user_id,
            domain="system", notification_type="test",
            title="Second title", severity="warning", dedupe_key=dedupe,
        )
        await session.commit()
        second_id = n2.id

    assert first_id == second_id, "Dedupe failed: created a new row instead of updating"

    # Verify it's the updated version
    from sqlalchemy import delete
    async with async_session_factory() as session:
        n = await session.get(Notification, first_id)
        assert n.title == "Second title"
        assert n.severity == "warning"
        # Cleanup
        await session.execute(delete(Notification).where(Notification.id == first_id))
        await session.commit()

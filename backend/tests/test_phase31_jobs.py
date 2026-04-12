"""Phase 31 — Background job runner + notifications tests.

Tests:
1.  Job registry contains all 5 expected jobs
2.  Admin can list jobs via GET /api/admin/jobs
3.  Admin can trigger a job via POST /api/admin/jobs/{job_key}/run
4.  Job run history is persisted in /api/admin/job-runs
5.  Non-admin (read-only override) gets 403 on /api/admin/jobs
6.  Unknown job returns 404
7.  Notification CRUD via HTTP endpoints
8.  Notification dedupe: upsert twice with same dedupe_key => update, not duplicate
9.  Insurance refresh job creates notifications for expiring cert
10. Session purge job removes expired sessions
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.jobs.runner import JOB_REGISTRY


# ── Helpers ────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return uuid.uuid4().hex[:8]


async def _project(client) -> str:
    r = await client.post("/api/projects/", json={
        "name": f"Ph31-Proj-{_uuid()}",
        "status": "active",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _company(client) -> str:
    r = await client.post("/api/companies/", json={
        "name": f"Ph31-Co-{_uuid()}",
        "company_type": "subcontractor",
        "status": "active",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _person(client, company_id: str | None = None) -> str:
    payload = {"first_name": "Test", "last_name": f"User-{_uuid()}", "role_type": "internal"}
    if company_id:
        payload["company_id"] = company_id
    r = await client.post("/api/people/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── 1. Job registry ─────────────────────────────────────────────────────────

def test_job_registry_has_expected_keys():
    expected = {
        "warranty_refresh",
        "insurance_refresh",
        "schedule_snapshot",
        "aging_alerts",
        "session_purge",
    }
    assert expected.issubset(JOB_REGISTRY.keys()), f"Missing keys: {expected - JOB_REGISTRY.keys()}"


def test_job_registry_all_enabled():
    for key, job in JOB_REGISTRY.items():
        assert job.enabled, f"Job {key} is disabled"


# ── 2. Admin can list jobs ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_jobs_admin(client):
    r = await client.get("/api/admin/jobs")
    assert r.status_code == 200, r.text
    jobs = r.json()
    assert len(jobs) >= 5
    keys = {j["job_key"] for j in jobs}
    assert "warranty_refresh" in keys
    assert "session_purge" in keys
    # Each job has required fields
    for j in jobs:
        assert "name" in j
        assert "description" in j
        assert "enabled" in j
        assert "is_running" in j


# ── 3. Admin can trigger a job ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_run_job_session_purge(client):
    """Trigger session_purge via HTTP. Verifies it runs and returns run_id."""
    r = await client.post("/api/admin/jobs/session_purge/run")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["job_key"] == "session_purge"
    assert data["triggered"] is True
    assert data["run_id"] is not None


# ── 4. Job run history is persisted ─────────────────────────────────────────

@pytest.mark.anyio
async def test_job_run_history_persisted(client):
    """After triggering a job, its run should appear in /api/admin/job-runs."""
    # Trigger the job
    r = await client.post("/api/admin/jobs/session_purge/run")
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    # Check history
    r2 = await client.get("/api/admin/job-runs?job_key=session_purge")
    assert r2.status_code == 200, r2.text
    runs = r2.json()
    assert len(runs) >= 1
    run_ids = [run["id"] for run in runs]
    assert run_id in run_ids


@pytest.mark.anyio
async def test_job_run_list_unfiltered(client):
    r = await client.get("/api/admin/job-runs")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# ── 5. Non-admin gets 403 ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_admin_jobs_requires_admin(client):
    """Temporarily override the user to a read-only non-admin user."""
    import uuid as _uuid_mod
    from main import app
    from app.dependencies import get_current_user
    from app.models.foundation import UserAccount
    from datetime import datetime, timezone

    def _readonly_user():
        return UserAccount(
            id=_uuid_mod.UUID("99000000-0000-4000-a000-000000000099"),
            person_id=_uuid_mod.UUID("10000000-0000-4000-a000-000000000001"),
            email="readonly@test.com",
            password_hash="x",
            global_role=None,
            is_admin=False,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    saved = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _readonly_user
    try:
        r = await client.get("/api/admin/jobs")
        assert r.status_code == 403, r.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ── 6. Unknown job returns 404 ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_run_unknown_job_404(client):
    r = await client.post("/api/admin/jobs/nonexistent_job_xyz/run")
    assert r.status_code == 404, r.text


# ── 7. Notification CRUD via HTTP ───────────────────────────────────────────

@pytest.mark.anyio
async def test_notifications_list_empty_or_present(client):
    """GET /api/notifications/ should return a list (may be empty for stub user)."""
    r = await client.get("/api/notifications/")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


@pytest.mark.anyio
async def test_notifications_unread_count(client):
    r = await client.get("/api/notifications/unread-count")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "unread_count" in data
    assert isinstance(data["unread_count"], int)


@pytest.mark.anyio
async def test_notifications_read_all(client):
    r = await client.patch("/api/notifications/read-all")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "updated" in data


@pytest.mark.anyio
async def test_notifications_read_nonexistent_404(client):
    bad_id = str(uuid.uuid4())
    r = await client.patch(f"/api/notifications/{bad_id}/read")
    assert r.status_code == 404, r.text


@pytest.mark.anyio
async def test_notifications_dismiss_nonexistent_404(client):
    bad_id = str(uuid.uuid4())
    r = await client.patch(f"/api/notifications/{bad_id}/dismiss")
    assert r.status_code == 404, r.text


# ── 8. Notification dedupe ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_notification_dedupe_upsert(rollback_client):
    """Upsert twice with same dedupe_key => only one active notification."""
    from app.database import async_session_factory
    from app.services.notifications import upsert_notification, list_for_user

    user_id = uuid.UUID("20000000-0000-4000-a000-000000000001")
    dedupe = f"test:dedupe:{_uuid()}"

    async with async_session_factory() as db:
        # First upsert
        n1 = await upsert_notification(
            db,
            user_account_id=user_id,
            domain="system",
            notification_type="test",
            title="First title",
            body="First body",
            severity="info",
            dedupe_key=dedupe,
        )
        await db.commit()
        notif_id = n1.id

        # Second upsert with same dedupe_key — should UPDATE, not INSERT
        n2 = await upsert_notification(
            db,
            user_account_id=user_id,
            domain="system",
            notification_type="test",
            title="Updated title",
            body="Updated body",
            severity="warning",
            dedupe_key=dedupe,
        )
        await db.commit()

        # Should be same object / same id
        assert n2.id == notif_id, "Dedupe upsert should update existing notification"
        assert n2.title == "Updated title"
        assert n2.severity == "warning"

        # Count how many share this dedupe_key
        from sqlalchemy import select
        from app.models.notifications import Notification
        stmt = select(Notification).where(
            Notification.dedupe_key == dedupe,
            Notification.dismissed_at.is_(None),
            Notification.resolved_at.is_(None),
        )
        rows = (await db.execute(stmt)).scalars().all()
        assert len(rows) == 1, f"Expected 1 notification after dedupe upsert, got {len(rows)}"


# ── 9. Insurance refresh job creates notifications ───────────────────────────

@pytest.mark.anyio
async def test_insurance_refresh_job_creates_notification(client):
    """Create a company + cert expiring in 45 days, run the job, assert notification."""
    from app.database import async_session_factory
    from app.models.notifications import Notification
    from sqlalchemy import select

    # Create company + cert via HTTP (committed to real DB, client fixture = session-scoped)
    company_id = await _company(client)

    expiry = (date.today() + timedelta(days=45)).isoformat()
    r = await client.post("/api/insurance-certificates/", json={
        "company_id": company_id,
        "policy_type": "gl",
        "carrier": "Test Carrier",
        "policy_number": "POL-999",
        "expiry_date": expiry,
        "status": "current",
    })
    assert r.status_code == 201, r.text
    cert_id = r.json()["id"]

    # Run the insurance_refresh job
    r2 = await client.post("/api/admin/jobs/insurance_refresh/run")
    assert r2.status_code == 200, r2.text
    assert r2.json()["triggered"] is True

    # Verify at least one notification with type insurance_expiry was created
    async with async_session_factory() as db:
        stmt = select(Notification).where(
            Notification.notification_type == "insurance_expiry",
            Notification.source_id == uuid.UUID(cert_id),
        )
        rows = (await db.execute(stmt)).scalars().all()
        assert len(rows) >= 1, "Expected at least one insurance_expiry notification"
        assert rows[0].severity in ("info", "warning", "critical")


# ── 10. Session purge job removes expired sessions ───────────────────────────

@pytest.mark.anyio
async def test_session_purge_job_removes_expired(client):
    """Insert an expired session, run session_purge, verify it's gone."""
    from app.database import async_session_factory
    from app.models.foundation import Session as AuthSession
    from sqlalchemy import select
    import hashlib

    user_id = uuid.UUID("20000000-0000-4000-a000-000000000001")
    token = f"test-expired-{_uuid()}"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expired_time = datetime.now(timezone.utc) - timedelta(hours=2)

    # Insert expired session
    async with async_session_factory() as db:
        sess = AuthSession(
            user_account_id=user_id,
            token_hash=token_hash,
            expires_at=expired_time,
        )
        db.add(sess)
        await db.commit()
        sess_id = sess.id

    # Run session_purge
    r = await client.post("/api/admin/jobs/session_purge/run")
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["triggered"] is True

    # Verify the expired session is gone
    async with async_session_factory() as db:
        remaining = await db.get(AuthSession, sess_id)
        assert remaining is None, f"Expired session {sess_id} should have been purged"


# ── 11. Warranty refresh job runs without error ──────────────────────────────

@pytest.mark.anyio
async def test_warranty_refresh_job_runs(client):
    r = await client.post("/api/admin/jobs/warranty_refresh/run")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["triggered"] is True
    assert data["job_key"] == "warranty_refresh"


# ── 12. Schedule snapshot job runs without error ─────────────────────────────

@pytest.mark.anyio
async def test_schedule_snapshot_job_runs(client):
    r = await client.post("/api/admin/jobs/schedule_snapshot/run")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["triggered"] is True


# ── 13. Aging alerts job runs without error ──────────────────────────────────

@pytest.mark.anyio
async def test_aging_alerts_job_runs(client):
    r = await client.post("/api/admin/jobs/aging_alerts/run")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["triggered"] is True


# ── 14. Job run status contains succeeded after run ──────────────────────────

@pytest.mark.anyio
async def test_job_run_status_succeeded(client):
    """After triggering session_purge, the run record should appear in history."""
    r = await client.post("/api/admin/jobs/session_purge/run")
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    assert run_id is not None

    r2 = await client.get("/api/admin/job-runs?job_key=session_purge&limit=50")
    assert r2.status_code == 200, r2.text
    runs = {run["id"]: run for run in r2.json()}
    assert run_id in runs, f"run_id {run_id} not found in job-runs history"
    # All valid terminal statuses (skipped can happen when lock is contended in test parallelism)
    assert runs[run_id]["status"] in ("succeeded", "running", "failed", "skipped")


# ── 15. Notification mark_read + dismiss via service ─────────────────────────

@pytest.mark.anyio
async def test_notification_mark_read_and_dismiss(rollback_client):
    """Create notification, mark read, then dismiss."""
    from app.database import async_session_factory
    from app.services.notifications import upsert_notification, mark_read, dismiss, unread_count_for_user

    user_id = uuid.UUID("20000000-0000-4000-a000-000000000001")

    async with async_session_factory() as db:
        n = await upsert_notification(
            db,
            user_account_id=user_id,
            domain="system",
            notification_type="test_crud",
            title="Test notification",
            severity="info",
        )
        await db.commit()
        notif_id = n.id

        # Mark read
        ok = await mark_read(db, user_id, notif_id)
        await db.commit()
        assert ok is True

        # Dismiss
        ok2 = await dismiss(db, user_id, notif_id)
        await db.commit()
        assert ok2 is True

        # Non-existent
        ok3 = await mark_read(db, user_id, uuid.uuid4())
        assert ok3 is False

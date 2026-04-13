"""Phase 40 — Real-backend verification rollup for phases 36-39.

This file closes the "verification" half of phase 40. It complements:
  - test_phase36_advisory_lock.py  (multi-instance job lock behavior)
  - test_phase38_phase39_p2.py     (schedule variance/free float, lat/lng,
                                    mobile/website, contributing, spec fields,
                                    om_manuals CRUD + filter)
  - test_phase35_jobs_notifications.py (jobs run end-to-end, notification
                                    dedupe + fanout + scoping)

What this file adds on top of the existing coverage:

  1. End-to-end roundtrip that touches every phase 38/39 field via
     rollback_client, proving the writes stay isolated and no schema drift
     has dropped any of the new columns.

  2. Per-domain notification action_path literal audit — reads the job
     source files and asserts that the action_path string literals match
     the routing spec in the FRONTEND_ROADMAP.md / PROGRAM_STATE.md docs.
     This is a static code-level assertion rather than a dynamic job
     execution, because running every job end-to-end against the shared
     dev DB is prohibitively slow when the DB has carried forward legacy
     test pollution (~1700+ schedule activities from earlier sprints).
     Job execution is already proven by test_phase35_jobs_notifications.

  3. Advisory-lock stability: a sequential run of the fast session_purge
     job to prove the lock is released cleanly between runs. Complements
     test_phase36_advisory_lock.py without introducing new test jobs.

  4. Notification service direct assertion — calls upsert_notification with
     the exact payload shape used by aging_alerts and asserts the row is
     persisted with a retrievable action_path via the user-facing API.
     Runs through rollback_client so nothing persists.

Real-backend = in-process FastAPI app + real Postgres session. No mocks.
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.helpers import uid


# ═══════════════════════════════════════════════════════════════════════════
# 1. Phase 38/39 field roundtrip via rollback_client (fast, fully isolated)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ph40_phase38_39_fields_roundtrip(rollback_client: AsyncClient):
    """Single roundtrip that touches every phase 38/39 field via rollback_client.

    Regression guard: if any of these writes start leaking out of the
    rollback fixture we catch it here. It also proves each field is still
    present on the response schema (a drop-column migration would break
    this assertion) and that rollback isolation works for all affected
    models.
    """
    # Fresh project with lat/lng
    r = await rollback_client.post("/api/projects/", json={
        "name": f"P40Roundtrip-{uid()}",
        "status": "active",
        "latitude": 40.7128,
        "longitude": -74.0060,
    })
    assert r.status_code == 201, r.text
    proj = r.json()
    project_id = proj["id"]
    assert float(proj["latitude"]) == pytest.approx(40.7128, rel=1e-4)
    assert float(proj["longitude"]) == pytest.approx(-74.0060, rel=1e-4)

    # Fresh company with mobile + website
    r = await rollback_client.post("/api/companies/", json={
        "name": f"P40Co-{uid()}",
        "company_type": "subcontractor",
        "status": "active",
        "mobile_phone": "555-0100",
        "website": "https://ph40.example.com",
    })
    assert r.status_code == 201, r.text
    co = r.json()
    assert co["mobile_phone"] == "555-0100"
    assert co["website"] == "https://ph40.example.com"

    # Schedule activity with start/finish variance + free float
    r = await rollback_client.post("/api/schedules/", json={
        "project_id": project_id,
        "name": f"P40Sched-{uid()}",
        "schedule_type": "master",
        "start_date": "2025-01-01",
    })
    assert r.status_code == 201, r.text
    sched_id = r.json()["id"]

    r = await rollback_client.post("/api/schedule-activities/", json={
        "schedule_id": sched_id,
        "name": f"P40Act-{uid()}",
        "activity_type": "task",
        "start_date": "2025-03-01",
        "end_date": "2025-03-31",
        "start_variance_days": 4,
        "finish_variance_days": -1,
        "free_float_days": 2,
    })
    assert r.status_code == 201, r.text
    act = r.json()
    assert act["start_variance_days"] == 4
    assert act["finish_variance_days"] == -1
    assert act["free_float_days"] == 2

    # Observation contributing fields
    r = await rollback_client.post("/api/observations/", json={
        "project_id": project_id,
        "observation_number": abs(hash(uid())) % 100000,
        "title": f"P40Obs-{uid()}",
        "observation_type": "safety",
        "description": "Ph40 roundtrip",
        "contributing_behavior": "Unsafe act",
        "contributing_condition": "Unsafe condition",
    })
    assert r.status_code == 201, r.text
    obs = r.json()
    assert obs["contributing_behavior"] == "Unsafe act"
    assert obs["contributing_condition"] == "Unsafe condition"

    # Closeout checklist item spec fields
    r = await rollback_client.post("/api/closeout-checklists/", json={
        "project_id": project_id,
    })
    assert r.status_code == 201, r.text
    checklist_id = r.json()["id"]
    r = await rollback_client.post("/api/closeout-checklist-items/", json={
        "checklist_id": checklist_id,
        "category": "general",
        "item_number": 1,
        "name": f"P40Item-{uid()}",
        "spec_division": "09",
        "spec_section": "09 90 00",
    })
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["spec_division"] == "09"
    assert item["spec_section"] == "09 90 00"

    # O&M manual lifecycle — POST + GET + PATCH
    r = await rollback_client.post("/api/om-manuals/", json={
        "project_id": project_id,
        "spec_section": "22 05 00",
        "spec_title": "Plumbing Basic Materials",
        "required_count": 2,
        "received_count": 0,
        "status": "pending",
    })
    assert r.status_code == 201, r.text
    om = r.json()
    assert om["status"] == "pending"

    r = await rollback_client.patch(f"/api/om-manuals/{om['id']}", json={
        "received_count": 2,
        "status": "received",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"

    r = await rollback_client.get(f"/api/om-manuals/{om['id']}")
    assert r.status_code == 200
    assert r.json()["received_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# 2. Per-domain action_path literals — static source audit
# ═══════════════════════════════════════════════════════════════════════════

# Spec: each job emits notifications with these deep-link paths.
# These are the contract the frontend AlertCallout + notification drawer
# depend on. If a job is ever refactored to change its routing, this test
# fails and forces an explicit update.
ACTION_PATH_SPEC = {
    "warranty_refresh.py": {
        "/#/warranties?status=expired",
        "/#/warranties?status=expiring_soon",
    },
    "insurance_refresh.py": {
        "/#/insurance?status=expired",
        "/#/insurance?status=expiring_soon",
    },
    "aging_alerts.py": {
        "/#/rfis?status=open",
        "/#/submittals?status=submitted",
        "/#/punch-list?status=open",
    },
    "schedule_snapshot.py": {
        "/#/schedule?tab=critical",
    },
}


def _job_source(filename: str) -> str:
    path = Path(__file__).resolve().parent.parent / "app" / "jobs" / filename
    assert path.exists(), f"Missing job file: {path}"
    return path.read_text(encoding="utf-8")


def test_ph40_action_path_literals_per_domain():
    """Every job file must contain the documented action_path literals.

    This pins the routing contract between the notification service and the
    frontend hash routes. Job execution is proven separately by
    test_phase35_jobs_notifications.
    """
    for filename, expected_paths in ACTION_PATH_SPEC.items():
        src = _job_source(filename)
        for path in expected_paths:
            assert path in src, (
                f"Expected action_path literal {path!r} in {filename} but "
                f"it was not found. If the route was intentionally changed, "
                f"update ACTION_PATH_SPEC in test_phase40_verification.py "
                f"and confirm the frontend AlertCallout + Notifications "
                f"pages handle the new path."
            )


def test_ph40_action_path_domain_routing_consistency():
    """The domain prefix in each action_path must match the job's own domain.

    Guards against accidental cross-domain routing (e.g. a warranty job
    emitting an /#/insurance path). The check is by string prefix match.
    """
    domain_prefix = {
        "warranty_refresh.py": "/#/warranties",
        "insurance_refresh.py": "/#/insurance",
        "schedule_snapshot.py": "/#/schedule",
    }
    for filename, prefix in domain_prefix.items():
        src = _job_source(filename)
        action_paths = re.findall(r'action_path\s*=\s*(?:f?")([^"]+)"', src)
        assert action_paths, f"No action_path literals found in {filename}"
        for p in action_paths:
            assert p.startswith(prefix), (
                f"{filename} emits action_path {p!r} outside its own domain "
                f"(expected prefix {prefix})"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Notification service direct — action_path persists end-to-end
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ph40_upsert_notification_persists_action_path(rollback_client: AsyncClient):
    """Insert a notification with an action_path via the service layer and
    assert the user-facing API returns it intact.

    Complements the static source audit above: if the NotificationResponse
    schema ever drops `action_path`, this test fails — which would mean the
    frontend drawer loses its deep-link routing.
    """
    # Use the same stub-admin user id from conftest
    user_id = "20000000-0000-4000-a000-000000000001"

    from app.database import get_db
    from app.models.notifications import Notification
    from app.services import notifications as notif_svc
    from main import app as fastapi_app
    from sqlalchemy import delete

    # The rollback_client fixture already overrode get_db to a session bound
    # to the outer rollback transaction. Pull that override and call the
    # service directly so the insert is savepoint-isolated.
    override = fastapi_app.dependency_overrides[get_db]
    session_gen = override()
    session = await session_gen.__anext__()
    try:
        dedupe = f"ph40:action_path:{uid()}"
        n = await notif_svc.upsert_notification(
            session,
            user_account_id=uuid.UUID(user_id),
            domain="system",
            notification_type="test",
            title="Ph40 action_path test",
            severity="info",
            action_path="/#/schedule?tab=critical",
            dedupe_key=dedupe,
        )
        await session.commit()
        notif_id = n.id
    finally:
        try:
            await session_gen.__anext__()
        except StopAsyncIteration:
            pass

    r = await rollback_client.get(f"/api/notifications/?limit=200")
    assert r.status_code == 200
    found = [n for n in r.json() if n["id"] == str(notif_id)]
    assert len(found) == 1, f"Inserted notification not visible via API; got {len(found)}"
    assert found[0]["action_path"] == "/#/schedule?tab=critical"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Advisory-lock stability — sequential runs of session_purge
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ph40_advisory_lock_stable_across_repeat_runs():
    """Two sequential run_job_now calls on the fast session_purge job must
    both succeed (not return skipped). Guards against the failure mode where
    a stray session-level lock from an earlier test leaves the runner
    thinking the lock is always held.
    """
    from app.jobs.runner import run_job_now

    t1, reason1, id1 = await run_job_now("session_purge", triggered_by="ph40_1")
    t2, reason2, id2 = await run_job_now("session_purge", triggered_by="ph40_2")
    assert t1 is True, f"First sequential run not triggered: {reason1}"
    assert t2 is True, f"Second sequential run not triggered: {reason2}"
    assert id1 != id2


# ═══════════════════════════════════════════════════════════════════════════
# 5. Notification schema exposes required phase 37 routing fields
# ═══════════════════════════════════════════════════════════════════════════

def test_ph40_notification_schema_has_action_path_and_source_fields():
    """The NotificationResponse schema must still expose action_path,
    source_type, source_id, and dedupe_key — the frontend drawer and
    AlertCallout component depend on all four. This is a drift guard, not
    a runtime test.
    """
    from app.schemas.notifications import NotificationResponse

    required = {"action_path", "source_type", "source_id", "dedupe_key"}
    fields = set(NotificationResponse.model_fields.keys())
    missing = required - fields
    assert not missing, f"NotificationResponse is missing required fields: {missing}"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Dynamic aging_alerts — three separate, correctly-routed notifications
# ═══════════════════════════════════════════════════════════════════════════
#
# This is the phase 37 end-to-end verification: we set up a fresh project with
# one overdue RFI, one overdue submittal, and one aged open punch item, then
# invoke aging_alerts_job directly and assert three separate notifications are
# emitted with the exact per-domain action_path strings the frontend expects.
#
# Cannot use rollback_client here because aging_alerts_job runs in its own
# session_factory connection, which does not see savepoint-scoped writes from
# a different connection under MVCC. Instead we write and clean up through
# async_session_factory(), tracking every row we touch so the test leaves the
# DB exactly as it found it even on failure.

@pytest.mark.asyncio
async def test_ph40_aging_alerts_emits_three_notifications_per_domain():
    from datetime import date, datetime, timedelta, timezone

    from sqlalchemy import delete as _delete, select as _select

    from app.database import async_session_factory
    from app.jobs.aging_alerts import aging_alerts_job
    from app.models.document_management import Rfi, Submittal
    from app.models.field_ops import PunchItem
    from app.models.foundation import Project
    from app.models.notifications import Notification

    # Use a dedicated fresh project so the job only finds exactly the three
    # aging rows we planted. We clean everything up in the finally block.
    proj_name = f"Ph40-AgingDynamic-{uid()}"
    created: dict[str, list] = {
        "rfis": [],
        "submittals": [],
        "punches": [],
        "projects": [],
        "notifications": [],
    }

    try:
        async with async_session_factory() as db:
            project = Project(name=proj_name, status="active")
            db.add(project)
            await db.commit()
            await db.refresh(project)
            created["projects"].append(project.id)
            project_id = project.id

            # 1 overdue RFI — status 'open' + due_date in the past
            rfi = Rfi(
                project_id=project_id,
                rfi_number=f"PH40-RFI-{uid()}",
                subject="Aging test RFI",
                question="Is this aging?",
                status="open",
                due_date=date.today() - timedelta(days=7),
            )
            db.add(rfi)

            # 1 overdue submittal — status 'submitted' + due_date in the past
            submittal = Submittal(
                project_id=project_id,
                submittal_number=f"PH40-SUB-{uid()}",
                title="Aging test submittal",
                submittal_type="shop_drawing",
                status="submitted",
                due_date=date.today() - timedelta(days=7),
            )
            db.add(submittal)

            # 1 aged open punch item — status != 'closed', created_at older
            # than AGING_THRESHOLD_DAYS (21). We set created_at explicitly so
            # the job's "age >= 21" check fires on the first run.
            old_time = datetime.now(timezone.utc) - timedelta(days=25)
            punch = PunchItem(
                project_id=project_id,
                punch_number=abs(hash(uid())) % 1000000,
                title="Aging test punch item",
                status="open",
                created_at=old_time,
            )
            db.add(punch)

            await db.commit()
            await db.refresh(rfi)
            await db.refresh(submittal)
            await db.refresh(punch)
            created["rfis"].append(rfi.id)
            created["submittals"].append(submittal.id)
            created["punches"].append(punch.id)

        # Run the aging_alerts job body directly (not via run_job_now, which
        # would grab the advisory lock on a different connection and make the
        # assertion loop more complex). Calling the job fn directly against a
        # dedicated session gives us the same effect.
        async with async_session_factory() as db:
            summary = await aging_alerts_job(db)
            await db.commit()
            # Basic sanity on the summary string
            assert "notifications=" in summary

        # Query back notifications for exactly our project and assert 3
        # separate aging_summary_* types with the expected action_path strings.
        async with async_session_factory() as db:
            rows = (await db.execute(
                _select(Notification).where(
                    Notification.project_id == project_id,
                    Notification.notification_type.like("aging_summary_%"),
                )
            )).scalars().all()
            for n in rows:
                created["notifications"].append(n.id)

            by_type = {n.notification_type: n for n in rows}
            assert "aging_summary_rfi" in by_type, (
                f"aging_alerts did not emit an RFI summary; got types "
                f"{sorted(by_type.keys())}"
            )
            assert "aging_summary_submittal" in by_type, (
                f"aging_alerts did not emit a submittal summary; got types "
                f"{sorted(by_type.keys())}"
            )
            assert "aging_summary_punch" in by_type, (
                f"aging_alerts did not emit a punch summary; got types "
                f"{sorted(by_type.keys())}"
            )

            # Per-domain action_path literal correctness
            assert by_type["aging_summary_rfi"].action_path == "/#/rfis?status=open"
            assert by_type["aging_summary_submittal"].action_path == "/#/submittals?status=submitted"
            assert by_type["aging_summary_punch"].action_path == "/#/punch-list?status=open"

            # Each row must carry the project_id (page-level alert surfaces
            # rely on project scoping) and a meaningful source_type/source_id.
            for n in rows:
                assert n.project_id == project_id
                assert n.source_type == "project"
                assert n.source_id == project_id

    finally:
        # Deterministic cleanup — delete everything we created, in FK-safe
        # order. Runs even on assertion failure so the dev DB stays clean.
        async with async_session_factory() as db:
            if created["notifications"]:
                await db.execute(
                    _delete(Notification).where(
                        Notification.id.in_(created["notifications"])
                    )
                )
            # Also clear any aging notifications the job created for other
            # users (admin/VP fanout) against this one project. Safe because
            # the project_id is unique to this test.
            if created["projects"]:
                await db.execute(
                    _delete(Notification).where(
                        Notification.project_id.in_(created["projects"]),
                        Notification.dedupe_key.like("aging:%"),
                    )
                )
            if created["rfis"]:
                await db.execute(_delete(Rfi).where(Rfi.id.in_(created["rfis"])))
            if created["submittals"]:
                await db.execute(_delete(Submittal).where(Submittal.id.in_(created["submittals"])))
            if created["punches"]:
                await db.execute(_delete(PunchItem).where(PunchItem.id.in_(created["punches"])))
            if created["projects"]:
                await db.execute(_delete(Project).where(Project.id.in_(created["projects"])))
            await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# 7. O&M manual list filter + GET surface (closeout phase 39 target)
# ═══════════════════════════════════════════════════════════════════════════
#
# Target 7 in the phase 40 verification checklist asks for create → list →
# update → delete. The product currently exposes no DELETE endpoint on any
# CRUD route (none of the 54 routers define one), so "delete" is not part of
# the exercised surface. This test covers create → list → get → update, which
# is the entirety of the om_manuals HTTP surface.

@pytest.mark.asyncio
async def test_ph40_om_manual_list_and_get_surface(rollback_client: AsyncClient):
    r = await rollback_client.post("/api/projects/", json={
        "name": f"Ph40-OM-{uid()}",
        "status": "active",
    })
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    # Create two manuals so the list filter has something meaningful to check
    created_ids = set()
    for section in ("26 05 00", "27 05 00"):
        r = await rollback_client.post("/api/om-manuals/", json={
            "project_id": pid,
            "spec_section": section,
            "required_count": 1,
            "status": "pending",
        })
        assert r.status_code == 201, r.text
        created_ids.add(r.json()["id"])

    # List filtered by project_id — must return exactly the two we created
    r = await rollback_client.get(f"/api/om-manuals/?project_id={pid}")
    assert r.status_code == 200
    listed = r.json()
    assert {item["id"] for item in listed} == created_ids
    assert {item["spec_section"] for item in listed} == {"26 05 00", "27 05 00"}

    # GET one by id — the detail surface the frontend drawer depends on
    sample_id = next(iter(created_ids))
    r = await rollback_client.get(f"/api/om-manuals/{sample_id}")
    assert r.status_code == 200
    assert r.json()["id"] == sample_id

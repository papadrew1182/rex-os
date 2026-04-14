import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Redirect storage to a temp dir BEFORE app import so the storage adapter
# initializes against the test path.
_TEST_STORAGE_DIR = tempfile.mkdtemp(prefix="rex_test_storage_")
os.environ["REX_STORAGE_PATH"] = _TEST_STORAGE_DIR

# Disable slowapi login rate limiting under pytest so the ~20 login hits
# across the suite don't trip the production 10/minute limiter. Must be
# set BEFORE ``from main import app`` because ``app.rate_limit`` reads the
# env var at module-import time.
os.environ.setdefault("REX_LOGIN_RATE_LIMIT", "100000/minute")

from main import app  # noqa: E402
from app.database import engine, get_db  # noqa: E402
from app.dependencies import get_current_user  # noqa: E402
from app.models.foundation import UserAccount  # noqa: E402


def _stub_admin_user() -> UserAccount:
    """Stub admin user injected into all existing tests via dependency override.

    This keeps the pre-Sprint-D test suite working without per-test auth setup.
    Auth-specific tests use the `real_auth_client` fixture to bypass this stub.
    """
    return UserAccount(
        id=uuid.UUID("20000000-0000-4000-a000-000000000001"),
        person_id=uuid.UUID("10000000-0000-4000-a000-000000000001"),
        email="aroberts@exxircapital.com",
        password_hash="(stub-not-used)",
        global_role="vp",
        is_admin=True,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# Default override: every test runs as the seeded admin/vp user.
app.dependency_overrides[get_current_user] = _stub_admin_user


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ── Advisory lock cleanup (test-session startup) ───────────────────────────
#
# When a pytest process is interrupted or asyncpg connections are not cleanly
# closed (common on Windows), session-level advisory locks can linger on
# PostgreSQL backend connections from a previous test run. This fixture
# terminates those stale backends at the start of each test session.
#
# pg_terminate_backend requires pg_signal_backend or superuser. If the DB
# user lacks that privilege, the termination is skipped silently.

@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _terminate_stale_lock_backends():
    """Kill PG backends holding any advisory locks (from prior test runs)."""
    from app.database import engine
    from sqlalchemy import text as _t

    try:
        async with engine.connect() as conn:
            # Find any backends holding advisory locks other than our own connection.
            result = await conn.execute(
                _t(
                    "SELECT DISTINCT pid FROM pg_locks "
                    "WHERE locktype = 'advisory' "
                    "  AND pid <> pg_backend_pid()"
                )
            )
            pids = [row[0] for row in result.fetchall()]
            for pid in pids:
                try:
                    await conn.execute(
                        _t("SELECT pg_terminate_backend(:pid)"), {"pid": pid}
                    )
                except Exception:  # noqa: BLE001
                    pass
            if pids:
                import logging as _logging
                _logging.getLogger("rex.tests").info(
                    "terminated %d stale backend(s) holding advisory locks: %s",
                    len(pids),
                    pids,
                )
            await conn.commit()
    except Exception:  # noqa: BLE001
        pass  # Best-effort; never block tests due to cleanup failure

    yield


# ── Session start pollution scrub ───────────────────────────────────────────
#
# The ``client`` fixture is session-scoped and commits directly to the real
# dev DB. Every earlier test session therefore leaks hundreds of projects,
# warranties, notifications, etc. When the ``warranty_refresh`` /
# ``insurance_refresh`` / ``aging_alerts`` jobs then iterate every row in
# those tables on the next run, the job can take 5+ seconds and eventually
# cause ``asyncpg`` connection-closed errors under the advisory-lock
# connection, which surfaces as a flaky ``test_e2e_run_warranty_refresh_job``.
#
# To keep the suite honest (and the jobs honest-to-scale) we scrub all
# non-seed rows from the transactional tables at the start of each pytest
# session. Only the seeded UUID-prefixed rows survive (foundation data:
# companies 00000000-, people 10000000-, users 20000000-, roles 30000000-,
# projects 40000000-, project_members 50000000-, templates a0000*). This
# runs once per ``pytest`` invocation — never mid-session — so it cannot
# interfere with in-session fixture ordering.

@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _scrub_test_pollution_and_reseed():
    from app.database import engine
    from sqlalchemy import text as _t

    # Tables that are purely transactional / created by tests. TRUNCATE CASCADE
    # is safe because there is no production data on the dev DB and the
    # foundation tables (below) never reference rows in these tables.
    transactional_tables = [
        "rex.notifications",
        "rex.job_runs",
        "rex.attachments",
        "rex.schedule_snapshots",
        "rex.schedule_constraints",
        "rex.activity_links",
        "rex.schedule_activities",
        "rex.schedules",
        "rex.budget_snapshots",
        "rex.budget_line_items",
        "rex.cost_codes",
        "rex.commitment_change_orders",
        "rex.commitment_line_items",
        "rex.commitments",
        "rex.pco_cco_links",
        "rex.change_event_line_items",
        "rex.change_events",
        "rex.potential_change_orders",
        "rex.prime_contracts",
        "rex.direct_costs",
        "rex.lien_waivers",
        "rex.billing_periods",
        "rex.payment_applications",
        "rex.correspondence",
        "rex.submittals",
        "rex.submittal_packages",
        "rex.rfis",
        "rex.specifications",
        "rex.drawing_revisions",
        "rex.drawing_areas",
        "rex.drawings",
        "rex.meeting_action_items",
        "rex.meetings",
        "rex.punch_items",
        "rex.inspection_items",
        "rex.inspections",
        "rex.safety_incidents",
        "rex.observations",
        "rex.daily_logs",
        "rex.manpower_entries",
        "rex.tasks",
        "rex.photos",
        "rex.photo_albums",
        "rex.om_manuals",
        "rex.warranty_claims",
        "rex.warranty_alerts",
        "rex.warranties",
        "rex.insurance_certificates",
        "rex.closeout_checklist_items",
        "rex.closeout_checklists",
        "rex.completion_milestones",
        "rex.sessions",
        "rex.role_template_overrides",
    ]

    try:
        async with engine.connect() as conn:
            # Single TRUNCATE CASCADE clears all test pollution fast.
            stmt = (
                "TRUNCATE "
                + ", ".join(transactional_tables)
                + " RESTART IDENTITY CASCADE"
            )
            await conn.execute(_t(stmt))

            # Trim non-seed foundation rows (project_members, projects,
            # user_accounts, people, companies, role_templates). Seeded rows
            # use UUID prefixes specific to foundation_bootstrap.sql.
            await conn.execute(_t(
                "DELETE FROM rex.project_members "
                "WHERE id::text NOT LIKE '50000000-%'"
            ))
            await conn.execute(_t(
                "DELETE FROM rex.projects "
                "WHERE id::text NOT LIKE '40000000-%'"
            ))
            await conn.execute(_t(
                "DELETE FROM rex.user_accounts "
                "WHERE id::text NOT LIKE '20000000-%'"
            ))
            await conn.execute(_t(
                "DELETE FROM rex.people "
                "WHERE id::text NOT LIKE '10000000-%'"
            ))
            await conn.execute(_t(
                "DELETE FROM rex.companies "
                "WHERE id::text NOT LIKE '00000000-%'"
            ))
            await conn.execute(_t(
                "DELETE FROM rex.role_templates "
                "WHERE id::text NOT LIKE '30000000-%'"
            ))
            try:
                await conn.execute(_t(
                    "DELETE FROM rex.closeout_templates "
                    "WHERE id::text NOT LIKE 'a0000%'"
                ))
            except Exception:  # noqa: BLE001
                pass

            # Re-seed the milestone rows that rex2_business_seed leaves to the
            # caller. ``seed_project_milestones`` is ON CONFLICT DO NOTHING so
            # this is idempotent.
            await conn.execute(_t(
                "SELECT rex.seed_project_milestones("
                "'40000000-0000-4000-a000-000000000001'::uuid, 'multifamily')"
            ))

            await conn.commit()
    except Exception:  # noqa: BLE001
        pass  # Best-effort; never block tests due to scrub failure

    yield


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def real_auth_client(client):
    """Yields the same shared client but with the auth override removed.

    Use this fixture in auth-specific tests that need to exercise the real
    login/permission flow. The override is restored after the test.
    """
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield client
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


# ── Per-test rollback isolation (opt-in) ────────────────────────────────────
#
# Sprint F added an opt-in ``rollback_client`` fixture that wraps the entire
# test in a single outer connection + outer transaction, with a SAVEPOINT for
# every request. All commits inside handlers turn into savepoint releases; the
# outer transaction is rolled back at test teardown, so nothing the test
# creates persists in the database.
#
# This is opt-in rather than global because:
#   1. Existing tests already pass; forcing them through the wrapper risks
#      changing semantics around session cleanup or opportunistic jobs.
#   2. A few tests talk directly to asyncpg via ``db.py`` (legacy pool). Those
#      commits bypass SQLAlchemy entirely and would not be rolled back even
#      under this fixture — they must stay on the existing non-isolated path.
#
# New tests that only use SQLAlchemy-backed routes should request
# ``rollback_client`` instead of ``client`` to avoid leaving data behind.


@pytest_asyncio.fixture
async def rollback_client():
    """Yields an AsyncClient with per-test DB rollback.

    Opens one connection, starts an outer transaction, and binds a session
    factory to that connection with ``join_transaction_mode="create_savepoint"``.
    Every request handler session joins the outer transaction via a SAVEPOINT,
    so handler commits release the savepoint but never touch the outer
    transaction. On teardown the outer transaction is rolled back, discarding
    everything the test did.

    Uses a dedicated ``AsyncClient`` (not the session-scoped one) so the
    override is isolated to this fixture and cannot affect parallel tests.

    Disposes the engine pool before acquiring a connection so any cached
    asyncpg connections bound to an earlier event loop are dropped first.
    Without this, CI (where tests execute fast enough for the pool to
    still hold a live connection from the session-startup fixture) hits
    "got Future attached to a different loop" at fixture setup. Locally
    on Windows the timing masks it; on Linux it's deterministic.
    """
    await engine.dispose()
    async with engine.connect() as connection:
        outer_trans = await connection.begin()

        bound_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def _override_get_db():
            async with bound_factory() as session:
                yield session

        saved_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = _override_get_db

        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
        finally:
            if saved_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = saved_override
            if outer_trans.is_active:
                await outer_trans.rollback()

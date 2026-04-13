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
    """
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

"""Task 8 — Admin HTTP trigger for Procore resource syncs.

Verifies the thin pass-through at POST /api/connectors/{account_id}/sync/{resource_type}:

  - admin call against a real procore connector_account dispatches to
    the orchestrator and returns ``{rows_fetched, rows_upserted}``
  - unknown account_id returns 404
  - an unauthenticated call is rejected

The session-scoped ``client`` fixture from tests/conftest.py already stubs
an admin user on every request via dependency_overrides[get_current_user],
so an authenticated admin call is the default path.

FIXTURE NOTE: The session-scoped ``client`` runs on anyio's event loop,
and the SQLAlchemy engine's global pool is bound to a different loop in
CI (pytest-anyio creates a per-test loop; the engine pool was initialized
against a different one). Opening a new AsyncSession through the shared
pool from inside a ``client``-using test triggers "Future attached to a
different loop" on Linux CI.  We sidestep this by using raw asyncpg for
the rare SQL setup/teardown here — asyncpg.connect() creates a fresh
connection bound to whichever loop is active at call time, no shared
pool state. The deep cross-schema assertions (staging + rex.rfis +
source_links + sync_runs + cursors) live in test_orchestrator.py, which
doesn't use the HTTP client and thus uses the SQLAlchemy pool cleanly.
"""

from __future__ import annotations

import os
import ssl
import uuid

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import text


# Fixed connector kind UUID seeded by migration 012 for 'procore'.
_PROCORE_CONNECTOR_ID = "b1000000-0000-4000-c000-000000000001"


def _require_live_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


async def _connect():
    """Open a raw asyncpg connection bound to the current event loop.

    Avoid the SQLAlchemy shared pool — see module docstring.
    """
    url = os.environ["DATABASE_URL"]
    # DATABASE_URL in this repo uses the postgresql+asyncpg:// prefix for
    # SQLAlchemy; strip it for raw asyncpg.
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]

    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ssl_ctx = None
    if use_ssl:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ssl_ctx)


@pytest_asyncio.fixture
async def procore_connector_account():
    """Seed a unique rex.connector_accounts row for procore (raw asyncpg).

    Yields the UUID string. Cleans up rfis_raw + sync_runs + sync_cursors +
    account row on teardown.
    """
    _require_live_db()
    account_id = str(uuid.uuid4())
    label = f"test-admin-sync-{account_id}"

    conn = await _connect()
    try:
        await conn.execute(
            "INSERT INTO rex.connector_accounts "
            "(id, connector_id, label, environment, status, is_primary) "
            "VALUES ($1::uuid, $2::uuid, $3, 'test', 'configured', false)",
            account_id, _PROCORE_CONNECTOR_ID, label,
        )
    finally:
        await conn.close()

    yield account_id

    conn = await _connect()
    try:
        await conn.execute(
            "DELETE FROM connector_procore.rfis_raw WHERE account_id = $1::uuid",
            account_id,
        )
        await conn.execute(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = $1::uuid",
            account_id,
        )
        await conn.execute(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = $1::uuid",
            account_id,
        )
        await conn.execute(
            "DELETE FROM rex.connector_accounts WHERE id = $1::uuid",
            account_id,
        )
    finally:
        await conn.close()


@pytest.mark.anyio
async def test_admin_sync_rfis_returns_counts(
    client, procore_connector_account, monkeypatch
):
    """Admin POST → orchestrator runs → 200 with counts.

    Zero procore.rfis + zero project mappings means the orchestrator's
    happy path returns {0, 0} — sufficient to prove the route is wired.
    Deep end-to-end with real data lives in test_orchestrator.py.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    try:
        response = await client.post(
            f"/api/connectors/{procore_connector_account}/sync/rfis",
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "rows_fetched" in body
        assert "rows_upserted" in body
        # Rigorous dispatch verification (sync_runs row landed) is in
        # test_orchestrator.py — can't cross event loops here.
    finally:
        import app.services.connectors.procore.rex_app_pool as mod2
        if mod2._pool:
            await mod2._pool.close()
            mod2._pool = None


@pytest.mark.anyio
async def test_admin_sync_unknown_account_returns_404(client):
    """A connector_account_id that doesn't exist must 404 before we
    dispatch to any orchestrator."""
    _require_live_db()
    bogus = str(uuid.uuid4())
    response = await client.post(
        f"/api/connectors/{bogus}/sync/rfis",
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_admin_sync_requires_auth(client, procore_connector_account):
    """An unauthenticated request must be rejected (401/403).

    The conftest.py sets a session-wide stub admin via
    ``app.dependency_overrides[get_current_user]``. We temporarily pop
    that override to exercise the real auth dependency, then restore it.
    """
    from main import app
    from app.dependencies import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await client.post(
            f"/api/connectors/{procore_connector_account}/sync/rfis",
        )
        assert response.status_code in (401, 403), response.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved

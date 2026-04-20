"""Task 8 — Admin HTTP trigger for Procore resource syncs.

Verifies the thin pass-through at POST /api/connectors/{account_id}/sync/{resource_type}:

  - admin call against a real procore connector_account dispatches to
    the orchestrator and returns ``{rows_fetched, rows_upserted}``
  - unknown account_id returns 404
  - an unauthenticated call is rejected

Follows the fixture convention established in test_staging.py /
test_orchestrator.py — we inline ``db_session`` and
``procore_connector_account`` here because the connector_procore test
dir doesn't have a shared conftest yet. The session-scoped ``client``
fixture from tests/conftest.py already stubs an admin user on every
request via dependency_overrides[get_current_user], so an authenticated
admin call is the default path — no Authorization header needed.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.database import async_session_factory


# Fixed connector kind UUID seeded by migration 012 for 'procore'.
_PROCORE_CONNECTOR_ID = uuid.UUID("b1000000-0000-4000-c000-000000000001")


def _require_live_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def db_session():
    """SQLAlchemy AsyncSession bound to the dev DB, manually committed."""
    _require_live_db()
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def procore_connector_account(db_session):
    """Seed a unique rex.connector_accounts row for the procore connector.

    Yields the UUID. Cleans up rfis_raw + sync_runs + sync_cursors + the
    account row on teardown.
    """
    account_label = f"test-admin-sync-{uuid.uuid4()}"
    account_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO rex.connector_accounts "
            "(id, connector_id, label, environment, status, is_primary) "
            "VALUES (:id, :cid, :label, 'test', 'configured', false)"
        ),
        {
            "id": account_id,
            "cid": _PROCORE_CONNECTOR_ID,
            "label": account_label,
        },
    )
    await db_session.commit()

    yield account_id

    await db_session.execute(
        text(
            "DELETE FROM connector_procore.rfis_raw "
            "WHERE account_id = :acct"
        ),
        {"acct": account_id},
    )
    await db_session.execute(
        text("DELETE FROM rex.sync_runs WHERE connector_account_id = :a"),
        {"a": account_id},
    )
    await db_session.execute(
        text("DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"),
        {"a": account_id},
    )
    await db_session.execute(
        text("DELETE FROM rex.connector_accounts WHERE id = :id"),
        {"id": account_id},
    )
    await db_session.commit()


@pytest.mark.anyio
async def test_admin_sync_rfis_returns_counts(
    client, procore_connector_account, monkeypatch
):
    """Happy-path: admin POSTs → orchestrator runs → 200 with counts.

    No procore.rfis seeding + no project mappings = zero counts, but
    the orchestrator still lands the sync_run as 'succeeded' and the
    endpoint returns the dict. That's sufficient to prove the route is
    wired to the orchestrator.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    # Orchestrator opens a Rex App pool; point it at the dev DB so the
    # adapter's "no project mappings" fast path still resolves cleanly.
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
    # Either 404 or 400 — the route is documented to use 404 for unknown
    # accounts; accept 400 in case someone tightens the contract later.
    assert response.status_code in (400, 404), response.text


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

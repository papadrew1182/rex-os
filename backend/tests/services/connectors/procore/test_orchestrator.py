"""End-to-end test for the Procore RFI sync orchestrator (Task 7).

Exercises the full pipeline: adapter reads from the Rex App DB (pointed
at the dev DB here via monkeypatch), the staging upsert lands the raw
payload, the mapper converts it, the orchestrator upserts into rex.rfis,
writes a source_link, advances the cursor, and finalizes the sync_run.

Follows the fixture conventions established in test_staging.py — we
inline ``db_session`` and ``procore_connector_account`` here rather
than relying on conftest machinery, because connector_procore tests
don't have a shared conftest yet.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.database import async_session_factory
from app.services.connectors.procore.orchestrator import sync_resource


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
    """Seed a unique rex.connector_accounts row for the procore connector."""
    account_label = f"test-orchestrator-{uuid.uuid4()}"
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

    # Teardown: sync_runs / sync_cursors cascade via ON DELETE CASCADE
    # on connector_account_id; staging rows do not, so delete them first.
    await db_session.execute(
        text(
            "DELETE FROM connector_procore.rfis_raw "
            "WHERE account_id = :acct"
        ),
        {"acct": account_id},
    )
    await db_session.execute(
        text("DELETE FROM rex.connector_accounts WHERE id = :id"),
        {"id": account_id},
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def project_with_source_link(db_session, procore_connector_account):
    """Seed a rex.projects row and a rex.connector_mappings row linking it
    to procore project_id=42.

    The orchestrator iterates rex.connector_mappings WHERE
    source_table='procore.projects' to discover which projects to sync.
    Without this fixture, sync_resource has no projects to work on and
    returns zero counts.
    """
    pid = await db_session.execute(text(
        "INSERT INTO rex.projects (id, name, status, project_number) "
        "VALUES (gen_random_uuid(), 'Test Orchestrator Project', 'active', 'TEST-ORCH-001') "
        "RETURNING id"
    ))
    canonical_id = pid.scalar_one()
    await db_session.execute(text(
        "INSERT INTO rex.connector_mappings "
        "(rex_table, rex_id, connector, external_id, source_table, synced_at) "
        "VALUES ('rex.projects', :rid, 'procore', '42', 'procore.projects', now())"
    ), {"rid": canonical_id})
    await db_session.commit()

    yield canonical_id

    # Cleanup: delete any mapping rows keyed on this canonical project
    # AND any source_links for RFIs we wrote (external_id='201' is the
    # test RFI). rex.rfis rows on this project go first.
    await db_session.execute(text(
        "DELETE FROM rex.connector_mappings "
        "WHERE rex_id = :rid "
        "   OR (connector = 'procore' AND source_table = 'procore.rfis')"
    ), {"rid": canonical_id})
    await db_session.execute(text(
        "DELETE FROM rex.rfis WHERE project_id = :rid"
    ), {"rid": canonical_id})
    await db_session.execute(
        text("DELETE FROM rex.projects WHERE id = :rid"),
        {"rid": canonical_id},
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_sync_resource_rfis_end_to_end(
    db_session,
    procore_connector_account,
    project_with_source_link,
    monkeypatch,
):
    """Full pipeline: staging → canonical → source_links → cursor → sync_run."""
    # Point the Rex App pool at the same dev DB so the adapter reads
    # the procore.rfis rows we seed below.
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    # Seed procore.rfis with a single row. Notes:
    #  * ``question`` is present and non-null because rex.rfis.question
    #    is NOT NULL and the mapper passes payload.question through
    #    unmodified; a NULL here would fail the canonical INSERT.
    #  * ``number`` is typed integer here (not numeric(10,2) as the real
    #    rex-procore table uses) so the asyncpg-returned value is a
    #    plain int rather than a Decimal. Task 6's
    #    _coerce_rfi_number handles int + float but not Decimal —
    #    the Decimal gap is a separate concern for the follow-up
    #    resource-rollout plan, and the orchestrator's correctness
    #    doesn't hinge on that detail.
    await db_session.execute(text("CREATE SCHEMA IF NOT EXISTS procore"))
    # Drop any prior-shaped test table before recreating so column types
    # are consistent with this test's expectations.
    await db_session.execute(text("DROP TABLE IF EXISTS procore.rfis"))
    await db_session.execute(text("""
        CREATE TABLE procore.rfis (
            procore_id bigint PRIMARY KEY,
            project_id bigint,
            number integer,
            subject text,
            question text,
            status text,
            updated_at timestamptz
        )
    """))
    await db_session.execute(text(
        "INSERT INTO procore.rfis "
        "(procore_id, project_id, number, subject, question, status, updated_at) "
        "VALUES (201, 42, 1, 'alpha', 'q-alpha', 'open', '2026-01-01T00:00:00Z')"
    ))
    await db_session.commit()

    try:
        # Act
        result = await sync_resource(
            db_session,
            account_id=procore_connector_account,
            resource_type="rfis",
        )

        # Orchestrator return value
        assert result["rows_fetched"] == 1
        assert result["rows_upserted"] == 1

        # Staging landed
        r = await db_session.execute(text(
            "SELECT source_id, payload->>'subject' AS s "
            "FROM connector_procore.rfis_raw "
            "WHERE account_id = :a"
        ), {"a": procore_connector_account})
        assert [(row["source_id"], row["s"]) for row in r.mappings().all()] == [
            ("201", "alpha"),
        ]

        # Canonical rex.rfis
        canonical = await db_session.execute(text(
            "SELECT subject, status, question "
            "FROM rex.rfis "
            "WHERE project_id = :pid AND rfi_number = '1'"
        ), {"pid": project_with_source_link})
        row = canonical.mappings().first()
        assert row is not None, "canonical rex.rfis row was not written"
        assert row["subject"] == "alpha"
        assert row["status"] == "open"
        assert row["question"] == "q-alpha"

        # source_link row
        sl = await db_session.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND external_id='201' "
            "  AND source_table='procore.rfis'"
        ))
        assert sl.scalar_one() == 1

        # sync_runs row: succeeded with correct counts
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id=:a AND resource_type='rfis' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        row = sr.mappings().first()
        assert row["status"] == "succeeded"
        assert row["rows_fetched"] == 1
        assert row["rows_upserted"] == 1

        # Cursor advanced to (contain) the row's updated_at.
        cur = await db_session.execute(text(
            "SELECT cursor_value FROM rex.sync_cursors "
            "WHERE connector_account_id=:a AND resource_type='rfis'"
        ), {"a": procore_connector_account})
        cursor_value = cur.scalar_one()
        assert cursor_value is not None
        assert "2026-01-01" in cursor_value

    finally:
        # Cleanup procore schema + staging + run/cursor + source_link.
        # rex.rfis + project-mapping cleanup lives in the fixture teardown.
        await db_session.execute(text("DROP TABLE IF EXISTS procore.rfis"))
        await db_session.execute(text(
            "DELETE FROM connector_procore.rfis_raw WHERE account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector = 'procore' AND external_id = '201'"
        ))
        await db_session.commit()
        import app.services.connectors.procore.rex_app_pool as mod2
        if mod2._pool:
            await mod2._pool.close()
            mod2._pool = None


@pytest.mark.asyncio
async def test_sync_resource_unknown_resource_type_raises(
    db_session, procore_connector_account
):
    """Dispatch table only has 'rfis' wired; anything else must be an
    explicit NotImplementedError rather than a silent no-op so the
    follow-up resource-rollout plan fails loud when someone calls
    sync_resource(resource_type='submittals') before submittals is added.
    """
    with pytest.raises(NotImplementedError, match="submittals"):
        await sync_resource(
            db_session,
            account_id=procore_connector_account,
            resource_type="submittals",
        )


@pytest.mark.asyncio
async def test_sync_resource_no_project_mappings_is_zero_counts(
    db_session, procore_connector_account, monkeypatch
):
    """If rex.connector_mappings has no source_table='procore.projects'
    rows, sync_resource completes successfully with zero counts rather
    than erroring. The sync_run should still be marked 'succeeded'.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    try:
        result = await sync_resource(
            db_session,
            account_id=procore_connector_account,
            resource_type="rfis",
        )
        assert result == {"rows_fetched": 0, "rows_upserted": 0}

        # sync_run still succeeded
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id = :a AND resource_type = 'rfis' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        row = sr.mappings().first()
        assert row is not None
        assert row["status"] == "succeeded"
        assert row["rows_fetched"] == 0
        assert row["rows_upserted"] == 0
    finally:
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.commit()
        import app.services.connectors.procore.rex_app_pool as mod2
        if mod2._pool:
            await mod2._pool.close()
            mod2._pool = None

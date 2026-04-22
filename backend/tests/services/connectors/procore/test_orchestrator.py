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
async def test_sync_resource_vendors_end_to_end(
    db_session, procore_connector_account, monkeypatch
):
    """Full root-resource pipeline for vendors: seed procore.vendors ->
    sync_resource('vendors') -> rex.companies canonical rows +
    rex.connector_mappings source_links + sync_runs / sync_cursors state.

    Uses distinctive P4A-VENDOR-* vendor names so teardown is safe even
    if a prior test run left residue. The distinctive prefix also keeps
    the UNIQUE (name) constraint (migration 027) from colliding with
    live rex.companies rows.
    """
    import os
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    # Seed procore.vendors with the minimal column set
    # build_vendor_payload reads. DROP/CREATE instead of TRUNCATE
    # because prior test runs may have left a table with a different
    # column shape.
    await db_session.execute(text("CREATE SCHEMA IF NOT EXISTS procore"))
    await db_session.execute(text("DROP TABLE IF EXISTS procore.vendors"))
    await db_session.execute(text("""
        CREATE TABLE procore.vendors (
            procore_id bigint PRIMARY KEY,
            vendor_name text,
            company_name text,
            trade_name text,
            email_address text,
            business_phone text,
            mobile_phone text,
            address text,
            city text,
            state_code text,
            zip_code text,
            website text,
            is_active boolean,
            license_number text,
            insurance_expiration_date date,
            insurance_gl_expiration_date date,
            insurance_wc_expiration_date date,
            insurance_auto_expiration_date date,
            created_at timestamptz,
            updated_at timestamptz
        )
    """))
    await db_session.execute(text(
        "INSERT INTO procore.vendors "
        "(procore_id, vendor_name, trade_name, is_active, "
        " insurance_gl_expiration_date) "
        "VALUES (9901, 'P4A-VENDOR-ALPHA', 'Electrical', true, "
        "        '2027-03-15'), "
        "       (9902, 'P4A-VENDOR-BETA',  'Plumbing',   true, NULL)"
    ))
    await db_session.commit()

    try:
        result = await sync_resource(
            db_session,
            account_id=procore_connector_account,
            resource_type="vendors",
        )
        assert result["rows_fetched"] == 2
        assert result["rows_upserted"] == 2

        # Canonical rows landed in rex.companies
        canonical = await db_session.execute(text(
            "SELECT name, company_type, trade, insurance_expiry "
            "FROM rex.companies "
            "WHERE name LIKE 'P4A-VENDOR-%' "
            "ORDER BY name"
        ))
        rows = canonical.mappings().all()
        assert len(rows) == 2
        assert rows[0]["name"] == "P4A-VENDOR-ALPHA"
        assert rows[0]["company_type"] == "subcontractor"  # default
        assert rows[0]["trade"] == "Electrical"
        # GL expiry preferred by the mapper
        import datetime as _dt
        assert rows[0]["insurance_expiry"] == _dt.date(2027, 3, 15)
        assert rows[1]["name"] == "P4A-VENDOR-BETA"
        assert rows[1]["trade"] == "Plumbing"
        assert rows[1]["insurance_expiry"] is None

        # source_links: one per seeded procore vendor, pointing at rex.companies
        links = await db_session.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.vendors' "
            "  AND external_id IN ('9901','9902')"
        ))
        assert links.scalar_one() == 2

        # Staging landed in connector_procore.vendors_raw
        staged = await db_session.execute(text(
            "SELECT source_id, payload->>'vendor_name' AS vn "
            "FROM connector_procore.vendors_raw "
            "WHERE account_id = :a "
            "  AND source_id IN ('9901','9902') "
            "ORDER BY source_id"
        ), {"a": procore_connector_account})
        staged_rows = [(row["source_id"], row["vn"]) for row in staged.mappings().all()]
        assert staged_rows == [
            ("9901", "P4A-VENDOR-ALPHA"),
            ("9902", "P4A-VENDOR-BETA"),
        ]

        # sync_run finished in 'succeeded' state with correct counts
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id=:a AND resource_type='vendors' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        run = sr.mappings().first()
        assert run is not None
        assert run["status"] == "succeeded"
        assert run["rows_fetched"] == 2
        assert run["rows_upserted"] == 2

        # Cursor advanced to the last procore_id (bigint as string)
        cur = await db_session.execute(text(
            "SELECT cursor_value FROM rex.sync_cursors "
            "WHERE connector_account_id=:a AND resource_type='vendors'"
        ), {"a": procore_connector_account})
        cursor_value = cur.scalar_one()
        assert cursor_value == "9902"

    finally:
        await db_session.execute(text("DROP TABLE IF EXISTS procore.vendors"))
        # Order matters: connector_mappings references rex.companies by rex_id,
        # so delete mappings first, then the canonical rows, then staging.
        await db_session.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.vendors' "
            "  AND external_id IN ('9901','9902')"
        ))
        await db_session.execute(text(
            "DELETE FROM rex.companies WHERE name LIKE 'P4A-VENDOR-%'"
        ))
        await db_session.execute(text(
            "DELETE FROM connector_procore.vendors_raw WHERE account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.commit()
        import app.services.connectors.procore.rex_app_pool as mod2
        if mod2._pool:
            await mod2._pool.close()
            mod2._pool = None


@pytest.mark.asyncio
async def test_sync_resource_unknown_resource_type_raises(
    db_session, procore_connector_account
):
    """Unsupported resource types must raise NotImplementedError
    rather than silently no-op, so adding a new resource forces a
    code change in _RESOURCE_CONFIG (not just a DB row somewhere).

    We use ``documents`` as the sentinel here — it's a Wave 2/3 scope
    resource that hasn't landed its _RESOURCE_CONFIG entry yet. The
    earlier sentinel ``submittals`` graduated to real support in
    Phase 4 Wave 2 Task 3 and moved out of the not-implemented set.
    """
    with pytest.raises(NotImplementedError, match="documents"):
        await sync_resource(
            db_session,
            account_id=procore_connector_account,
            resource_type="documents",
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


@pytest.mark.asyncio
async def test_sync_resource_rfis_cursor_advance_uses_min_across_projects(
    db_session, procore_connector_account, monkeypatch
):
    """Two procore projects with diverging updated_at: the shared cursor must
    advance to the OLDER of their next_cursor values so the slower-updating
    project is never starved on subsequent syncs."""
    import os
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    # Seed two canonical projects + two source_link rows mapping to procore project ids
    pa = await db_session.execute(text(
        "INSERT INTO rex.projects (id, name, status, project_number) "
        "VALUES (gen_random_uuid(), 'ProjA', 'active', 'PA') RETURNING id"
    ))
    pa_id = pa.scalar_one()
    pb = await db_session.execute(text(
        "INSERT INTO rex.projects (id, name, status, project_number) "
        "VALUES (gen_random_uuid(), 'ProjB', 'active', 'PB') RETURNING id"
    ))
    pb_id = pb.scalar_one()
    await db_session.execute(text("""
        INSERT INTO rex.connector_mappings
        (rex_table, rex_id, connector, external_id, source_table, synced_at)
        VALUES ('rex.projects', :a, 'procore', '500', 'procore.projects', now()),
               ('rex.projects', :b, 'procore', '600', 'procore.projects', now())
    """), {"a": pa_id, "b": pb_id})

    # Seed procore.rfis: project 500 updated recently, project 600 updated long ago.
    # Include ``question`` because rex.rfis.question is NOT NULL — the mapper
    # passes it through unmodified and a NULL would fail the canonical INSERT.
    await db_session.execute(text("CREATE SCHEMA IF NOT EXISTS procore"))
    await db_session.execute(text("DROP TABLE IF EXISTS procore.rfis"))
    await db_session.execute(text("""
        CREATE TABLE procore.rfis (
            procore_id bigint PRIMARY KEY, project_id bigint,
            number numeric(10,2), subject text, question text, status text,
            updated_at timestamptz
        )
    """))
    await db_session.execute(text(
        "INSERT INTO procore.rfis (procore_id, project_id, number, subject, question, status, updated_at) VALUES "
        "(901, 500, 1, 'fast', 'q-fast', 'open', '2026-04-01T00:00:00Z'),"
        "(902, 600, 1, 'slow', 'q-slow', 'open', '2026-01-01T00:00:00Z')"
    ))
    await db_session.commit()

    try:
        result = await sync_resource(
            db_session, account_id=procore_connector_account, resource_type="rfis"
        )
        assert result["rows_fetched"] == 2
        assert result["rows_upserted"] == 2

        # Cursor should be advanced to the MIN (older) of the two projects' next_cursors
        cur = await db_session.execute(text(
            "SELECT cursor_value FROM rex.sync_cursors "
            "WHERE connector_account_id=:a AND resource_type='rfis'"
        ), {"a": procore_connector_account})
        cursor_value = cur.scalar_one()
        assert cursor_value is not None
        # The slow project's updated_at is 2026-01-01; the fast project's is 2026-04-01.
        # MIN across the two = 2026-01-01.
        assert "2026-01-01" in cursor_value
        assert "2026-04-01" not in cursor_value
    finally:
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
            "DELETE FROM rex.connector_mappings WHERE connector='procore' "
            "AND external_id IN ('500','600','901','902')"
        ))
        await db_session.execute(text(
            "DELETE FROM rex.rfis WHERE project_id IN (:a, :b)"
        ), {"a": pa_id, "b": pb_id})
        await db_session.execute(text(
            "DELETE FROM rex.projects WHERE id IN (:a, :b)"
        ), {"a": pa_id, "b": pb_id})
        await db_session.commit()
        import app.services.connectors.procore.rex_app_pool as mod2
        if mod2._pool:
            await mod2._pool.close()
            mod2._pool = None


@pytest.mark.asyncio
async def test_sync_resource_projects_end_to_end(
    db_session, procore_connector_account, monkeypatch
):
    """Full root-resource pipeline: seed procore.projects -> sync_resource
    -> rex.projects canonical rows + rex.connector_mappings source_links
    + sync_runs / sync_cursors state.

    Uses distinctive P4A-SMOKE-* project_numbers so teardown is safe even
    if a prior test run left residue.
    """
    import os
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    # Seed procore.projects with the minimal column set the payload
    # builder reads. DROP/CREATE instead of TRUNCATE because prior
    # test runs may have left a table with a different column shape.
    await db_session.execute(text("CREATE SCHEMA IF NOT EXISTS procore"))
    await db_session.execute(text("DROP TABLE IF EXISTS procore.projects"))
    await db_session.execute(text("""
        CREATE TABLE procore.projects (
            procore_id bigint PRIMARY KEY,
            company_id bigint,
            project_name text,
            project_number text,
            status text,
            start_date date,
            completion_date date,
            address text,
            city text,
            state_code text,
            zip_code text,
            created_at timestamptz,
            updated_at timestamptz
        )
    """))
    await db_session.execute(text(
        "INSERT INTO procore.projects "
        "(procore_id, project_name, project_number, status) "
        "VALUES (9991, 'P4a Test Alpha', 'P4A-SMOKE-001', 'Active'), "
        "       (9992, 'P4a Test Beta',  'P4A-SMOKE-002', 'Active')"
    ))
    await db_session.commit()

    try:
        result = await sync_resource(
            db_session,
            account_id=procore_connector_account,
            resource_type="projects",
        )
        assert result["rows_fetched"] == 2
        assert result["rows_upserted"] == 2

        # Canonical rows landed in rex.projects
        canonical = await db_session.execute(text(
            "SELECT name, project_number, status FROM rex.projects "
            "WHERE project_number LIKE 'P4A-SMOKE-%' "
            "ORDER BY project_number"
        ))
        rows = canonical.mappings().all()
        assert len(rows) == 2
        assert rows[0]["name"] == "P4a Test Alpha"
        assert rows[0]["project_number"] == "P4A-SMOKE-001"
        assert rows[0]["status"] == "active"  # lowercased by mapper
        assert rows[1]["name"] == "P4a Test Beta"

        # source_links: one per seeded procore project, pointing at rex.projects
        links = await db_session.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.projects' "
            "  AND external_id IN ('9991','9992')"
        ))
        assert links.scalar_one() == 2

        # Staging landed in connector_procore.projects_raw
        staged = await db_session.execute(text(
            "SELECT source_id, payload->>'project_name' AS n "
            "FROM connector_procore.projects_raw "
            "WHERE account_id = :a "
            "  AND source_id IN ('9991','9992') "
            "ORDER BY source_id"
        ), {"a": procore_connector_account})
        staged_rows = [(row["source_id"], row["n"]) for row in staged.mappings().all()]
        assert staged_rows == [
            ("9991", "P4a Test Alpha"),
            ("9992", "P4a Test Beta"),
        ]

        # sync_run finished in 'succeeded' state with correct counts
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id=:a AND resource_type='projects' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        run = sr.mappings().first()
        assert run is not None
        assert run["status"] == "succeeded"
        assert run["rows_fetched"] == 2
        assert run["rows_upserted"] == 2

        # Cursor advanced to the last procore_id (bigint as string)
        cur = await db_session.execute(text(
            "SELECT cursor_value FROM rex.sync_cursors "
            "WHERE connector_account_id=:a AND resource_type='projects'"
        ), {"a": procore_connector_account})
        cursor_value = cur.scalar_one()
        assert cursor_value == "9992"

    finally:
        await db_session.execute(text("DROP TABLE IF EXISTS procore.projects"))
        await db_session.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.projects' "
            "  AND external_id IN ('9991','9992')"
        ))
        await db_session.execute(text(
            "DELETE FROM rex.projects WHERE project_number LIKE 'P4A-SMOKE-%'"
        ))
        await db_session.execute(text(
            "DELETE FROM connector_procore.projects_raw WHERE account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.commit()
        import app.services.connectors.procore.rex_app_pool as mod2
        if mod2._pool:
            await mod2._pool.close()
            mod2._pool = None


@pytest.mark.asyncio
async def test_sync_resource_users_end_to_end(
    db_session, procore_connector_account, monkeypatch
):
    """Full root-resource pipeline for users: seed procore.users ->
    sync_resource('users') -> rex.people canonical rows +
    rex.connector_mappings source_links + sync_runs / sync_cursors state.

    Uses distinctive P4A-USER-* email addresses so teardown is safe even
    if a prior test run left residue.
    """
    import os
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    # Seed procore.users with the minimal column set build_user_payload
    # reads. DROP/CREATE instead of TRUNCATE because prior test runs may
    # have left a table with a different column shape.
    await db_session.execute(text("CREATE SCHEMA IF NOT EXISTS procore"))
    await db_session.execute(text("DROP TABLE IF EXISTS procore.users"))
    await db_session.execute(text("""
        CREATE TABLE procore.users (
            procore_id bigint PRIMARY KEY,
            first_name text,
            last_name text,
            full_name text,
            email_address text,
            mobile_phone text,
            business_phone text,
            job_title jsonb,
            is_active boolean,
            is_employee boolean,
            city text,
            state_code text,
            zip_code text,
            vendor_id bigint,
            employee_id text,
            created_at timestamptz,
            updated_at timestamptz,
            last_login_at timestamptz
        )
    """))
    await db_session.execute(text(
        "INSERT INTO procore.users "
        "(procore_id, first_name, last_name, email_address, is_active) "
        "VALUES (8801, 'Alpha', 'Tester', 'P4A-USER-ALPHA@test.invalid', true), "
        "       (8802, 'Beta',  'Tester', 'P4A-USER-BETA@test.invalid',  true)"
    ))
    await db_session.commit()

    try:
        result = await sync_resource(
            db_session,
            account_id=procore_connector_account,
            resource_type="users",
        )
        assert result["rows_fetched"] == 2
        assert result["rows_upserted"] == 2

        # Canonical rows landed in rex.people
        canonical = await db_session.execute(text(
            "SELECT first_name, last_name, email, role_type "
            "FROM rex.people "
            "WHERE email LIKE 'P4A-USER-%' "
            "ORDER BY email"
        ))
        rows = canonical.mappings().all()
        assert len(rows) == 2
        assert rows[0]["first_name"] == "Alpha"
        assert rows[0]["last_name"] == "Tester"
        assert rows[0]["email"] == "P4A-USER-ALPHA@test.invalid"
        assert rows[0]["role_type"] == "external"
        assert rows[1]["first_name"] == "Beta"

        # source_links: one per seeded procore user, pointing at rex.people
        links = await db_session.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.users' "
            "  AND external_id IN ('8801','8802')"
        ))
        assert links.scalar_one() == 2

        # Staging landed in connector_procore.users_raw
        staged = await db_session.execute(text(
            "SELECT source_id, payload->>'first_name' AS fn "
            "FROM connector_procore.users_raw "
            "WHERE account_id = :a "
            "  AND source_id IN ('8801','8802') "
            "ORDER BY source_id"
        ), {"a": procore_connector_account})
        staged_rows = [(row["source_id"], row["fn"]) for row in staged.mappings().all()]
        assert staged_rows == [
            ("8801", "Alpha"),
            ("8802", "Beta"),
        ]

        # sync_run finished in 'succeeded' state with correct counts
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id=:a AND resource_type='users' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        run = sr.mappings().first()
        assert run is not None
        assert run["status"] == "succeeded"
        assert run["rows_fetched"] == 2
        assert run["rows_upserted"] == 2

        # Cursor advanced to the last procore_id (bigint as string)
        cur = await db_session.execute(text(
            "SELECT cursor_value FROM rex.sync_cursors "
            "WHERE connector_account_id=:a AND resource_type='users'"
        ), {"a": procore_connector_account})
        cursor_value = cur.scalar_one()
        assert cursor_value == "8802"

    finally:
        await db_session.execute(text("DROP TABLE IF EXISTS procore.users"))
        # Order matters: connector_mappings references rex.people by rex_id,
        # so delete mappings first, then the canonical rows, then staging.
        await db_session.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.users' "
            "  AND external_id IN ('8801','8802')"
        ))
        await db_session.execute(text(
            "DELETE FROM rex.people WHERE email LIKE 'P4A-USER-%'"
        ))
        await db_session.execute(text(
            "DELETE FROM connector_procore.users_raw WHERE account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.commit()
        import app.services.connectors.procore.rex_app_pool as mod2
        if mod2._pool:
            await mod2._pool.close()
            mod2._pool = None


@pytest.mark.asyncio
async def test_sync_resource_submittals_end_to_end(
    db_session,
    procore_connector_account,
    project_with_source_link,
    monkeypatch,
):
    """Full project-scoped pipeline for submittals (Phase 4 Wave 2 direct API).

    Unlike the rfis path that reads procore.rfis via RexAppDbClient, this
    resource calls ProcoreClient.list_submittals directly. We mock
    ``ProcoreClient.from_env`` so the adapter returns a canned 2-row
    response without needing real Procore OAuth env vars.

    The ``project_with_source_link`` fixture seeds a rex.projects row
    mapped to procore project_id=42 via rex.connector_mappings — the
    orchestrator's per-project loop discovers the project, the adapter
    is called with project_external_id='42', and the mocked client
    returns the two canned rows.

    Asserts the full pipeline:
      1. Staging landed in connector_procore.submittals_raw (with
         project_source_id='42')
      2. Canonical rex.submittals rows exist, keyed on (project_id,
         submittal_number)
      3. rex.connector_mappings source_links point procore.submittals
         external_ids at rex.submittals canonical ids
      4. sync_runs row marked 'succeeded' with correct counts
    """
    from unittest.mock import AsyncMock, patch

    # Fake Procore API response that ProcoreClient.list_submittals would
    # return for project 42. Shape mirrors what the real API emits:
    # ``id``, ``number``, ``title``, ``status``, ``submittal_type``,
    # ``updated_at``, etc. build_submittal_payload normalizes this; the
    # mapper further normalizes status/type to canonical enums.
    fake_rows = [
        {
            "id": 701,
            "number": "SUB-P4W2-ALPHA",
            "title": "Alpha shop drawings",
            "status": "Open",
            "submittal_type": "Shop Drawings",
            "spec_section": "05 12 00",
            "due_date": "2026-05-15",
            "updated_at": "2026-04-22T10:00:00Z",
        },
        {
            "id": 702,
            "number": "SUB-P4W2-BETA",
            "title": "Beta product data",
            "status": "Approved",
            "submittal_type": "Product Data",
            "spec_section": "09 91 00",
            "due_date": "2026-06-01",
            "updated_at": "2026-04-22T11:00:00Z",
        },
    ]

    fake_client = AsyncMock()
    fake_client.list_submittals = AsyncMock(return_value=fake_rows)

    try:
        with patch(
            "app.services.ai.tools.procore_api.ProcoreClient.from_env",
            return_value=fake_client,
        ):
            result = await sync_resource(
                db_session,
                account_id=procore_connector_account,
                resource_type="submittals",
            )

        assert result["rows_fetched"] == 2
        assert result["rows_upserted"] == 2

        # Staging: connector_procore.submittals_raw got both rows scoped
        # to the right project_source_id.
        staged = await db_session.execute(text(
            "SELECT source_id, project_source_id, "
            "       payload->>'title' AS title "
            "FROM connector_procore.submittals_raw "
            "WHERE account_id = :a "
            "  AND source_id IN ('701','702') "
            "ORDER BY source_id"
        ), {"a": procore_connector_account})
        staged_rows = [
            (r["source_id"], r["project_source_id"], r["title"])
            for r in staged.mappings().all()
        ]
        assert staged_rows == [
            ("701", "42", "Alpha shop drawings"),
            ("702", "42", "Beta product data"),
        ]

        # Canonical: rex.submittals rows with normalized status/type enums.
        canonical = await db_session.execute(text(
            "SELECT submittal_number, title, status, submittal_type, "
            "       spec_section "
            "FROM rex.submittals "
            "WHERE project_id = :pid "
            "  AND submittal_number LIKE 'SUB-P4W2-%' "
            "ORDER BY submittal_number"
        ), {"pid": project_with_source_link})
        rows = canonical.mappings().all()
        assert len(rows) == 2
        # Row 0: 'Open' -> 'pending', 'Shop Drawings' -> 'shop_drawing'
        assert rows[0]["submittal_number"] == "SUB-P4W2-ALPHA"
        assert rows[0]["title"] == "Alpha shop drawings"
        assert rows[0]["status"] == "pending"
        assert rows[0]["submittal_type"] == "shop_drawing"
        assert rows[0]["spec_section"] == "05 12 00"
        # Row 1: 'Approved' -> 'approved', 'Product Data' -> 'product_data'
        assert rows[1]["submittal_number"] == "SUB-P4W2-BETA"
        assert rows[1]["status"] == "approved"
        assert rows[1]["submittal_type"] == "product_data"

        # source_links: one per seeded procore submittal
        links = await db_session.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.submittals' "
            "  AND external_id IN ('701','702')"
        ))
        assert links.scalar_one() == 2

        # sync_runs row: succeeded with correct counts
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id=:a AND resource_type='submittals' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        run = sr.mappings().first()
        assert run is not None
        assert run["status"] == "succeeded"
        assert run["rows_fetched"] == 2
        assert run["rows_upserted"] == 2

    finally:
        # Teardown: mappings first (FK to rex.submittals via rex_id),
        # then canonical rows, then staging + run state.
        await db_session.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.submittals' "
            "  AND external_id IN ('701','702')"
        ))
        await db_session.execute(text(
            "DELETE FROM rex.submittals "
            "WHERE submittal_number LIKE 'SUB-P4W2-%'"
        ))
        await db_session.execute(text(
            "DELETE FROM connector_procore.submittals_raw "
            "WHERE account_id = :a AND source_id IN ('701','702')"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.commit()


@pytest.mark.asyncio
async def test_sync_resource_daily_logs_end_to_end(
    db_session,
    procore_connector_account,
    project_with_source_link,
    monkeypatch,
):
    """Full project-scoped pipeline for daily_logs (Phase 4 Wave 2 direct API).

    Mirrors the submittals end-to-end test. Unlike the rfis path that
    reads procore.rfis via RexAppDbClient, this resource calls
    ProcoreClient.list_daily_logs directly. We mock
    ``ProcoreClient.from_env`` so the adapter returns a canned 2-row
    response without needing real Procore OAuth env vars.

    The ``project_with_source_link`` fixture seeds a rex.projects row
    mapped to procore project_id=42 via rex.connector_mappings — the
    orchestrator's per-project loop discovers the project, the adapter
    is called with project_external_id='42', and the mocked client
    returns the two canned rows.

    Asserts the full pipeline:
      1. Staging landed in connector_procore.daily_logs_raw (with
         project_source_id='42')
      2. Canonical rex.daily_logs rows exist, keyed on (project_id,
         log_date)
      3. rex.connector_mappings source_links point procore.daily_logs
         external_ids at rex.daily_logs canonical ids
      4. sync_runs row marked 'succeeded' with correct counts
    """
    from unittest.mock import AsyncMock, patch

    # Fake Procore API response that ProcoreClient.list_daily_logs would
    # return for project 42. Shape mirrors what the construction_report_logs
    # endpoint emits: ``id``, ``date``, ``is_published``, ``weather_conditions``
    # subobject, ``notes``, ``updated_at``. build_daily_log_payload normalizes
    # this; the mapper further derives status from is_published and
    # flattens weather.
    fake_rows = [
        {
            "id": 801,
            "date": "2026-04-22",
            "is_published": True,
            "notes": "Poured slab north wing.",
            "weather_conditions": {
                "conditions":       "Partly cloudy",
                "temperature_high": 72,
                "temperature_low":  55,
            },
            "updated_at": "2026-04-22T15:00:00Z",
        },
        {
            "id": 802,
            "date": "2026-04-21",
            "is_published": False,
            "notes": "Framing continues.",
            "weather_conditions": {
                "conditions":       "Clear",
                "temperature_high": 68,
                "temperature_low":  52,
            },
            "updated_at": "2026-04-21T15:00:00Z",
        },
    ]

    fake_client = AsyncMock()
    fake_client.list_daily_logs = AsyncMock(return_value=fake_rows)

    try:
        with patch(
            "app.services.ai.tools.procore_api.ProcoreClient.from_env",
            return_value=fake_client,
        ):
            result = await sync_resource(
                db_session,
                account_id=procore_connector_account,
                resource_type="daily_logs",
            )

        assert result["rows_fetched"] == 2
        assert result["rows_upserted"] == 2

        # Staging: connector_procore.daily_logs_raw got both rows scoped
        # to the right project_source_id.
        staged = await db_session.execute(text(
            "SELECT source_id, project_source_id, "
            "       payload->>'log_date' AS log_date "
            "FROM connector_procore.daily_logs_raw "
            "WHERE account_id = :a "
            "  AND source_id IN ('801','802') "
            "ORDER BY source_id"
        ), {"a": procore_connector_account})
        staged_rows = [
            (r["source_id"], r["project_source_id"], r["log_date"])
            for r in staged.mappings().all()
        ]
        assert staged_rows == [
            ("801", "42", "2026-04-22"),
            ("802", "42", "2026-04-21"),
        ]

        # Canonical: rex.daily_logs rows with derived status from
        # is_published and flattened weather.
        import datetime as _dt
        canonical = await db_session.execute(text(
            "SELECT log_date, status, weather_summary, "
            "       temp_high_f, temp_low_f, work_summary "
            "FROM rex.daily_logs "
            "WHERE project_id = :pid "
            "  AND log_date IN ('2026-04-22', '2026-04-21') "
            "ORDER BY log_date DESC"
        ), {"pid": project_with_source_link})
        rows = canonical.mappings().all()
        assert len(rows) == 2
        # Row 0: 2026-04-22, published -> 'submitted'
        assert rows[0]["log_date"] == _dt.date(2026, 4, 22)
        assert rows[0]["status"] == "submitted"
        assert rows[0]["weather_summary"] == "Partly cloudy"
        assert rows[0]["temp_high_f"] == 72
        assert rows[0]["temp_low_f"] == 55
        assert rows[0]["work_summary"] == "Poured slab north wing."
        # Row 1: 2026-04-21, unpublished -> 'draft'
        assert rows[1]["log_date"] == _dt.date(2026, 4, 21)
        assert rows[1]["status"] == "draft"
        assert rows[1]["weather_summary"] == "Clear"

        # source_links: one per seeded procore daily_log
        links = await db_session.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.daily_logs' "
            "  AND external_id IN ('801','802')"
        ))
        assert links.scalar_one() == 2

        # sync_runs row: succeeded with correct counts
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id=:a AND resource_type='daily_logs' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        run = sr.mappings().first()
        assert run is not None
        assert run["status"] == "succeeded"
        assert run["rows_fetched"] == 2
        assert run["rows_upserted"] == 2

    finally:
        # Teardown: mappings first (FK to rex.daily_logs via rex_id),
        # then canonical rows, then staging + run state.
        await db_session.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.daily_logs' "
            "  AND external_id IN ('801','802')"
        ))
        await db_session.execute(text(
            "DELETE FROM rex.daily_logs "
            "WHERE project_id = :pid "
            "  AND log_date IN ('2026-04-22', '2026-04-21')"
        ), {"pid": project_with_source_link})
        await db_session.execute(text(
            "DELETE FROM connector_procore.daily_logs_raw "
            "WHERE account_id = :a AND source_id IN ('801','802')"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.commit()


@pytest.mark.asyncio
async def test_sync_resource_schedule_activities_end_to_end(
    db_session,
    procore_connector_account,
    project_with_source_link,
    monkeypatch,
):
    """Full project-scoped pipeline for schedule_activities (Phase 4 Wave
    2 direct API). Mirrors the submittals / daily_logs end-to-end tests
    with an additional assertion on the rex.schedules bootstrap.

    Unique to this resource: rex.schedule_activities.schedule_id is a
    NOT NULL FK to rex.schedules, and Procore's standard_tasks endpoint
    has no first-class "schedule" concept. The writer bootstraps a
    "Procore default schedule" row per project on the fly. The test
    asserts that after the sync, exactly one rex.schedules row exists
    for the project with the expected name.

    Pipeline assertions:
      1. Staging landed in connector_procore.schedule_tasks_raw (with
         project_source_id='42')
      2. A rex.schedules row was bootstrapped for the project
      3. Canonical rex.schedule_activities rows exist, keyed on
         (schedule_id, activity_number)
      4. rex.connector_mappings source_links point
         procore.schedule_activities external_ids at rex.schedule_activities
         canonical ids
      5. sync_runs row marked 'succeeded' with correct counts
    """
    from unittest.mock import AsyncMock, patch

    # Fake Procore API response that ProcoreClient.list_schedule_tasks
    # would return for project 42. Shape mirrors what the standard_tasks
    # endpoint emits: ``id``, ``task_number``, ``name``, ``start_date``,
    # ``finish_date``, ``percent_complete``, ``updated_at``.
    # build_schedule_activity_payload normalizes this; the mapper
    # defaults activity_type to 'task' and bootstraps the schedule name.
    fake_rows = [
        {
            "id": 901,
            "task_number": "A-100",
            "name": "Pour footings",
            "start_date": "2026-05-01",
            "finish_date": "2026-05-05",
            "percent_complete": 25,
            "updated_at": "2026-04-22T15:00:00Z",
        },
        {
            "id": 902,
            "task_number": "A-200",
            "name": "Form walls",
            "start_date": "2026-05-06",
            "finish_date": "2026-05-10",
            "percent_complete": 0,
            "updated_at": "2026-04-22T16:00:00Z",
        },
    ]

    fake_client = AsyncMock()
    fake_client.list_schedule_tasks = AsyncMock(return_value=fake_rows)

    try:
        with patch(
            "app.services.ai.tools.procore_api.ProcoreClient.from_env",
            return_value=fake_client,
        ):
            result = await sync_resource(
                db_session,
                account_id=procore_connector_account,
                resource_type="schedule_activities",
            )

        assert result["rows_fetched"] == 2
        assert result["rows_upserted"] == 2

        # Staging: connector_procore.schedule_tasks_raw got both rows
        # scoped to the right project_source_id.
        staged = await db_session.execute(text(
            "SELECT source_id, project_source_id, "
            "       payload->>'name' AS name "
            "FROM connector_procore.schedule_tasks_raw "
            "WHERE account_id = :a "
            "  AND source_id IN ('901','902') "
            "ORDER BY source_id"
        ), {"a": procore_connector_account})
        staged_rows = [
            (r["source_id"], r["project_source_id"], r["name"])
            for r in staged.mappings().all()
        ]
        assert staged_rows == [
            ("901", "42", "Pour footings"),
            ("902", "42", "Form walls"),
        ]

        # Bootstrap: exactly one rex.schedules row for the project with
        # the expected name. The writer should converge on the same
        # schedule row for both activities (not create a second one on
        # the second activity's upsert).
        schedules = await db_session.execute(text(
            "SELECT name, schedule_type, status "
            "FROM rex.schedules "
            "WHERE project_id = :pid "
            "  AND name = 'Procore default schedule'"
        ), {"pid": project_with_source_link})
        sched_rows = schedules.mappings().all()
        assert len(sched_rows) == 1
        assert sched_rows[0]["name"] == "Procore default schedule"
        assert sched_rows[0]["schedule_type"] == "master"
        assert sched_rows[0]["status"] == "active"

        # Canonical: rex.schedule_activities rows keyed on
        # (schedule_id, activity_number). Both should attach to the
        # single bootstrapped schedule.
        import datetime as _dt
        canonical = await db_session.execute(text(
            "SELECT sa.activity_number, sa.name, sa.activity_type, "
            "       sa.start_date, sa.end_date, sa.percent_complete "
            "FROM rex.schedule_activities sa "
            "JOIN rex.schedules s ON s.id = sa.schedule_id "
            "WHERE s.project_id = :pid "
            "  AND sa.activity_number IN ('A-100', 'A-200') "
            "ORDER BY sa.activity_number"
        ), {"pid": project_with_source_link})
        rows = canonical.mappings().all()
        assert len(rows) == 2
        # Row 0: A-100 — Pour footings (task, 25% complete)
        assert rows[0]["activity_number"] == "A-100"
        assert rows[0]["name"] == "Pour footings"
        assert rows[0]["activity_type"] == "task"
        assert rows[0]["start_date"] == _dt.date(2026, 5, 1)
        assert rows[0]["end_date"] == _dt.date(2026, 5, 5)
        assert rows[0]["percent_complete"] == 25
        # Row 1: A-200 — Form walls (task, 0% complete)
        assert rows[1]["activity_number"] == "A-200"
        assert rows[1]["name"] == "Form walls"
        assert rows[1]["percent_complete"] == 0

        # source_links: one per seeded procore schedule task, pointing at
        # rex.schedule_activities canonical rows.
        links = await db_session.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.schedule_activities' "
            "  AND external_id IN ('901','902')"
        ))
        assert links.scalar_one() == 2

        # sync_runs row: succeeded with correct counts
        sr = await db_session.execute(text(
            "SELECT status, rows_fetched, rows_upserted "
            "FROM rex.sync_runs "
            "WHERE connector_account_id=:a "
            "  AND resource_type='schedule_activities' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": procore_connector_account})
        run = sr.mappings().first()
        assert run is not None
        assert run["status"] == "succeeded"
        assert run["rows_fetched"] == 2
        assert run["rows_upserted"] == 2

    finally:
        # Teardown: mappings first (FK to rex.schedule_activities via
        # rex_id), then canonical activity rows, then the bootstrapped
        # schedule row, then staging + run state.
        await db_session.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' "
            "  AND source_table='procore.schedule_activities' "
            "  AND external_id IN ('901','902')"
        ))
        await db_session.execute(text(
            "DELETE FROM rex.schedule_activities sa "
            "USING rex.schedules s "
            "WHERE sa.schedule_id = s.id "
            "  AND s.project_id = :pid "
            "  AND sa.activity_number IN ('A-100', 'A-200')"
        ), {"pid": project_with_source_link})
        await db_session.execute(text(
            "DELETE FROM rex.schedules "
            "WHERE project_id = :pid "
            "  AND name = 'Procore default schedule'"
        ), {"pid": project_with_source_link})
        await db_session.execute(text(
            "DELETE FROM connector_procore.schedule_tasks_raw "
            "WHERE account_id = :a AND source_id IN ('901','902')"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": procore_connector_account})
        await db_session.commit()

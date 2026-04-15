"""Session 2 migration sanity tests.

Verifies that all 14 Session 2 migration slots (009-022) are in
MIGRATION_ORDER and that the expected rex.* tables + connector_*
schemas exist on the live test DB after migrate.py runs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.migrate import MIGRATION_ORDER


SESSION2_MIGRATIONS = [
    "009_rbac_roles_permissions.sql",
    "010_user_roles_preferences.sql",
    "011_project_assignment_bridges.sql",
    "012_connector_registry.sql",
    "013_connector_procore_stage.sql",
    "014_connector_exxir_stage.sql",
    "015_sync_runs_and_source_links.sql",
    "016_canonical_core_additions.sql",
    "017_canonical_pm_additions.sql",
    "018_canonical_financial_additions.sql",
    "019_canonical_schedule_additions.sql",
    "020_canonical_docs_quality_additions.sql",
    "021_seed_roles_and_aliases.sql",
    "022_canonical_read_views.sql",
]


def test_session2_migrations_in_order():
    """Every Session 2 slot is present in MIGRATION_ORDER in ascending order."""
    missing = [m for m in SESSION2_MIGRATIONS if m not in MIGRATION_ORDER]
    assert not missing, f"Session 2 migrations missing from MIGRATION_ORDER: {missing}"

    # Verify they land in the correct order (009 before 010, ..., 021 before 022).
    positions = [MIGRATION_ORDER.index(m) for m in SESSION2_MIGRATIONS]
    assert positions == sorted(positions), (
        f"Session 2 migrations are not in ascending order: {positions}"
    )


async def test_session2_rbac_tables_exist(rollback_client):
    """The four RBAC tables from 009 exist."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        for tbl in ("roles", "permissions", "role_permissions", "role_aliases"):
            row = (await db.execute(
                text("SELECT to_regclass(:q) AS reg"),
                {"q": f"rex.{tbl}"},
            )).mappings().first()
            assert row["reg"] is not None, f"rex.{tbl} missing"


async def test_session2_user_role_objects_exist(rollback_client):
    """010 objects: user_roles table, user_preferences table, v_users view."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        for name in ("user_roles", "user_preferences"):
            row = (await db.execute(
                text("SELECT to_regclass(:q) AS reg"),
                {"q": f"rex.{name}"},
            )).mappings().first()
            assert row["reg"] is not None, f"rex.{name} missing"
        # v_users is a view — to_regclass handles views too.
        row = (await db.execute(
            text("SELECT to_regclass('rex.v_users') AS reg"),
        )).mappings().first()
        assert row["reg"] is not None, "rex.v_users view missing"


async def test_session2_connector_schemas_exist(rollback_client):
    """013 and 014 create the two connector-specific schemas."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        rows = (await db.execute(
            text(
                "SELECT nspname FROM pg_namespace "
                "WHERE nspname IN ('connector_procore', 'connector_exxir') "
                "ORDER BY nspname"
            )
        )).mappings().all()
        names = [r["nspname"] for r in rows]
        assert names == ["connector_exxir", "connector_procore"], (
            f"expected both connector schemas, got {names}"
        )


async def test_session2_connector_registry_tables_exist(rollback_client):
    """012 + 015 connector control-plane tables exist."""
    from app.database import async_session_factory
    expected = {
        "connectors", "connector_accounts",
        "sync_runs", "sync_cursors", "connector_event_log",
    }
    async with async_session_factory() as db:
        for tbl in expected:
            row = (await db.execute(
                text("SELECT to_regclass(:q) AS reg"),
                {"q": f"rex.{tbl}"},
            )).mappings().first()
            assert row["reg"] is not None, f"rex.{tbl} missing"


async def test_session2_source_links_view(rollback_client):
    """rex.source_links view from 015 resolves and has charter columns."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        row = (await db.execute(
            text("SELECT to_regclass('rex.source_links') AS reg")
        )).mappings().first()
        assert row["reg"] is not None, "rex.source_links view missing"

        cols = [r["column_name"] for r in (await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'rex' AND table_name = 'source_links' "
                "ORDER BY ordinal_position"
            )
        )).mappings().all()]
        expected_columns = {
            "connector_key", "source_table", "source_id",
            "canonical_table", "canonical_id", "project_id", "metadata",
        }
        missing = expected_columns - set(cols)
        assert not missing, f"source_links view missing columns: {missing}"


async def test_session2_canonical_additions_exist(rollback_client):
    """017-020 net-new canonical tables exist."""
    from app.database import async_session_factory
    expected = {
        "meeting_decisions", "pending_decisions",
        "procurement_items", "delay_events",
        "quality_findings", "weather_observations",
        "project_locations", "project_calendars",
    }
    async with async_session_factory() as db:
        for tbl in expected:
            row = (await db.execute(
                text("SELECT to_regclass(:q) AS reg"),
                {"q": f"rex.{tbl}"},
            )).mappings().first()
            assert row["reg"] is not None, f"rex.{tbl} missing"

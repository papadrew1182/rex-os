"""Session 2 view smoke + endpoint contract tests.

Covers:
  - the seven top-level rex.v_* views resolve and return rows
  - /api/me returns charter-shaped user envelope
  - /api/me/permissions returns a list of canonical permission slugs
  - /api/context/current resolves to the caller's project + suggested actions
  - /api/connectors lists both procore and exxir
  - /api/connectors/health returns per-connector health rollup
  - source_links uniqueness guarantee via rex.connector_mappings unique key
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text


CANONICAL_VIEWS = [
    "v_project_mgmt",
    "v_financials",
    "v_schedule",
    "v_directory",
    "v_portfolio",
    "v_risk",
    "v_myday",
]


async def test_all_canonical_views_exist(rollback_client):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        for v in CANONICAL_VIEWS:
            row = (await db.execute(
                text("SELECT to_regclass(:q) AS reg"),
                {"q": f"rex.{v}"},
            )).mappings().first()
            assert row["reg"] is not None, f"rex.{v} missing"


async def test_v_project_mgmt_returns_rows(rollback_client):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        count = (await db.execute(
            text("SELECT COUNT(*) FROM rex.v_project_mgmt")
        )).scalar_one()
        # May be zero in a fresh DB, but the query itself must succeed.
        assert count >= 0


async def test_v_financials_returns_one_row_per_project(rollback_client):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        view_count = (await db.execute(
            text("SELECT COUNT(*) FROM rex.v_financials")
        )).scalar_one()
        project_count = (await db.execute(
            text("SELECT COUNT(*) FROM rex.projects")
        )).scalar_one()
        assert view_count == project_count, (
            f"v_financials should have one row per project ({project_count}), got {view_count}"
        )


async def test_v_risk_query_succeeds(rollback_client):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        rows = (await db.execute(
            text("SELECT risk_type, project_id FROM rex.v_risk LIMIT 10")
        )).mappings().all()
        # Just verifies the UNION ALL compiles + can execute with real schema
        assert isinstance(rows, list)


async def test_v_myday_query_succeeds(rollback_client):
    """v_myday joins user_accounts + people + project_members + many lateral
    subqueries. This test just confirms it compiles + executes."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        rows = (await db.execute(
            text("SELECT user_account_id, item_type, project_id FROM rex.v_myday LIMIT 5")
        )).mappings().all()
        assert isinstance(rows, list)


# ── Endpoint contract tests (via the stub_admin client fixture) ─────────

async def test_me_endpoint_returns_charter_shape(client: AsyncClient):
    """client fixture injects the stub admin user, so /api/me should
    return a charter-shaped envelope for that user."""
    r = await client.get("/api/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "user" in body
    user = body["user"]
    for key in ("id", "email", "full_name", "primary_role_key",
                "role_keys", "legacy_role_aliases", "project_ids", "feature_flags"):
        assert key in user, f"/api/me missing key: {key}"
    assert isinstance(user["role_keys"], list)
    assert isinstance(user["legacy_role_aliases"], list)
    assert isinstance(user["project_ids"], list)
    assert isinstance(user["feature_flags"], dict)


async def test_me_permissions_endpoint_returns_list(client: AsyncClient):
    r = await client.get("/api/me/permissions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "permissions" in body
    perms = body["permissions"]
    assert isinstance(perms, list)
    # The seeded admin user (aroberts) backfills to VP role via global_role
    # = 'vp' alias. VP has all permissions.
    if perms:
        assert all(isinstance(p, str) for p in perms)


async def test_context_current_endpoint_shape(client: AsyncClient):
    r = await client.get("/api/context/current")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("project", "route", "page_context", "assistant_defaults"):
        assert key in body, f"/api/context/current missing key: {key}"
    assert "suggested_action_slugs" in body["assistant_defaults"]
    assert isinstance(body["assistant_defaults"]["suggested_action_slugs"], list)


async def test_connectors_endpoint_lists_procore_and_exxir(client: AsyncClient):
    r = await client.get("/api/connectors")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    keys = [i["connector_key"] for i in items]
    assert "procore" in keys, f"procore missing from /api/connectors: {keys}"
    assert "exxir" in keys, f"exxir missing from /api/connectors: {keys}"
    for item in items:
        assert item["status"] in (
            "connected", "configured", "disconnected", "error", "disabled"
        )


async def test_connectors_health_endpoint_shape(client: AsyncClient):
    r = await client.get("/api/connectors/health")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) >= 2
    for item in items:
        for key in ("connector_key", "label", "healthy",
                    "last_success_at", "last_error_at", "last_error_message"):
            assert key in item
        assert isinstance(item["healthy"], bool)


async def test_source_link_uniqueness_constraint_exists(rollback_client):
    """The charter requires unique (connector_key, source_table, source_id).
    rex.source_links is a view over rex.connector_mappings, which enforces
    the equivalent uniqueness via (rex_table, connector, external_id).
    Verify by inspecting pg_constraint — no data writes, no ordering hazard.
    """
    from app.database import async_session_factory
    async with async_session_factory() as db:
        # The uq_connector_mapping constraint is defined in
        # rex2_foundation_bootstrap.sql and/or rex2_canonical_ddl.sql.
        # Query pg_constraint directly rather than trying to trigger it.
        row = (await db.execute(
            text(
                """
                SELECT conname, pg_get_constraintdef(c.oid) AS def
                FROM pg_constraint c
                JOIN pg_class cl ON cl.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = cl.relnamespace
                WHERE n.nspname = 'rex'
                  AND cl.relname = 'connector_mappings'
                  AND c.contype = 'u'
                """
            )
        )).mappings().first()
        assert row is not None, (
            "rex.connector_mappings must have a unique constraint backing "
            "the (connector_key, source_table, source_id) contract from "
            "rex.source_links"
        )
        defn = row["def"]
        assert "rex_table" in defn and "connector" in defn and "external_id" in defn, (
            f"unique constraint {row['conname']!r} does not cover the expected "
            f"column set: {defn}"
        )

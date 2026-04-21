"""adapter.list_projects — reads procore.projects.

Exercises the same schema-bootstrap pattern as test_adapter_fetch_rfis.py.
Points REX_APP_DATABASE_URL at the dev DATABASE_URL so the adapter's
RexAppDbClient pool speaks to the same Postgres we seed below.

The real Rex App DB has 8 projects and uses procore_id (bigint) as the
monotonic cursor because procore.projects.updated_at is NULL for most
rows — see payloads.build_project_payload + adapter.list_projects.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from app.services.connectors.procore.adapter import ProcoreAdapter
from app.services.connectors.procore.rex_app_pool import (
    close_rex_app_pool,
    get_rex_app_pool,
)


@pytest_asyncio.fixture
async def setup_projects(monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None
    pool = await get_rex_app_pool()

    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS procore")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS procore.projects (
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
        """)
        await conn.execute("TRUNCATE procore.projects")
        await conn.executemany(
            "INSERT INTO procore.projects "
            "(procore_id, project_name, project_number, status) "
            "VALUES ($1, $2, $3, $4)",
            [
                (1001, "Alpha Bldg", "A-001", "Active"),
                (1002, "Beta Bldg",  "B-002", "Active"),
                (1003, "Gamma Bldg", "G-003", "Inactive"),
            ],
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE procore.projects")
    await close_rex_app_pool()


@pytest.mark.asyncio
async def test_list_projects_returns_all_rows(setup_projects):
    """One page should return every seeded row since the default page
    size is comfortably above 3."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_projects()
    ids = [item["id"] for item in page.items]
    assert "1001" in ids
    assert "1002" in ids
    assert "1003" in ids
    # Cursor set to the last item's id (bigint as string) so the next
    # call starts from procore_id > this value.
    assert page.next_cursor == "1003"


@pytest.mark.asyncio
async def test_list_projects_cursor_advances(setup_projects):
    """Second call with the first call's next_cursor should return no
    new rows (we already consumed everything)."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    first = await adapter.list_projects()
    second = await adapter.list_projects(cursor=first.next_cursor)
    assert second.items == []
    assert second.next_cursor is None


@pytest.mark.asyncio
async def test_list_projects_respects_cursor(setup_projects):
    """Passing a mid-range cursor (procore_id > 1001) should return
    only the later rows."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_projects(cursor="1001")
    ids = [item["id"] for item in page.items]
    assert ids == ["1002", "1003"]


@pytest.mark.asyncio
async def test_list_projects_payload_shape(setup_projects):
    """Smoke-check the payload shape matches build_project_payload's
    contract: ``id``, ``project_name``, ``status``, and
    ``project_source_id = None`` (root resource)."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_projects()
    items_by_id = {item["id"]: item for item in page.items}
    alpha = items_by_id["1001"]
    assert alpha["project_name"] == "Alpha Bldg"
    assert alpha["project_number"] == "A-001"
    assert alpha["status"] == "Active"
    assert alpha["project_source_id"] is None

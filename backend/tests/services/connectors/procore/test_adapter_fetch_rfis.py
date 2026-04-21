import os
import pytest
from datetime import datetime, timezone
from app.services.connectors.procore.rex_app_pool import (
    get_rex_app_pool,
    close_rex_app_pool,
)
from app.services.connectors.procore.adapter import ProcoreAdapter


@pytest.fixture
async def setup_rfis_fixture(monkeypatch):
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
            CREATE TABLE IF NOT EXISTS procore.rfis (
                procore_id   bigint PRIMARY KEY,
                project_id   bigint,
                project_name text,
                number       numeric(10,2),
                subject      text,
                question     text,
                answer       text,
                status       text,
                ball_in_court text,
                assignee     text,
                rfi_manager  text,
                due_date     timestamptz,
                closed_at    timestamptz,
                created_at   timestamptz,
                updated_at   timestamptz,
                cost_impact  numeric,
                schedule_impact numeric
            )
        """)
        await conn.execute("TRUNCATE procore.rfis")
        await conn.executemany(
            "INSERT INTO procore.rfis (procore_id, project_id, subject, status, updated_at) "
            "VALUES ($1,$2,$3,$4,$5)",
            [
                (101, 42, "a", "open",   datetime(2026,1,1,tzinfo=timezone.utc)),
                (102, 42, "b", "open",   datetime(2026,1,2,tzinfo=timezone.utc)),
                (103, 99, "c", "closed", datetime(2026,1,3,tzinfo=timezone.utc)),
            ],
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE procore.rfis")
    await close_rex_app_pool()


@pytest.mark.asyncio
async def test_fetch_rfis_scopes_to_project(setup_rfis_fixture):
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.fetch_rfis(project_external_id="42")
    ids = [item["id"] for item in page.items]
    assert ids == ["101", "102"]


@pytest.mark.asyncio
async def test_fetch_rfis_advances_cursor(setup_rfis_fixture):
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page1 = await adapter.fetch_rfis(project_external_id="42")
    assert page1.next_cursor is not None
    page2 = await adapter.fetch_rfis(
        project_external_id="42",
        cursor=page1.next_cursor,
    )
    assert page2.items == []


@pytest.mark.asyncio
async def test_fetch_rfis_rejects_non_numeric_project_id(setup_rfis_fixture):
    adapter = ProcoreAdapter(account_id="00000000-0000-0000-0000-000000000001", config={})
    with pytest.raises(ValueError, match="numeric procore project id"):
        await adapter.fetch_rfis(project_external_id="not-a-number")


@pytest.mark.asyncio
async def test_fetch_rfis_raises_when_last_row_has_null_updated_at(monkeypatch):
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
            CREATE TABLE IF NOT EXISTS procore.rfis (
                procore_id   bigint PRIMARY KEY,
                project_id   bigint,
                number       numeric(10,2),
                subject      text,
                status       text,
                updated_at   timestamptz
            )
        """)
        await conn.execute("TRUNCATE procore.rfis")
        await conn.execute(
            "INSERT INTO procore.rfis (procore_id, project_id, subject, status, updated_at) "
            "VALUES (201, 42, 'nulltest', 'open', NULL)"
        )

    try:
        adapter = ProcoreAdapter(account_id="00000000-0000-0000-0000-000000000001", config={})
        with pytest.raises(ValueError, match="cannot advance cursor"):
            await adapter.fetch_rfis(project_external_id="42")
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DROP TABLE procore.rfis")
        await close_rex_app_pool()

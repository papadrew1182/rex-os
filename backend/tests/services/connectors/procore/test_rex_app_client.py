import os
import pytest
from datetime import datetime, timezone
from app.services.connectors.procore.rex_app_pool import (
    get_rex_app_pool,
    close_rex_app_pool,
)
from app.services.connectors.procore.rex_app_client import RexAppDbClient


@pytest.fixture
async def pool(monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None
    pool = await get_rex_app_pool()
    yield pool
    await close_rex_app_pool()


@pytest.fixture
async def fake_procore_rfis(pool):
    """Create a tiny procore.rfis table, seed 3 rows, clean up."""
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS procore")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS procore.rfis (
                procore_id bigint PRIMARY KEY,
                project_id bigint,
                subject text,
                status text,
                updated_at timestamptz
            )
        """)
        await conn.execute("TRUNCATE procore.rfis")
        await conn.executemany(
            "INSERT INTO procore.rfis (procore_id, project_id, subject, status, updated_at) "
            "VALUES ($1, $2, $3, $4, $5)",
            [
                (1, 100, "r1", "open",   datetime(2026, 1, 1, tzinfo=timezone.utc)),
                (2, 100, "r2", "open",   datetime(2026, 1, 2, tzinfo=timezone.utc)),
                (3, 100, "r3", "closed", datetime(2026, 1, 3, tzinfo=timezone.utc)),
            ],
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE procore.rfis")


@pytest.mark.asyncio
async def test_fetch_rows_no_cursor_returns_all_ordered(pool, fake_procore_rfis):
    client = RexAppDbClient(pool)
    rows = await client.fetch_rows(
        schema="procore",
        table="rfis",
        cursor_col="updated_at",
        cursor_value=None,
        limit=10,
    )
    assert [r["procore_id"] for r in rows] == [1, 2, 3]


@pytest.mark.asyncio
async def test_fetch_rows_respects_cursor(pool, fake_procore_rfis):
    client = RexAppDbClient(pool)
    rows = await client.fetch_rows(
        schema="procore",
        table="rfis",
        cursor_col="updated_at",
        cursor_value=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat(),
        limit=10,
    )
    assert [r["procore_id"] for r in rows] == [2, 3]


@pytest.mark.asyncio
async def test_fetch_rows_respects_limit(pool, fake_procore_rfis):
    client = RexAppDbClient(pool)
    rows = await client.fetch_rows(
        schema="procore",
        table="rfis",
        cursor_col="updated_at",
        cursor_value=None,
        limit=2,
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_fetch_rows_respects_filters(pool, fake_procore_rfis):
    client = RexAppDbClient(pool)
    rows = await client.fetch_rows(
        schema="procore",
        table="rfis",
        cursor_col="updated_at",
        cursor_value=None,
        limit=10,
        filters=[("status", "=", "closed")],
    )
    assert [r["procore_id"] for r in rows] == [3]


@pytest.mark.asyncio
async def test_fetch_rows_rejects_non_identifier_schema(pool):
    client = RexAppDbClient(pool)
    with pytest.raises(ValueError, match="identifier"):
        await client.fetch_rows(
            schema="public; DROP TABLE foo;",
            table="rfis",
            cursor_col="updated_at",
            cursor_value=None,
            limit=10,
        )


@pytest.mark.asyncio
async def test_fetch_rows_rejects_bad_filter_op(pool):
    client = RexAppDbClient(pool)
    with pytest.raises(ValueError, match="op"):
        await client.fetch_rows(
            schema="procore",
            table="rfis",
            cursor_col="updated_at",
            cursor_value=None,
            limit=10,
            filters=[("status", "OR 1=1 --", "open")],
        )

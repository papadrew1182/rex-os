"""adapter.list_users — reads procore.users.

Exercises the same schema-bootstrap pattern as test_adapter_list_projects.py.
Points REX_APP_DATABASE_URL at the dev DATABASE_URL so the adapter's
RexAppDbClient pool speaks to the same Postgres we seed below.

The real Rex App DB has ~615 users and uses procore_id (bigint) as the
monotonic cursor because procore.users.updated_at is NULL for most
rows — see payloads.build_user_payload + adapter.list_users.
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
async def setup_users(monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None
    pool = await get_rex_app_pool()

    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS procore")
        # Minimal column set for the payload builder. job_title is jsonb
        # on the real source (multiselect); the test table mirrors that.
        await conn.execute("DROP TABLE IF EXISTS procore.users")
        await conn.execute("""
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
        """)
        await conn.executemany(
            "INSERT INTO procore.users "
            "(procore_id, first_name, last_name, email_address, is_active) "
            "VALUES ($1, $2, $3, $4, $5)",
            [
                (7001, "Alpha", "User",  "alpha@test.invalid", True),
                (7002, "Beta",  "User",  "beta@test.invalid",  True),
                (7003, "Gamma", "User",  "gamma@test.invalid", False),
            ],
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS procore.users")
    await close_rex_app_pool()


@pytest.mark.asyncio
async def test_list_users_returns_all_rows(setup_users):
    """One page should return every seeded row since the default page
    size is comfortably above 3."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_users()
    ids = [item["id"] for item in page.items]
    assert "7001" in ids
    assert "7002" in ids
    assert "7003" in ids
    # Cursor set to the last item's id (bigint as string) so the next
    # call starts from procore_id > this value.
    assert page.next_cursor == "7003"


@pytest.mark.asyncio
async def test_list_users_cursor_advances(setup_users):
    """Second call with the first call's next_cursor should return no
    new rows (we already consumed everything)."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    first = await adapter.list_users()
    second = await adapter.list_users(cursor=first.next_cursor)
    assert second.items == []
    assert second.next_cursor is None


@pytest.mark.asyncio
async def test_list_users_respects_cursor(setup_users):
    """Passing a mid-range cursor (procore_id > 7001) should return
    only the later rows."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_users(cursor="7001")
    ids = [item["id"] for item in page.items]
    assert ids == ["7002", "7003"]


@pytest.mark.asyncio
async def test_list_users_payload_shape(setup_users):
    """Smoke-check the payload shape matches build_user_payload's
    contract: ``id``, ``first_name``, ``email``, and
    ``project_source_id = None`` (root resource)."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_users()
    items_by_id = {item["id"]: item for item in page.items}
    alpha = items_by_id["7001"]
    assert alpha["first_name"] == "Alpha"
    assert alpha["last_name"] == "User"
    assert alpha["email"] == "alpha@test.invalid"
    assert alpha["project_source_id"] is None

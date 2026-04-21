"""adapter.list_vendors — reads procore.vendors.

Exercises the same schema-bootstrap pattern as test_adapter_list_users.py.
Points REX_APP_DATABASE_URL at the dev DATABASE_URL so the adapter's
RexAppDbClient pool speaks to the same Postgres we seed below.

The real Rex App DB has ~619 vendors and uses procore_id (bigint) as
the monotonic cursor for consistency with projects/users — even though
procore.vendors.updated_at IS populated on the live source, staying on
procore_id keeps the cursor type uniform across the three root
resources. See payloads.build_vendor_payload + adapter.list_vendors.
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
async def setup_vendors(monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None
    pool = await get_rex_app_pool()

    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS procore")
        # Minimal column set for the payload builder. The real source
        # has 57 columns but the builder reads only ~30.
        await conn.execute("DROP TABLE IF EXISTS procore.vendors")
        await conn.execute("""
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
        """)
        await conn.executemany(
            "INSERT INTO procore.vendors "
            "(procore_id, vendor_name, trade_name, is_active) "
            "VALUES ($1, $2, $3, $4)",
            [
                (7001, "Alpha Subs LLC",  "Electrical", True),
                (7002, "Beta Subs LLC",   "Plumbing",   True),
                (7003, "Gamma Subs LLC",  "Framing",    False),
            ],
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS procore.vendors")
    await close_rex_app_pool()


@pytest.mark.asyncio
async def test_list_vendors_returns_all_rows(setup_vendors):
    """One page should return every seeded row since the default page
    size is comfortably above 3."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_vendors()
    ids = [item["id"] for item in page.items]
    assert "7001" in ids
    assert "7002" in ids
    assert "7003" in ids
    # Cursor set to the last item's id (bigint as string) so the next
    # call starts from procore_id > this value.
    assert page.next_cursor == "7003"


@pytest.mark.asyncio
async def test_list_vendors_cursor_advances(setup_vendors):
    """Second call with the first call's next_cursor should return no
    new rows (we already consumed everything)."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    first = await adapter.list_vendors()
    second = await adapter.list_vendors(cursor=first.next_cursor)
    assert second.items == []
    assert second.next_cursor is None


@pytest.mark.asyncio
async def test_list_vendors_respects_cursor(setup_vendors):
    """Passing a mid-range cursor (procore_id > 7001) should return
    only the later rows."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_vendors(cursor="7001")
    ids = [item["id"] for item in page.items]
    assert ids == ["7002", "7003"]


@pytest.mark.asyncio
async def test_list_vendors_payload_shape(setup_vendors):
    """Smoke-check the payload shape matches build_vendor_payload's
    contract: ``id``, ``vendor_name``, ``trade_name``, and
    ``project_source_id = None`` (root/company-level resource)."""
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.list_vendors()
    items_by_id = {item["id"]: item for item in page.items}
    alpha = items_by_id["7001"]
    assert alpha["vendor_name"] == "Alpha Subs LLC"
    assert alpha["trade_name"] == "Electrical"
    assert alpha["project_source_id"] is None

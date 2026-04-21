"""Tests for connector_procore staging-table upserts (Task 5).

Verifies the upsert_raw behavior against the live dev DB:
  - inserts new rows on first call
  - subsequent call with unchanged payload is a no-op (checksum dedup)
  - subsequent call with changed payload updates the row

There are no pre-existing ``db_session`` or ``procore_connector_account``
fixtures in this repo for connector_procore tests, so we inline both:
  - a SQLAlchemy AsyncSession bound to the dev DB via async_session_factory
  - a freshly seeded rex.connector_accounts row for the procore kind

Both fixtures clean up after themselves.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.database import async_session_factory
from app.services.connectors.procore.staging import upsert_raw


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

    Yields the UUID of the account, and TRUNCATEs the rfis_raw rows we
    wrote for that account, then deletes the account itself on teardown.
    """
    account_label = f"test-staging-{uuid.uuid4()}"
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

    # Teardown: delete any rows we wrote during the test. The connector_accounts
    # row has ON DELETE CASCADE for rfis_raw so deleting the account is enough,
    # but be explicit for clarity.
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


@pytest.mark.asyncio
async def test_upsert_raw_inserts_new_rows(db_session, procore_connector_account):
    items = [
        {
            "id": "101",
            "project_source_id": "42",
            "subject": "a",
            "updated_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "id": "102",
            "project_source_id": "42",
            "subject": "b",
            "updated_at": "2026-01-02T00:00:00+00:00",
        },
    ]
    inserted = await upsert_raw(
        db_session,
        raw_table="rfis_raw",
        items=items,
        account_id=procore_connector_account,
    )
    assert inserted == 2

    result = await db_session.execute(
        text(
            "SELECT source_id, payload->>'subject' AS subj "
            "FROM connector_procore.rfis_raw "
            "WHERE account_id = :acct ORDER BY source_id"
        ),
        {"acct": procore_connector_account},
    )
    rows = result.mappings().all()
    assert [(r["source_id"], r["subj"]) for r in rows] == [("101", "a"), ("102", "b")]


@pytest.mark.asyncio
async def test_upsert_raw_dedups_on_unchanged_checksum(
    db_session, procore_connector_account
):
    items = [
        {
            "id": "101",
            "project_source_id": "42",
            "subject": "a",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    await upsert_raw(
        db_session,
        raw_table="rfis_raw",
        items=items,
        account_id=procore_connector_account,
    )
    inserted = await upsert_raw(
        db_session,
        raw_table="rfis_raw",
        items=items,
        account_id=procore_connector_account,
    )
    assert inserted == 1


@pytest.mark.asyncio
async def test_upsert_raw_updates_payload_on_content_change(
    db_session, procore_connector_account
):
    await upsert_raw(
        db_session,
        raw_table="rfis_raw",
        items=[
            {
                "id": "101",
                "project_source_id": "42",
                "subject": "a",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
        account_id=procore_connector_account,
    )
    await upsert_raw(
        db_session,
        raw_table="rfis_raw",
        items=[
            {
                "id": "101",
                "project_source_id": "42",
                "subject": "b-NEW",
                "updated_at": "2026-01-05T00:00:00+00:00",
            }
        ],
        account_id=procore_connector_account,
    )
    result = await db_session.execute(
        text(
            "SELECT payload->>'subject' AS subj "
            "FROM connector_procore.rfis_raw "
            "WHERE source_id = '101' AND account_id = :acct"
        ),
        {"acct": procore_connector_account},
    )
    assert result.scalar_one() == "b-NEW"


@pytest.mark.asyncio
async def test_upsert_raw_rejects_unknown_table(db_session, procore_connector_account):
    with pytest.raises(ValueError, match="ALLOWED_TABLES"):
        await upsert_raw(
            db_session,
            raw_table="malicious_table",
            items=[{"id": "1"}],
            account_id=procore_connector_account,
        )


@pytest.mark.asyncio
async def test_upsert_raw_empty_items_is_noop(db_session, procore_connector_account):
    inserted = await upsert_raw(
        db_session,
        raw_table="rfis_raw",
        items=[],
        account_id=procore_connector_account,
    )
    assert inserted == 0

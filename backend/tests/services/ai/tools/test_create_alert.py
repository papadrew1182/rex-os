"""create_alert — INSERT rex.notifications. Auto-pass always.
Compensator deletes the row by id."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_alert import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_user():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Alert', 'Recipient', $2, 'internal')",
            person_id, f"alert-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"ca-{user_id}@t.invalid",
        )
        yield {"user_id": user_id, "person_id": person_id}
    finally:
        await conn.execute(
            "DELETE FROM rex.notifications WHERE user_account_id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_auto_pass(seeded_user):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_user["user_id"])
        br = await SPEC.classify({
            "user_account_id": str(seeded_user["user_id"]),
            "domain": "schedule",
            "notification_type": "schedule_drift",
            "severity": "warning",
            "title": "Drift detected",
        }, ctx)
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_notification(seeded_user):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_user["user_id"],
            args={
                "user_account_id": str(seeded_user["user_id"]),
                "domain": "field_ops",
                "notification_type": "daily_log_missing",
                "severity": "warning",
                "title": "Bishop Modern — no daily log today",
                "body": "The daily log has not been submitted for today.",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT severity, title, domain FROM rex.notifications WHERE id = $1::uuid",
            UUID(result.result_payload["notification_id"]),
        )
        assert row["severity"] == "warning"
        assert row["domain"] == "field_ops"
        assert row["title"] == "Bishop Modern — no daily log today"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_compensator_deletes_the_notification(seeded_user):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_user["user_id"],
            args={
                "user_account_id": str(seeded_user["user_id"]),
                "domain": "system",
                "notification_type": "test",
                "severity": "info",
                "title": "Temp",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        nid = UUID(result.result_payload["notification_id"])
        assert SPEC.compensator is not None
        await SPEC.compensator(
            result.result_payload,
            ActionContext(conn=conn, user_account_id=seeded_user["user_id"],
                          args={}, action_id=uuid4(),
                          original_result=result.result_payload),
        )
        row = await conn.fetchrow(
            "SELECT id FROM rex.notifications WHERE id = $1::uuid", nid,
        )
        assert row is None
    finally:
        await conn.close()

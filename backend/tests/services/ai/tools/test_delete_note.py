"""delete_note — DELETE rex.notes after full-row snapshot.
Compensator re-INSERTs from the snapshot."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.delete_note import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_note():
    require_live_db()
    conn = await connect_raw()
    note_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'DN', 'Seeder', $2, 'internal')",
            person_id, f"dn-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"dn-{user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.notes (id, user_account_id, content) "
            "VALUES ($1::uuid, $2::uuid, 'To be deleted')",
            note_id, user_id,
        )
        yield {"note_id": note_id, "user_id": user_id, "person_id": person_id}
    finally:
        await conn.execute("DELETE FROM rex.notes WHERE user_account_id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_auto_pass(seeded_note):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_note["user_id"])
        br = await SPEC.classify({"note_id": str(seeded_note["note_id"])}, ctx)
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_deletes_and_captures_snapshot(seeded_note):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_note["user_id"],
            args={"note_id": str(seeded_note["note_id"])},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        gone = await conn.fetchrow(
            "SELECT id FROM rex.notes WHERE id = $1::uuid",
            seeded_note["note_id"],
        )
        assert gone is None
        assert result.result_payload["snapshot"]["content"] == "To be deleted"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_compensator_reinserts_from_snapshot(seeded_note):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_note["user_id"],
            args={"note_id": str(seeded_note["note_id"])},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert SPEC.compensator is not None
        await SPEC.compensator(
            result.result_payload,
            ActionContext(conn=conn, user_account_id=seeded_note["user_id"],
                          args={}, action_id=uuid4(),
                          original_result=result.result_payload),
        )
        back = await conn.fetchrow(
            "SELECT content FROM rex.notes WHERE id = $1::uuid",
            seeded_note["note_id"],
        )
        assert back is not None
        assert back["content"] == "To be deleted"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_raises_on_missing_note():
    require_live_db()
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=uuid4(),
            args={"note_id": str(uuid4())}, action_id=uuid4(),
        )
        with pytest.raises(ValueError, match="note .* not found"):
            await SPEC.handler(ctx)
    finally:
        await conn.close()

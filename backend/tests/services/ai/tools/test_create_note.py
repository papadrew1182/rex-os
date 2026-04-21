"""create_note — auto-pass; persists to rex.notes."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_note import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_user_project():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    proj_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Note', 'Taker', $2, 'internal')",
            person_id, f"note-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"note-{user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'N', 'active', $2)",
            proj_id, f"N-{str(proj_id)[:8]}",
        )
        yield {"user_id": user_id, "proj_id": proj_id, "person_id": person_id}
    finally:
        # CASCADE from projects cleans rex.notes automatically.
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_always_auto(seeded_user_project):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_user_project["user_id"])
        br = await SPEC.classify(
            {"content": "hello", "project_id": str(seeded_user_project["proj_id"])},
            ctx,
        )
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_note(seeded_user_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_user_project["user_id"],
            args={"content": "lunchtime note", "project_id": str(seeded_user_project["proj_id"])},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert "note_id" in result.result_payload
        row = await conn.fetchrow(
            "SELECT content FROM rex.notes WHERE id = $1::uuid",
            UUID(result.result_payload["note_id"]),
        )
        assert row["content"] == "lunchtime note"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_accepts_no_project(seeded_user_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_user_project["user_id"],
            args={"content": "standalone note"},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT content, project_id FROM rex.notes WHERE id = $1::uuid",
            UUID(result.result_payload["note_id"]),
        )
        assert row["content"] == "standalone note"
        assert row["project_id"] is None
        # Cleanup
        await conn.execute(
            "DELETE FROM rex.notes WHERE id = $1::uuid",
            UUID(result.result_payload["note_id"]),
        )
    finally:
        await conn.close()


def test_spec_metadata():
    assert SPEC.slug == "create_note"
    assert SPEC.fires_external_effect is False

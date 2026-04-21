"""save_draft — INSERT rex.correspondence with type=email, status=draft.
Auto-pass always. Compensator deletes the row by id."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.save_draft import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_project():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()  # rex.user_accounts.person_id is NOT NULL
    proj_number = f"SD-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Save Draft Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Draft', 'Tester', $2, 'internal')",
            person_id, f"drafter-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"sd-{user_id}@t.invalid",
        )
        yield {"project_id": proj_id, "user_id": user_id, "person_id": person_id}
    finally:
        await conn.execute(
            "DELETE FROM rex.correspondence WHERE project_id = $1::uuid", proj_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_auto_pass(seeded_project):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_project["user_id"])
        br = await SPEC.classify({
            "project_id": str(seeded_project["project_id"]),
            "subject": "Test draft", "body": "Hello",
        }, ctx)
        assert br.audience == 'internal'
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_draft_row(seeded_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_project["user_id"],
            args={
                "project_id": str(seeded_project["project_id"]),
                "subject": "Duct conflict follow-up",
                "body": "Per our conversation...",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT correspondence_type, status, subject FROM rex.correspondence "
            "WHERE id = $1::uuid",
            UUID(result.result_payload["correspondence_id"]),
        )
        assert row["correspondence_type"] == "email"
        assert row["status"] == "draft"
        assert row["subject"] == "Duct conflict follow-up"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_compensator_deletes_the_draft(seeded_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_project["user_id"],
            args={
                "project_id": str(seeded_project["project_id"]),
                "subject": "Draft to undo", "body": "...",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        corr_id = UUID(result.result_payload["correspondence_id"])
        assert SPEC.compensator is not None
        await SPEC.compensator(
            result.result_payload,
            ActionContext(conn=conn, user_account_id=seeded_project["user_id"],
                          args={}, action_id=uuid4(),
                          original_result=result.result_payload),
        )
        row = await conn.fetchrow(
            "SELECT id FROM rex.correspondence WHERE id = $1::uuid", corr_id,
        )
        assert row is None
    finally:
        await conn.close()

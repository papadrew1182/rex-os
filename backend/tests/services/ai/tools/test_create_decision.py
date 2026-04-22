"""create_decision — INSERT rex.pending_decisions. Auto-pass internal;
compensator DELETEs by id."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_decision import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_project():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    proj_number = f"DEC-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Decision Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Dec', 'Raiser', $2, 'internal')",
            person_id, f"dec-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"dec-u-{user_id}@t.invalid",
        )
        yield {"project_id": proj_id, "user_id": user_id, "person_id": person_id}
    finally:
        await conn.execute("DELETE FROM rex.pending_decisions WHERE project_id = $1::uuid", proj_id)
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
            "title": "Detail A-501 vs A-502",
        }, ctx)
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_pending_decision(seeded_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_project["user_id"],
            args={
                "project_id": str(seeded_project["project_id"]),
                "title": "Detail A-501 vs A-502 at grid B/4",
                "description": "Structural team needs an answer before shop drawings.",
                "priority": "high",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT title, priority, status, raised_by FROM rex.pending_decisions "
            "WHERE id = $1::uuid",
            UUID(result.result_payload["decision_id"]),
        )
        assert row["title"] == "Detail A-501 vs A-502 at grid B/4"
        assert row["priority"] == "high"
        assert row["status"] == "open"
        # raised_by should be the seeded person (looked up from user_account_id)
        assert row["raised_by"] == seeded_project["person_id"]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_compensator_deletes_the_decision(seeded_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_project["user_id"],
            args={
                "project_id": str(seeded_project["project_id"]),
                "title": "Ephemeral decision to undo",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        decision_id = UUID(result.result_payload["decision_id"])
        assert SPEC.compensator is not None
        await SPEC.compensator(
            result.result_payload,
            ActionContext(conn=conn, user_account_id=seeded_project["user_id"],
                          args={}, action_id=uuid4(),
                          original_result=result.result_payload),
        )
        row = await conn.fetchrow(
            "SELECT id FROM rex.pending_decisions WHERE id = $1::uuid", decision_id,
        )
        assert row is None
    finally:
        await conn.close()

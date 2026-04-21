"""create_task tool — auto if internal/self; approval if external."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_task import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_people():
    require_live_db()
    conn = await connect_raw()
    internal_id = uuid4()
    external_id = uuid4()
    proj_id = uuid4()
    requester_user_id = uuid4()
    req_person_id = uuid4()
    # Keep project_number unique-per-test to avoid colliding with seeds.
    proj_number = f"CT-{uuid4().hex[:8]}"
    try:
        for pid, role, first in [
            (internal_id, 'internal', 'Alice'),
            (external_id, 'external', 'Bob'),
            (req_person_id, 'internal', 'Carol'),
        ]:
            await conn.execute(
                "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
                "VALUES ($1::uuid, $2, 'Test', $3, $4)",
                pid, first, f"{first.lower()}-{pid}@t.invalid", role,
            )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            requester_user_id, req_person_id, f"req-{requester_user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Task Test', 'active', $2)",
            proj_id, proj_number,
        )
        yield {
            "requester_user_id": requester_user_id,
            "internal_person_id": internal_id,
            "external_person_id": external_id,
            "project_id": proj_id,
            "req_person_id": req_person_id,
        }
    finally:
        await conn.execute("DELETE FROM rex.tasks WHERE project_id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", requester_user_id)
        await conn.execute(
            "DELETE FROM rex.people WHERE id IN ($1::uuid, $2::uuid, $3::uuid)",
            internal_id, external_id, req_person_id,
        )
        await conn.close()


@pytest.mark.asyncio
async def test_classify_internal_assignee_is_auto(seeded_people):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_people["requester_user_id"])
        br = await SPEC.classify(
            {
                "title": "Check the duct conflict",
                "assignee_person_id": str(seeded_people["internal_person_id"]),
                "project_id": str(seeded_people["project_id"]),
            },
            ctx,
        )
        assert br.audience == 'internal'
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_classify_external_assignee_requires_approval(seeded_people):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_people["requester_user_id"])
        br = await SPEC.classify(
            {
                "title": "Send files to GC",
                "assignee_person_id": str(seeded_people["external_person_id"]),
                "project_id": str(seeded_people["project_id"]),
            },
            ctx,
        )
        assert br.audience == 'external'
        assert br.requires_approval() is True
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_classify_self_assigned_is_auto(seeded_people):
    """No assignee_person_id means self-assigned -> internal."""
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_people["requester_user_id"])
        br = await SPEC.classify({"title": "My own task"}, ctx)
        assert br.audience == 'internal'
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_task(seeded_people):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_people["requester_user_id"],
            args={
                "title": "Walk the punch list",
                "assignee_person_id": str(seeded_people["internal_person_id"]),
                "project_id": str(seeded_people["project_id"]),
                "due_date": "2030-01-15",
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert "task_id" in result.result_payload
        row = await conn.fetchrow(
            "SELECT title, project_id FROM rex.tasks WHERE id = $1::uuid",
            UUID(result.result_payload["task_id"]),
        )
        assert row["title"] == "Walk the punch list"
    finally:
        await conn.close()


def test_spec_metadata():
    assert SPEC.slug == "create_task"
    assert SPEC.fires_external_effect is False
    assert "title" in SPEC.tool_schema["input_schema"]["properties"]
    assert "title" in SPEC.tool_schema["input_schema"]["required"]

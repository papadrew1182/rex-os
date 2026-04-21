"""update_task_status — auto-pass always (internal single-row mutation)."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest, pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.update_task_status import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_task():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    proj_id = uuid4()
    task_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Task', 'Updater', $2, 'internal')",
            person_id, f"task-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"task-{user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'UT Test', 'active', $2)",
            proj_id, f"UT-{str(proj_id)[:8]}",
        )
        await conn.execute(
            "INSERT INTO rex.tasks (id, project_id, task_number, title, status, due_date, created_at, updated_at) "
            "VALUES ($1::uuid, $2::uuid, 1, 'Test task', 'open', $3::date, now(), now())",
            task_id, proj_id, date.today() + timedelta(days=7),
        )
        yield {"task_id": task_id, "user_id": user_id, "proj_id": proj_id, "person_id": person_id}
    finally:
        await conn.execute("DELETE FROM rex.tasks WHERE id = $1::uuid", task_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_always_auto(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_task["user_id"])
        br = await SPEC.classify(
            {"task_id": str(seeded_task["task_id"]), "status": "in_progress"},
            ctx,
        )
        assert br.audience == 'internal'
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_updates_status(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_task["user_id"],
            args={"task_id": str(seeded_task["task_id"]), "status": "in_progress"},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert result.result_payload["previous_status"] == "open"
        assert result.result_payload["new_status"] == "in_progress"
        new = await conn.fetchval(
            "SELECT status FROM rex.tasks WHERE id = $1::uuid",
            seeded_task["task_id"],
        )
        assert new == "in_progress"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_raises_on_unknown_task(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_task["user_id"],
            args={"task_id": str(uuid4()), "status": "in_progress"},
            action_id=uuid4(),
        )
        with pytest.raises(ValueError, match="not found"):
            await SPEC.handler(ctx)
    finally:
        await conn.close()


def test_spec_metadata():
    assert SPEC.slug == "update_task_status"
    assert SPEC.fires_external_effect is False


@pytest.mark.asyncio
async def test_update_task_status_compensator_restores_previous_status(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_task["user_id"],
            args={"task_id": str(seeded_task["task_id"]), "status": "in_progress"},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert result.result_payload["previous_status"] == "open"
        row = await conn.fetchrow(
            "SELECT status FROM rex.tasks WHERE id = $1::uuid", seeded_task["task_id"],
        )
        assert row["status"] == "in_progress"

        assert SPEC.compensator is not None
        await SPEC.compensator(
            result.result_payload,
            ActionContext(conn=conn, user_account_id=seeded_task["user_id"],
                          args={}, action_id=uuid4(),
                          original_result=result.result_payload),
        )
        row = await conn.fetchrow(
            "SELECT status FROM rex.tasks WHERE id = $1::uuid", seeded_task["task_id"],
        )
        assert row["status"] == "open"
    finally:
        await conn.close()

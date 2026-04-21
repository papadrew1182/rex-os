"""delete_task — DELETE rex.tasks by id after full-row snapshot.
Compensator re-INSERTs from the snapshot."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.delete_task import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_task():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    task_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    proj_number = f"DT-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Delete Task Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'DT', 'Seeder', $2, 'internal')",
            person_id, f"dt-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"dt-{user_id}@t.invalid",
        )
        await conn.execute(
            """
            INSERT INTO rex.tasks (id, project_id, task_number, title, status,
                                    priority, due_date)
            VALUES ($1::uuid, $2::uuid, 1, 'To be deleted', 'open', 'medium',
                    $3::date)
            """,
            task_id, proj_id, date(2026, 5, 1),
        )
        yield {"task_id": task_id, "project_id": proj_id, "user_id": user_id, "person_id": person_id}
    finally:
        await conn.execute("DELETE FROM rex.tasks WHERE project_id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_auto_pass(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_task["user_id"])
        br = await SPEC.classify({"task_id": str(seeded_task["task_id"])}, ctx)
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_deletes_and_captures_snapshot(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_task["user_id"],
            args={"task_id": str(seeded_task["task_id"])},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        gone = await conn.fetchrow(
            "SELECT id FROM rex.tasks WHERE id = $1::uuid",
            seeded_task["task_id"],
        )
        assert gone is None
        snap = result.result_payload["snapshot"]
        assert snap["title"] == "To be deleted"
        assert snap["status"] == "open"
        assert "task_number" in snap
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_compensator_reinserts_from_snapshot(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_task["user_id"],
            args={"task_id": str(seeded_task["task_id"])},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert SPEC.compensator is not None
        await SPEC.compensator(
            result.result_payload,
            ActionContext(conn=conn, user_account_id=seeded_task["user_id"],
                          args={}, action_id=uuid4(),
                          original_result=result.result_payload),
        )
        back = await conn.fetchrow(
            "SELECT title, status FROM rex.tasks WHERE id = $1::uuid",
            seeded_task["task_id"],
        )
        assert back is not None
        assert back["title"] == "To be deleted"
        assert back["status"] == "open"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_raises_on_missing_task():
    require_live_db()
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=uuid4(),
            args={"task_id": str(uuid4())}, action_id=uuid4(),
        )
        with pytest.raises(ValueError, match="task .* not found"):
            await SPEC.handler(ctx)
    finally:
        await conn.close()

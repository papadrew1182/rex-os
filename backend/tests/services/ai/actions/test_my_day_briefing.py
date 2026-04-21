"""my_day_briefing — pulls rex.v_myday for the requesting user."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.my_day_briefing import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_myday():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'My', 'Day', $2, 'internal')",
            person_id, f"md-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"md-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'My Day', 'active', 'MD-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        today = date.today()
        # 1 RFI ball-in-court, due today.
        await conn.execute(
            "INSERT INTO rex.rfis "
            "(id, project_id, rfi_number, subject, question, status, ball_in_court, due_date, created_at, updated_at) "
            "VALUES (gen_random_uuid(), $1::uuid, 'R-1', 'Due today', 'q', 'open', $2::uuid, $3::date, now(), now())",
            project_id, person_id, today,
        )
        # 1 RFI assigned, overdue (2 days).
        await conn.execute(
            "INSERT INTO rex.rfis "
            "(id, project_id, rfi_number, subject, question, status, assigned_to, due_date, created_at, updated_at) "
            "VALUES (gen_random_uuid(), $1::uuid, 'R-2', 'Overdue', 'q', 'open', $2::uuid, $3::date, now(), now())",
            project_id, person_id, today - timedelta(days=2),
        )
        # 1 Task assigned to user.
        await conn.execute(
            "INSERT INTO rex.tasks "
            "(id, project_id, task_number, title, status, assigned_to, due_date, created_at, updated_at) "
            "VALUES (gen_random_uuid(), $1::uuid, 1, 'Task for me', 'in_progress', $2::uuid, $3::date, now(), now())",
            project_id, person_id, today + timedelta(days=3),
        )
        yield user_id, project_id, person_id
    finally:
        await conn.execute("DELETE FROM rex.rfis WHERE project_id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.tasks WHERE project_id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_my_day_briefing(seeded_myday):
    user_id, _, _ = seeded_myday
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["total_items"] == 3
        assert r.stats["overdue"] == 1
        assert r.stats["due_today"] == 1
        assert len(r.sample_rows) == 3
    finally:
        await conn.close()

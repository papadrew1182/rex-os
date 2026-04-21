"""two_week_lookahead — tasks starting in [today, today+14d]."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.two_week_lookahead import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_lookahead():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    schedule_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'LA', 'Tester', $2, 'internal')",
            person_id, f"la-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"la-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'LA Test', 'active', 'LA-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.schedules "
            "(id, project_id, name, schedule_type, status, start_date) "
            "VALUES ($1::uuid, $2::uuid, 'Master', 'master', 'active', CURRENT_DATE)",
            schedule_id, project_id,
        )
        today = date.today()
        # In-range: day 1, day 7, day 14. Out-of-range: day -1, day 20.
        for name, start_offset in [
            ("In-range A (tomorrow)", 1),
            ("In-range B (day 7)",    7),
            ("In-range C (day 14)",   14),
            ("Past (yesterday)",      -1),
            ("Future (day 20)",       20),
        ]:
            await conn.execute(
                "INSERT INTO rex.schedule_activities "
                "(id, schedule_id, name, activity_type, start_date, end_date, "
                "percent_complete, is_critical) "
                "VALUES (gen_random_uuid(), $1::uuid, $2, 'task', "
                "$3::date, $3::date + INTERVAL '3 days', 0, false)",
                schedule_id, name, today + timedelta(days=start_offset),
            )
        yield user_id, project_id
    finally:
        await conn.execute("DELETE FROM rex.schedule_activities WHERE schedule_id = $1::uuid", schedule_id)
        await conn.execute("DELETE FROM rex.schedules WHERE id = $1::uuid", schedule_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_two_week_lookahead(seeded_lookahead):
    user_id, _ = seeded_lookahead
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["tasks_starting_next_14d"] == 3
        assert r.stats["projects_with_starts"] == 1
        # Earliest first
        assert r.sample_rows[0]["task_name"].startswith("In-range A")
    finally:
        await conn.close()

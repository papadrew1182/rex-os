"""critical_path_delays — critical activities with variance_days > 2."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.critical_path_delays import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_schedule():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    schedule_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Sch', 'Tester', $2, 'internal')",
            person_id, f"sch-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"sch-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Schedule Test', 'active', 'SCH-1')",
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
        # 5 activities: 2 critical + delayed (var=5, var=10), 1 critical on-time (var=0),
        # 1 non-critical + delayed (var=8), 1 critical + var=2 (NOT delayed — threshold is > 2).
        rows = [
            ("Framing",    True,  5),
            ("Roofing",    True,  10),
            ("Paint",      True,  0),
            ("Landscape",  False, 8),
            ("Walls",      True,  2),
        ]
        for name, crit, var in rows:
            await conn.execute(
                "INSERT INTO rex.schedule_activities "
                "(id, schedule_id, name, activity_type, start_date, end_date, "
                "percent_complete, is_critical, variance_days) "
                "VALUES (gen_random_uuid(), $1::uuid, $2, 'task', "
                "CURRENT_DATE, CURRENT_DATE + INTERVAL '5 days', 50, $3, $4)",
                schedule_id, name, crit, var,
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
async def test_critical_path_delays(seeded_schedule):
    user_id, _ = seeded_schedule
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        # Framing (5) and Roofing (10) — critical + variance > 2.
        assert r.stats["critical_tasks_delayed"] == 2
        assert r.stats["worst_delay_days"] == 10
        assert r.sample_rows[0]["variance_days"] == 10
        assert r.sample_rows[1]["variance_days"] == 5
    finally:
        await conn.close()

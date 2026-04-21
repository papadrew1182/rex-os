"""daily_log_summary — 7-day log counts + today's manpower."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.daily_log_summary import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_logs():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    company_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Log', 'Tester', $2, 'internal')",
            person_id, f"log-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"log-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Log Test', 'active', 'LOG-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        # companies: name NOT NULL, company_type NOT NULL CHECK IN (...).
        await conn.execute(
            "INSERT INTO rex.companies (id, name, company_type) "
            "VALUES ($1::uuid, 'ACME Trades', 'subcontractor')",
            company_id,
        )
        today = date.today()
        # 4 daily logs: today, yesterday, 3d ago, 10d ago
        # (only first 3 count in the 7-day window).
        logs = [
            (today, True),
            (today - timedelta(days=1), False),
            (today - timedelta(days=3), False),
            (today - timedelta(days=10), False),
        ]
        log_ids = []
        for log_date, is_today in logs:
            lid = uuid4()
            log_ids.append((lid, is_today))
            await conn.execute(
                "INSERT INTO rex.daily_logs "
                "(id, project_id, log_date, status, weather_summary, work_summary) "
                "VALUES ($1::uuid, $2::uuid, $3::date, 'submitted', 'clear', 'work')",
                lid, project_id, log_date,
            )
        # Manpower entry ONLY for today's log.
        for lid, is_today in log_ids:
            if is_today:
                await conn.execute(
                    "INSERT INTO rex.manpower_entries "
                    "(id, daily_log_id, company_id, worker_count, hours) "
                    "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, 12, 96)",
                    lid, company_id,
                )
        yield user_id, project_id
    finally:
        await conn.execute(
            "DELETE FROM rex.manpower_entries WHERE daily_log_id IN "
            "(SELECT id FROM rex.daily_logs WHERE project_id = $1::uuid)",
            project_id,
        )
        await conn.execute("DELETE FROM rex.daily_logs WHERE project_id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.companies WHERE id = $1::uuid", company_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_daily_log_summary(seeded_logs):
    user_id, _ = seeded_logs
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["logs_last_7_days"] == 3
        assert r.stats["today_total_manpower"] == 12
        assert r.stats["projects_without_today_log"] == 0
        assert "Quick action data: daily_log_summary" in r.prompt_fragment
    finally:
        await conn.close()

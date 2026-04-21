"""documentation_compliance — closeout checklist items overdue or near-due."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.documentation_compliance import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_closeout():
    """Seed 1 user/person/project/checklist + 5 closeout checklist items:
    2 overdue (not complete, due in the past), 1 near-due (within 30 days),
    1 far-future (60 days out), 1 complete (should be excluded from all
    non-complete buckets). Yields (user_account_id, project_id).

    Note: rex.closeout_checklists has no `name`/`status` columns; the
    canonical DDL defines only project/template/substantial_completion_date/
    counters. Items' status CHECK is ('not_started','in_progress','complete',
    'n_a') — so we use 'not_started' / 'in_progress' / 'complete' (NOT
    'open' / 'completed').
    """
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    checklist_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'DC', 'Tester', $2, 'internal')",
            person_id, f"dc-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"dc-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'DC Test', 'active', 'DC-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.closeout_checklists "
            "(id, project_id, substantial_completion_date) "
            "VALUES ($1::uuid, $2::uuid, $3::date)",
            checklist_id, project_id, date.today() + timedelta(days=60),
        )
        today = date.today()
        items = [
            # (name, status, due_date)
            ("Overdue-1",   "not_started", today - timedelta(days=5)),
            ("Overdue-2",   "in_progress", today - timedelta(days=12)),
            ("Near-due",    "not_started", today + timedelta(days=15)),
            ("Far-future",  "not_started", today + timedelta(days=60)),
            ("Completed",   "complete",    today - timedelta(days=20)),
        ]
        for idx, (name, status, due) in enumerate(items, start=1):
            await conn.execute(
                "INSERT INTO rex.closeout_checklist_items "
                "(id, checklist_id, category, item_number, name, status, due_date) "
                "VALUES (gen_random_uuid(), $1::uuid, 'general', $2, $3, $4, $5::date)",
                checklist_id, idx, name, status, due,
            )
        yield user_id, project_id
    finally:
        await conn.execute(
            "DELETE FROM rex.closeout_checklist_items WHERE checklist_id = $1::uuid",
            checklist_id,
        )
        await conn.execute(
            "DELETE FROM rex.closeout_checklists WHERE id = $1::uuid", checklist_id,
        )
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_documentation_compliance(seeded_closeout):
    user_id, _ = seeded_closeout
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        # Overdue = 2, near-due (within 30d and not complete) = 1.
        assert r.stats["overdue_items"] == 2
        assert r.stats["due_within_30_days"] == 1
        assert all(row["status"] != "complete" for row in r.sample_rows)
    finally:
        await conn.close()

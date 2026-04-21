"""submittal_sla handler — open submittals with SLA-aging buckets.

rex.v_project_mgmt has days_open=NULL for submittals; the handler
derives days_since_created from v_project_mgmt.created_at.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.submittal_sla import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_submittals():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Sub', 'Tester', $2, 'internal')",
            person_id, f"sub-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"sub-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Submittal Test', 'active', 'SUB-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        now = datetime.now(timezone.utc)
        # 4 open submittals at varying ages (2d, 12d, 25d, 40d) + 1 closed.
        # rex.submittals.status is constrained; "open" is the semantic bucket
        # {draft, pending, submitted}. "closed" matches the literal 'closed' status.
        for days_ago, num, status in [
            (2,  "S-1", "submitted"),
            (12, "S-2", "submitted"),
            (25, "S-3", "pending"),
            (40, "S-4", "draft"),
            (5,  "S-5", "closed"),  # ignored
        ]:
            await conn.execute(
                "INSERT INTO rex.submittals "
                "(id, project_id, submittal_number, title, status, submittal_type, "
                " created_at, updated_at) "
                "VALUES (gen_random_uuid(), $1::uuid, $2, 'Title', $3, 'shop_drawing', "
                " $4, $4)",
                project_id, num, status, now - timedelta(days=days_ago),
            )
        yield user_id, project_id
    finally:
        await conn.execute("DELETE FROM rex.submittals WHERE project_id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_submittal_sla_portfolio_mode(seeded_submittals):
    user_id, _ = seeded_submittals
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["total_open"] == 4
        buckets = r.stats["buckets"]
        assert buckets["0_to_5"]   == 1   # 2d
        assert buckets["6_to_10"]  == 0
        assert buckets["11_to_20"] == 1   # 12d
        assert buckets["21_plus"]  == 2   # 25d + 40d
        assert r.stats["oldest_days"] == 40
        assert len(r.sample_rows) == 4
        # Oldest first
        assert r.sample_rows[0]["days_since_created"] == 40
        assert "Quick action data: submittal_sla" in r.prompt_fragment
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_submittal_sla_empty(seeded_submittals):
    user_id, project_id = seeded_submittals
    conn = await connect_raw()
    try:
        await conn.execute(
            "UPDATE rex.submittals SET status = 'closed' WHERE project_id = $1::uuid",
            project_id,
        )
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["total_open"] == 0
        assert "no open submittals" in r.prompt_fragment.lower()
    finally:
        await conn.close()

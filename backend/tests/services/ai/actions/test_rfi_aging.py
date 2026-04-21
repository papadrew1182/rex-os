"""rfi_aging handler — reads from rex.v_project_mgmt where entity_type='rfi'."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.rfi_aging import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_rfis():
    """Seed 1 user, 1 person, 1 project, 4 open RFIs with varying days_open
    (3/10/20/40), plus 1 closed RFI (should be ignored).
    Yields (user_account_id, project_id, rfi_ids)."""
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    rfi_ids: list[UUID] = []
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Aging', 'Tester', $2, 'internal')",
            person_id, f"aging-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"aging-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Aging Test', 'active', 'AGE-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        now = datetime.now(timezone.utc)
        for days_open, subject in [
            (3,  "Fresh"),
            (10, "Ten-day"),
            (20, "Twenty-day"),
            (40, "Forty-day"),
        ]:
            rid = uuid4()
            rfi_ids.append(rid)
            await conn.execute(
                "INSERT INTO rex.rfis "
                "(id, project_id, rfi_number, subject, question, status, days_open, created_at, updated_at) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, 'q', 'open', $5, $6, $6)",
                rid, project_id, f"RFI-{days_open}", subject, days_open,
                now - timedelta(days=days_open),
            )
        # Closed RFI — should NOT be counted.
        cid = uuid4()
        await conn.execute(
            "INSERT INTO rex.rfis "
            "(id, project_id, rfi_number, subject, question, status, days_open, created_at, updated_at) "
            "VALUES ($1::uuid, $2::uuid, 'RFI-CLOSED', 'Closed one', 'q', 'closed', 99, $3, $3)",
            cid, project_id, now,
        )
        rfi_ids.append(cid)
        yield user_id, project_id, rfi_ids
    finally:
        await conn.execute("DELETE FROM rex.rfis WHERE project_id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_portfolio_mode(seeded_rfis):
    user_id, _, _ = seeded_rfis
    conn = await connect_raw()
    try:
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert result.stats["total_open"] == 4
        buckets = result.stats["buckets"]
        assert buckets["0_to_7"] == 1
        assert buckets["8_to_14"] == 1
        assert buckets["15_to_30"] == 1
        assert buckets["30_plus"] == 1
        assert result.stats["oldest_days"] == 40
        assert len(result.sample_rows) == 4
        assert result.sample_rows[0]["days_open"] == 40
        assert "Quick action data: rfi_aging" in result.prompt_fragment
        assert "Total open RFIs: 4" in result.prompt_fragment
        assert "verbatim" in result.prompt_fragment.lower()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_project_mode_restricts_to_project(seeded_rfis):
    user_id, project_id, _ = seeded_rfis
    conn = await connect_raw()
    try:
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=project_id,
        ))
        assert result.stats["total_open"] == 4
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_empty_result(seeded_rfis):
    user_id, project_id, _ = seeded_rfis
    conn = await connect_raw()
    try:
        await conn.execute(
            "UPDATE rex.rfis SET status = 'closed' WHERE project_id = $1::uuid",
            project_id,
        )
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert result.stats["total_open"] == 0
        assert result.sample_rows == []
        assert "no open rfis" in result.prompt_fragment.lower()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_user_without_assignments_returns_empty(seeded_rfis):
    _, _, _ = seeded_rfis
    lonely_user = uuid4()
    conn = await connect_raw()
    try:
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=lonely_user, project_id=None,
        ))
        assert result.stats["total_open"] == 0
        assert "no open rfis" in result.prompt_fragment.lower()
    finally:
        await conn.close()

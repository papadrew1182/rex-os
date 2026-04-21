"""budget_variance handler — reads rex.v_financials, flags |delta|>5%.

rex.v_financials derives revised_budget and budget_over_under from
rex.v_budgets, which rolls up rex.budget_line_items per project. So we
seed one budget_line_item per project with the values we want to
surface (original_budget, revised_budget, over_under). The test spec in
the plan referenced rex.budget_snapshots, but the real bridge view
reads budget_line_items (per migration 022 + rex2_canonical_ddl line
530).
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.budget_variance import Handler
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_budgets():
    """Seed 3 projects with varying budget_over_under deltas:
       A: +3%  (NOT flagged)
       B: +10% (flagged)
       C: -20% (flagged, abs value)
    Yields (user_account_id, project_a, project_b, project_c)."""
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    project_a = uuid4()
    project_b = uuid4()
    project_c = uuid4()
    cost_code_ids: list[UUID] = []
    line_item_ids: list[UUID] = []
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Bud', 'Tester', $2, 'internal')",
            person_id, f"bud-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"bud-{person_id}@test.invalid",
        )
        for pid, num, orig, rev, over in [
            (project_a, "BUD-A", 100000, 100000, 3000),    # +3%
            (project_b, "BUD-B", 500000, 500000, 50000),   # +10%
            (project_c, "BUD-C", 200000, 200000, -40000),  # -20%
        ]:
            await conn.execute(
                "INSERT INTO rex.projects (id, name, status, project_number) "
                "VALUES ($1::uuid, $2, 'active', $3)",
                pid, f"Budget {num}", num,
            )
            await conn.execute(
                "INSERT INTO rex.project_members "
                "(id, project_id, person_id, is_active, is_primary) "
                "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
                pid, person_id,
            )
            # v_budgets aggregates rex.budget_line_items per project, and
            # budget_line_items requires a cost_code. One cost_code + one
            # line item per project is enough to surface the row through
            # rex.v_financials.
            cc_id = uuid4()
            cost_code_ids.append(cc_id)
            await conn.execute(
                "INSERT INTO rex.cost_codes "
                "(id, project_id, code, name, cost_type, is_active) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, 'other', true)",
                cc_id, pid, f"CC-{num}", f"Cost Code {num}",
            )
            li_id = uuid4()
            line_item_ids.append(li_id)
            await conn.execute(
                """
                INSERT INTO rex.budget_line_items
                    (id, project_id, cost_code_id,
                     original_budget, approved_changes, revised_budget,
                     committed_costs, direct_costs, pending_changes,
                     projected_cost, over_under)
                VALUES ($1::uuid, $2::uuid, $3::uuid,
                        $4::numeric, 0, $5::numeric, 0, 0, 0,
                        $5::numeric + $6::numeric, $6::numeric)
                """,
                li_id, pid, cc_id, orig, rev, over,
            )
        yield user_id, project_a, project_b, project_c
    finally:
        for pid in (project_a, project_b, project_c):
            await conn.execute(
                "DELETE FROM rex.budget_line_items WHERE project_id = $1::uuid", pid,
            )
            await conn.execute(
                "DELETE FROM rex.cost_codes WHERE project_id = $1::uuid", pid,
            )
            await conn.execute(
                "DELETE FROM rex.project_members WHERE project_id = $1::uuid", pid,
            )
            await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", pid)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_budget_variance_flags_over_5pct(seeded_budgets):
    user_id, _a, _b, _c = seeded_budgets
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["projects_over_5pct"] == 2
        assert r.stats["total_projects"] == 3
        # Ordered by abs(delta_pct) DESC: C (20%), B (10%), A (3%)
        assert len(r.sample_rows) == 3
        assert abs(r.sample_rows[0]["delta_pct"]) >= abs(r.sample_rows[1]["delta_pct"])
        assert "Quick action data: budget_variance" in r.prompt_fragment
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_budget_variance_project_mode_restricts_to_project(seeded_budgets):
    user_id, _a, project_b, _c = seeded_budgets
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=project_b,
        ))
        assert r.stats["total_projects"] == 1
        assert r.stats["projects_over_5pct"] == 1
        assert len(r.sample_rows) == 1
        # Project B is +10% → flagged.
        assert abs(r.sample_rows[0]["delta_pct"] - 0.10) < 1e-6
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_budget_variance_user_without_assignments_returns_empty():
    require_live_db()
    lonely_user = uuid4()
    conn = await connect_raw()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=lonely_user, project_id=None,
        ))
        assert r.stats["total_projects"] == 0
        assert r.stats["projects_over_5pct"] == 0
        assert r.sample_rows == []
        assert "no budget data" in r.prompt_fragment.lower()
    finally:
        await conn.close()

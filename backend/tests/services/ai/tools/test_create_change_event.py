"""create_change_event — INSERT rex.change_events. Approval-required
(financial instrument); no compensator."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_change_event import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_project():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    proj_number = f"CE-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Change Event Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'CE', 'Seeder', $2, 'internal')",
            person_id, f"ce-p-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"ce-{user_id}@t.invalid",
        )
        yield {"project_id": proj_id, "user_id": user_id, "person_id": person_id}
    finally:
        await conn.execute("DELETE FROM rex.change_events WHERE project_id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_approval_required(seeded_project):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_project["user_id"])
        br = await SPEC.classify({
            "project_id": str(seeded_project["project_id"]),
            "event_number": "CE-1",
            "title": "Owner change",
            "change_reason": "owner_change",
            "event_type": "owner_change",
            "estimated_amount": 5000,
        }, ctx)
        assert br.fires_external_effect is True
        assert br.requires_approval() is True
        assert br.financial_dollar_amount == 5000.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_classify_zero_amount_still_requires_approval(seeded_project):
    """financial_dollar_amount=0 but fires_external_effect=True still forces approval."""
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_project["user_id"])
        br = await SPEC.classify({
            "project_id": str(seeded_project["project_id"]),
            "event_number": "CE-2",
            "title": "No-impact change",
            "change_reason": "unforeseen",
            "event_type": "tbd",
        }, ctx)
        assert br.requires_approval() is True
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_change_event(seeded_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_project["user_id"],
            args={
                "project_id": str(seeded_project["project_id"]),
                "event_number": "CE-42",
                "title": "Canopy revision",
                "description": "Per owner directive dated 4/15.",
                "change_reason": "owner_change",
                "event_type": "owner_change",
                "scope": "in_scope",
                "estimated_amount": 12500,
            },
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        row = await conn.fetchrow(
            "SELECT event_number, title, status, change_reason, event_type, scope, estimated_amount "
            "FROM rex.change_events WHERE id = $1::uuid",
            UUID(result.result_payload["change_event_id"]),
        )
        assert row["event_number"] == "CE-42"
        assert row["title"] == "Canopy revision"
        assert row["status"] == "open"
        assert row["change_reason"] == "owner_change"
        assert row["event_type"] == "owner_change"
        assert row["scope"] == "in_scope"
        assert float(row["estimated_amount"]) == 12500.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_spec_has_no_compensator():
    assert SPEC.compensator is None, "financial tools don't have compensators in Wave 2"

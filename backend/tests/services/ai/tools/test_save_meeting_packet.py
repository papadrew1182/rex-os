"""save_meeting_packet — UPDATEs rex.meetings.packet_url. Auto-pass always.
Compensator restores the prior packet_url."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.save_meeting_packet import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_meeting():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    meeting_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    proj_number = f"MP-{uuid4().hex[:8]}"
    try:
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Meeting Packet Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Meeting', 'Packeteer', $2, 'internal')",
            person_id, f"mp-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"mp-{user_id}@t.invalid",
        )
        await conn.execute(
            """
            INSERT INTO rex.meetings (id, project_id, meeting_type, title, meeting_date, packet_url)
            VALUES ($1::uuid, $2::uuid, 'owner_meeting', 'Weekly OAC',
                    $3::date, 'https://old.example.com/packet.pdf')
            """,
            meeting_id, proj_id, date(2026, 4, 22),
        )
        yield {"meeting_id": meeting_id, "project_id": proj_id, "user_id": user_id}
    finally:
        await conn.execute("DELETE FROM rex.meetings WHERE id = $1::uuid", meeting_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_is_auto_pass(seeded_meeting):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_meeting["user_id"])
        br = await SPEC.classify({"meeting_id": str(seeded_meeting["meeting_id"]),
                                   "packet_url": "https://new.example.com/packet.pdf"}, ctx)
        assert br.audience == 'internal'
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_updates_packet_url_and_captures_prior(seeded_meeting):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_meeting["user_id"],
            args={"meeting_id": str(seeded_meeting["meeting_id"]),
                   "packet_url": "https://new.example.com/packet.pdf"},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert result.result_payload["prior_packet_url"] == "https://old.example.com/packet.pdf"
        row = await conn.fetchrow(
            "SELECT packet_url FROM rex.meetings WHERE id = $1::uuid",
            seeded_meeting["meeting_id"],
        )
        assert row["packet_url"] == "https://new.example.com/packet.pdf"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_compensator_restores_prior_packet_url(seeded_meeting):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=seeded_meeting["user_id"],
            args={"meeting_id": str(seeded_meeting["meeting_id"]),
                   "packet_url": "https://new.example.com/packet.pdf"},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert SPEC.compensator is not None
        await SPEC.compensator(
            result.result_payload,
            ActionContext(conn=conn, user_account_id=seeded_meeting["user_id"],
                          args={}, action_id=uuid4(),
                          original_result=result.result_payload),
        )
        row = await conn.fetchrow(
            "SELECT packet_url FROM rex.meetings WHERE id = $1::uuid",
            seeded_meeting["meeting_id"],
        )
        assert row["packet_url"] == "https://old.example.com/packet.pdf"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_raises_on_missing_meeting():
    require_live_db()
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn, user_account_id=uuid4(),
            args={"meeting_id": str(uuid4()),
                   "packet_url": "https://example.com/packet.pdf"},
            action_id=uuid4(),
        )
        with pytest.raises(ValueError, match="meeting .* not found"):
            await SPEC.handler(ctx)
    finally:
        await conn.close()

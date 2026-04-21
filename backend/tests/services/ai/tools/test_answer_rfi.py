"""answer_rfi — approval-required; fires Procore API call."""
from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools import answer_rfi as answer_rfi_mod
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_rfi():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    proj_id = uuid4()
    rfi_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'RFI', 'Tester', $2, 'internal')",
            person_id, f"rfi-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"rfi-{user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'RFI Test', 'active', $2)",
            proj_id, f"RT-{str(proj_id)[:8]}",
        )
        await conn.execute(
            "INSERT INTO rex.rfis (id, project_id, rfi_number, subject, question, status, created_at, updated_at) "
            "VALUES ($1::uuid, $2::uuid, '42', 'Duct conflict', 'where?', 'open', now(), now())",
            rfi_id, proj_id,
        )
        await conn.execute(
            "INSERT INTO rex.connector_mappings "
            "(rex_table, rex_id, connector, external_id, source_table, synced_at) "
            "VALUES ('rex.rfis', $1::uuid, 'procore', '99123', 'procore.rfis', now())",
            rfi_id,
        )
        yield {"user_id": user_id, "rfi_id": rfi_id, "proj_id": proj_id, "person_id": person_id}
    finally:
        await conn.execute(
            "DELETE FROM rex.connector_mappings WHERE rex_id = $1::uuid",
            rfi_id,
        )
        await conn.execute("DELETE FROM rex.rfis WHERE id = $1::uuid", rfi_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_requires_approval(seeded_rfi):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_rfi["user_id"])
        br = await answer_rfi_mod.SPEC.classify(
            {"rfi_id": str(seeded_rfi["rfi_id"]), "answer_text": "Resolved."},
            ctx,
        )
        assert br.fires_external_effect is True
        assert br.requires_approval() is True
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_updates_rex_and_calls_procore(seeded_rfi, monkeypatch):
    monkeypatch.setenv("PROCORE_CLIENT_ID", "cid")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PROCORE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("PROCORE_COMPANY_ID", "42")

    def _transport(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        if request.url.path == "/rest/v1.0/rfis/99123":
            return httpx.Response(200, json={"id": 99123, "status": "closed"})
        return httpx.Response(404)

    # Patch ProcoreClient.from_env to inject the mock transport
    from app.services.ai.tools import procore_api as procore_mod
    original = procore_mod.ProcoreClient.from_env
    monkeypatch.setattr(
        procore_mod.ProcoreClient, "from_env",
        classmethod(lambda cls, transport=None: original.__func__(
            cls, transport=httpx.MockTransport(_transport),
        )),
    )

    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_rfi["user_id"],
            args={"rfi_id": str(seeded_rfi["rfi_id"]), "answer_text": "Duct resolved."},
            action_id=uuid4(),
        )
        result = await answer_rfi_mod.SPEC.handler(ctx)
        assert result.result_payload["rfi_id"] == str(seeded_rfi["rfi_id"])
        assert result.result_payload["procore_response"]["id"] == 99123
        row = await conn.fetchrow(
            "SELECT status, answer FROM rex.rfis WHERE id = $1::uuid",
            seeded_rfi["rfi_id"],
        )
        assert row["status"] in ("answered", "closed")
        assert row["answer"] == "Duct resolved."
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_raises_when_no_procore_mapping(seeded_rfi, monkeypatch):
    monkeypatch.setenv("PROCORE_CLIENT_ID", "cid")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PROCORE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("PROCORE_COMPANY_ID", "42")

    # Create a fresh RFI with NO Procore mapping
    conn = await connect_raw()
    try:
        orphan_rfi = uuid4()
        await conn.execute(
            "INSERT INTO rex.rfis (id, project_id, rfi_number, subject, question, status, created_at, updated_at) "
            "VALUES ($1::uuid, $2::uuid, '99', 'Orphan', 'q', 'open', now(), now())",
            orphan_rfi, seeded_rfi["proj_id"],
        )
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_rfi["user_id"],
            args={"rfi_id": str(orphan_rfi), "answer_text": "x"},
            action_id=uuid4(),
        )
        with pytest.raises(ValueError, match="no Procore source_link"):
            await answer_rfi_mod.SPEC.handler(ctx)
        await conn.execute("DELETE FROM rex.rfis WHERE id = $1::uuid", orphan_rfi)
    finally:
        await conn.close()


def test_spec_metadata():
    assert answer_rfi_mod.SPEC.slug == "answer_rfi"
    assert answer_rfi_mod.SPEC.fires_external_effect is True

"""Contract tests for the assistant router (Session 1, feat/ai-spine).

Replaces the lazily-built ``AssistantDispatcher`` on
``app.state.assistant_dispatcher`` with a ``FakeDispatcher`` that serves a
synthesized catalog from the Python source of truth. That isolates the
router tests from the ``rex.*`` tables so the suite can run green before
migrations 006/007/008 are applied to the dev DB.
"""

from __future__ import annotations

import json

import pytest

from main import app
from schemas.catalog import CatalogResponse
from services.ai.catalog_import import build_catalog_response_from_source
from tests._assistant_fakes import FakeDispatcher


# Serve the full 77-slug catalog from the source-of-truth Python module.
SEED_CATALOG: CatalogResponse = CatalogResponse.model_validate(
    build_catalog_response_from_source()
)


@pytest.fixture(autouse=True)
def _install_fake_dispatcher():
    saved = getattr(app.state, "assistant_dispatcher", None)
    app.state.assistant_dispatcher = FakeDispatcher.build(SEED_CATALOG)
    try:
        yield
    finally:
        if saved is None:
            if hasattr(app.state, "assistant_dispatcher"):
                delattr(app.state, "assistant_dispatcher")
        else:
            app.state.assistant_dispatcher = saved


# ── GET /api/assistant/catalog ────────────────────────────────────────────
async def test_catalog_returns_full_77_slug_catalog(client):
    resp = await client.get("/api/assistant/catalog")
    assert resp.status_code == 200
    body = resp.json()

    assert body["version"] == "v1"
    assert len(body["actions"]) == 77
    slugs = {a["slug"] for a in body["actions"]}
    # spot-check canonical slugs
    for expected in ("budget_variance", "submittal_sla", "monthly_owner_report",
                     "rfi_aging", "command_mode", "training_status"):
        assert expected in slugs


async def test_catalog_preserves_dedupe_aliases(client):
    resp = await client.get("/api/assistant/catalog")
    body = resp.json()
    by_slug = {a["slug"]: a for a in body["actions"]}

    assert set(by_slug["submittal_sla"]["legacy_aliases"]) == {"C-8", "C-28"}
    assert set(by_slug["monthly_owner_report"]["legacy_aliases"]) == {"C-15", "C-60"}
    assert set(by_slug["rfi_aging"]["legacy_aliases"]) == {"C-5", "C-29"}


async def test_catalog_has_no_C_star_primary_identities(client):
    resp = await client.get("/api/assistant/catalog")
    body = resp.json()
    for action in body["actions"]:
        assert not action["slug"].upper().startswith("C-"), action["slug"]


async def test_catalog_role_visibility_is_canonical_keys_only(client):
    resp = await client.get("/api/assistant/catalog")
    body = resp.json()
    canonical = {"VP", "PM", "GENERAL_SUPER", "LEAD_SUPER", "ASSISTANT_SUPER", "ACCOUNTANT"}
    for action in body["actions"]:
        for role in action["role_visibility"]:
            assert role in canonical, f"{action['slug']}: {role}"


# ── POST /api/assistant/chat (SSE) ────────────────────────────────────────
async def test_chat_sse_emits_full_event_vocabulary(client):
    resp = await client.post(
        "/api/assistant/chat",
        json={
            "message": "What's happening on Tower 3 today?",
            "active_action_slug": "budget_variance",
            "page_context": {"route": "/projects/tower-3", "surface": "assistant_sidebar"},
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(resp.text)
    types = [e["type"] for e in events]

    for expected in ("conversation.created", "message.started", "message.delta",
                     "followups.generated", "message.completed"):
        assert expected in types, f"missing {expected}"

    assert types.index("conversation.created") < types.index("message.started")
    assert types.index("message.delta") < types.index("message.completed")
    assert types.index("followups.generated") < types.index("message.completed")

    followups = next(e for e in events if e["type"] == "followups.generated")
    assert any("cost codes" in f.lower() or "variance" in f.lower() for f in followups["items"])


# ── GET /api/assistant/conversations round-trip ───────────────────────────
async def test_conversation_create_list_detail_roundtrip(client):
    post_resp = await client.post(
        "/api/assistant/chat",
        json={"message": "First conversation", "page_context": {}},
    )
    assert post_resp.status_code == 200
    events = _parse_sse_events(post_resp.text)
    created_event = next(e for e in events if e["type"] == "conversation.created")
    conv_id = created_event["conversation_id"]

    list_resp = await client.get("/api/assistant/conversations")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == conv_id

    detail_resp = await client.get(f"/api/assistant/conversations/{conv_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["conversation"]["id"] == conv_id
    assert len(detail["messages"]) == 2
    senders = [m["sender_type"] for m in detail["messages"]]
    assert senders == ["user", "assistant"]


async def test_conversation_detail_returns_404_for_unknown_id(client):
    import uuid
    bad_id = uuid.uuid4()
    resp = await client.get(f"/api/assistant/conversations/{bad_id}")
    assert resp.status_code == 404


async def test_archive_conversation_removes_from_list(client):
    create_resp = await client.post(
        "/api/assistant/chat",
        json={"message": "To be archived", "page_context": {}},
    )
    events = _parse_sse_events(create_resp.text)
    conv_id = next(e for e in events if e["type"] == "conversation.created")["conversation_id"]

    del_resp = await client.delete(f"/api/assistant/conversations/{conv_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get("/api/assistant/conversations")
    assert list_resp.json()["items"] == []

    del_again = await client.delete(f"/api/assistant/conversations/{conv_id}")
    assert del_again.status_code == 404


def _parse_sse_events(body: str) -> list[dict]:
    events: list[dict] = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if not frame.startswith("data:"):
            continue
        payload = frame[len("data:"):].strip()
        if not payload:
            continue
        events.append(json.loads(payload))
    return events

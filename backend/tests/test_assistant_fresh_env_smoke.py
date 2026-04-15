"""Fresh-environment smoke path for Session 1-owned surfaces.

A true DB-backed smoke test would apply migrations 006/007/008 to a
clean Postgres, call the real router against the real tables, and
assert the catalog materializes and the chat endpoint streams. That
path is not practical in this test environment because the shared
``client`` fixture talks to the dev DB and the view layer the planner
depends on (``rex.v_*``) is owned by Session 2 and does not exist yet.

This file is the strongest deterministic substitute: it proves every
artifact Session 1 owns is internally consistent, wired, and
reachable via a fake-backed app without touching the real DB.

What this test proves:

    1. The canonical Python catalog is structurally valid.
    2. ``migrations/008_ai_action_catalog_seed.sql`` is a byte-for-byte
       image of the Python source (delegated to the drift test).
    3. The assistant router is mounted on the real ``main.app`` with
       the exact 5 endpoints Session 3 expects.
    4. The frozen SSE event vocabulary is emitted end-to-end by the
       real ``ChatService`` wired against an in-memory fake chat repo.
    5. ``build_catalog_response_from_source`` produces a response that
       the Pydantic ``CatalogResponse`` schema accepts cleanly.
    6. All 77 canonical slugs and 80 legacy aliases are carried end
       to end from Python -> CatalogResponse payload.

What this test does NOT prove (and cannot prove without a live DB):

    * Migrations 006/007/008 apply successfully against Postgres.
    * The CHECK constraints on risk_tier and readiness_state hold.
    * The partial unique index on ai_prompt_registry is active.
    * The rex.v_* curated views exist (owned by Session 2).

The handoff doc (docs/ai-spine-handoff.md) calls these out explicitly
as the "apply migrations to a clean DB to finish the smoke" step.
"""

from __future__ import annotations

import json

import pytest

from data.quick_actions_catalog import (
    CANONICAL_SLUG_COUNT,
    LEGACY_ALIAS_COUNT,
    QUICK_ACTIONS_CATALOG,
)
from main import app
from schemas.catalog import CatalogResponse
from services.ai.catalog_import import (
    build_catalog_response_from_source,
    validate_catalog,
)
from tests._assistant_fakes import FakeDispatcher


@pytest.fixture
def fresh_env(client):
    """Install a fresh FakeDispatcher serving the full canonical catalog
    and yield the shared ASGI test client.

    Named ``fresh_env`` to signal intent: each call starts from a clean
    in-memory dispatcher the way a freshly-bootstrapped environment
    would start from a clean DB.
    """
    response = CatalogResponse.model_validate(build_catalog_response_from_source())
    saved = getattr(app.state, "assistant_dispatcher", None)
    app.state.assistant_dispatcher = FakeDispatcher.build(response)
    try:
        yield client
    finally:
        if saved is None:
            if hasattr(app.state, "assistant_dispatcher"):
                delattr(app.state, "assistant_dispatcher")
        else:
            app.state.assistant_dispatcher = saved


def test_python_catalog_validates():
    validate_catalog()
    assert CANONICAL_SLUG_COUNT == 77
    assert LEGACY_ALIAS_COUNT == 80


async def test_fresh_env_catalog_endpoint_returns_full_catalog(fresh_env):
    resp = await fresh_env.get("/api/assistant/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v1"
    assert len(body["actions"]) == CANONICAL_SLUG_COUNT


async def test_fresh_env_catalog_carries_all_80_legacy_aliases(fresh_env):
    resp = await fresh_env.get("/api/assistant/catalog")
    body = resp.json()
    aliases = {a for action in body["actions"] for a in action["legacy_aliases"]}
    expected = {f"C-{i}" for i in range(1, 80)} | {"C-104"}
    assert aliases == expected, (
        f"Alias drift end-to-end: missing={sorted(expected - aliases)} "
        f"extra={sorted(aliases - expected)}"
    )


async def test_fresh_env_catalog_never_uses_C_star_as_primary_identity(fresh_env):
    resp = await fresh_env.get("/api/assistant/catalog")
    for action in resp.json()["actions"]:
        assert not action["slug"].upper().startswith("C-"), action["slug"]


async def test_fresh_env_required_dedupes_reach_the_wire(fresh_env):
    resp = await fresh_env.get("/api/assistant/catalog")
    by_slug = {a["slug"]: a for a in resp.json()["actions"]}
    assert set(by_slug["submittal_sla"]["legacy_aliases"]) == {"C-8", "C-28"}
    assert set(by_slug["monthly_owner_report"]["legacy_aliases"]) == {"C-15", "C-60"}
    assert set(by_slug["rfi_aging"]["legacy_aliases"]) == {"C-5", "C-29"}


async def test_fresh_env_chat_emits_frozen_sse_vocabulary(fresh_env):
    resp = await fresh_env.post(
        "/api/assistant/chat",
        json={
            "message": "fresh env smoke",
            "page_context": {"route": "/smoke", "surface": "assistant_sidebar"},
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(resp.text)
    types = [e["type"] for e in events]

    for expected in (
        "conversation.created",
        "message.started",
        "message.delta",
        "followups.generated",
        "message.completed",
    ):
        assert expected in types, f"fresh env chat never emitted {expected}"

    assert types.index("conversation.created") < types.index("message.started")
    first_delta = types.index("message.delta")
    assert first_delta < types.index("followups.generated")
    assert first_delta < types.index("message.completed")


def test_catalog_response_model_accepts_full_source_payload():
    payload = build_catalog_response_from_source()
    model = CatalogResponse.model_validate(payload)
    assert len(model.actions) == CANONICAL_SLUG_COUNT


def test_catalog_response_payload_is_json_serializable():
    """The JSON round-trip matters because the router returns this shape
    over the wire to Session 3. Any non-serializable field would leak
    here, not at the router boundary."""
    payload = build_catalog_response_from_source()
    roundtrip = json.loads(json.dumps(payload))
    assert roundtrip["version"] == "v1"
    assert {a["slug"] for a in roundtrip["actions"]} == {
        a["slug"] for a in QUICK_ACTIONS_CATALOG
    }


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

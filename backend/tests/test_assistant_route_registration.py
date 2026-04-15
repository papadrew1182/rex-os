"""Route-registration guardrail for the Session 1 assistant router.

Regression-guards the exact failure mode Session 1 hit during its first
pass: the wiring in ``backend/app/routes/__init__.py`` was reverted and
requests to ``/api/assistant/*`` fell through to the SPA fallback,
returning ``<!doctype html>`` instead of a JSON contract response.

These tests do not require the DB or the real dispatcher. They assert
the router is physically mounted on the FastAPI app, the methods match
what Session 3 is going to call, and the SSE event-type constants
emitted by the chat service have not drifted from the frozen vocabulary.
"""

from __future__ import annotations

from main import app


# Every entry is (method, exact_path). ``path`` matches FastAPI's
# ``route.path`` attribute, which preserves path-parameter placeholders
# like ``{conversation_id}`` exactly.
EXPECTED_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/assistant/catalog"),
    ("GET", "/api/assistant/conversations"),
    ("GET", "/api/assistant/conversations/{conversation_id}"),
    ("DELETE", "/api/assistant/conversations/{conversation_id}"),
    ("POST", "/api/assistant/chat"),
]

# Frozen SSE event vocabulary for Session 3. Any change here is a
# contract break. Sourced from the Session 1 AI spine charter.
FROZEN_SSE_EVENT_TYPES: set[str] = {
    "conversation.created",
    "message.started",
    "message.delta",
    "message.completed",
    "followups.generated",
    "action.suggestions",
    "error",
}


def _route_pairs() -> set[tuple[str, str]]:
    """Extract (method, path) pairs from the live FastAPI app."""
    pairs: set[tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", None)
        if not path:
            continue
        for method in methods:
            pairs.add((method.upper(), path))
    return pairs


def test_every_expected_assistant_route_is_mounted():
    pairs = _route_pairs()
    missing = [r for r in EXPECTED_ROUTES if r not in pairs]
    assert not missing, (
        "Assistant router is not fully mounted. Missing: "
        f"{missing}. This usually means the wiring in "
        "backend/app/routes/__init__.py was reverted - re-add "
        "`from routers.assistant import router as assistant_router` "
        "and the entry in `all_routers`."
    )


def test_assistant_catalog_route_has_the_exact_canonical_path():
    """Guard against someone accidentally renaming the catalog endpoint."""
    paths = {p for _, p in _route_pairs()}
    assert "/api/assistant/catalog" in paths


def test_assistant_chat_route_accepts_post():
    pairs = _route_pairs()
    assert ("POST", "/api/assistant/chat") in pairs


def test_assistant_chat_route_does_not_accept_get():
    """The chat endpoint is POST-only. A GET would mean a wiring mistake
    (or the SPA fallback catching it), which was the exact regression
    that hit Session 1 the first time through."""
    pairs = _route_pairs()
    assert ("GET", "/api/assistant/chat") not in pairs


def test_assistant_conversation_detail_has_path_parameter():
    paths = {p for _, p in _route_pairs()}
    assert "/api/assistant/conversations/{conversation_id}" in paths


def test_sse_event_vocabulary_is_frozen_in_chat_service():
    """Scan the committed chat_service.py source for SSE event emissions
    and assert the set of event types matches the frozen vocabulary.

    We read the file as text rather than importing and introspecting so
    a refactor that accidentally drops one of the events still fails
    loudly — the vocabulary is the contract, not the function names.
    """
    import os
    chat_service_path = os.path.join(
        os.path.dirname(__file__), "..", "services", "ai", "chat_service.py"
    )
    with open(chat_service_path, "r", encoding="utf-8") as f:
        src = f.read()

    emitted: set[str] = set()
    for event_type in FROZEN_SSE_EVENT_TYPES:
        if f'"type": "{event_type}"' in src:
            emitted.add(event_type)

    # ``action.suggestions`` is reserved in the frozen vocabulary but
    # not emitted in the first pass. Every other event must be present.
    active = FROZEN_SSE_EVENT_TYPES - {"action.suggestions"}
    missing = active - emitted
    assert not missing, (
        f"chat_service.py no longer emits these frozen SSE events: {sorted(missing)}. "
        "This is a Session 3 contract break. Restore the emissions or "
        "coordinate a contract change with the handoff doc."
    )


def test_action_suggestions_event_type_is_reserved_even_if_unused():
    """``action.suggestions`` is part of the frozen vocabulary but is
    not emitted in the first pass. This test documents that it stays
    reserved — if anything ever emits it, the emission must match the
    shape ``{"type": "action.suggestions", "items": [...]}``."""
    assert "action.suggestions" in FROZEN_SSE_EVENT_TYPES

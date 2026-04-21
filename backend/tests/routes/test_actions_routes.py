"""Phase 6 action routes - approve / discard / undo / pending.

EVENT-LOOP NOTE: These tests intentionally do NOT carry ``@pytest.mark.anyio``.
The session-scoped ``client`` fixture (see tests/conftest.py) and the shared
SQLAlchemy engine pool are bound to pytest-asyncio's session loop. Adding
``@pytest.mark.anyio`` would route these through pytest-anyio's per-test
loop instead, which on Linux CI (Python 3.14 + asyncpg) triggers
"Future attached to a different loop" / "got result for unknown protocol
state 3" the moment ``Depends(get_db)`` checks out a pooled connection.
On Windows the race is slow enough to mask the bug locally.

The module's ``auto`` mode (see backend/pytest.ini) collects plain
``async def test_*`` functions directly under pytest-asyncio with the
session-scoped loop, matching every other route test in this suite.
"""
from __future__ import annotations

from uuid import uuid4


async def test_approve_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/approve")
    assert r.status_code == 404


async def test_discard_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/discard")
    assert r.status_code == 404


async def test_undo_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/undo")
    assert r.status_code == 404


async def test_pending_endpoint_returns_empty_for_clean_user(client):
    r = await client.get("/api/actions/pending")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


async def test_requires_auth(client):
    """Pop the admin override to exercise real auth dep."""
    from main import app
    from app.dependencies import get_current_user
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.post(f"/api/actions/{uuid4()}/approve")
        assert r.status_code in (401, 403)
    finally:
        if saved:
            app.dependency_overrides[get_current_user] = saved

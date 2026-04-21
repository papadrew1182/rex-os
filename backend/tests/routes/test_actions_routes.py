"""Phase 6 action routes — approve / discard / undo / pending."""
from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.mark.anyio
async def test_approve_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/approve")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_discard_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/discard")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_undo_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/undo")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_pending_endpoint_returns_empty_for_clean_user(client):
    r = await client.get("/api/actions/pending")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


@pytest.mark.anyio
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

"""Tests for ProcoreAdapter.fetch_change_events — Phase 4 Wave 2 direct API.

Task 6 replaces the Phase 4a stub ``fetch_change_events`` (empty page)
with a real implementation that calls ProcoreClient.list_change_events
(direct Procore REST API, ``/rest/v1.0/projects/{id}/change_events``)
instead of reading from the old rex-procore Railway DB. The returned
ConnectorPage carries items shaped via build_change_event_payload.

Overlap note: Phase 6b Wave 2 shipped a ``create_change_event`` LLM tool
that inserts into ``rex.change_events`` directly. The Procore sync and
the LLM tool both upsert to the same natural key (project_id,
event_number) — both sources converge via ON CONFLICT at the writer.
The adapter doesn't need to know about the other source; it just keeps
its side of the upsert idempotent.

Patch target: we patch ProcoreClient.from_env on the source module
(``app.services.ai.tools.procore_api``) — calls inside the adapter
resolve the attribute from the same module every time ``from_env()``
runs, so patching the attribute on the module itself works regardless
of whether the adapter imported it ``from X import`` or ``import X``.
Mirrors T3/T4/T5's pattern.

Graceful-degradation case: if env vars aren't set,
``ProcoreNotConfigured`` bubbles out of ``ProcoreClient.from_env()``.
The adapter catches it and returns an empty page so Phase 4a sync
pipelines don't crash on a box that hasn't configured Procore OAuth
yet.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.connectors.procore.adapter import ProcoreAdapter


@pytest.mark.asyncio
async def test_fetch_change_events_returns_connector_page():
    """Happy path: adapter calls list_change_events, wraps rows via
    build_change_event_payload, returns ConnectorPage.items."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    fake_rows = [
        {
            "id": 501,
            "number": "CE-001",
            "title": "Differing site conditions",
            "status": "open",
            "change_reason": "Unforeseen",
            "event_type": "tbd",
            "scope": "in_scope",
            "estimated_amount": 12500.00,
            "updated_at": "2026-04-22T15:00:00Z",
        },
        {
            "id": 502,
            "number": "CE-002",
            "title": "Owner-requested finish upgrade",
            "status": "pending",
            "change_reason": "Owner Change",
            "event_type": "owner_change",
            "scope": "in_scope",
            "estimated_amount": 8000.00,
            "updated_at": "2026-04-22T16:00:00Z",
        },
    ]
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_change_events = AsyncMock(return_value=fake_rows)
        mk.return_value = client
        page = await adapter.fetch_change_events(
            project_external_id="99", cursor=None
        )
        assert len(page.items) == 2
        r0 = page.items[0]
        # build_change_event_payload mirrors build_daily_log_payload's
        # shape: ``id`` is the stringified procore change_event id
        # (staging.upsert_raw reads ``item["id"]``), ``project_source_id``
        # is the stringified project_external_id this call was scoped to.
        assert r0["id"] == "501"
        assert r0["project_source_id"] == "99"
        client.list_change_events.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_change_events_passes_cursor_as_updated_since():
    """Cursor is an ISO timestamp — the updated_at watermark of the last
    successful run. Adapter parses it into a datetime (keeping tzinfo)
    and passes it to list_change_events as ``updated_since``."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    cursor_iso = "2026-04-22T10:00:00+00:00"
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_change_events = AsyncMock(return_value=[])
        mk.return_value = client
        await adapter.fetch_change_events(
            project_external_id="99", cursor=cursor_iso
        )
        kw = client.list_change_events.await_args.kwargs
        assert kw["project_id"] == "99"
        since = kw["updated_since"]
        assert since is not None
        assert since.tzinfo is not None


@pytest.mark.asyncio
async def test_fetch_change_events_gracefully_handles_not_configured():
    """If Procore env vars aren't set, fetch returns an empty page and
    does NOT crash. Scheduler calls fetch_* across many accounts; one
    account's missing OAuth config must not kill the whole run."""
    from app.services.ai.tools.procore_api import ProcoreNotConfigured
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
        side_effect=ProcoreNotConfigured("test"),
    ):
        page = await adapter.fetch_change_events(
            project_external_id="99", cursor=None
        )
        assert page.items == []
        assert page.next_cursor is None

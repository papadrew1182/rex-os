"""Tests for ProcoreAdapter.fetch_inspections — Phase 4 Wave 2 direct API.

Task 7 ships the fifth and final Wave 2 resource: inspections. The
adapter method calls ProcoreClient.list_inspections (direct Procore
REST API, ``/rest/v1.0/projects/{id}/inspection_lists``) and wraps
the response rows in a ConnectorPage via
``payloads.build_inspection_payload``.

Patch target: we patch ProcoreClient.from_env on the source module
(``app.services.ai.tools.procore_api``) — calls inside the adapter
resolve the attribute from the same module every time ``from_env()``
runs, so patching the attribute on the module itself works regardless
of whether the adapter imported it ``from X import`` or ``import X``.
Mirrors T3/T4/T5/T6's pattern.

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
async def test_fetch_inspections_returns_connector_page():
    """Happy path: adapter calls list_inspections, wraps rows via
    build_inspection_payload, returns ConnectorPage.items."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    fake_rows = [
        {
            "id": 501,
            "inspection_number": "INS-1",
            "name": "Pre-pour inspection",
            "updated_at": "2026-04-22T15:00:00Z",
        },
        {
            "id": 502,
            "inspection_number": "INS-2",
            "name": "Framing inspection",
            "updated_at": "2026-04-22T16:00:00Z",
        },
    ]
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_inspections = AsyncMock(return_value=fake_rows)
        mk.return_value = client
        page = await adapter.fetch_inspections(
            project_external_id="99", cursor=None
        )
        assert len(page.items) == 2
        # build_inspection_payload mirrors the other Wave 2 builders:
        # ``id`` is the stringified procore inspection id (staging's
        # upsert_raw reads ``item["id"]``), ``project_source_id`` is the
        # stringified project_external_id this call was scoped to.
        assert page.items[0]["id"] == "501"
        assert page.items[0]["project_source_id"] == "99"
        client.list_inspections.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_inspections_passes_cursor_as_updated_since():
    """Cursor is an ISO timestamp — the updated_at watermark of the last
    successful run. Adapter parses it into a datetime (keeping tzinfo)
    and passes it to list_inspections as ``updated_since``."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    cursor_iso = "2026-04-22T10:00:00+00:00"
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_inspections = AsyncMock(return_value=[])
        mk.return_value = client
        await adapter.fetch_inspections(
            project_external_id="99", cursor=cursor_iso
        )
        kw = client.list_inspections.await_args.kwargs
        assert kw["project_id"] == "99"
        since = kw.get("updated_since")
        assert since is not None
        assert since.tzinfo is not None


@pytest.mark.asyncio
async def test_fetch_inspections_gracefully_handles_not_configured():
    """If Procore env vars aren't set, fetch returns an empty page and
    does NOT crash. Scheduler calls fetch_* across many accounts; one
    account's missing OAuth config must not kill the whole run."""
    from app.services.ai.tools.procore_api import ProcoreNotConfigured
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
        side_effect=ProcoreNotConfigured("test"),
    ):
        page = await adapter.fetch_inspections(
            project_external_id="99", cursor=None
        )
        assert page.items == []
        assert page.next_cursor is None

"""Tests for ProcoreAdapter.fetch_daily_logs — Phase 4 Wave 2 direct API.

Task 4 replaces the Phase 4a stub with a real implementation that calls
ProcoreClient.list_daily_logs (direct Procore REST API) instead of
reading from the old rex-procore Railway DB. The returned ConnectorPage
carries items shaped via build_daily_log_payload.

Patch target: the adapter imports ProcoreClient from
``app.services.ai.tools.procore_api`` at module load time, so we patch
at that source module path — calls inside the adapter resolve the
``ProcoreClient`` attribute from the same module every time
``from_env()`` runs, so patching the attribute on the module itself
works regardless of whether the adapter imported it ``from X import``
or ``import X``. We use the source module as the patch path for
clarity.

Graceful-degradation case: if env vars aren't set, ProcoreNotConfigured
bubbles out of ``ProcoreClient.from_env()``. The adapter catches it and
returns an empty page so Phase 4a sync pipelines don't crash on a
box that hasn't configured Procore OAuth yet.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.connectors.procore.adapter import ProcoreAdapter


@pytest.mark.asyncio
async def test_fetch_daily_logs_returns_connector_page():
    """Happy path: adapter calls list_daily_logs, wraps rows via
    build_daily_log_payload, returns ConnectorPage.items."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    fake_rows = [
        {"id": 201, "date": "2026-04-22", "updated_at": "2026-04-22T15:00:00Z"},
        {"id": 202, "date": "2026-04-21", "updated_at": "2026-04-21T15:00:00Z"},
    ]
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_daily_logs = AsyncMock(return_value=fake_rows)
        mk.return_value = client
        page = await adapter.fetch_daily_logs(project_external_id="99", cursor=None)
        assert len(page.items) == 2
        r0 = page.items[0]
        # build_daily_log_payload mirrors build_submittal_payload's shape:
        # ``id`` is the stringified procore id (staging.upsert_raw reads
        # ``item["id"]``), ``project_source_id`` is the stringified
        # project_external_id this call was scoped to.
        assert r0["id"] == "201"
        assert r0["project_source_id"] == "99"
        client.list_daily_logs.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_daily_logs_passes_cursor_as_updated_since():
    """Cursor is an ISO timestamp — the updated_at watermark of the
    last successful run. Adapter parses it into a datetime (keeping
    the tzinfo) and passes it to list_daily_logs as ``updated_since``."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    cursor_iso = "2026-04-22T10:00:00+00:00"
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_daily_logs = AsyncMock(return_value=[])
        mk.return_value = client
        await adapter.fetch_daily_logs(project_external_id="99", cursor=cursor_iso)
        kw = client.list_daily_logs.await_args.kwargs
        assert kw["project_id"] == "99"
        since = kw["updated_since"]
        assert since is not None
        assert since.tzinfo is not None


@pytest.mark.asyncio
async def test_fetch_daily_logs_gracefully_handles_not_configured():
    """If Procore env vars aren't set, fetch returns an empty page and
    does NOT crash. Scheduler calls fetch_* across many accounts; one
    account's missing OAuth config must not kill the whole run."""
    from app.services.ai.tools.procore_api import ProcoreNotConfigured
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
        side_effect=ProcoreNotConfigured("test"),
    ):
        page = await adapter.fetch_daily_logs(project_external_id="99", cursor=None)
        assert page.items == []
        assert page.next_cursor is None

"""Tests for ProcoreAdapter.fetch_schedule_activities — Phase 4 Wave 2 direct API.

Task 5 replaces the Phase 4a stub ``fetch_schedule`` with a real
implementation ``fetch_schedule_activities`` that calls
ProcoreClient.list_schedule_tasks (direct Procore REST API,
``/rest/v1.0/projects/{id}/schedule/standard_tasks``) instead of reading
from the old rex-procore Railway DB. The returned ConnectorPage carries
items shaped via build_schedule_activity_payload.

Name rationale: the ``_RESOURCE_CONFIG`` key is ``schedule_activities``
(matches the rex.schedule_activities canonical table), so the adapter
method name matches for consistency with other Wave 2 resources
(fetch_submittals, fetch_daily_logs).

Patch target: we patch ProcoreClient.from_env on the source module
(``app.services.ai.tools.procore_api``) — calls inside the adapter
resolve the attribute from the same module every time
``from_env()`` runs, so patching the attribute on the module itself
works regardless of whether the adapter imported it ``from X import``
or ``import X``. Mirrors T3/T4's pattern.

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
async def test_fetch_schedule_activities_returns_connector_page():
    """Happy path: adapter calls list_schedule_tasks, wraps rows via
    build_schedule_activity_payload, returns ConnectorPage.items."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    fake_rows = [
        {
            "id": 301,
            "task_number": "001",
            "name": "Pour footings",
            "start_date": "2026-05-01",
            "finish_date": "2026-05-05",
            "updated_at": "2026-04-22T15:00:00Z",
        },
        {
            "id": 302,
            "task_number": "002",
            "name": "Form walls",
            "start_date": "2026-05-06",
            "finish_date": "2026-05-10",
            "updated_at": "2026-04-22T16:00:00Z",
        },
    ]
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_schedule_tasks = AsyncMock(return_value=fake_rows)
        mk.return_value = client
        page = await adapter.fetch_schedule_activities(
            project_external_id="99", cursor=None
        )
        assert len(page.items) == 2
        r0 = page.items[0]
        # build_schedule_activity_payload mirrors build_daily_log_payload's
        # shape: ``id`` is the stringified procore task id (staging.upsert_raw
        # reads ``item["id"]``), ``project_source_id`` is the stringified
        # project_external_id this call was scoped to.
        assert r0["id"] == "301"
        assert r0["project_source_id"] == "99"
        client.list_schedule_tasks.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_schedule_activities_passes_cursor_as_updated_since():
    """Cursor is an ISO timestamp — the updated_at watermark of the
    last successful run. Adapter parses it into a datetime (keeping
    the tzinfo) and passes it to list_schedule_tasks as
    ``updated_since``."""
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    cursor_iso = "2026-04-22T10:00:00+00:00"
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
    ) as mk:
        client = AsyncMock()
        client.list_schedule_tasks = AsyncMock(return_value=[])
        mk.return_value = client
        await adapter.fetch_schedule_activities(
            project_external_id="99", cursor=cursor_iso
        )
        kw = client.list_schedule_tasks.await_args.kwargs
        assert kw["project_id"] == "99"
        since = kw["updated_since"]
        assert since is not None
        assert since.tzinfo is not None


@pytest.mark.asyncio
async def test_fetch_schedule_activities_gracefully_handles_not_configured():
    """If Procore env vars aren't set, fetch returns an empty page and
    does NOT crash. Scheduler calls fetch_* across many accounts; one
    account's missing OAuth config must not kill the whole run."""
    from app.services.ai.tools.procore_api import ProcoreNotConfigured
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    with patch(
        "app.services.ai.tools.procore_api.ProcoreClient.from_env",
        side_effect=ProcoreNotConfigured("test"),
    ):
        page = await adapter.fetch_schedule_activities(
            project_external_id="99", cursor=None
        )
        assert page.items == []
        assert page.next_cursor is None

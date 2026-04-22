"""Task 8 — apscheduler job that polls Procore API every 30 min.

The job iterates all active procore connector_accounts and runs each of
the 5 Wave 2 resource syncs against the orchestrator. One failing
(account, resource) pair does NOT halt the rest — the job logs the
failure and continues so the next resource / account / tick still
makes progress.

Also asserts the job is registered under the existing @register_job
decorator pattern with the expected cron expression.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.jobs.runner import JOB_REGISTRY
from app.services.connectors.procore.scheduler_job import (
    RESOURCE_TYPES,
    procore_api_sync_job,
)


# ── Registry wiring ────────────────────────────────────────────────────


def test_procore_api_sync_is_registered_every_30_min():
    """The @register_job decorator must register procore_api_sync with a
    cron that fires every 30 minutes."""
    assert "procore_api_sync" in JOB_REGISTRY, (
        f"procore_api_sync missing from JOB_REGISTRY "
        f"(have: {sorted(JOB_REGISTRY.keys())})"
    )
    job = JOB_REGISTRY["procore_api_sync"]
    assert job.enabled is True
    assert job.cron == "*/30 * * * *", (
        f"expected every-30-min cron, got {job.cron!r}"
    )


def test_resource_types_covers_all_five_wave2_resources():
    """RESOURCE_TYPES must contain exactly the 5 Wave 2 resources."""
    assert set(RESOURCE_TYPES) == {
        "submittals",
        "daily_logs",
        "schedule_activities",
        "change_events",
        "inspections",
    }


# ── Behavior ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iterates_all_5_resources_per_account():
    """Given one active procore account, sync_resource() is called 5
    times with the 5 resource type names."""
    account_id = uuid4()

    mk_sync = AsyncMock(return_value={"rows_fetched": 0, "rows_upserted": 0})
    db_stub = MagicMock()

    with patch(
        "app.services.connectors.procore.scheduler_job._list_active_procore_accounts",
        new_callable=AsyncMock,
        return_value=[{"id": account_id, "label": "Test"}],
    ), patch(
        "app.services.connectors.procore.scheduler_job.sync_resource",
        new=mk_sync,
    ):
        summary = await procore_api_sync_job(db_stub)

    assert mk_sync.await_count == len(RESOURCE_TYPES)
    called_resource_types = [
        c.kwargs["resource_type"] for c in mk_sync.await_args_list
    ]
    assert set(called_resource_types) == set(RESOURCE_TYPES)
    # Every call is scoped to the one account we seeded.
    called_account_ids = [c.kwargs["account_id"] for c in mk_sync.await_args_list]
    assert set(called_account_ids) == {account_id}
    # Summary string mentions counts.
    assert "accounts=1" in summary
    assert "ok=5" in summary
    assert "fail=0" in summary


@pytest.mark.asyncio
async def test_one_resource_failure_does_not_halt_others():
    """If sync_resource raises for one resource, the job moves on to
    the next and still attempts all 5."""
    account_id = uuid4()

    call_count = [0]

    async def flaky_sync(db, *, account_id, resource_type):
        call_count[0] += 1
        if resource_type == "daily_logs":
            raise RuntimeError("procore 500")
        return {"rows_fetched": 0, "rows_upserted": 0}

    db_stub = MagicMock()

    with patch(
        "app.services.connectors.procore.scheduler_job._list_active_procore_accounts",
        new_callable=AsyncMock,
        return_value=[{"id": account_id, "label": "Test"}],
    ), patch(
        "app.services.connectors.procore.scheduler_job.sync_resource",
        new=AsyncMock(side_effect=flaky_sync),
    ):
        summary = await procore_api_sync_job(db_stub)

    # All 5 resources attempted even though one raised.
    assert call_count[0] == 5
    # Failure is counted into the summary string.
    assert "ok=4" in summary
    assert "fail=1" in summary


@pytest.mark.asyncio
async def test_no_active_accounts_is_noop():
    """Empty account list should return a summary cleanly, no exceptions,
    and sync_resource is never called."""
    mk_sync = AsyncMock()
    db_stub = MagicMock()

    with patch(
        "app.services.connectors.procore.scheduler_job._list_active_procore_accounts",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.connectors.procore.scheduler_job.sync_resource",
        new=mk_sync,
    ):
        summary = await procore_api_sync_job(db_stub)

    assert mk_sync.await_count == 0
    assert "accounts=0" in summary


@pytest.mark.asyncio
async def test_iterates_across_multiple_accounts():
    """Two active accounts → 5 resources * 2 = 10 sync_resource calls."""
    a1 = uuid4()
    a2 = uuid4()

    mk_sync = AsyncMock(return_value={"rows_fetched": 0, "rows_upserted": 0})
    db_stub = MagicMock()

    with patch(
        "app.services.connectors.procore.scheduler_job._list_active_procore_accounts",
        new_callable=AsyncMock,
        return_value=[
            {"id": a1, "label": "acct-1"},
            {"id": a2, "label": "acct-2"},
        ],
    ), patch(
        "app.services.connectors.procore.scheduler_job.sync_resource",
        new=mk_sync,
    ):
        summary = await procore_api_sync_job(db_stub)

    assert mk_sync.await_count == 10
    # Both accounts get every resource.
    by_account: dict[UUID, set[str]] = {a1: set(), a2: set()}
    for c in mk_sync.await_args_list:
        by_account[c.kwargs["account_id"]].add(c.kwargs["resource_type"])
    assert by_account[a1] == set(RESOURCE_TYPES)
    assert by_account[a2] == set(RESOURCE_TYPES)
    assert "accounts=2" in summary
    assert "ok=10" in summary

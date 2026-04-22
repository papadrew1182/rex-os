"""apscheduler job — every 30 min, poll Procore's direct API for the
five Phase 4 Wave 2 resources across every active procore
connector_account.

Integration shape
-----------------
The job is wired via the existing ``@register_job`` decorator (see
``app.jobs.runner``). That path:

  * takes an ``AsyncSession`` handed in by ``run_job_now``
  * returns a short summary string that lands in ``rex.job_runs.summary``
  * is gated by ``REX_ENABLE_SCHEDULER`` — the same env flag that
    controls whether the AsyncIOScheduler boots at all. Demo scheduler
    stays off by default; prod Railway instances set
    ``REX_ENABLE_SCHEDULER=1``.
  * is cross-instance safe via Postgres advisory locks (built into
    ``run_job_now``) — the second Railway instance running its tick
    records a 'skipped' row and returns cleanly.

Per-resource failure semantics
------------------------------
One (account, resource) pair raising does NOT stop the rest. We log
the exception and move on to the next resource / account so a single
Procore 500 doesn't starve the other four resources for 30 min. The
orchestrator already marks ``rex.sync_runs`` as 'failed' on its own
path, so the next tick picks up from the cursor that was persisted
before the failure — idempotent replay fills any gaps.

Wave 2 resources covered: submittals, daily_logs, schedule_activities,
change_events, inspections. Phase 4a resources (projects, users,
vendors, rfis) are synced via the rex-procore Railway pass-through
and continue on their own path.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import register_job
from app.services.connectors.procore.orchestrator import sync_resource

log = logging.getLogger("rex.connectors.procore.scheduler")

# The five resources Phase 4 Wave 2 added. Order is deterministic but
# not load-bearing — each resource sync is independent and failure of
# one does not affect the others.
RESOURCE_TYPES: list[str] = [
    "submittals",
    "daily_logs",
    "schedule_activities",
    "change_events",
    "inspections",
]


async def _list_active_procore_accounts(db: AsyncSession) -> list[dict[str, Any]]:
    """Return ``[{id, label}]`` for every procore connector_account with
    status='connected'.

    The status enum (see migration 012) is one of
    {'configured', 'connected', 'disconnected', 'error', 'disabled'};
    only 'connected' accounts have a live token worth syncing.
    """
    result = await db.execute(
        text(
            """
            SELECT ca.id, ca.label
            FROM rex.connector_accounts ca
            JOIN rex.connectors c ON c.id = ca.connector_id
            WHERE c.connector_key = 'procore'
              AND ca.status = 'connected'
            ORDER BY ca.label
            """
        )
    )
    return [dict(r) for r in result.mappings().all()]


@register_job(
    job_key="procore_api_sync",
    name="Procore API sync (Wave 2)",
    description=(
        "Poll Procore REST API for the five Phase 4 Wave 2 resources "
        "(submittals, daily_logs, schedule_activities, change_events, "
        "inspections) across all active procore connector_accounts."
    ),
    cron="*/30 * * * *",  # every 30 minutes
)
async def procore_api_sync_job(db: AsyncSession) -> str:
    """Iterate every active procore connector_account * each of the 5
    Wave 2 resources; dispatch to the orchestrator's ``sync_resource``.

    Per-resource failures are logged and counted but do NOT halt the
    loop. The returned summary string ends up in ``rex.job_runs.summary``
    for admin visibility: it reports the counts of accounts touched,
    resources that succeeded, and resources that failed.
    """
    accounts = await _list_active_procore_accounts(db)

    if not accounts:
        log.info("procore_api_sync_job no_active_accounts")
        return "accounts=0 ok=0 fail=0"

    ok = 0
    fail = 0
    for account in accounts:
        account_id = account["id"]
        for resource_type in RESOURCE_TYPES:
            try:
                await sync_resource(
                    db,
                    account_id=account_id,
                    resource_type=resource_type,
                )
                ok += 1
                log.info(
                    "procore_api_sync ok account=%s resource=%s",
                    account_id, resource_type,
                )
            except Exception as exc:  # noqa: BLE001
                fail += 1
                # sync_resource already marks the sync_run 'failed' and
                # records the error excerpt — we log here for tail-f
                # visibility and keep iterating.
                log.exception(
                    "procore_api_sync FAIL account=%s resource=%s err=%s",
                    account_id, resource_type, exc,
                )

    return f"accounts={len(accounts)} ok={ok} fail={fail}"

"""Procore connector adapter.

Hybrid read model:

* **Phase 4a resources** (projects, users, vendors, rfis) read from the
  "Rex App" Railway Postgres (old rex-procore sync app) via
  RexAppDbClient — the old app already syncs Procore's API on a cron
  and we consume its flattened ``procore.*`` tables.

* **Phase 4 Wave 2 resources** (submittals + follow-ups: daily_logs,
  schedule_activities, change_events, inspections) call Procore's REST
  API directly via ``ProcoreClient`` from
  ``app.services.ai.tools.procore_api``. These resources were never
  ingested into the rex-procore app, so going direct is the only
  way to get them without building a full parallel ingest first.

Each ``fetch_<resource>`` picks the right path per its comment. The
adapter's public ConnectorPage shape is the same across both paths —
callers don't need to know which way the data came in.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.ai.tools.procore_api import ProcoreClient, ProcoreNotConfigured
from app.services.connectors.base import (
    ConnectorAdapter,
    ConnectorHealth,
    ConnectorPage,
)
from app.services.connectors.procore.payloads import (
    build_project_payload,
    build_rfi_payload,
    build_submittal_payload,
    build_user_payload,
    build_vendor_payload,
)
from app.services.connectors.procore.rex_app_client import RexAppDbClient
from app.services.connectors.procore.rex_app_pool import get_rex_app_pool

DEFAULT_PAGE_SIZE = 500


class ProcoreAdapter(ConnectorAdapter):
    connector_key = "procore"

    def __init__(self, *, account_id: str, config: dict[str, Any] | None = None):
        super().__init__(account_id=account_id, config=config)
        self._client: RexAppDbClient | None = None

    async def _get_client(self) -> RexAppDbClient:
        if self._client is None:
            pool = await get_rex_app_pool()
            self._client = RexAppDbClient(pool)
        return self._client

    async def health_check(self) -> ConnectorHealth:
        try:
            client = await self._get_client()
            rows = await client.fetch_rows(
                schema="procore",
                table="sync_log",
                cursor_col="started_at",
                cursor_value=None,
                limit=1,
            )
            return ConnectorHealth(
                healthy=True,
                details={"last_rex_app_sync_row": rows[0] if rows else None},
            )
        except Exception as e:
            return ConnectorHealth(
                healthy=False,
                last_error_message=str(e),
                details={
                    "state": "rex_app_probe_failed",
                    "error_type": type(e).__name__,
                },
            )

    async def list_projects(self, cursor: str | None = None) -> ConnectorPage:
        """Fetch one page of ``procore.projects`` rows from the Rex App DB.

        Cursor semantics: ``procore.projects`` lacks a reliable
        ``updated_at`` (most rows are NULL on the live source), so we
        use the bigint ``procore_id`` as the monotonic cursor. Each
        call requests rows with ``procore_id > cursor`` in ascending
        order; ``next_cursor`` is the last item's id or None when the
        page was empty. The bigint cast goes through
        ``RexAppDbClient.fetch_rows(cursor_col_type='bigint')``.
        """
        client = await self._get_client()
        rows = await client.fetch_rows(
            schema="procore",
            table="projects",
            cursor_col="procore_id",
            cursor_col_type="bigint",
            cursor_value=cursor,
            limit=DEFAULT_PAGE_SIZE,
        )
        items = [build_project_payload(r) for r in rows]
        next_cursor: str | None = None
        if items:
            next_cursor = items[-1]["id"]
        return ConnectorPage(items=items, next_cursor=next_cursor)

    async def list_users(self, cursor: str | None = None) -> ConnectorPage:
        """Fetch one page of ``procore.users`` rows from the Rex App DB.

        Cursor semantics: ``procore.users`` lacks a reliable ``updated_at``
        (most rows are NULL on the live source — same pattern as projects),
        so we use the bigint ``procore_id`` as the monotonic cursor. Each
        call requests rows with ``procore_id > cursor`` in ascending order;
        ``next_cursor`` is the last item's id or None when the page was
        empty. The bigint cast goes through
        ``RexAppDbClient.fetch_rows(cursor_col_type='bigint')``.
        """
        client = await self._get_client()
        rows = await client.fetch_rows(
            schema="procore",
            table="users",
            cursor_col="procore_id",
            cursor_col_type="bigint",
            cursor_value=cursor,
            limit=DEFAULT_PAGE_SIZE,
        )
        items = [build_user_payload(r) for r in rows]
        next_cursor: str | None = None
        if items:
            next_cursor = items[-1]["id"]
        return ConnectorPage(items=items, next_cursor=next_cursor)

    async def list_vendors(self, cursor: str | None = None) -> ConnectorPage:
        """Fetch one page of ``procore.vendors`` rows from the Rex App DB.

        Procore-specific (not on ``ConnectorAdapter`` ABC): vendors are a
        concept the Procore connector surfaces via its own
        ``procore.vendors`` table. The ABC's ``list_users`` covers the
        cross-project directory; a future multi-connector vendor API
        would add ``list_vendors`` to the ABC (with stubs for the
        adapters that don't implement it). The orchestrator calls this
        through ``getattr(adapter, cfg['fetch_fn_name'])``, which is
        duck-typed — so adding the method here without extending the
        ABC works cleanly.

        Cursor semantics: ``procore.vendors.updated_at`` IS populated on
        the live source, but we use the bigint ``procore_id`` as the
        monotonic cursor for consistency with projects/users (both use
        procore_id because their updated_at is sparse). Keeping the
        cursor type uniform across the three root resources simplifies
        the mental model and the client's ``cursor_col_type`` plumbing.
        """
        client = await self._get_client()
        rows = await client.fetch_rows(
            schema="procore",
            table="vendors",
            cursor_col="procore_id",
            cursor_col_type="bigint",
            cursor_value=cursor,
            limit=DEFAULT_PAGE_SIZE,
        )
        items = [build_vendor_payload(r) for r in rows]
        next_cursor: str | None = None
        if items:
            next_cursor = items[-1]["id"]
        return ConnectorPage(items=items, next_cursor=next_cursor)

    async def fetch_project_directory(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_rfis(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        client = await self._get_client()
        try:
            pid = int(project_external_id)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"project_external_id must be a numeric procore project id; got {project_external_id!r}"
            ) from e

        rows = await client.fetch_rows(
            schema="procore",
            table="rfis",
            cursor_col="updated_at",
            cursor_value=cursor,
            limit=DEFAULT_PAGE_SIZE,
            filters=[("project_id", "=", pid)],
        )
        items = [build_rfi_payload(r) for r in rows]
        next_cursor: str | None = None
        if items:
            last_updated = items[-1].get("updated_at")
            if last_updated is None:
                raise ValueError(
                    "rfis row missing updated_at; cannot advance cursor. "
                    "Source table procore.rfis is expected to have non-null updated_at."
                )
            next_cursor = last_updated
        return ConnectorPage(items=items, next_cursor=next_cursor)

    async def fetch_submittals(
        self, project_external_id: str, cursor: str | None = None,
    ) -> ConnectorPage:
        """Fetch a page of submittals from Procore's REST API directly.

        ``project_external_id`` is the Procore project id (bigint as
        string) the adapter was given by the orchestrator's per-project
        loop. ``cursor``, if present, is an ISO timestamp — the
        ``updated_at`` watermark of the last successful run — which we
        forward to Procore as the ``updated_since`` filter so the upstream
        returns only changed rows.

        Graceful degradation: if Procore env vars aren't configured
        (``ProcoreNotConfigured``), returns an empty page instead of
        crashing. The scheduler iterates fetch_* across many accounts;
        one account's missing OAuth config must not kill the whole run.
        Any other upstream error (HTTP 4xx/5xx) propagates to the
        orchestrator so the sync_run is marked 'failed'.

        Pagination: ``ProcoreClient.list_submittals`` already loops its
        own page-number pagination until an empty page, so the returned
        list is the complete changed set for this run. ``next_cursor``
        is always None here — the orchestrator uses the source row's
        ``updated_at`` to decide the next watermark, not a per-page
        cursor handle.
        """
        try:
            client = ProcoreClient.from_env()
        except ProcoreNotConfigured:
            return ConnectorPage(items=[], next_cursor=None)
        updated_since = datetime.fromisoformat(cursor) if cursor else None
        rows = await client.list_submittals(
            project_id=project_external_id,
            updated_since=updated_since,
        )
        items = [build_submittal_payload(project_external_id, r) for r in rows]
        return ConnectorPage(items=items, next_cursor=None)

    async def fetch_daily_logs(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_budget(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_commitments(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_change_events(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_schedule(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_documents(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)


__all__ = ["ProcoreAdapter"]

"""Procore connector adapter.

Reads from the "Rex App" Railway Postgres (old rex-procore sync app)
via RexAppDbClient. No longer talks to Procore's HTTP API directly —
the old app already does that and we consume its flattened tables.

Only fetch_rfis is wired for real in this commit; the other fetch_*
methods land in the follow-up resource-rollout plan.
"""

from __future__ import annotations

from typing import Any

from app.services.connectors.base import (
    ConnectorAdapter,
    ConnectorHealth,
    ConnectorPage,
)
from app.services.connectors.procore.payloads import build_rfi_payload
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
                details={"state": "rex_app_pool_unreachable"},
            )

    async def list_projects(self, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def list_users(self, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

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
            next_cursor = items[-1].get("updated_at")
        return ConnectorPage(items=items, next_cursor=next_cursor)

    async def fetch_submittals(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

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

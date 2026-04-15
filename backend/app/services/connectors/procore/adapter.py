"""Procore connector adapter.

Session 2 (feat/canonical-connectors) lane.

First live connector. Implements the ConnectorAdapter contract; real
HTTP calls live in client.py, raw->canonical mapping lives in mapper.py.
This module orchestrates the two and stays thin.

Until the HTTP client is wired for real, every fetch_* method returns
an empty ConnectorPage. That's explicitly fine — it lets the sync
service, the control-plane endpoints, and the tests exercise the
full pipeline without touching Procore.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.connectors.base import (
    ConnectorAdapter,
    ConnectorHealth,
    ConnectorPage,
)
from app.services.connectors.procore.client import ProcoreClient


class ProcoreAdapter(ConnectorAdapter):
    connector_key = "procore"

    def __init__(self, *, account_id: str, config: dict[str, Any] | None = None):
        super().__init__(account_id=account_id, config=config)
        self._client = ProcoreClient(
            base_url=self.config.get("base_url", "https://api.procore.com"),
            client_id=self.config.get("client_id"),
            client_secret=self.config.get("client_secret"),
            access_token=self.config.get("access_token"),
            refresh_token=self.config.get("refresh_token"),
            company_id=self.config.get("company_id"),
        )

    async def health_check(self) -> ConnectorHealth:
        # Skeleton: return "configured" as the default until the client
        # can actually ping Procore. Sync service treats this as healthy
        # only if a later sync actually succeeded.
        return ConnectorHealth(
            healthy=False,
            last_error_message="procore adapter skeleton: HTTP client not yet wired",
            details={"state": "skeleton"},
        )

    async def list_projects(self, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def list_users(self, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_project_directory(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_rfis(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

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

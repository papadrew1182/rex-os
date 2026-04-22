"""Exxir connector adapter.

Session 2 (feat/canonical-connectors) lane.

First-class adapter contract. Owner/operator platform. Implements the
full ConnectorAdapter surface so the charter's multi-connector
guarantee holds, but several fetch methods return empty pages + log a
skeleton note because Exxir does not natively surface every PM domain
Procore does. The supports() method reports false for those so
downstream sync orchestrators can gracefully skip them.
"""

from __future__ import annotations

from typing import Any

from app.services.connectors.base import (
    ConnectorAdapter,
    ConnectorHealth,
    ConnectorPage,
)
from app.services.connectors.exxir.client import ExxirClient


class ExxirAdapter(ConnectorAdapter):
    connector_key = "exxir"

    # Exxir does NOT natively surface these — mark them unsupported so
    # the sync service + control plane can skip without treating it
    # as an error.
    _unsupported: frozenset[str] = frozenset(
        {
            "fetch_rfis",
            "fetch_submittals",
            "fetch_daily_logs",
            "fetch_schedule_activities",
        }
    )

    def __init__(self, *, account_id: str, config: dict[str, Any] | None = None):
        super().__init__(account_id=account_id, config=config)
        self._client = ExxirClient(
            base_url=self.config.get("base_url"),
            api_key=self.config.get("api_key"),
        )

    def supports(self, capability: str) -> bool:
        if capability in self._unsupported:
            return False
        return super().supports(capability)

    async def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            healthy=False,
            last_error_message="exxir adapter skeleton: HTTP client not yet wired",
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

    # PM domain methods Exxir does not natively surface: return an
    # empty page. supports() still returns False so orchestrators skip.
    async def fetch_rfis(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_submittals(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_daily_logs(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_schedule_activities(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    # Financial + documents — Exxir's primary surface.
    async def fetch_budget(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_commitments(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_change_events(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_documents(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)


__all__ = ["ExxirAdapter"]

"""Base connector adapter contract.

Every connector kind (procore, exxir, future) implements ConnectorAdapter.
The Session 2 charter pins the method shapes so Session 1's assistant,
Session 3's control plane, and future sync jobs can target a stable
interface regardless of which connector is actually attached.

Exxir is NOT forced to mirror Procore field-for-field at the connector
layer. Each adapter's fetch_* methods return a ConnectorPage of
source-native dicts; normalization into canonical rex.* happens in the
mapper layer, not here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable


@dataclass
class ConnectorPage:
    """A page of source-native rows plus a next-cursor handle.

    `items` are dicts in whatever shape the upstream API returns; the
    mapper normalizes them before they touch rex.*. `next_cursor` is an
    opaque string the adapter understands; the caller just passes it
    back on the next fetch_* call.
    """

    items: list[dict[str, Any]]
    next_cursor: str | None = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConnectorHealth:
    """Rolling health snapshot for a connector account.

    Returned by health_check() so the control-plane /api/connectors/health
    endpoint can surface adapter-side liveness without exposing
    connector-native error shapes.
    """

    healthy: bool
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ConnectorAdapter(ABC):
    """Abstract base class every connector adapter implements.

    Concrete adapters live in sibling subpackages (procore/, exxir/).
    A ConnectorAdapter instance is account-scoped — it carries enough
    configuration (via __init__) to identify one rex.connector_accounts
    row. The caller orchestrates sync_runs and writes source_links; the
    adapter only knows how to talk to one upstream account.
    """

    #: Stable connector kind key — must match rex.connectors.connector_key.
    connector_key: str = "unknown"

    def __init__(self, *, account_id: str, config: dict[str, Any] | None = None):
        self.account_id = account_id
        self.config = config or {}

    # ── lifecycle ────────────────────────────────────────────────────

    @abstractmethod
    async def health_check(self) -> ConnectorHealth:
        """Return a liveness snapshot for the current account."""

    # ── directory ────────────────────────────────────────────────────

    @abstractmethod
    async def list_projects(self, cursor: str | None = None) -> ConnectorPage:
        """Return projects visible to this account."""

    @abstractmethod
    async def list_users(self, cursor: str | None = None) -> ConnectorPage:
        """Return users visible to this account across all projects."""

    @abstractmethod
    async def fetch_project_directory(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return the team roster for one project."""

    # ── project management domain ────────────────────────────────────

    @abstractmethod
    async def fetch_rfis(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return RFIs for a project."""

    @abstractmethod
    async def fetch_submittals(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return submittals for a project."""

    @abstractmethod
    async def fetch_daily_logs(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return daily logs for a project."""

    # ── financial domain ─────────────────────────────────────────────

    @abstractmethod
    async def fetch_budget(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return budget line items for a project."""

    @abstractmethod
    async def fetch_commitments(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return commitments for a project."""

    @abstractmethod
    async def fetch_change_events(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return change events for a project."""

    # ── schedule + documents ─────────────────────────────────────────

    @abstractmethod
    async def fetch_schedule(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return schedule tasks / milestones for a project."""

    @abstractmethod
    async def fetch_documents(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        """Return document metadata for a project."""

    # ── optional capability discovery ────────────────────────────────

    def supports(self, capability: str) -> bool:
        """Return whether this adapter supports a named capability.

        Callers use this to gracefully skip methods that a given
        connector has not implemented yet. Default: all ConnectorAdapter
        methods are considered supported by the ABC contract. Concrete
        adapters may override to report false for unsupported fetch_*
        methods during early implementation.
        """
        return capability in {
            "list_projects", "list_users", "fetch_project_directory",
            "fetch_rfis", "fetch_submittals", "fetch_daily_logs",
            "fetch_budget", "fetch_commitments", "fetch_change_events",
            "fetch_schedule", "fetch_documents",
        }


__all__ = ["ConnectorAdapter", "ConnectorPage", "ConnectorHealth"]

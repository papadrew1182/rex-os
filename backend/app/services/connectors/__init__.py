"""Connector adapter package.

Session 2 (feat/canonical-connectors) lane.

Structure:
  base.py          -- ConnectorAdapter ABC that every adapter implements
  registry.py      -- Process-wide registry mapping connector_key -> adapter cls
  sync_service.py  -- Orchestration helpers for sync runs + source_links
  procore/         -- Procore adapter (first live connector)
  exxir/           -- Exxir adapter (first-class contract, not-yet-live)

Downstream rules:
  - Assistant / dashboards / automations MUST NOT import from
    backend.app.services.connectors.procore.* or exxir.* directly.
    They consume canonical rex.* and rex.v_* only.
  - The base ABC is the only stable import target for anything that
    needs to reason about "an adapter" generically (sync service,
    control-plane health checks, tests).
"""

from app.services.connectors.base import ConnectorAdapter, ConnectorPage, ConnectorHealth
from app.services.connectors.registry import (
    ConnectorRegistry,
    get_registry,
    register_adapter,
)

__all__ = [
    "ConnectorAdapter",
    "ConnectorPage",
    "ConnectorHealth",
    "ConnectorRegistry",
    "get_registry",
    "register_adapter",
]

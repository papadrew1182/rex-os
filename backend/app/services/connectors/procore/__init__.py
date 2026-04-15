"""Procore connector adapter subpackage.

Session 2 (feat/canonical-connectors) lane.

Imports the concrete adapter and registers it with the process-wide
ConnectorRegistry at import time. Downstream code that wants to use
the Procore adapter should NEVER import ProcoreAdapter directly —
it should resolve by key via get_registry().get('procore').
"""

from app.services.connectors.procore.adapter import ProcoreAdapter
from app.services.connectors.registry import register_adapter

register_adapter("procore", ProcoreAdapter)

__all__ = ["ProcoreAdapter"]

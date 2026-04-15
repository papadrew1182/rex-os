"""Exxir connector adapter subpackage.

Session 2 (feat/canonical-connectors) lane.

First-class adapter contract. Exxir is an owner/operator platform and
is NOT forced to mirror Procore field-for-field at the connector layer.
Its narrower staging set (budget, commitments, change_events,
documents, milestones) is reflected in the mapper and in the
connector_exxir schema.
"""

from app.services.connectors.exxir.adapter import ExxirAdapter
from app.services.connectors.registry import register_adapter

register_adapter("exxir", ExxirAdapter)

__all__ = ["ExxirAdapter"]

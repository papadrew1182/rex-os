"""Exxir -> canonical rex mapper.

Exxir is an owner/operator platform — its native shape is NOT
Procore-shaped. The mapper deliberately keeps field names
connector-agnostic at the output layer. Where Exxir and Procore differ
(e.g. cost allocation structure), the canonical rex side wins and the
mapper flattens the connector-native view.

Skeleton — every function is a pass-through until real Exxir payloads
are available. The shape of the return dict is stable so the sync
service can rely on it.
"""

from __future__ import annotations

from typing import Any


def map_project(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", raw.get("project_id", ""))),
        "name": raw.get("name"),
        "status": raw.get("status", "active"),
    }


def map_budget_line_item(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", "")),
        "project_id": project_canonical_id,
        "description": raw.get("description"),
        "original_budget": raw.get("original_amount"),
        "revised_budget": raw.get("current_amount"),
    }


def map_commitment(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", "")),
        "project_id": project_canonical_id,
        "title": raw.get("name") or raw.get("title"),
        "contract_type": raw.get("type", "subcontract"),
        "original_value": raw.get("amount"),
    }


def map_milestone(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", "")),
        "project_id": project_canonical_id,
        "milestone_name": raw.get("name"),
        "forecast_date": raw.get("forecast_date"),
        "scheduled_date": raw.get("scheduled_date"),
        "actual_date": raw.get("actual_date"),
    }


__all__ = ["map_project", "map_budget_line_item", "map_commitment", "map_milestone"]

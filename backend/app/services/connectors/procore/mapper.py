"""Procore -> canonical rex mapper.

Turns source-native dicts (whatever Procore returned) into rows suitable
for rex.* tables. Called by the sync service after the adapter has
landed a page into connector_procore.*_raw and before upserting into
rex.* + writing rex.source_links.

Currently a skeleton — each map_* function returns the source dict
unchanged with a stable shape the sync service can read. Concrete
field mapping lands in a later Session 2 commit when the Procore
client is wired for real.
"""

from __future__ import annotations

from typing import Any


def map_project(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", "")),
        "name": raw.get("name"),
        "project_number": raw.get("project_number"),
        "status": raw.get("active", True) and "active" or "inactive",
        "city": raw.get("city"),
        "state": raw.get("state_code"),
        "start_date": raw.get("start_date"),
        "end_date": raw.get("completion_date"),
    }


def map_rfi(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", "")),
        "project_id": project_canonical_id,
        "rfi_number": raw.get("number"),
        "subject": raw.get("subject"),
        "question": raw.get("question"),
        "status": raw.get("status"),
        "priority": raw.get("priority"),
        "due_date": raw.get("due_date"),
    }


def map_submittal(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", "")),
        "project_id": project_canonical_id,
        "submittal_number": raw.get("number"),
        "title": raw.get("title"),
        "status": raw.get("status"),
        "submittal_type": raw.get("submittal_type"),
    }


def map_commitment(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("id", "")),
        "project_id": project_canonical_id,
        "commitment_number": raw.get("number"),
        "title": raw.get("title"),
        "contract_type": raw.get("contract_type"),
        "status": raw.get("status"),
        "original_value": raw.get("grand_total"),
    }


__all__ = ["map_project", "map_rfi", "map_submittal", "map_commitment"]

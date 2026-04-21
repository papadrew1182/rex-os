"""Per-resource payload builders for the Rex App -> staging path.

Each build_<resource>_payload takes a flat row dict (asyncpg Record ->
dict) from the old rex-procore app's procore.<table> and returns the
JSON-serializable payload we'll store in connector_procore.<table>_raw.

Key names are chosen to match what the corresponding mapper.map_<resource>
reads via raw.get(...). Mapper and payload builder must evolve together.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def build_rfi_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id":                str(row["procore_id"]),
        "project_source_id": str(row.get("project_id")) if row.get("project_id") is not None else None,
        "project_name":      row.get("project_name"),
        "rfi_number":        row.get("number"),
        "subject":           row.get("subject"),
        "question":          row.get("question"),
        "answer":            row.get("answer"),
        "status":            row.get("status"),
        "ball_in_court":     row.get("ball_in_court"),
        "assignee":          row.get("assignee"),
        "rfi_manager":       row.get("rfi_manager"),
        "due_date":          _iso(row.get("due_date")),
        "closed_at":         _iso(row.get("closed_at")),
        "created_at":        _iso(row.get("created_at")),
        "updated_at":        _iso(row.get("updated_at")),
        "cost_impact":       row.get("cost_impact"),
        "schedule_impact":   row.get("schedule_impact"),
    }


def build_project_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Procore ``procore.projects`` row -> staging payload.

    Source schema (from schema_procore_all_tables.sql, verified against
    the live Rex App DB):
        procore_id (bigint PK), company_id (bigint),
        project_name, project_number, status,
        start_date (date), completion_date (date),
        address, city, state_code, zip_code,
        created_at (timestamptz), updated_at (timestamptz).

    Projects are a root resource — they ARE the scope other resources hang
    off of — so ``project_source_id`` is ``None``. Staging writer branches
    on this: ``connector_procore.projects_raw`` has no
    ``project_source_id`` column, and ``upsert_raw`` skips the bind when
    the raw table is in its ``_NON_PROJECT_TABLES`` set.

    The mapper (``mapper.map_project``) reads ``project_name``, ``status``,
    ``project_number``, ``city``, ``state_code``, ``start_date``,
    ``completion_date`` off this dict — keep those keys stable.
    """
    return {
        "id":                str(row["procore_id"]),
        "project_source_id": None,  # projects ARE the scope; no parent
        "project_name":      row.get("project_name"),
        "project_number":    row.get("project_number"),
        "status":            row.get("status"),
        "city":              row.get("city"),
        "state_code":        row.get("state_code"),
        "zip_code":          row.get("zip_code"),
        "start_date":        _iso(row.get("start_date")),
        "completion_date":   _iso(row.get("completion_date")),
        "address":           row.get("address"),
        "created_at":        _iso(row.get("created_at")),
        "updated_at":        _iso(row.get("updated_at")),
    }


__all__ = ["build_rfi_payload", "build_project_payload"]

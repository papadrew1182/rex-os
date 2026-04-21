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


def _stringify_jsonb(value: Any) -> str | None:
    """``procore.users.job_title`` is jsonb (multiselect). Coerce to a
    readable comma-joined string ('Foreman, Carpenter') or None.

    Handles:
      - None                -> None
      - empty str / empty   -> None (semantically "no title")
      - str                 -> passthrough
      - list                -> ", ".join(items); [] -> None
      - anything else       -> str(value) as a last resort so we never
                               crash the payload builder on an unexpected
                               jsonb shape.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else None
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


def build_user_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Procore ``procore.users`` row -> staging payload.

    Source schema (from schema_procore_all_tables.sql, 53 columns; this
    builder carries only the subset map_user / orchestrator consume,
    plus a couple of observability fields (is_employee, employee_id,
    last_login_at) we want available for future enrichment without
    re-running a full backfill).

    Users are a root / company-level resource — ``project_source_id`` is
    ``None``. ``staging.upsert_raw`` branches on the ``users_raw`` table
    name (``_NON_PROJECT_TABLES``) so the project_source_id column is
    not bound.

    Cursor: adapter.list_users uses ``procore_id`` (bigint) because the
    live source has ``updated_at`` NULL for most users — the same
    reason projects use procore_id.

    ``job_title`` is jsonb (multiselect) on the source; stringified here
    via ``_stringify_jsonb`` so the payload stays JSON-primitive. The
    mapper reads the already-stringified value.
    """
    return {
        "id":                str(row["procore_id"]),
        "project_source_id": None,  # users are company-level
        "first_name":        row.get("first_name"),
        "last_name":         row.get("last_name"),
        "full_name":         row.get("full_name"),
        "email":             row.get("email_address"),
        # mobile_phone wins over business_phone when both are present —
        # matches how the real Rex App renders the "primary" contact.
        "phone":             row.get("mobile_phone") or row.get("business_phone"),
        "job_title":         _stringify_jsonb(row.get("job_title")),
        "is_active":         row.get("is_active"),
        "is_employee":       row.get("is_employee"),
        "city":              row.get("city"),
        "state_code":        row.get("state_code"),
        "vendor_procore_id": row.get("vendor_id"),
        "employee_id":       row.get("employee_id"),
        "created_at":        _iso(row.get("created_at")),
        "updated_at":        _iso(row.get("updated_at")),
        "last_login_at":     _iso(row.get("last_login_at")),
    }


def build_vendor_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Procore ``procore.vendors`` row -> staging payload.

    Source schema (from schema_procore_all_tables.sql, 57 columns; this
    builder carries only the subset map_vendor / orchestrator consume
    plus insurance-expiration dates that back the Wave 1
    ``vendor_compliance`` action).

    Vendors are a root / company-level resource — ``project_source_id`` is
    ``None``. ``staging.upsert_raw`` branches on the ``vendors_raw`` table
    name (``_NON_PROJECT_TABLES``) so the project_source_id column is
    not bound.

    Cursor: adapter.list_vendors uses ``procore_id`` (bigint) for
    consistency with projects/users. ``procore.vendors.updated_at`` IS
    populated on the live source (last_upd 2026-03-13), so a timestamptz
    cursor would work here — but keeping the cursor type uniform across
    all three root resources simplifies the mental model and the
    client's ``cursor_col_type`` plumbing.

    ``vendor_name`` falls back to ``company_name`` because some Procore
    rows have a null vendor_name with a populated company_name. The
    mapper reads the already-resolved ``vendor_name`` key.

    ``phone`` prefers ``business_phone`` over ``mobile_phone`` — unlike
    users where the mobile is treated as the primary "reach a person"
    number, vendors are companies and the business line is the right
    front door for compliance outreach.
    """
    return {
        "id":                             str(row["procore_id"]),
        "project_source_id":              None,  # vendors are company-level
        "vendor_name":                    row.get("vendor_name") or row.get("company_name"),
        "trade_name":                     row.get("trade_name"),
        "email":                          row.get("email_address"),
        "phone":                          row.get("business_phone") or row.get("mobile_phone"),
        "website":                        row.get("website"),
        "address":                        row.get("address"),
        "city":                           row.get("city"),
        "state_code":                     row.get("state_code"),
        "zip_code":                       row.get("zip_code"),
        "is_active":                      row.get("is_active"),
        "license_number":                 row.get("license_number"),
        "insurance_expiration_date":      _iso(row.get("insurance_expiration_date")),
        "insurance_gl_expiration_date":   _iso(row.get("insurance_gl_expiration_date")),
        "insurance_wc_expiration_date":   _iso(row.get("insurance_wc_expiration_date")),
        "insurance_auto_expiration_date": _iso(row.get("insurance_auto_expiration_date")),
        "created_at":                     _iso(row.get("created_at")),
        "updated_at":                     _iso(row.get("updated_at")),
    }


__all__ = [
    "build_rfi_payload",
    "build_project_payload",
    "build_user_payload",
    "build_vendor_payload",
]

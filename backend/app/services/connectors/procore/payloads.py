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


def build_submittal_payload(
    project_external_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Procore API submittals row -> staging payload.

    Unlike ``build_rfi_payload`` (which reads a flat asyncpg row from the
    rex-procore Railway DB), this builder consumes a dict returned
    directly by Procore's REST API via ``ProcoreClient.list_submittals``.
    The project scope comes from the adapter's
    ``project_external_id`` argument rather than the row itself, because
    Procore's ``/rest/v1.0/projects/{id}/submittals`` endpoint already
    scopes by path — the response rows don't redundantly carry
    ``project_id``.

    Shape is deliberately parallel to ``build_rfi_payload``: ``id`` and
    ``project_source_id`` are top-level string keys (what staging's
    ``upsert_raw`` reads), ``updated_at`` is the ISO-stringified
    watermark, and every other payload key mirrors the Procore API field
    name. Keep the keys stable — ``mapper.map_submittal`` reads them via
    ``raw.get(...)``.

    Procore's submittal status vocabulary (``Open``, ``Closed``, etc.)
    and type vocabulary (``Shop Drawings``, ``Product Data``, etc.) stay
    as-is here; the mapper normalizes them to the rex.submittals CHECK
    constraint's enum.
    """
    return {
        "id":                str(raw["id"]),
        "project_source_id": str(project_external_id),
        "submittal_number":  raw.get("number"),
        "title":             raw.get("title"),
        "status":            raw.get("status"),
        "submittal_type":    raw.get("submittal_type") or raw.get("type"),
        "spec_section":      raw.get("spec_section"),
        "due_date":          _iso(raw.get("due_date")),
        "submitted_date":    _iso(raw.get("submit_by") or raw.get("submitted_date")),
        "approved_date":     _iso(raw.get("approved_date")),
        "assignee":          raw.get("assignee") or raw.get("ball_in_court"),
        "ball_in_court":     raw.get("ball_in_court"),
        "responsible_contractor": raw.get("responsible_contractor"),
        "created_at":        _iso(raw.get("created_at")),
        "updated_at":        _iso(raw.get("updated_at")),
    }


def build_daily_log_payload(
    project_external_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Procore API daily-log row -> staging payload.

    Consumes a dict returned directly by Procore's REST API via
    ``ProcoreClient.list_daily_logs`` (the
    ``/rest/v1.0/projects/{id}/daily_logs/construction_report_logs``
    endpoint). Mirrors ``build_submittal_payload`` — the project scope
    comes from the adapter's ``project_external_id`` argument rather
    than the row itself, because Procore's endpoint already scopes by
    path.

    Shape is deliberately parallel to ``build_submittal_payload``: ``id``
    and ``project_source_id`` are top-level string keys (what staging's
    ``upsert_raw`` reads), ``updated_at`` is the ISO-stringified
    watermark. Every other payload key mirrors the Procore API field
    name so ``mapper.map_daily_log`` can read them via ``raw.get(...)``
    without translation.

    Procore's construction-report daily-log shape carries:
      * ``date`` — the log_date (rex.daily_logs.log_date is NOT NULL)
      * ``is_published`` (bool) — published logs are 'submitted' in
        rex's 3-value enum; unpublished logs stay 'draft'.
      * Weather: nested ``weather_conditions`` field with subfields
        including ``temperature`` variations and free-text
        ``conditions``. We stash the whole weather sub-object alongside
        a pre-flattened summary so the mapper can either use the
        convenience strings or dig into the full structured object.
      * Notes: ``notes`` (free-text, the main log body). Procore does
        not natively split work/delay/safety/visitor notes, so we
        only populate ``work_summary`` and leave the rest None.

    Keys unknown-to-Procore-but-known-to-rex are intentionally NOT
    fabricated here — the mapper emits None for them.
    """
    return {
        "id":                str(raw["id"]),
        "project_source_id": str(project_external_id),
        "log_date":          _iso(raw.get("date") or raw.get("log_date")),
        "is_published":      raw.get("is_published"),
        "status":            raw.get("status"),
        "notes":             raw.get("notes"),
        "weather":           raw.get("weather_conditions") or raw.get("weather"),
        "weather_conditions": raw.get("weather_conditions"),
        "created_at":        _iso(raw.get("created_at")),
        "updated_at":        _iso(raw.get("updated_at")),
    }


def build_schedule_activity_payload(
    project_external_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Procore API schedule-task row -> staging payload.

    Consumes a dict returned directly by Procore's REST API via
    ``ProcoreClient.list_schedule_tasks`` (the
    ``/rest/v1.0/projects/{id}/schedule/standard_tasks`` endpoint).
    Mirrors ``build_daily_log_payload`` / ``build_submittal_payload`` —
    the project scope comes from the adapter's ``project_external_id``
    argument rather than the row itself, because Procore's endpoint
    already scopes by path.

    Shape is deliberately parallel to the other Wave 2 direct-Procore
    builders: ``id`` and ``project_source_id`` are top-level string keys
    (what staging's ``upsert_raw`` reads), ``updated_at`` is the
    ISO-stringified watermark. Every other payload key mirrors the
    Procore API field name so ``mapper.map_schedule_activity`` can read
    them via ``raw.get(...)`` without translation.

    Procore's standard_tasks endpoint carries at least:
      * ``id``         — the task id (canonical natural key here)
      * ``task_number`` — user-visible task number (mapped to
        rex.schedule_activities.activity_number)
      * ``name``        — task name (NOT NULL on the canonical side)
      * ``start_date`` / ``finish_date`` — both dates; finish_date maps
        to rex.schedule_activities.end_date
      * ``percent_complete`` — numeric 0-100
      * ``updated_at`` — watermark for cursor advancement

    Predecessors/successors and parent/child hierarchy are NOT carried
    here — the mapper emits None for the canonical parent_id and
    predecessor rows (a separate rex.activity_links relation table)
    are a follow-up resource.
    """
    return {
        "id":                str(raw["id"]),
        "project_source_id": str(project_external_id),
        "task_number":       raw.get("task_number"),
        "name":              raw.get("name"),
        "start_date":        _iso(raw.get("start_date")),
        "finish_date":       _iso(raw.get("finish_date") or raw.get("end_date")),
        "percent_complete":  raw.get("percent_complete"),
        "status":            raw.get("status"),
        "created_at":        _iso(raw.get("created_at")),
        "updated_at":        _iso(raw.get("updated_at")),
    }


def build_change_event_payload(
    project_external_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Procore API change-event row -> staging payload.

    Consumes a dict returned directly by Procore's REST API via
    ``ProcoreClient.list_change_events`` (the
    ``/rest/v1.0/projects/{id}/change_events`` endpoint). Mirrors
    ``build_daily_log_payload`` / ``build_schedule_activity_payload``:
    the project scope comes from the adapter's ``project_external_id``
    argument rather than the row itself, because Procore's endpoint
    already scopes by path.

    Shape is deliberately parallel to the other Wave 2 direct-Procore
    builders: ``id`` and ``project_source_id`` are top-level string keys
    (what staging's ``upsert_raw`` reads), ``updated_at`` is the
    ISO-stringified watermark. Every other payload key mirrors the
    Procore API field name so ``mapper.map_change_event`` can read them
    via ``raw.get(...)`` without translation.

    Procore's change_events endpoint carries at least:
      * ``id``                — change event id (canonical natural key
        flows through ``number`` below; this ``id`` is preserved for
        staging's (account_id, source_id) dedup key).
      * ``number``            — user-visible change event number
        (mapped to rex.change_events.event_number — the natural key
        with project_id for ON CONFLICT upserts).
      * ``title``             — NOT NULL on the canonical side.
      * ``description``       — free-text description.
      * ``status``            — Procore status string (Open, Pending,
        Approved, Closed, Void); the mapper normalizes to rex's CHECK
        enum.
      * ``change_reason``     — reason classifier (Owner Change, Design
        Change, Unforeseen, Allowance, Contingency); normalized to
        rex's CHECK enum.
      * ``event_type``        — type classifier (TBD, Allowance,
        Contingency, Owner Change, Transfer); normalized to rex's CHECK
        enum.
      * ``scope``             — scope classifier (In Scope, Out of
        Scope, TBD); normalized to rex's CHECK enum.
      * ``estimated_amount``  — numeric dollar estimate.
      * ``updated_at``        — watermark for cursor advancement.

    FKs (rfi_id, prime_contract_id, created_by) are NOT carried on the
    Procore change_events row in a form that resolves to canonical rex
    UUIDs; the mapper emits None for them. A follow-up enrichment pass
    can populate them by joining on other sync_service state.
    """
    return {
        "id":                str(raw["id"]),
        "project_source_id": str(project_external_id),
        "number":            raw.get("number"),
        "title":             raw.get("title"),
        "description":       raw.get("description"),
        "status":            raw.get("status"),
        "change_reason":     raw.get("change_reason"),
        "event_type":        raw.get("event_type"),
        "scope":             raw.get("scope"),
        "estimated_amount":  raw.get("estimated_amount"),
        "created_at":        _iso(raw.get("created_at")),
        "updated_at":        _iso(raw.get("updated_at")),
    }


__all__ = [
    "build_change_event_payload",
    "build_daily_log_payload",
    "build_rfi_payload",
    "build_project_payload",
    "build_schedule_activity_payload",
    "build_submittal_payload",
    "build_user_payload",
    "build_vendor_payload",
]

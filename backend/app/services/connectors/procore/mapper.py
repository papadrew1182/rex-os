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


def _coerce_rfi_number(value: Any) -> str | None:
    """Procore exposes RFI numbers as numeric-ish (often float like 5.0).
    The canonical rex.rfis.rfi_number column is text NOT NULL. Render a
    whole-number float like 5.0 as "5" (users read "RFI #5", never
    "RFI #5.0"); pass everything else through as str(). None stays None
    so the caller can surface the missing-required-field error rather
    than writing the literal string "None"."""
    if value is None:
        return None
    if isinstance(value, bool):  # bool is a subclass of int in Python
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _iso_date(value: Any) -> str | None:
    """Reduce an ISO timestamp string ('2026-05-01T00:00:00+00:00') to
    its date portion ('2026-05-01') so it lands cleanly in a date column.
    Already-date strings and None pass through unchanged."""
    if value is None:
        return None
    if isinstance(value, str) and "T" in value:
        return value.split("T", 1)[0]
    return value


def map_rfi(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    """Map a Procore RFI payload (as produced by payloads.build_rfi_payload)
    to a dict keyed by rex.rfis canonical columns.

    Canonical rex.rfis columns (from migrations/rex2_canonical_ddl.sql
    lines 823-846 + migration 002_field_parity_batch.sql):

        id              uuid PK                    -- db-generated; NOT emitted
        project_id      uuid NOT NULL              -- <- project_canonical_id
        rfi_number      text NOT NULL              -- <- coerced from payload float
        subject         text NOT NULL
        status          text NOT NULL              -- draft|open|answered|closed|void
        priority        text NOT NULL default 'medium' -- OMITTED from output on purpose
        question        text NOT NULL
        answer          text
        cost_impact     text                       -- yes|no|tbd
        schedule_impact text                       -- yes|no|tbd
        cost_code_id    uuid                       -- resolve later; None
        assigned_to     uuid                       -- resolve name->person_id later; None
        ball_in_court   uuid                       -- resolve name->person_id later; None
        created_by      uuid                       -- not in payload; None
        due_date        date
        answered_date   date                       -- derived from closed_at
        days_open       int                        -- computed later; None
        drawing_id      uuid                       -- not in payload; None
        spec_section    text                       -- not in payload; None
        location        text                       -- not in payload; None
        rfi_manager     uuid (migration 002)       -- resolve name->person_id later; None
        created_at      timestamptz default now()  -- db-managed; NOT emitted
        updated_at      timestamptz default now()  -- db-managed; NOT emitted

    Contract:

    * Output contains ONLY canonical rex.rfis column keys -- safe to
      splat into a generic INSERT without "column does not exist".
    * `priority` is OMITTED on purpose. The column is NOT NULL
      DEFAULT 'medium', but defaults don't fire when the column is
      included in the INSERT with a NULL value. Omitting the key
      lets the DB default apply cleanly.
    * `source_id` is NOT emitted here -- Task 7 reads `item["id"]`
      directly from the raw payload for the source_links writer.
    * Name->person-UUID resolution (assignee, ball_in_court,
      rfi_manager) is left as None here. The enrichment pass reads
      names from the raw payload, not from this mapper's output, so
      no source_names_* sidecar keys are emitted.
    * `id`, `created_at`, `updated_at` are DB-managed and are not in
      the output.
    """
    return {
        # Identity / links
        "project_id":      project_canonical_id,

        # Direct canonical fields
        "rfi_number":      _coerce_rfi_number(raw.get("rfi_number")),
        "subject":         raw.get("subject"),
        "status":          raw.get("status"),
        "question":        raw.get("question"),
        "answer":          raw.get("answer"),
        "cost_impact":     raw.get("cost_impact"),
        "schedule_impact": raw.get("schedule_impact"),

        # People FKs -- resolve name->uuid in a later pass (Task 7+)
        "assigned_to":     None,
        "ball_in_court":   None,
        "rfi_manager":     None,
        "created_by":      None,

        # Dates
        "due_date":        _iso_date(raw.get("due_date")),
        "answered_date":   _iso_date(raw.get("closed_at")),

        # Computed / not-in-payload canonical columns
        "cost_code_id":    None,
        "days_open":       None,
        "drawing_id":      None,
        "spec_section":    None,
        "location":        None,
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

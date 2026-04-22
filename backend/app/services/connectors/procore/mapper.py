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

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def map_project(raw: dict[str, Any]) -> dict[str, Any]:
    """Procore payload (from ``payloads.build_project_payload``) ->
    canonical ``rex.projects`` row dict.

    Canonical rex.projects columns (from migrations/rex2_canonical_ddl.sql
    line 16-33):
        id              uuid PK (db-generated; not emitted)
        name            text NOT NULL
        project_number  text  (UNIQUE — see migration 025)
        status          text NOT NULL CHECK in
                        (active | inactive | archived |
                         pre_construction | completed)
        project_type    text CHECK (...)          (not in payload; omitted)
        address_line1   text                      (omitted: payload's
                        ``address`` field is a single freeform blob today;
                        splitting into line1/line2 is a later concern)
        city            text
        state           text                      (<- payload.state_code)
        zip             text                      (omitted for now:
                        payload has zip_code but we're keeping the
                        initial mapper conservative; enable in a later
                        commit with targeted migration coverage)
        start_date      date
        end_date        date                      (<- payload.completion_date)
        contract_value  numeric                   (not in Procore payload)
        square_footage  numeric                   (not in Procore payload)
        description     text                      (not in Procore payload)
        created_at      timestamptz default now() (db-managed)
        updated_at      timestamptz default now() (db-managed)

    Contract:
    * Root resource — takes ONE argument (no ``project_canonical_id``
      because projects ARE the canonical scope).
    * Output contains ONLY canonical rex.projects column keys so
      orchestrator._write_projects can splat them into INSERT ... ON
      CONFLICT directly.
    * ``project_number`` is the natural key — upsert is keyed on it
      (migration 025 adds the UNIQUE constraint). Required on live
      Procore rows in practice, but the payload may carry None;
      treat that as "row has no natural key" and let the DB fail
      the INSERT loud rather than silently swallow.
    * Procore statuses today are capitalized: 'Active' / 'Inactive' /
      'Archived'. Lowercase + default missing/unknown to 'active' so
      the CHECK constraint passes. Intentionally NOT a hard raise —
      the live source has one-off free-text statuses we don't want
      to block a full sync on.
    """
    status_raw = (raw.get("status") or "").lower()
    canonical_status = {
        "active":           "active",
        "inactive":         "inactive",
        "archived":         "archived",
        "pre_construction": "pre_construction",
        "completed":        "completed",
        "":                 "active",
    }.get(status_raw, "active")

    return {
        "name":           raw.get("project_name") or "Untitled Project",
        "project_number": raw.get("project_number"),
        "status":         canonical_status,
        "city":           raw.get("city"),
        # canonical rex.projects column is ``state`` (not ``state_code``)
        "state":          raw.get("state_code"),
        "start_date":     _iso_date(raw.get("start_date")),
        "end_date":       _iso_date(raw.get("completion_date")),
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
    if isinstance(value, Decimal):
        # procore.rfis.number is numeric(10,2); asyncpg returns Decimal.
        # Decimal('1.00') -> "1" (not "1.00"); Decimal('1.25') -> "1.25".
        if value == value.to_integral_value():
            return str(int(value))
        return format(value.normalize(), "f")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _iso_date(value: Any) -> date | None:
    """Coerce an ISO timestamp string, date-only string, datetime, or date
    into a Python `date` object so asyncpg can bind it to a rex.* `date`
    column without a text->date cast.

    Inputs we expect from payloads.build_rfi_payload:
      - None
      - ISO timestamp string with 'T' separator: "2026-05-01T00:00:00+00:00"
      - already-date string:                     "2026-05-01"

    Accepting datetime/date objects is defensive — if a future payload
    builder ever skips the ISO stringify, we still produce the right type.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # Pair with payloads._iso which emits `.isoformat()`. Split off the
        # time portion if present; the remainder is always YYYY-MM-DD.
        date_part = value.split("T", 1)[0]
        return date.fromisoformat(date_part)
    # Anything else we return unchanged and let asyncpg surface the type
    # error at bind time — preferable to a silent None here.
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


_SUBMITTAL_STATUS_MAP: dict[str, str] = {
    # Canonical-enum pass-through
    "draft":             "draft",
    "pending":           "pending",
    "submitted":         "submitted",
    "approved":          "approved",
    "approved_as_noted": "approved_as_noted",
    "rejected":          "rejected",
    "closed":            "closed",
    # Procore-native variants seen in the wild — normalize to canonical.
    # Procore's common submittal states: "Open", "Closed",
    # "Approved", "Approved as Noted", "Rejected", "Revise and Resubmit",
    # "For Record Only", "Pending", "Submitted". Map each to the closest
    # canonical value; anything unrecognized falls back to 'draft' via
    # the map.get(..., 'draft') guard below.
    "open":                 "pending",
    "approved as noted":    "approved_as_noted",
    "revise and resubmit":  "rejected",
    "for record only":      "closed",
    "in review":            "submitted",
    "for information only": "closed",
}


_SUBMITTAL_TYPE_MAP: dict[str, str] = {
    # Canonical-enum pass-through
    "shop_drawing": "shop_drawing",
    "product_data": "product_data",
    "sample":       "sample",
    "mock_up":      "mock_up",
    "test_report":  "test_report",
    "other":        "other",
    # Procore-native label variants (title-cased / spaced in the API)
    # normalized here. Anything unrecognized falls back to 'other' via
    # the map.get(..., 'other') guard below so the CHECK constraint
    # passes rather than blocking the whole sync on one oddball type.
    "shop drawings":           "shop_drawing",
    "shop drawing":            "shop_drawing",
    "product data":            "product_data",
    "samples":                 "sample",
    "mock up":                 "mock_up",
    "mock-up":                 "mock_up",
    "mockup":                  "mock_up",
    "test reports":            "test_report",
    "quality submittal":       "test_report",
    "informational submittal": "other",
    "informational":           "other",
}


def map_submittal(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    """Map a Procore submittal payload (as produced by
    ``payloads.build_submittal_payload``) to a dict keyed by rex.submittals
    canonical columns.

    Canonical rex.submittals columns (from migrations/rex2_canonical_ddl.sql
    lines 869-896):

        id                      uuid PK                    -- db-generated; NOT emitted
        project_id              uuid NOT NULL              -- <- project_canonical_id
        submittal_package_id    uuid                       -- not in payload; None
        submittal_number        text NOT NULL
        title                   text NOT NULL
        status                  text NOT NULL              -- 7-value enum; see _SUBMITTAL_STATUS_MAP
        submittal_type          text NOT NULL              -- 6-value enum; see _SUBMITTAL_TYPE_MAP
        spec_section            text
        current_revision        int NOT NULL DEFAULT 0     -- OMITTED (let DB default fire)
        cost_code_id            uuid                       -- resolve later; None
        schedule_activity_id    uuid                       -- resolve later; None
        assigned_to             uuid                       -- resolve name->person_id later; None
        ball_in_court           uuid                       -- resolve name->person_id later; None
        responsible_contractor  uuid                       -- resolve name->company_id later; None
        created_by              uuid                       -- not in payload; None
        due_date                date
        submitted_date          date
        approved_date           date
        lead_time_days          int                        -- not in payload; None
        required_on_site        date                       -- not in payload; None
        location                text                       -- not in payload; None
        created_at / updated_at                             -- DB-managed; NOT emitted

    Contract:

    * Output contains ONLY canonical rex.submittals column keys -- safe
      to splat into a generic INSERT without "column does not exist".
    * ``current_revision`` is OMITTED on purpose. The column is NOT NULL
      DEFAULT 0, but defaults don't fire when the column is included in
      the INSERT with a NULL value. Omitting the key lets the DB default
      apply cleanly.
    * ``source_id`` is NOT emitted here -- orchestrator reads ``item["id"]``
      directly from the raw payload for the source_links writer (same
      convention as map_rfi).
    * Name->person-UUID / name->company-UUID resolution for
      ``assigned_to``, ``ball_in_court``, ``responsible_contractor`` is
      left as None here. The enrichment pass reads names from the raw
      payload, not from this mapper's output.
    * ``title`` and ``submittal_number`` are NOT NULL on the canonical
      table; if the payload is missing either, the INSERT will fail
      loud rather than silently invent a natural key.
    """
    status_raw = (raw.get("status") or "").strip().lower()
    status = _SUBMITTAL_STATUS_MAP.get(status_raw, "draft")

    type_raw = (raw.get("submittal_type") or "").strip().lower()
    submittal_type = _SUBMITTAL_TYPE_MAP.get(type_raw, "other")

    return {
        # Identity / links
        "project_id":            project_canonical_id,

        # Direct canonical fields
        "submittal_number":      raw.get("submittal_number") or raw.get("number"),
        "title":                 raw.get("title"),
        "status":                status,
        "submittal_type":        submittal_type,
        "spec_section":          raw.get("spec_section"),

        # People / company FKs -- resolve name->uuid in a later pass
        "assigned_to":           None,
        "ball_in_court":         None,
        "responsible_contractor": None,
        "created_by":            None,

        # Dates
        "due_date":              _iso_date(raw.get("due_date")),
        "submitted_date":        _iso_date(raw.get("submitted_date")),
        "approved_date":         _iso_date(raw.get("approved_date")),

        # Canonical columns with no payload counterpart today
        "submittal_package_id":  None,
        "cost_code_id":          None,
        "schedule_activity_id":  None,
        "lead_time_days":        None,
        "required_on_site":      None,
        "location":              None,
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


def map_user(raw: dict[str, Any]) -> dict[str, Any]:
    """Procore user payload (from ``payloads.build_user_payload``) ->
    canonical ``rex.people`` row dict.

    Canonical rex.people columns we target (from
    migrations/rex2_canonical_ddl.sql lines 57-71):
        id              uuid PK (db-generated; not emitted)
        company_id      uuid FK   (resolve vendor->company later; None)
        first_name      text NOT NULL
        last_name       text NOT NULL
        email           text       (UPSERT natural key — migration 026
                                    adds UNIQUE (email) to back the
                                    orchestrator's ON CONFLICT)
        phone           text
        title           text       (<- payload.job_title)
        role_type       text NOT NULL CHECK in ('internal','external')
        is_active       boolean NOT NULL DEFAULT true  (OMITTED by mapper
                                    so DB default fires and an admin's
                                    manual deactivation is not overwritten
                                    on every sync)
        notes           text                         (not in payload)
        created_at/updated_at — DB-managed

    Role-type policy: default ``'external'``. Procore can't reliably
    distinguish Rex employees from subs / vendors with just the is_employee
    flag (the flag reflects the *Procore account* owner, not "Rex
    employee"), so we stamp everyone 'external' and an admin re-classifies
    true Rex internals in a follow-up UI pass.

    NOT NULL handling:
    * ``first_name`` / ``last_name`` — NOT NULL in the canonical table.
      If both are missing but ``full_name`` is present, split on the
      first space. Otherwise fall back to '(unknown)' so the INSERT
      still succeeds; a garbage name is preferable to a crashed sync.
    * ``email`` — NOT NULL in the task contract (UNIQUE via migration
      026 lets us upsert on it). If a source row has NULL email, we
      synthesize a deterministic ``procore-user-<id>@placeholder.invalid``
      placeholder. Deterministic means the next sync targets the same
      placeholder and the upsert converges on one row rather than
      spawning N duplicates across re-syncs.
    """
    first = raw.get("first_name") or ""
    last = raw.get("last_name") or ""
    full = raw.get("full_name") or f"{first} {last}".strip()

    # When first/last are both missing but full_name is present, try to
    # split on the first space. Single-token names ('Madonna') get
    # last_name='(unknown)' via the fallback below.
    if not first and not last and full:
        parts = full.split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""

    if not first:
        first = "(unknown)"
    if not last:
        last = "(unknown)"

    email = raw.get("email")
    if not email:
        # Deterministic synthetic placeholder — same source id always
        # yields the same email so the ON CONFLICT (email) upsert is
        # idempotent across re-syncs.
        email = f"procore-user-{raw.get('id')}@placeholder.invalid"

    return {
        "first_name": first,
        "last_name":  last,
        "email":      email,
        "phone":      raw.get("phone"),
        # rex.people.title <- payload.job_title
        "title":      raw.get("job_title"),
        "role_type":  "external",
    }


def map_vendor(raw: dict[str, Any]) -> dict[str, Any]:
    """Procore vendor payload (from ``payloads.build_vendor_payload``) ->
    canonical ``rex.companies`` row dict.

    Canonical rex.companies columns (from
    migrations/rex2_canonical_ddl.sql lines 36-55 + migration 005):
        id                  uuid PK (db-generated; not emitted)
        name                text NOT NULL (UNIQUE — migration 027)
        trade               text
        company_type        text NOT NULL CHECK IN (subcontractor|
                            supplier|architect|engineer|owner|gc|
                            consultant)
        status              text NOT NULL DEFAULT 'active'  (OMITTED
                            by mapper so DB default fires; don't
                            overwrite admin deactivation on every sync)
        phone               text
        email               text
        address_line1       text           (<- payload.address — the
                            Procore freeform address goes wholesale into
                            line1; splitting into line1/line2 is future
                            scope)
        city                text
        state               text           (<- payload.state_code)
        zip                 text           (<- payload.zip_code)
        license_number      text
        insurance_expiry    date           (<- GL expiry preferred,
                            generic expiration_date as fallback — see
                            note below)
        insurance_carrier   text           (not in Procore payload; None)
        bonding_capacity    numeric        (not in Procore payload)
        notes               text           (not in Procore payload)
        website             text           (added in migration 005)
        mobile_phone        text           (added in migration 005; not
                            emitted — procore row's mobile_phone is
                            already merged into ``phone`` via the
                            business_phone OR mobile_phone fallback in
                            build_vendor_payload)
        created_at/updated_at — DB-managed

    Contract:
    * Root resource — takes ONE argument (no parent scope).
    * Output contains ONLY canonical rex.companies column keys so
      orchestrator._write_vendors can splat them into INSERT ... ON
      CONFLICT directly.
    * ``name`` is the natural key — upsert keyed on it (migration 027
      adds UNIQUE). NOT NULL on the canonical table; fall back to
      '(unnamed vendor)' so an INSERT still succeeds on a Procore
      row with null vendor_name AND null company_name (rare but has
      been observed).
    * ``company_type`` defaults to ``'subcontractor'``. Procore's
      source doesn't expose a reliable classifier, and the dominant
      vendor relationship in Rex's book of business is subcontractors.
      Admin re-classifies architect / owner / GC post-sync.
    * ``insurance_expiry`` policy: prefer ``insurance_gl_expiration_date``
      (general liability — most frequently referenced on the Wave 1
      ``vendor_compliance`` action), falling back to the generic
      ``insurance_expiration_date`` when GL is null. This way a vendor
      with only one expiration on file still lands a compliance-ready
      date. Emits a Python ``date`` (not an ISO string) so asyncpg binds
      it natively to the ``date`` column.
    """
    insurance_expiry = (
        _iso_date(raw.get("insurance_gl_expiration_date"))
        or _iso_date(raw.get("insurance_expiration_date"))
    )
    return {
        "name":              raw.get("vendor_name") or "(unnamed vendor)",
        "company_type":      "subcontractor",
        "trade":             raw.get("trade_name"),
        "phone":             raw.get("phone"),
        "email":             raw.get("email"),
        # canonical rex.companies column is ``address_line1`` (not
        # ``address``); Procore's freeform address goes wholesale into
        # line1 for now.
        "address_line1":     raw.get("address"),
        "city":              raw.get("city"),
        # canonical column is ``state`` (not ``state_code``)
        "state":             raw.get("state_code"),
        # canonical column is ``zip`` (not ``zip_code``)
        "zip":               raw.get("zip_code"),
        "website":           raw.get("website"),
        "license_number":    raw.get("license_number"),
        "insurance_expiry":  insurance_expiry,
        # procore.vendors doesn't carry a carrier name — admins fill
        # this in manually post-sync.
        "insurance_carrier": None,
    }


__all__ = [
    "map_project",
    "map_rfi",
    "map_submittal",
    "map_commitment",
    "map_user",
    "map_vendor",
]

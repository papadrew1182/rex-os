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


_DAILY_LOG_STATUS_MAP: dict[str, str] = {
    # Canonical-enum pass-through (rex.daily_logs.status CHECK IN
    # ('draft','submitted','approved')).
    "draft":     "draft",
    "submitted": "submitted",
    "approved":  "approved",
    # Procore-native variants (the construction_report_logs endpoint
    # doesn't carry a free-text status — the is_published bool is the
    # main signal — but accept these for defensive compatibility with
    # sibling endpoints that do).
    "published":   "submitted",
    "unpublished": "draft",
}


def _coerce_temp(value: Any) -> int | None:
    """Coerce a Procore temperature value (int / float / numeric string)
    to a plain int. Returns None for None or anything unparseable.

    rex.daily_logs.temp_high_f and temp_low_f are typed ``int`` (not
    numeric). Procore's construction_report_logs endpoint sometimes
    returns integers, sometimes floats; a string is defensive.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int; reject outright rather than
        # silently coerce True/False to 1/0.
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    return None


def map_daily_log(
    raw: dict[str, Any], project_canonical_id: str
) -> dict[str, Any]:
    """Map a Procore daily-log payload (as produced by
    ``payloads.build_daily_log_payload``) to a dict keyed by
    rex.daily_logs canonical columns.

    Canonical rex.daily_logs columns (from migrations/rex2_canonical_ddl.sql
    lines 267-286):

        id               uuid PK                   -- db-generated; NOT emitted
        project_id       uuid NOT NULL             -- <- project_canonical_id
        log_date         date NOT NULL             -- <- payload["log_date"] / "date"
        status           text NOT NULL DEFAULT 'draft'
                         CHECK IN ('draft','submitted','approved')
        weather_summary  text                      -- flattened from weather.conditions
        temp_high_f      int
        temp_low_f       int
        is_weather_delay boolean NOT NULL DEFAULT false  -- OMITTED (let DB default fire)
        work_summary     text                      -- <- payload["notes"]
        delay_notes      text                      -- None (Procore doesn't split)
        safety_notes     text                      -- None
        visitor_notes    text                      -- None
        created_by       uuid                      -- resolve later; None
        approved_by      uuid                      -- resolve later; None
        approved_at      timestamptz               -- None (not in payload)
        created_at/updated_at — DB-managed

    Contract:

    * Output contains ONLY canonical rex.daily_logs column keys — safe
      to splat into a generic INSERT without "column does not exist".
    * ``is_weather_delay`` is OMITTED on purpose. The column is NOT NULL
      DEFAULT false, but defaults don't fire when the column is included
      in the INSERT with a NULL value. Omitting the key lets the DB
      default apply cleanly when Procore's response doesn't carry a
      delay signal.
    * ``source_id`` is NOT emitted — orchestrator reads ``item["id"]``
      directly from the raw payload for the source_links writer (same
      convention as map_submittal / map_rfi).
    * Name->person-UUID resolution for created_by / approved_by is left
      as None here. The enrichment pass reads names from the raw
      payload, not from this mapper's output.
    * ``log_date`` is NOT NULL on the canonical table; if the payload
      is missing it, the INSERT will fail loud rather than silently
      invent a date.

    Status policy: Procore's construction_report_logs endpoint does not
    carry a text status — the ``is_published`` bool is the main signal.
    Published logs map to 'submitted'; unpublished (or missing) log to
    'draft'. If the payload already carries a rex-canonical status (a
    future payload-builder revision could pre-normalize), pass it
    through.

    Weather shape: Procore's weather is a nested structured object with
    subfields ``conditions`` (free text like "Partly cloudy") and
    ``temperature_high`` / ``temperature_low`` (numeric). The mapper
    flattens ``conditions`` into ``weather_summary`` and coerces the
    highs/lows to int. Falls back to None on all three when the weather
    object is missing or shaped differently.
    """
    # Status: prefer an already-canonical payload value; else derive
    # from is_published; else default to 'draft'.
    status_raw = (raw.get("status") or "").strip().lower() if raw.get("status") else ""
    if status_raw and status_raw in _DAILY_LOG_STATUS_MAP:
        status = _DAILY_LOG_STATUS_MAP[status_raw]
    else:
        is_published = raw.get("is_published")
        status = "submitted" if is_published is True else "draft"

    # Weather: accept either the aliased ``weather`` key or the
    # Procore-native ``weather_conditions`` subobject.
    weather = raw.get("weather") or raw.get("weather_conditions") or {}
    if not isinstance(weather, dict):
        weather = {}
    weather_summary = weather.get("conditions") or weather.get("summary")
    temp_high = _coerce_temp(
        weather.get("temperature_high") or weather.get("temp_high_f")
    )
    temp_low = _coerce_temp(
        weather.get("temperature_low") or weather.get("temp_low_f")
    )

    return {
        # Identity / links
        "project_id":       project_canonical_id,

        # Direct canonical fields
        "log_date":         _iso_date(raw.get("log_date") or raw.get("date")),
        "status":           status,

        # Weather
        "weather_summary":  weather_summary,
        "temp_high_f":      temp_high,
        "temp_low_f":       temp_low,

        # Notes — Procore carries a single free-text "notes" field
        # that becomes the main work narrative; rex's delay/safety/
        # visitor columns have no Procore counterpart on this
        # endpoint.
        "work_summary":     raw.get("notes"),
        "delay_notes":      None,
        "safety_notes":     None,
        "visitor_notes":    None,

        # People FKs — resolve name->uuid in a later pass
        "created_by":       None,
        "approved_by":      None,
        "approved_at":      None,
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


def map_schedule_activity(
    raw: dict[str, Any], project_canonical_id: str
) -> dict[str, Any]:
    """Map a Procore schedule-task payload (as produced by
    ``payloads.build_schedule_activity_payload``) to a dict keyed by
    rex.schedule_activities canonical columns PLUS two sidecars the
    writer consumes before the canonical INSERT.

    Canonical rex.schedule_activities columns (from
    migrations/rex2_canonical_ddl.sql lines 191-216):

        id                     uuid PK                 -- db-generated; NOT emitted
        schedule_id            uuid NOT NULL           -- resolved by the writer
                                                          from (schedule_name,
                                                          project_id) sidecars;
                                                          NOT emitted here
        parent_id              uuid                    -- hierarchy; None
        activity_number        text                    -- natural key (with
                                                          schedule_id) for the
                                                          writer's upsert
        name                   text NOT NULL
        activity_type          text NOT NULL CHECK IN  -- defaulted to 'task'
                                (task|milestone|section|hammock)
        start_date             date NOT NULL
        end_date               date NOT NULL           -- <- payload.finish_date
        duration_days          int                     -- not in payload; omitted
        percent_complete       numeric NOT NULL DEFAULT 0
                                                       -- 0-100; defaults fire
                                                          only when key is
                                                          omitted, so the
                                                          mapper emits 0
                                                          explicitly when
                                                          Procore returns None
        is_critical            bool NOT NULL DEFAULT false
                                                       -- OMITTED (let DB default)
        is_manually_scheduled  bool NOT NULL DEFAULT false
                                                       -- OMITTED (let DB default)
        baseline_start         date                    -- not in payload; omitted
        baseline_end           date                    -- not in payload; omitted
        variance_days          int                     -- not in payload; omitted
        float_days             int                     -- not in payload; omitted
        assigned_company_id    uuid                    -- resolve later; None
        assigned_person_id     uuid                    -- resolve later; None
        cost_code_id           uuid                    -- resolve later; None
        location               text                    -- not in payload; omitted
        notes                  text                    -- not in payload; omitted
        sort_order             int NOT NULL DEFAULT 0  -- OMITTED (let DB default)
        created_at / updated_at                        -- DB-managed; NOT emitted

    Sidecars (NOT rex.schedule_activities columns — stripped by the
    writer before the INSERT):
        schedule_name          text — name of the rex.schedules row
                                this activity attaches to. The writer
                                upserts a rex.schedules row keyed on
                                (project_id, name) and resolves
                                schedule_id from it.
        project_id             uuid — the canonical rex.projects.id this
                                activity's schedule belongs under.

    Contract:
    * Output contains canonical rex.schedule_activities columns AND the
      two sidecars the writer consumes to bootstrap the schedule FK.
      The writer pops both sidecars before splatting the remaining keys
      into the INSERT.
    * ``source_id`` is NOT emitted — orchestrator reads ``item["id"]``
      directly from the raw payload for the source_links writer (same
      convention as map_daily_log / map_submittal / map_rfi).
    * ``schedule_id`` is NOT emitted — the writer resolves it from the
      (schedule_name, project_id) pair via an INSERT ... ON CONFLICT
      upsert against rex.schedules in the same transaction.
    * Name->UUID resolution for assigned_company_id / assigned_person_id
      is left as None. The enrichment pass reads names from the raw
      payload, not from this mapper's output.
    * ``activity_number`` falls back to the stringified Procore id when
      Procore's ``task_number`` is missing — the (schedule_id,
      activity_number) upsert key must never be NULL or the UNIQUE
      index treats rows as distinct (NULL != NULL in SQL).
    * ``activity_type`` defaults to 'task' — Procore's standard_tasks
      endpoint returns generic tasks without a milestone classifier.
      Admin re-classifies milestones post-sync.

    Schedule bootstrap: the canonical rex.schedule_activities row needs
    a valid ``schedule_id`` FK. Procore's concept of "schedule tasks"
    doesn't cleanly map to rex.schedules as a first-class entity —
    rex.schedules is a rex-specific abstraction. The writer handles the
    bootstrap: first INSERT-ON-CONFLICT a rex.schedules row keyed on
    (project_id, name) == (project_canonical_id, "Procore default
    schedule"), then insert the activity with the resolved schedule_id.
    This way the mapper stays logical (what data does Procore carry)
    and the writer owns the FK bookkeeping.
    """
    # activity_number: prefer task_number; fall back to str(id) so the
    # (schedule_id, activity_number) upsert key is never NULL.
    task_number = raw.get("task_number")
    if not task_number:
        task_number = str(raw.get("id", ""))

    # percent_complete: emit 0 explicitly when Procore returns None —
    # the DB default only fires when the column is omitted from the
    # INSERT, but we DO include percent_complete in the splat, so we
    # need a concrete value.
    pct = raw.get("percent_complete")
    if pct is None:
        pct = 0

    return {
        # Sidecars the writer consumes before the INSERT (stripped).
        "schedule_name":       "Procore default schedule",
        "project_id":          project_canonical_id,

        # Direct canonical fields
        "activity_number":     task_number,
        "name":                raw.get("name"),
        "activity_type":       "task",
        "start_date":          _iso_date(raw.get("start_date")),
        "end_date":             _iso_date(raw.get("finish_date") or raw.get("end_date")),
        "percent_complete":    pct,

        # FKs pending enrichment
        "parent_id":            None,
        "assigned_company_id":  None,
        "assigned_person_id":   None,
        "cost_code_id":         None,
    }


def map_change_event(
    raw: dict[str, Any], project_canonical_id: str
) -> dict[str, Any]:
    """Map a Procore change-event payload (as produced by
    ``payloads.build_change_event_payload``) to a dict keyed by
    rex.change_events canonical columns.

    Canonical rex.change_events columns (from
    migrations/rex2_canonical_ddl.sql lines 619-637):

        id                  uuid PK                  -- db-generated; NOT emitted
        project_id          uuid NOT NULL
        event_number        text NOT NULL
        title               text NOT NULL
        description         text
        status              text NOT NULL DEFAULT 'open' CHECK IN
                            (open|pending|approved|closed|void)
        change_reason       text NOT NULL CHECK IN
                            (owner_change|design_change|unforeseen|
                             allowance|contingency)
        event_type          text NOT NULL CHECK IN
                            (tbd|allowance|contingency|owner_change|
                             transfer)
        scope               text NOT NULL DEFAULT 'tbd' CHECK IN
                            (in_scope|out_of_scope|tbd)
        estimated_amount    numeric NOT NULL DEFAULT 0
        rfi_id              uuid                     -- deferred FK; None
        prime_contract_id   uuid                     -- FK; None (no resolver)
        created_by          uuid                     -- FK; None (no resolver)
        created_at / updated_at                      -- DB-managed; NOT emitted

    Contract:
    * Output contains ONLY canonical rex.change_events column keys so
      orchestrator._write_change_events can splat them into INSERT ...
      ON CONFLICT directly.
    * ``source_id`` is NOT emitted — orchestrator reads ``item["id"]``
      directly from the raw payload for the source_links writer (same
      convention as map_daily_log / map_submittal / map_schedule_activity).
    * ``event_number`` is the natural key (with project_id) for the ON
      CONFLICT upsert. The canonical DDL does not declare this UNIQUE —
      migration 033 adds the UNIQUE (project_id, event_number) index the
      writer relies on.
    * All three CHECK-constrained classifiers (``change_reason``,
      ``event_type``, ``scope``) normalize Procore's title-cased strings
      ("Owner Change", "In Scope") to the lowercase-underscore enum the
      CHECK allows. Unknown values fall back to sensible defaults
      (``owner_change`` / ``tbd`` / ``tbd``) rather than crashing the
      sync.
    * ``status`` default on the DB is ``'open'`` but the mapper still
      emits a concrete value — the default only fires when the column is
      omitted from the INSERT, and we always include it.
    * ``estimated_amount`` is forced to a float(0) fallback when Procore
      returns None; NOT NULL DEFAULT 0 on the DB only fires on omission.

    LLM-tool overlap: Phase 6b Wave 2 shipped a ``create_change_event``
    LLM tool that inserts into ``rex.change_events`` directly. Both
    paths converge on the same ``(project_id, event_number)`` natural
    key via the writer's ON CONFLICT DO UPDATE — the Procore sync is
    idempotent against existing LLM-created rows and vice versa.
    """
    # Status normalization: Procore returns title-cased strings; rex
    # CHECK enum is lowercase. Default missing/unknown to 'open'.
    status_raw = (raw.get("status") or "").strip().lower().replace(" ", "_")
    canonical_status = {
        "open":     "open",
        "pending":  "pending",
        "approved": "approved",
        "closed":   "closed",
        "void":     "void",
        "":         "open",
    }.get(status_raw, "open")

    # change_reason normalization: Procore returns "Owner Change",
    # "Design Change", "Unforeseen", etc. Lowercase + underscore.
    # Default missing/unknown to 'owner_change' (most-common case in
    # the target book of business).
    reason_raw = (raw.get("change_reason") or "").strip().lower().replace(" ", "_")
    canonical_reason = {
        "owner_change":  "owner_change",
        "design_change": "design_change",
        "unforeseen":    "unforeseen",
        "allowance":     "allowance",
        "contingency":   "contingency",
    }.get(reason_raw, "owner_change")

    # event_type normalization. Default missing/unknown to 'tbd'.
    type_raw = (raw.get("event_type") or "").strip().lower().replace(" ", "_")
    canonical_type = {
        "tbd":          "tbd",
        "allowance":    "allowance",
        "contingency":  "contingency",
        "owner_change": "owner_change",
        "transfer":     "transfer",
    }.get(type_raw, "tbd")

    # scope normalization. Default missing/unknown to 'tbd'.
    scope_raw = (raw.get("scope") or "").strip().lower().replace(" ", "_")
    canonical_scope = {
        "in_scope":     "in_scope",
        "out_of_scope": "out_of_scope",
        "tbd":          "tbd",
    }.get(scope_raw, "tbd")

    # event_number: the natural key (with project_id). Fall back to
    # stringified Procore id so the (project_id, event_number) upsert
    # key is never NULL — UNIQUE indexes treat NULLs as distinct.
    event_number = raw.get("number")
    if not event_number:
        event_number = str(raw.get("id", ""))

    # estimated_amount: rex column is NUMERIC NOT NULL DEFAULT 0. We
    # include it in every INSERT (DB default only fires on omission),
    # so coerce None -> 0.
    amount = raw.get("estimated_amount")
    if amount is None:
        amount = 0
    else:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0

    return {
        "project_id":        project_canonical_id,
        "event_number":      event_number,
        "title":              raw.get("title") or "(untitled change event)",
        "description":        raw.get("description"),
        "status":             canonical_status,
        "change_reason":      canonical_reason,
        "event_type":         canonical_type,
        "scope":              canonical_scope,
        "estimated_amount":   amount,
        # FKs pending enrichment (no resolver)
        "rfi_id":             None,
        "prime_contract_id":  None,
        "created_by":         None,
    }


__all__ = [
    "map_project",
    "map_rfi",
    "map_submittal",
    "map_daily_log",
    "map_schedule_activity",
    "map_change_event",
    "map_commitment",
    "map_user",
    "map_vendor",
]

"""Tests for app.services.connectors.procore.mapper.map_rfi.

Canonical rex.rfis columns targeted (from migrations/rex2_canonical_ddl.sql
lines 823-846 + migration 002_field_parity_batch.sql's rfi_manager ADD):

    id              uuid PK (db-generated; not emitted by mapper)
    project_id      uuid NOT NULL
    rfi_number      text NOT NULL
    subject         text NOT NULL
    status          text NOT NULL  -- draft|open|answered|closed|void
    priority        text NOT NULL default 'medium' (OMITTED by mapper)
    question        text NOT NULL
    answer          text
    cost_impact     text           -- yes|no|tbd
    schedule_impact text           -- yes|no|tbd
    cost_code_id    uuid
    assigned_to     uuid           -- people FK
    ball_in_court   uuid           -- people FK
    created_by      uuid           -- people FK
    due_date        date
    answered_date   date
    days_open       int
    drawing_id      uuid
    spec_section    text
    location        text
    rfi_manager     uuid           -- people FK (migration 002)
    created_at      timestamptz default now() (db-managed)
    updated_at      timestamptz default now() (db-managed)

Mapper contract:
- Output contains ONLY canonical rex.rfis column keys.
- `priority` is omitted so the DB default ('medium') fires.
- `source_id` and `source_names_*` are NOT emitted -- Task 7 reads
  those from the raw payload item directly.
"""

from app.services.connectors.procore.mapper import (
    map_change_event,
    map_daily_log,
    map_project,
    map_rfi,
    map_schedule_activity,
    map_submittal,
    map_user,
    map_vendor,
)

PROJECT_CANONICAL_ID = "11111111-1111-1111-1111-111111111111"


def _realistic_payload() -> dict:
    """Mirror what payloads.build_rfi_payload would produce for a
    representative Procore RFI row."""
    return {
        "id":                "1234",
        "project_source_id": "42",
        "project_name":      "Bishop Modern",
        "rfi_number":        5.0,
        "subject":           "Dimension clash at grid B/4",
        "question":          "Please confirm wall thickness",
        "answer":            None,
        "status":            "open",
        "ball_in_court":     "Architect",
        "assignee":          "Jane Smith",
        "rfi_manager":       "John PM",
        "due_date":          "2026-05-01T00:00:00+00:00",
        "closed_at":         None,
        "created_at":        "2026-04-15T00:00:00+00:00",
        "updated_at":        "2026-04-20T00:00:00+00:00",
        "cost_impact":       None,
        "schedule_impact":   None,
    }


def test_map_rfi_maps_project_fk():
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["project_id"] == PROJECT_CANONICAL_ID


def test_map_rfi_does_not_emit_source_id():
    """source_id is NOT a rex.rfis column. Task 7 reads the Procore id
    directly from the raw payload (item["id"]) for source_links."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert "source_id" not in m


def test_map_rfi_maps_core_text_fields():
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["subject"]  == "Dimension clash at grid B/4"
    assert m["question"] == "Please confirm wall thickness"
    assert m["answer"]   is None
    assert m["status"]   == "open"


def test_map_rfi_coerces_rfi_number_whole_float_to_int_string():
    """rex.rfis.rfi_number is `text NOT NULL`. Procore numbers are
    usually floats (5.0) but render as "RFI #5", not "RFI #5.0"."""
    raw = _realistic_payload()
    raw["rfi_number"] = 5.0
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["rfi_number"] == "5"
    assert isinstance(m["rfi_number"], str)


def test_map_rfi_rfi_number_int_stringifies():
    raw = _realistic_payload()
    raw["rfi_number"] = 7
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["rfi_number"] == "7"


def test_map_rfi_rfi_number_non_whole_float_stringifies_full():
    raw = _realistic_payload()
    raw["rfi_number"] = 5.25
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["rfi_number"] == "5.25"


def test_map_rfi_rfi_number_none_stays_none():
    """Required-field enforcement is the DB's job; the mapper must
    not mask a missing source number by writing the literal 'None'."""
    raw = _realistic_payload()
    raw["rfi_number"] = None
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["rfi_number"] is None


def test_map_rfi_rfi_number_decimal_whole_becomes_integer_string():
    """asyncpg returns numeric(10,2) as Decimal. Decimal('1.00') must
    render as '1' — we don't want rex.rfis to display 'RFI #1.00'."""
    from decimal import Decimal
    raw = _realistic_payload()
    raw["rfi_number"] = Decimal("1.00")
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["rfi_number"] == "1"


def test_map_rfi_rfi_number_decimal_fractional_preserves_precision():
    """Decimal('1.25') must render as '1.25' (not '1' — that would
    lose data on a real fractional RFI number)."""
    from decimal import Decimal
    raw = _realistic_payload()
    raw["rfi_number"] = Decimal("1.25")
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["rfi_number"] == "1.25"


def test_map_rfi_passes_through_impact_fields():
    raw = _realistic_payload()
    raw["cost_impact"] = "yes"
    raw["schedule_impact"] = "tbd"
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["cost_impact"]     == "yes"
    assert m["schedule_impact"] == "tbd"


def test_map_rfi_people_fks_are_none_pending_resolution():
    """assigned_to, ball_in_court, rfi_manager, created_by are uuid
    columns in rex.rfis but the payload carries names. Resolution
    happens in a later pass; mapper emits None."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["assigned_to"]   is None
    assert m["ball_in_court"] is None
    assert m["rfi_manager"]   is None
    assert m["created_by"]    is None


def test_map_rfi_does_not_emit_source_names_sidecar_keys():
    """source_names_* sidecars are NOT rex.rfis columns. Enrichment
    passes resolve names by re-reading the raw payload, not by
    pulling from the mapper output."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert "source_names_assigned_to"   not in m
    assert "source_names_ball_in_court" not in m
    assert "source_names_rfi_manager"   not in m


def test_map_rfi_due_date_iso_timestamp_becomes_date_object():
    """rex.rfis.due_date is `date`. Payload gives ISO timestamp; mapper
    must return a Python date object so asyncpg binds it natively."""
    from datetime import date
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["due_date"] == date(2026, 5, 1)
    assert isinstance(m["due_date"], date)


def test_map_rfi_due_date_none_stays_none():
    raw = _realistic_payload()
    raw["due_date"] = None
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["due_date"] is None


def test_map_rfi_answered_date_derived_from_closed_at():
    from datetime import date
    raw = _realistic_payload()
    raw["closed_at"] = "2026-05-10T14:30:00+00:00"
    raw["status"] = "closed"
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["answered_date"] == date(2026, 5, 10)
    assert isinstance(m["answered_date"], date)


def test_map_rfi_answered_date_none_when_not_closed():
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["answered_date"] is None


def test_map_rfi_computed_and_unsourced_fields_are_none():
    """These canonical columns have no payload counterpart today."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["cost_code_id"] is None
    assert m["days_open"]    is None
    assert m["drawing_id"]   is None
    assert m["spec_section"] is None
    assert m["location"]     is None


def test_map_rfi_omits_priority_so_db_default_fires():
    """rex.rfis.priority is NOT NULL DEFAULT 'medium'. If the mapper
    emitted `priority: None`, the INSERT would pass NULL and violate
    the NOT NULL constraint (defaults don't fire when the column is
    present with NULL). Omit the key entirely so the INSERT leaves
    the column out and the DB default applies."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert "priority" not in m


def test_map_rfi_emits_every_targeted_canonical_column():
    """Sanity: every rex.rfis column the mapper targets appears as a
    key in the output dict (value may be None, but the key exists).

    Excludes:
    - `priority` (omitted on purpose so DB default 'medium' fires)
    - `id`, `created_at`, `updated_at` (DB-managed)
    """
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    expected_canonical_keys = {
        "project_id",
        "rfi_number",
        "subject",
        "status",
        "question",
        "answer",
        "cost_impact",
        "schedule_impact",
        "cost_code_id",
        "assigned_to",
        "ball_in_court",
        "created_by",
        "due_date",
        "answered_date",
        "days_open",
        "drawing_id",
        "spec_section",
        "location",
        "rfi_manager",
    }
    assert set(m.keys()) == expected_canonical_keys, (
        f"mapper keys differ from expected canonical set.\n"
        f"  missing (in expected, not in m): {expected_canonical_keys - set(m.keys())}\n"
        f"  extra   (in m, not in expected): {set(m.keys()) - expected_canonical_keys}"
    )


# ── map_project ───────────────────────────────────────────────────────────


def _project_payload() -> dict:
    """Mirror ``payloads.build_project_payload`` output for a representative
    Procore project row."""
    return {
        "id":                "1001",
        "project_source_id": None,
        "project_name":      "Bishop Modern",
        "project_number":    "BM-001",
        "status":            "Active",
        "city":              "Austin",
        "state_code":        "TX",
        "zip_code":          "78701",
        "address":           "123 Main",
        "start_date":        "2026-01-01",
        "completion_date":   "2027-06-30",
        "created_at":        "2026-01-01T00:00:00+00:00",
        "updated_at":        "2026-04-01T00:00:00+00:00",
    }


def test_map_project_single_arg_signature():
    """Projects are a root resource — no parent project to inject."""
    m = map_project(_project_payload())
    assert isinstance(m, dict)


def test_map_project_sets_name_and_status():
    m = map_project(_project_payload())
    assert m["name"] == "Bishop Modern"
    assert m["status"] == "active"


def test_map_project_name_fallback_when_missing():
    """rex.projects.name is NOT NULL. A missing source name must fall
    back to a safe placeholder rather than emit None and break the
    canonical INSERT."""
    raw = _project_payload()
    raw["project_name"] = None
    m = map_project(raw)
    assert m["name"] == "Untitled Project"


def test_map_project_lowercases_status():
    raw = _project_payload()
    raw["status"] = "Inactive"
    m = map_project(raw)
    assert m["status"] == "inactive"


def test_map_project_archived_status_passes_through():
    raw = _project_payload()
    raw["status"] = "Archived"
    m = map_project(raw)
    assert m["status"] == "archived"


def test_map_project_missing_status_defaults_to_active():
    """rex.projects.status is NOT NULL CHECK in {active|inactive|archived|
    pre_construction|completed}. A None source status must coerce to
    'active' rather than pass None through."""
    raw = _project_payload()
    raw["status"] = None
    m = map_project(raw)
    assert m["status"] == "active"


def test_map_project_unknown_status_defaults_to_active():
    """Procore has free-text one-offs in the wild; unknown values must
    default to 'active' rather than break the CHECK constraint."""
    raw = _project_payload()
    raw["status"] = "WeirdCustomStatus"
    m = map_project(raw)
    assert m["status"] == "active"


def test_map_project_maps_state_code_to_state():
    """rex.projects column is ``state``; payload key is ``state_code``."""
    m = map_project(_project_payload())
    assert m["state"] == "TX"
    assert "state_code" not in m


def test_map_project_city_passthrough():
    m = map_project(_project_payload())
    assert m["city"] == "Austin"


def test_map_project_dates_become_date_objects():
    """rex.projects.start_date and end_date are typed ``date``; the
    mapper must emit ``date`` objects (not ISO strings) so asyncpg
    binds them natively."""
    from datetime import date
    m = map_project(_project_payload())
    assert m["start_date"] == date(2026, 1, 1)
    assert m["end_date"] == date(2027, 6, 30)


def test_map_project_completion_date_becomes_end_date():
    """Procore payload field is ``completion_date``; canonical column
    is ``end_date``. Renaming happens here."""
    raw = _project_payload()
    raw["completion_date"] = "2030-12-31"
    m = map_project(raw)
    assert "completion_date" not in m
    from datetime import date
    assert m["end_date"] == date(2030, 12, 31)


def test_map_project_none_dates_stay_none():
    raw = _project_payload()
    raw["start_date"] = None
    raw["completion_date"] = None
    m = map_project(raw)
    assert m["start_date"] is None
    assert m["end_date"] is None


def test_map_project_project_number_passthrough():
    m = map_project(_project_payload())
    assert m["project_number"] == "BM-001"


def test_map_project_project_number_none_stays_none():
    """Required-field enforcement is the DB's job; the mapper must not
    silently invent a natural key for rows that lack one."""
    raw = _project_payload()
    raw["project_number"] = None
    m = map_project(raw)
    assert m["project_number"] is None


def test_map_project_emits_only_canonical_columns():
    """Every key the mapper emits must be a real rex.projects column
    so the orchestrator's INSERT ... ON CONFLICT splat doesn't
    reference a nonexistent column."""
    m = map_project(_project_payload())
    expected = {
        "name",
        "project_number",
        "status",
        "city",
        "state",
        "start_date",
        "end_date",
    }
    assert set(m.keys()) == expected, (
        f"mapper keys differ from expected canonical set.\n"
        f"  missing: {expected - set(m.keys())}\n"
        f"  extra:   {set(m.keys()) - expected}"
    )


# ── map_user ──────────────────────────────────────────────────────────────


def _user_payload() -> dict:
    """Mirror ``payloads.build_user_payload`` output for a representative
    Procore user row."""
    return {
        "id":                "5001",
        "project_source_id": None,
        "first_name":        "Jane",
        "last_name":         "Smith",
        "full_name":         "Jane Smith",
        "email":             "jane@example.com",
        "phone":             "555-1111",
        "job_title":         "Project Manager",
        "is_active":         True,
        "is_employee":       False,
        "city":              "Austin",
        "state_code":        "TX",
        "vendor_procore_id": 9001,
        "employee_id":       "E-42",
        "created_at":        "2026-01-01T00:00:00+00:00",
        "updated_at":        "2026-04-01T00:00:00+00:00",
        "last_login_at":     "2026-04-15T00:00:00+00:00",
    }


def test_map_user_single_arg_signature():
    """Users are a root resource — no parent project to inject."""
    m = map_user(_user_payload())
    assert isinstance(m, dict)


def test_map_user_maps_name_fields():
    m = map_user(_user_payload())
    assert m["first_name"] == "Jane"
    assert m["last_name"] == "Smith"


def test_map_user_maps_email_phone_title():
    m = map_user(_user_payload())
    assert m["email"] == "jane@example.com"
    assert m["phone"] == "555-1111"
    assert m["title"] == "Project Manager"


def test_map_user_role_type_defaults_to_external():
    """Procore can't reliably distinguish Rex employees from subs/vendors;
    default to 'external' and let an admin re-classify true internals later.
    The rex.people CHECK constraint allows only ('internal','external')."""
    m = map_user(_user_payload())
    assert m["role_type"] == "external"


def test_map_user_first_name_fallback_when_missing():
    """rex.people.first_name is NOT NULL. An empty/None source must be
    coerced to a safe placeholder rather than fail the canonical INSERT."""
    raw = _user_payload()
    raw["first_name"] = None
    raw["last_name"] = None
    raw["full_name"] = None
    m = map_user(raw)
    assert m["first_name"] == "(unknown)"
    assert m["last_name"] == "(unknown)"


def test_map_user_splits_full_name_when_first_last_missing():
    """Some live rows only have full_name populated. Split on first space
    so 'Jane Q Smith' -> first='Jane', last='Q Smith'."""
    raw = _user_payload()
    raw["first_name"] = None
    raw["last_name"] = None
    raw["full_name"] = "Jane Q Smith"
    m = map_user(raw)
    assert m["first_name"] == "Jane"
    assert m["last_name"] == "Q Smith"


def test_map_user_single_word_full_name_last_falls_back():
    """'Madonna' style single-token names: last_name falls back to
    '(unknown)' so the NOT NULL constraint still holds."""
    raw = _user_payload()
    raw["first_name"] = None
    raw["last_name"] = None
    raw["full_name"] = "Madonna"
    m = map_user(raw)
    assert m["first_name"] == "Madonna"
    assert m["last_name"] == "(unknown)"


def test_map_user_missing_email_synthesizes_placeholder():
    """rex.people.email is the natural key we upsert on (migration 026
    adds UNIQUE). A missing email must synthesize a deterministic
    placeholder including the procore id so a re-sync is idempotent."""
    raw = _user_payload()
    raw["email"] = None
    m = map_user(raw)
    assert m["email"] == "procore-user-5001@placeholder.invalid"


def test_map_user_missing_email_is_idempotent_same_id():
    """Re-mapping the same source row must produce the same synthetic
    email so the ON CONFLICT upsert converges on one row rather than
    creating N duplicates across re-syncs."""
    raw = _user_payload()
    raw["email"] = None
    first = map_user(raw)
    second = map_user(raw)
    assert first["email"] == second["email"]


def test_map_user_does_not_emit_source_id():
    """source_id is NOT a rex.people column. Orchestrator reads the
    procore id directly from the raw payload (item["id"]) for the
    source_links writer."""
    m = map_user(_user_payload())
    assert "source_id" not in m


def test_map_user_emits_only_canonical_columns():
    """Every key the mapper emits must be a real rex.people column
    so the orchestrator's INSERT ... ON CONFLICT splat doesn't
    reference a nonexistent column.

    Excluded from the output:
    - id, created_at, updated_at (DB-managed)
    - company_id, notes (not sourced from Procore today)
    - is_active (DB default true; omitted so default fires — we don't
      want to overwrite an admin's manual deactivation on every sync)
    """
    m = map_user(_user_payload())
    expected = {
        "first_name",
        "last_name",
        "email",
        "phone",
        "title",
        "role_type",
    }
    assert set(m.keys()) == expected, (
        f"mapper keys differ from expected canonical set.\n"
        f"  missing: {expected - set(m.keys())}\n"
        f"  extra:   {set(m.keys()) - expected}"
    )


# ── map_vendor ────────────────────────────────────────────────────────────


def _vendor_payload() -> dict:
    """Mirror ``payloads.build_vendor_payload`` output for a representative
    Procore vendor row."""
    return {
        "id":                             "6001",
        "project_source_id":              None,
        "vendor_name":                    "Acme Subs LLC",
        "trade_name":                     "Electrical",
        "email":                          "contact@acme.example",
        "phone":                          "555-7000",
        "website":                        "https://acme.example",
        "address":                        "500 Industrial Dr",
        "city":                           "Dallas",
        "state_code":                     "TX",
        "zip_code":                       "75201",
        "is_active":                      True,
        "license_number":                 "TECL-12345",
        "insurance_expiration_date":      "2027-01-31",
        "insurance_gl_expiration_date":   "2027-03-15",
        "insurance_wc_expiration_date":   "2027-04-30",
        "insurance_auto_expiration_date": "2027-05-30",
        "created_at":                     "2026-01-01T00:00:00+00:00",
        "updated_at":                     "2026-04-01T00:00:00+00:00",
    }


def test_map_vendor_single_arg_signature():
    """Vendors are a root resource — no parent project to inject."""
    m = map_vendor(_vendor_payload())
    assert isinstance(m, dict)


def test_map_vendor_sets_name_and_company_type():
    m = map_vendor(_vendor_payload())
    assert m["name"] == "Acme Subs LLC"
    # rex.companies.company_type is NOT NULL CHECK IN
    # (subcontractor|supplier|architect|engineer|owner|gc|consultant)
    # — Procore doesn't expose a reliable classifier, so we default to
    # 'subcontractor' and admins re-classify.
    assert m["company_type"] == "subcontractor"


def test_map_vendor_name_fallback_when_missing():
    """rex.companies.name is NOT NULL. A missing source name must fall
    back to a safe placeholder rather than emit None and break the
    canonical INSERT."""
    raw = _vendor_payload()
    raw["vendor_name"] = None
    m = map_vendor(raw)
    assert m["name"] == "(unnamed vendor)"


def test_map_vendor_maps_trade_email_phone():
    m = map_vendor(_vendor_payload())
    assert m["trade"] == "Electrical"
    assert m["email"] == "contact@acme.example"
    assert m["phone"] == "555-7000"


def test_map_vendor_maps_state_code_to_state():
    """rex.companies column is ``state``; payload key is ``state_code``."""
    m = map_vendor(_vendor_payload())
    assert m["state"] == "TX"
    assert "state_code" not in m


def test_map_vendor_maps_address_to_address_line1():
    """rex.companies canonical column is ``address_line1`` (not
    ``address``). Procore payload's freeform ``address`` field goes
    into line1 wholesale — splitting into line1/line2 is a future
    concern."""
    m = map_vendor(_vendor_payload())
    assert m["address_line1"] == "500 Industrial Dr"
    assert "address" not in m


def test_map_vendor_maps_zip_code_to_zip():
    """rex.companies canonical column is ``zip`` (not ``zip_code``)."""
    m = map_vendor(_vendor_payload())
    assert m["zip"] == "75201"
    assert "zip_code" not in m


def test_map_vendor_maps_city_and_website():
    m = map_vendor(_vendor_payload())
    assert m["city"] == "Dallas"
    assert m["website"] == "https://acme.example"


def test_map_vendor_maps_license_number():
    m = map_vendor(_vendor_payload())
    assert m["license_number"] == "TECL-12345"


def test_map_vendor_insurance_expiry_prefers_gl_expiration():
    """The GL (general liability) expiration is the most commonly
    referenced carrier date on the vendor_compliance action. Prefer it
    over the generic ``insurance_expiration_date`` when both are set,
    and emit a Python ``date`` object so asyncpg binds it natively to
    rex.companies.insurance_expiry."""
    from datetime import date
    m = map_vendor(_vendor_payload())
    assert m["insurance_expiry"] == date(2027, 3, 15)
    assert isinstance(m["insurance_expiry"], date)


def test_map_vendor_insurance_expiry_falls_back_to_generic():
    """When insurance_gl_expiration_date is NULL, fall back to the
    generic ``insurance_expiration_date`` so vendors with only one
    expiration on file still land a compliance-ready value."""
    from datetime import date
    raw = _vendor_payload()
    raw["insurance_gl_expiration_date"] = None
    m = map_vendor(raw)
    assert m["insurance_expiry"] == date(2027, 1, 31)


def test_map_vendor_insurance_expiry_none_when_both_missing():
    raw = _vendor_payload()
    raw["insurance_gl_expiration_date"] = None
    raw["insurance_expiration_date"] = None
    m = map_vendor(raw)
    assert m["insurance_expiry"] is None


def test_map_vendor_insurance_carrier_is_none():
    """procore.vendors doesn't carry the carrier name; admins fill it
    in manually post-sync."""
    m = map_vendor(_vendor_payload())
    assert m["insurance_carrier"] is None


def test_map_vendor_does_not_emit_source_id():
    """source_id is NOT a rex.companies column. Orchestrator reads the
    procore id directly from the raw payload (item["id"]) for the
    source_links writer."""
    m = map_vendor(_vendor_payload())
    assert "source_id" not in m


def test_map_vendor_emits_only_canonical_columns():
    """Every key the mapper emits must be a real rex.companies column
    so the orchestrator's INSERT ... ON CONFLICT (name) splat doesn't
    reference a nonexistent column.

    Excluded from the output:
    - id, created_at, updated_at (DB-managed)
    - status (DB default 'active'; omitted so default fires — don't
      overwrite an admin's manual deactivation)
    - bonding_capacity, notes, mobile_phone (not sourced from Procore today)
    """
    m = map_vendor(_vendor_payload())
    expected = {
        "name",
        "company_type",
        "trade",
        "phone",
        "email",
        "address_line1",
        "city",
        "state",
        "zip",
        "website",
        "license_number",
        "insurance_expiry",
        "insurance_carrier",
    }
    assert set(m.keys()) == expected, (
        f"mapper keys differ from expected canonical set.\n"
        f"  missing: {expected - set(m.keys())}\n"
        f"  extra:   {set(m.keys()) - expected}"
    )


# ── map_submittal ─────────────────────────────────────────────────────────


def _submittal_payload() -> dict:
    """Mirror ``payloads.build_submittal_payload`` output for a representative
    Procore submittal row. Procore's submittal API returns title-cased
    status ('Open') and human-readable submittal_type ('Shop Drawings');
    the mapper normalizes both to the rex.submittals enum."""
    return {
        "id":                      "7001",
        "project_source_id":       "42",
        "submittal_number":        "SUB-0001",
        "title":                   "Structural steel shop drawings",
        "status":                  "Open",
        "submittal_type":          "Shop Drawings",
        "spec_section":            "05 12 00",
        "due_date":                "2026-05-15T00:00:00+00:00",
        "submitted_date":          "2026-04-20T00:00:00+00:00",
        "approved_date":           None,
        "assignee":                "Jane Smith",
        "ball_in_court":           "Architect",
        "responsible_contractor":  "Acme Steel",
        "created_at":              "2026-04-01T00:00:00+00:00",
        "updated_at":              "2026-04-22T10:00:00+00:00",
    }


def test_map_submittal_maps_project_fk():
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert m["project_id"] == PROJECT_CANONICAL_ID


def test_map_submittal_does_not_emit_source_id():
    """source_id is NOT a rex.submittals column. Orchestrator reads the
    procore id directly from the raw payload (item["id"]) for the
    source_links writer — same convention as map_rfi."""
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert "source_id" not in m


def test_map_submittal_maps_core_text_fields():
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert m["submittal_number"] == "SUB-0001"
    assert m["title"] == "Structural steel shop drawings"
    assert m["spec_section"] == "05 12 00"


def test_map_submittal_submittal_number_falls_back_to_number_key():
    """Some upstream shapes emit the natural-key field under the key
    ``number`` rather than ``submittal_number``. Accept both so a
    future payload-builder tweak doesn't silently null the natural key."""
    raw = _submittal_payload()
    del raw["submittal_number"]
    raw["number"] = "SUB-1234"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["submittal_number"] == "SUB-1234"


def test_map_submittal_normalizes_open_status_to_pending():
    """Procore's native 'Open' status has no direct rex.submittals enum
    equivalent; the closest semantic match is 'pending' (awaiting action)."""
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert m["status"] == "pending"


def test_map_submittal_normalizes_approved_as_noted():
    """'Approved as Noted' (with spaces) -> canonical 'approved_as_noted'."""
    raw = _submittal_payload()
    raw["status"] = "Approved as Noted"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "approved_as_noted"


def test_map_submittal_normalizes_revise_and_resubmit_to_rejected():
    """'Revise and Resubmit' is Procore's way of saying 'rejected — try
    again'. Map to the canonical 'rejected' state so action queues can
    filter on a single meaning."""
    raw = _submittal_payload()
    raw["status"] = "Revise and Resubmit"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "rejected"


def test_map_submittal_canonical_status_passthrough():
    raw = _submittal_payload()
    raw["status"] = "approved"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "approved"


def test_map_submittal_unknown_status_defaults_to_draft():
    """rex.submittals.status is NOT NULL CHECK in a 7-value enum. Procore
    has free-text one-offs in the wild (custom statuses per company);
    unknown values must default to 'draft' rather than break the CHECK."""
    raw = _submittal_payload()
    raw["status"] = "SomeOrgCustomStatus"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "draft"


def test_map_submittal_missing_status_defaults_to_draft():
    raw = _submittal_payload()
    raw["status"] = None
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "draft"


def test_map_submittal_normalizes_shop_drawings_type():
    """'Shop Drawings' (human-readable, plural) -> canonical 'shop_drawing'."""
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert m["submittal_type"] == "shop_drawing"


def test_map_submittal_normalizes_product_data_type():
    raw = _submittal_payload()
    raw["submittal_type"] = "Product Data"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["submittal_type"] == "product_data"


def test_map_submittal_canonical_type_passthrough():
    raw = _submittal_payload()
    raw["submittal_type"] = "sample"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["submittal_type"] == "sample"


def test_map_submittal_unknown_type_defaults_to_other():
    """rex.submittals.submittal_type is NOT NULL CHECK in a 6-value enum
    ending in 'other'. Unknown types from Procore default to 'other'
    rather than break the CHECK."""
    raw = _submittal_payload()
    raw["submittal_type"] = "WeirdCustomType"
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["submittal_type"] == "other"


def test_map_submittal_missing_type_defaults_to_other():
    raw = _submittal_payload()
    raw["submittal_type"] = None
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["submittal_type"] == "other"


def test_map_submittal_dates_become_date_objects():
    """rex.submittals.due_date / submitted_date / approved_date are typed
    ``date``; the mapper must emit ``date`` objects (not ISO strings)
    so asyncpg binds them natively."""
    from datetime import date
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert m["due_date"] == date(2026, 5, 15)
    assert isinstance(m["due_date"], date)
    assert m["submitted_date"] == date(2026, 4, 20)
    assert m["approved_date"] is None


def test_map_submittal_none_dates_stay_none():
    raw = _submittal_payload()
    raw["due_date"] = None
    raw["submitted_date"] = None
    raw["approved_date"] = None
    m = map_submittal(raw, PROJECT_CANONICAL_ID)
    assert m["due_date"] is None
    assert m["submitted_date"] is None
    assert m["approved_date"] is None


def test_map_submittal_people_and_company_fks_are_none_pending_resolution():
    """assigned_to, ball_in_court, responsible_contractor, created_by are
    uuid columns but the payload carries names. Resolution happens in a
    later pass (same convention as map_rfi)."""
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert m["assigned_to"] is None
    assert m["ball_in_court"] is None
    assert m["responsible_contractor"] is None
    assert m["created_by"] is None


def test_map_submittal_omits_current_revision_so_db_default_fires():
    """rex.submittals.current_revision is NOT NULL DEFAULT 0. If the
    mapper emitted current_revision=None, the INSERT would pass NULL
    and violate the NOT NULL constraint (defaults don't fire when the
    column is present with NULL). Omit the key so the DB default
    applies."""
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    assert "current_revision" not in m


def test_map_submittal_emits_only_canonical_columns():
    """Every key the mapper emits must be a real rex.submittals column
    so orchestrator._write_submittals' INSERT ... ON CONFLICT splat
    doesn't reference a nonexistent column.

    Excluded from the output:
    - id, created_at, updated_at (DB-managed)
    - current_revision (DB default 0; omitted so default fires)
    """
    m = map_submittal(_submittal_payload(), PROJECT_CANONICAL_ID)
    expected = {
        "project_id",
        "submittal_package_id",
        "submittal_number",
        "title",
        "status",
        "submittal_type",
        "spec_section",
        "cost_code_id",
        "schedule_activity_id",
        "assigned_to",
        "ball_in_court",
        "responsible_contractor",
        "created_by",
        "due_date",
        "submitted_date",
        "approved_date",
        "lead_time_days",
        "required_on_site",
        "location",
    }
    assert set(m.keys()) == expected, (
        f"mapper keys differ from expected canonical set.\n"
        f"  missing: {expected - set(m.keys())}\n"
        f"  extra:   {set(m.keys()) - expected}"
    )


# ── map_daily_log ─────────────────────────────────────────────────────────


def _daily_log_payload() -> dict:
    """Mirror ``payloads.build_daily_log_payload`` output for a
    representative Procore daily-log row from the
    construction_report_logs endpoint."""
    return {
        "id":                 "5001",
        "project_source_id":  "42",
        "log_date":           "2026-04-22",
        "is_published":       True,
        "status":             None,
        "notes":              "Poured slab on grade north wing.",
        "weather":            {
            "conditions":           "Partly cloudy",
            "temperature_high":     72,
            "temperature_low":      55,
            "precipitation_inches": 0.0,
        },
        "weather_conditions": {
            "conditions":           "Partly cloudy",
            "temperature_high":     72,
            "temperature_low":      55,
            "precipitation_inches": 0.0,
        },
        "created_at":         "2026-04-22T08:00:00+00:00",
        "updated_at":         "2026-04-22T15:00:00+00:00",
    }


def test_map_daily_log_maps_project_fk():
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert m["project_id"] == PROJECT_CANONICAL_ID


def test_map_daily_log_does_not_emit_source_id():
    """source_id is NOT a rex.daily_logs column. Orchestrator reads the
    procore id directly from the raw payload (item["id"]) for the
    source_links writer — same convention as map_submittal."""
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert "source_id" not in m


def test_map_daily_log_maps_log_date_as_date_object():
    """rex.daily_logs.log_date is typed ``date`` (NOT NULL); the mapper
    must emit a ``date`` object (not an ISO string) so asyncpg binds it
    natively."""
    from datetime import date
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert m["log_date"] == date(2026, 4, 22)
    assert isinstance(m["log_date"], date)


def test_map_daily_log_published_is_submitted():
    """Procore's ``is_published=True`` means the log has been finalized
    for the day; rex's equivalent status is 'submitted'."""
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert m["status"] == "submitted"


def test_map_daily_log_unpublished_is_draft():
    """An unpublished (is_published=False) log is still in progress —
    rex's 'draft' state."""
    raw = _daily_log_payload()
    raw["is_published"] = False
    m = map_daily_log(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "draft"


def test_map_daily_log_missing_is_published_defaults_to_draft():
    """If Procore's response omits is_published (shape varies across
    endpoint revisions), default to 'draft' so the CHECK constraint
    passes. Don't assume published — a missing signal is NOT a signal
    of readiness."""
    raw = _daily_log_payload()
    raw["is_published"] = None
    m = map_daily_log(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "draft"


def test_map_daily_log_canonical_status_passthrough():
    """If the payload already carries a rex-canonical status (e.g. from
    a future payload-builder revision that pre-normalizes), pass it
    through unchanged."""
    raw = _daily_log_payload()
    raw["status"] = "approved"
    m = map_daily_log(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "approved"


def test_map_daily_log_flattens_weather_to_summary_and_temps():
    """Procore's weather is a nested structured object. The mapper
    flattens the conditions string into weather_summary and pulls
    numeric highs/lows into their canonical columns."""
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert m["weather_summary"] == "Partly cloudy"
    assert m["temp_high_f"] == 72
    assert m["temp_low_f"] == 55


def test_map_daily_log_missing_weather_is_none_fields():
    """If Procore's weather field is entirely absent, every weather
    column on the mapper output is None (rex columns are nullable
    except is_weather_delay which gets False)."""
    raw = _daily_log_payload()
    raw["weather"] = None
    raw["weather_conditions"] = None
    m = map_daily_log(raw, PROJECT_CANONICAL_ID)
    assert m["weather_summary"] is None
    assert m["temp_high_f"] is None
    assert m["temp_low_f"] is None


def test_map_daily_log_notes_land_in_work_summary():
    """Procore's single 'notes' field is the main narrative body.
    Rex splits notes into work/delay/safety/visitor columns; the
    Procore response does not distinguish those so we land the whole
    narrative in work_summary and leave the other three None."""
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert m["work_summary"] == "Poured slab on grade north wing."
    assert m["delay_notes"] is None
    assert m["safety_notes"] is None
    assert m["visitor_notes"] is None


def test_map_daily_log_people_fks_are_none_pending_resolution():
    """created_by, approved_by are uuid columns but the payload
    carries no person names here. Resolution happens in a later
    pass (same convention as map_submittal)."""
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert m["created_by"] is None
    assert m["approved_by"] is None
    assert m["approved_at"] is None


def test_map_daily_log_omits_is_weather_delay_when_unknown():
    """rex.daily_logs.is_weather_delay is NOT NULL DEFAULT false. If the
    mapper emitted is_weather_delay=None, the INSERT would pass NULL
    and violate the NOT NULL constraint (defaults don't fire when the
    column is present with NULL). Omit the key so the DB default
    applies when Procore's response doesn't carry a delay signal."""
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    assert "is_weather_delay" not in m


def test_map_daily_log_emits_only_canonical_columns():
    """Every key the mapper emits must be a real rex.daily_logs column
    so orchestrator._write_daily_logs' INSERT ... ON CONFLICT splat
    doesn't reference a nonexistent column.

    Excluded from the output:
    - id, created_at, updated_at (DB-managed)
    - is_weather_delay (DB default false; omitted so default fires
      when Procore's response doesn't carry a delay signal)
    """
    m = map_daily_log(_daily_log_payload(), PROJECT_CANONICAL_ID)
    expected = {
        "project_id",
        "log_date",
        "status",
        "weather_summary",
        "temp_high_f",
        "temp_low_f",
        "work_summary",
        "delay_notes",
        "safety_notes",
        "visitor_notes",
        "created_by",
        "approved_by",
        "approved_at",
    }
    assert set(m.keys()) == expected, (
        f"daily_log mapper keys differ from expected canonical set.\n"
        f"  missing: {expected - set(m.keys())}\n"
        f"  extra:   {set(m.keys()) - expected}"
    )


# ── map_schedule_activity ────────────────────────────────────────────────


def _schedule_activity_payload() -> dict:
    """Mirror ``payloads.build_schedule_activity_payload`` output for a
    representative Procore standard_tasks row."""
    return {
        "id":                "4001",
        "project_source_id": "42",
        "task_number":       "A-1000",
        "name":              "Pour footings",
        "start_date":        "2026-05-01",
        "finish_date":       "2026-05-05",
        "percent_complete":  25,
        "status":            None,
        "created_at":        "2026-04-22T08:00:00+00:00",
        "updated_at":        "2026-04-22T15:00:00+00:00",
    }


def test_map_schedule_activity_maps_project_scope_via_schedule_name():
    """The mapper does NOT emit ``project_id`` directly — schedule
    activities attach to rex.schedules, not rex.projects. Instead the
    mapper emits a ``schedule_name`` sidecar the orchestrator's writer
    uses to look up (or bootstrap) a rex.schedules row scoped to the
    project, then resolves that row's uuid into ``schedule_id`` at
    write time.

    The project_canonical_id argument is still threaded through so the
    writer knows which project to bootstrap the schedule under.
    """
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    assert m["schedule_name"] == "Procore default schedule"
    assert m["project_id"] == PROJECT_CANONICAL_ID


def test_map_schedule_activity_does_not_emit_source_id():
    """source_id is NOT a rex.schedule_activities column. Orchestrator
    reads the procore id directly from the raw payload (item["id"])
    for the source_links writer — same convention as map_daily_log /
    map_submittal."""
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    assert "source_id" not in m


def test_map_schedule_activity_maps_activity_number_from_task_number():
    """Procore's ``task_number`` is the user-visible task identifier
    (A-1000, 001, etc). It maps directly to
    rex.schedule_activities.activity_number — the natural key the
    writer's ON CONFLICT (schedule_id, activity_number) upsert relies
    on."""
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    assert m["activity_number"] == "A-1000"


def test_map_schedule_activity_missing_task_number_falls_back_to_id():
    """If Procore's response omits ``task_number`` (rare but possible
    for ad-hoc tasks), fall back to the stringified Procore id so the
    (schedule_id, activity_number) upsert key stays deterministic.
    Without this fallback, a NULL activity_number would defeat the
    upsert — UNIQUE indexes treat NULLs as distinct."""
    raw = _schedule_activity_payload()
    raw["task_number"] = None
    m = map_schedule_activity(raw, PROJECT_CANONICAL_ID)
    assert m["activity_number"] == "4001"


def test_map_schedule_activity_maps_dates_as_date_objects():
    """rex.schedule_activities.start_date + end_date are typed ``date``
    and both NOT NULL. The mapper must emit ``date`` objects (not ISO
    strings) so asyncpg binds them natively. Procore's ``finish_date``
    maps to rex's ``end_date`` — the column name in the canonical
    table is ``end_date`` (matches the rex.schedules.end_date pattern)."""
    from datetime import date
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    assert m["start_date"] == date(2026, 5, 1)
    assert m["end_date"] == date(2026, 5, 5)
    assert isinstance(m["start_date"], date)
    assert isinstance(m["end_date"], date)


def test_map_schedule_activity_percent_complete_passthrough():
    """Procore's percent_complete is already in 0-100 range (matches
    rex's CHECK constraint). Pass through unchanged."""
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    assert m["percent_complete"] == 25


def test_map_schedule_activity_missing_percent_complete_defaults_to_zero():
    """rex.schedule_activities.percent_complete is NOT NULL DEFAULT 0.
    When Procore's response omits the field, emit 0 explicitly rather
    than None — the column has a DB default but defaults don't fire
    when the INSERT includes the column with NULL."""
    raw = _schedule_activity_payload()
    raw["percent_complete"] = None
    m = map_schedule_activity(raw, PROJECT_CANONICAL_ID)
    assert m["percent_complete"] == 0


def test_map_schedule_activity_defaults_activity_type_to_task():
    """rex.schedule_activities.activity_type is NOT NULL CHECK IN
    ('task','milestone','section','hammock'). Procore's standard_tasks
    endpoint doesn't expose a reliable activity_type classifier — every
    row is a "task" from Procore's POV. Default to 'task' so the
    CHECK constraint passes. An admin can re-classify milestones in a
    follow-up UI pass."""
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    assert m["activity_type"] == "task"


def test_map_schedule_activity_parent_and_assignments_are_none():
    """parent_id (hierarchy), assigned_company_id, assigned_person_id,
    cost_code_id are uuid FKs the mapper leaves as None pending
    follow-up enrichment passes. Predecessor/successor links live in
    rex.activity_links (a separate relation table) and are NOT this
    mapper's concern."""
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    assert m["parent_id"] is None
    assert m["assigned_company_id"] is None
    assert m["assigned_person_id"] is None
    assert m["cost_code_id"] is None


def test_map_schedule_activity_emits_only_expected_keys():
    """Every key the mapper emits is either a real rex.schedule_activities
    column OR a sidecar the writer consumes before the INSERT.

    The ``schedule_name`` + ``project_id`` sidecars are NOT canonical
    columns — they're consumed by _write_schedule_activities to
    bootstrap a rex.schedules row and resolve schedule_id before the
    canonical INSERT runs. The writer strips them from the row dict
    before splatting into the INSERT.

    Excluded from the output:
    - id, created_at, updated_at (DB-managed)
    - is_critical, is_manually_scheduled (DB defaults false; omitted so
      defaults fire)
    - duration_days, baseline_start, baseline_end, variance_days,
      float_days, location, notes, sort_order (not carried on the
      Procore standard_tasks response today)
    - schedule_id (resolved by the writer from schedule_name+project_id
      sidecars, NOT emitted by the mapper).
    """
    m = map_schedule_activity(_schedule_activity_payload(), PROJECT_CANONICAL_ID)
    expected = {
        # Sidecars the writer consumes before the INSERT
        "schedule_name",
        "project_id",
        # Real rex.schedule_activities columns
        "activity_number",
        "name",
        "activity_type",
        "start_date",
        "end_date",
        "percent_complete",
        "parent_id",
        "assigned_company_id",
        "assigned_person_id",
        "cost_code_id",
    }
    assert set(m.keys()) == expected, (
        f"schedule_activity mapper keys differ from expected set.\n"
        f"  missing: {expected - set(m.keys())}\n"
        f"  extra:   {set(m.keys()) - expected}"
    )


# ── map_change_event ─────────────────────────────────────────────────────


def _change_event_payload() -> dict:
    """Mirror ``payloads.build_change_event_payload`` output for a
    representative Procore change_events row. Procore returns
    title-cased strings for the three CHECK-enum classifiers
    (change_reason, event_type, scope); the mapper normalizes them."""
    return {
        "id":                "5001",
        "project_source_id": "42",
        "number":            "CE-042",
        "title":             "Differing site conditions at SE corner",
        "description":       "Rock encountered at 4' BFG; additional "
                             "excavation required.",
        "status":            "Open",
        "change_reason":     "Unforeseen",
        "event_type":        "TBD",
        "scope":             "In Scope",
        "estimated_amount":  12500.00,
        "created_at":        "2026-04-22T08:00:00+00:00",
        "updated_at":        "2026-04-22T15:00:00+00:00",
    }


def test_map_change_event_maps_project_id_from_argument():
    """The project_canonical_id argument threads directly onto
    rex.change_events.project_id (the NOT NULL FK). This is the
    canonical rex.projects.id — NOT the Procore project_source_id
    (bigint-as-string). The orchestrator resolves the canonical id via
    rex.connector_mappings before calling the mapper."""
    m = map_change_event(_change_event_payload(), PROJECT_CANONICAL_ID)
    assert m["project_id"] == PROJECT_CANONICAL_ID


def test_map_change_event_does_not_emit_source_id():
    """source_id is NOT a rex.change_events column. Orchestrator reads
    the procore id directly from the raw payload (item["id"]) for the
    source_links writer — same convention as map_daily_log /
    map_submittal / map_schedule_activity."""
    m = map_change_event(_change_event_payload(), PROJECT_CANONICAL_ID)
    assert "source_id" not in m


def test_map_change_event_maps_event_number_from_number():
    """Procore's ``number`` is the user-visible change event identifier.
    It maps directly to rex.change_events.event_number — the natural
    key (with project_id) for the writer's ON CONFLICT upsert that
    migration 033 backs with a UNIQUE constraint."""
    m = map_change_event(_change_event_payload(), PROJECT_CANONICAL_ID)
    assert m["event_number"] == "CE-042"


def test_map_change_event_missing_number_falls_back_to_id():
    """If Procore's response omits ``number`` (rare), fall back to the
    stringified Procore id so the (project_id, event_number) upsert
    key stays deterministic. UNIQUE indexes treat NULLs as distinct,
    so a NULL event_number would defeat idempotency."""
    raw = _change_event_payload()
    raw["number"] = None
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["event_number"] == "5001"


def test_map_change_event_normalizes_status_to_lowercase_enum():
    """Procore returns title-cased status strings (``Open``, ``Pending``).
    rex CHECK enum is lowercase (``open``, ``pending``, ``approved``,
    ``closed``, ``void``). Lowercase + strip."""
    raw = _change_event_payload()
    raw["status"] = "Pending"
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "pending"


def test_map_change_event_missing_status_defaults_to_open():
    """rex.change_events.status is NOT NULL DEFAULT 'open'. The mapper
    always emits a concrete value (defaults don't fire on explicit
    inclusion), so None / empty / unknown falls back to 'open'."""
    raw = _change_event_payload()
    raw["status"] = None
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["status"] == "open"


def test_map_change_event_normalizes_change_reason_title_case():
    """Procore's ``change_reason`` comes back title-cased ("Owner
    Change", "Design Change", "Unforeseen"). rex CHECK enum is
    lowercase-underscore. Normalize."""
    raw = _change_event_payload()
    raw["change_reason"] = "Owner Change"
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["change_reason"] == "owner_change"


def test_map_change_event_unknown_change_reason_falls_back_to_owner_change():
    """rex.change_events.change_reason is NOT NULL CHECK IN
    (owner_change|design_change|unforeseen|allowance|contingency).
    Unknown/missing Procore values fall back to 'owner_change' —
    dominant case in the target book of business — rather than
    crashing the sync."""
    raw = _change_event_payload()
    raw["change_reason"] = "Weird Unknown Value"
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["change_reason"] == "owner_change"


def test_map_change_event_normalizes_event_type_title_case():
    """Procore's ``event_type`` comes back title-cased ("TBD",
    "Owner Change"). rex CHECK enum is lowercase-underscore. Normalize."""
    raw = _change_event_payload()
    raw["event_type"] = "Owner Change"
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["event_type"] == "owner_change"


def test_map_change_event_unknown_event_type_falls_back_to_tbd():
    """rex.change_events.event_type is NOT NULL CHECK IN
    (tbd|allowance|contingency|owner_change|transfer). Unknown /
    missing values fall back to 'tbd' (the catch-all)."""
    raw = _change_event_payload()
    raw["event_type"] = None
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["event_type"] == "tbd"


def test_map_change_event_normalizes_scope_title_case():
    """Procore's ``scope`` comes back title-cased ("In Scope",
    "Out of Scope"). rex CHECK enum is lowercase-underscore. Normalize."""
    raw = _change_event_payload()
    raw["scope"] = "Out of Scope"
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["scope"] == "out_of_scope"


def test_map_change_event_unknown_scope_falls_back_to_tbd():
    """rex.change_events.scope is NOT NULL DEFAULT 'tbd' CHECK IN
    (in_scope|out_of_scope|tbd). Unknown / missing values fall back
    to 'tbd'."""
    raw = _change_event_payload()
    raw["scope"] = "Gibberish"
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["scope"] == "tbd"


def test_map_change_event_estimated_amount_passthrough():
    """estimated_amount coerces to float. rex column is NUMERIC — any
    numeric binds natively via asyncpg."""
    m = map_change_event(_change_event_payload(), PROJECT_CANONICAL_ID)
    assert m["estimated_amount"] == 12500.00


def test_map_change_event_missing_estimated_amount_defaults_to_zero():
    """rex.change_events.estimated_amount is NUMERIC NOT NULL DEFAULT
    0. The mapper always includes the column in the INSERT, so DB
    default won't fire; coerce None -> 0."""
    raw = _change_event_payload()
    raw["estimated_amount"] = None
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["estimated_amount"] == 0


def test_map_change_event_title_falls_back_when_missing():
    """rex.change_events.title is NOT NULL. Procore is expected to
    always carry a title in practice, but be defensive: fall back to
    a placeholder rather than crashing the sync with a NULL violation."""
    raw = _change_event_payload()
    raw["title"] = None
    m = map_change_event(raw, PROJECT_CANONICAL_ID)
    assert m["title"] == "(untitled change event)"


def test_map_change_event_fks_are_none():
    """rfi_id / prime_contract_id / created_by are uuid FKs the mapper
    leaves as None pending follow-up enrichment passes. There is no
    resolver for these on the Procore change_events response today."""
    m = map_change_event(_change_event_payload(), PROJECT_CANONICAL_ID)
    assert m["rfi_id"] is None
    assert m["prime_contract_id"] is None
    assert m["created_by"] is None


def test_map_change_event_emits_only_expected_keys():
    """Every key the mapper emits is a real rex.change_events column.
    No sidecars — change_events has a direct (project_id, event_number)
    natural key and doesn't need a parent-bootstrap like
    schedule_activities does for rex.schedules.

    Excluded:
    - id, created_at, updated_at (DB-managed)
    - source_id (orchestrator reads it from the raw payload directly)
    """
    m = map_change_event(_change_event_payload(), PROJECT_CANONICAL_ID)
    expected = {
        "project_id",
        "event_number",
        "title",
        "description",
        "status",
        "change_reason",
        "event_type",
        "scope",
        "estimated_amount",
        "rfi_id",
        "prime_contract_id",
        "created_by",
    }
    assert set(m.keys()) == expected, (
        f"change_event mapper keys differ from expected set.\n"
        f"  missing: {expected - set(m.keys())}\n"
        f"  extra:   {set(m.keys()) - expected}"
    )

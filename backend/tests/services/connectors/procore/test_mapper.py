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
    map_project,
    map_rfi,
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

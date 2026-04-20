"""Tests for app.services.connectors.procore.mapper.map_rfi.

Canonical rex.rfis columns targeted (from migrations/rex2_canonical_ddl.sql
lines 823-846 + migration 002_field_parity_batch.sql's rfi_manager ADD):

    id              uuid PK (db-generated; not emitted by mapper)
    project_id      uuid NOT NULL
    rfi_number      text NOT NULL
    subject         text NOT NULL
    status          text NOT NULL  -- draft|open|answered|closed|void
    priority        text NOT NULL default 'medium'
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

The mapper also emits a convenience `source_id` key (not a rex.rfis
column; consumed by the source_links writer) and source_names_* keys
for deferred name->people.id resolution.
"""

from app.services.connectors.procore.mapper import map_rfi

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


def test_map_rfi_maps_identity_and_project_fk():
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["source_id"]  == "1234"
    assert m["project_id"] == PROJECT_CANONICAL_ID


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


def test_map_rfi_preserves_source_names_for_deferred_resolution():
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["source_names_assigned_to"]   == "Jane Smith"
    assert m["source_names_ball_in_court"] == "Architect"
    assert m["source_names_rfi_manager"]   == "John PM"


def test_map_rfi_due_date_iso_timestamp_becomes_date_string():
    """rex.rfis.due_date is `date`. Payload gives ISO timestamp."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["due_date"] == "2026-05-01"


def test_map_rfi_due_date_none_stays_none():
    raw = _realistic_payload()
    raw["due_date"] = None
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["due_date"] is None


def test_map_rfi_answered_date_derived_from_closed_at():
    raw = _realistic_payload()
    raw["closed_at"] = "2026-05-10T14:30:00+00:00"
    raw["status"] = "closed"
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["answered_date"] == "2026-05-10"


def test_map_rfi_answered_date_none_when_not_closed():
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["answered_date"] is None


def test_map_rfi_computed_and_unsourced_fields_are_none():
    """These canonical columns have no payload counterpart today."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    assert m["priority"]     is None  # Procore RFIs don't surface priority in current payload
    assert m["cost_code_id"] is None
    assert m["days_open"]    is None
    assert m["drawing_id"]   is None
    assert m["spec_section"] is None
    assert m["location"]     is None


def test_map_rfi_emits_every_targeted_canonical_column():
    """Sanity: every rex.rfis column the mapper targets appears as a
    key in the output dict (value may be None, but the key exists)."""
    m = map_rfi(_realistic_payload(), PROJECT_CANONICAL_ID)
    expected_canonical_keys = {
        "project_id",
        "rfi_number",
        "subject",
        "status",
        "priority",
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
    missing = expected_canonical_keys - set(m.keys())
    assert not missing, f"mapper missing canonical keys: {missing}"

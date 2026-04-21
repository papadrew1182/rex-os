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

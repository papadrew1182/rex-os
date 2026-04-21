from datetime import date, datetime, timezone
from app.services.connectors.procore.payloads import (
    build_project_payload,
    build_rfi_payload,
)


def test_build_rfi_payload_happy_path():
    row = {
        "procore_id":     1234,
        "project_id":     100,
        "project_name":   "Bishop Modern",
        "number":         5.0,
        "subject":        "Dimension clash at grid B/4",
        "question":       "Please confirm wall thickness",
        "answer":         None,
        "status":         "open",
        "ball_in_court":  "Architect",
        "assignee":       "Jane Smith",
        "rfi_manager":    "John PM",
        "due_date":       datetime(2026, 5, 1, tzinfo=timezone.utc),
        "closed_at":      None,
        "created_at":     datetime(2026, 4, 15, tzinfo=timezone.utc),
        "updated_at":     datetime(2026, 4, 20, tzinfo=timezone.utc),
        "cost_impact":    None,
        "schedule_impact": None,
    }
    p = build_rfi_payload(row)
    assert p["id"] == "1234"
    assert p["project_source_id"] == "100"
    assert p["rfi_number"] == 5.0
    assert p["subject"] == "Dimension clash at grid B/4"
    assert p["status"] == "open"
    assert p["ball_in_court"] == "Architect"
    assert p["rfi_manager"] == "John PM"
    assert p["due_date"] == "2026-05-01T00:00:00+00:00"
    assert p["updated_at"] == "2026-04-20T00:00:00+00:00"


def test_build_rfi_payload_handles_none_dates():
    row = {
        "procore_id": 7,
        "project_id": 100,
        "number": 7.0,
        "subject": "x",
        "status": "open",
        "due_date": None,
        "closed_at": None,
        "created_at": None,
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    p = build_rfi_payload(row)
    assert p["due_date"] is None
    assert p["closed_at"] is None


def test_build_rfi_payload_coerces_ids_to_string():
    row = {"procore_id": 9, "project_id": 100, "subject": "s", "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    p = build_rfi_payload(row)
    assert isinstance(p["id"], str)
    assert isinstance(p["project_source_id"], str)


# ── build_project_payload ─────────────────────────────────────────────────


def test_build_project_payload_happy_path():
    row = {
        "procore_id":      1001,
        "company_id":      42,
        "project_name":    "Bishop Modern",
        "project_number":  "BM-001",
        "status":          "Active",
        "start_date":      date(2026, 1, 1),
        "completion_date": date(2027, 6, 30),
        "address":         "123 Main",
        "city":            "Austin",
        "state_code":      "TX",
        "zip_code":        "78701",
        "created_at":      datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at":      datetime(2026, 4, 1, tzinfo=timezone.utc),
    }
    p = build_project_payload(row)
    assert p["id"] == "1001"
    assert p["project_source_id"] is None  # root resource, no parent scope
    assert p["project_name"] == "Bishop Modern"
    assert p["project_number"] == "BM-001"
    assert p["status"] == "Active"
    assert p["city"] == "Austin"
    assert p["state_code"] == "TX"
    assert p["zip_code"] == "78701"
    assert p["address"] == "123 Main"
    assert p["start_date"] == "2026-01-01"
    assert p["completion_date"] == "2027-06-30"
    assert p["updated_at"] == "2026-04-01T00:00:00+00:00"


def test_build_project_payload_handles_null_dates():
    """Live rex-procore has many projects with NULL updated_at / start_date."""
    row = {
        "procore_id":      1002,
        "project_name":    "Ghost Project",
        "project_number":  None,
        "status":          None,
        "start_date":      None,
        "completion_date": None,
        "created_at":      None,
        "updated_at":      None,
    }
    p = build_project_payload(row)
    assert p["id"] == "1002"
    assert p["start_date"] is None
    assert p["completion_date"] is None
    assert p["updated_at"] is None


def test_build_project_payload_coerces_id_to_string():
    """Procore ids come back as bigint; staging's source_id column is text."""
    row = {"procore_id": 42}
    p = build_project_payload(row)
    assert isinstance(p["id"], str)
    assert p["id"] == "42"


def test_build_project_payload_project_source_id_always_none():
    """Sanity: projects are a root resource. staging.upsert_raw branches
    on the ``projects_raw`` table name to skip the project_source_id
    bind, but payload consumers should not rely on that — the explicit
    None here makes the contract visible to readers of the payload."""
    p = build_project_payload({"procore_id": 1})
    assert p["project_source_id"] is None

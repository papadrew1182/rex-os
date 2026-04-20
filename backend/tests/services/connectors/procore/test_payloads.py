from datetime import datetime, timezone
from app.services.connectors.procore.payloads import build_rfi_payload


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

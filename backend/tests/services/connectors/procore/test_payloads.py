from datetime import date, datetime, timezone
from app.services.connectors.procore.payloads import (
    build_project_payload,
    build_rfi_payload,
    build_user_payload,
    build_vendor_payload,
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


# ── build_user_payload ────────────────────────────────────────────────────


def test_build_user_payload_happy_path():
    row = {
        "procore_id":     5001,
        "first_name":     "Jane",
        "last_name":      "Smith",
        "full_name":      "Jane Smith",
        "email_address":  "jane@example.com",
        "mobile_phone":   "555-1111",
        "business_phone": "555-2222",
        "job_title":      ["Foreman", "Carpenter"],
        "is_active":      True,
        "is_employee":    False,
        "city":           "Austin",
        "state_code":     "TX",
        "zip_code":       "78701",
        "vendor_id":      9001,
        "employee_id":    "E-42",
        "created_at":     datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at":     datetime(2026, 4, 1, tzinfo=timezone.utc),
        "last_login_at":  datetime(2026, 4, 15, tzinfo=timezone.utc),
    }
    p = build_user_payload(row)
    assert p["id"] == "5001"
    assert p["project_source_id"] is None  # users are company-level
    assert p["first_name"] == "Jane"
    assert p["last_name"] == "Smith"
    assert p["full_name"] == "Jane Smith"
    assert p["email"] == "jane@example.com"
    # mobile_phone wins over business_phone when both present
    assert p["phone"] == "555-1111"
    assert p["job_title"] == "Foreman, Carpenter"
    assert p["is_active"] is True
    assert p["is_employee"] is False
    assert p["city"] == "Austin"
    assert p["state_code"] == "TX"
    assert p["vendor_procore_id"] == 9001
    assert p["employee_id"] == "E-42"
    assert p["created_at"] == "2026-01-01T00:00:00+00:00"
    assert p["updated_at"] == "2026-04-01T00:00:00+00:00"
    assert p["last_login_at"] == "2026-04-15T00:00:00+00:00"


def test_build_user_payload_phone_falls_back_to_business_when_mobile_missing():
    row = {
        "procore_id":     5002,
        "mobile_phone":   None,
        "business_phone": "555-2222",
    }
    p = build_user_payload(row)
    assert p["phone"] == "555-2222"


def test_build_user_payload_phone_none_when_both_missing():
    row = {"procore_id": 5003, "mobile_phone": None, "business_phone": None}
    p = build_user_payload(row)
    assert p["phone"] is None


def test_build_user_payload_job_title_string_passthrough():
    """Procore's users.job_title is jsonb — sometimes a string, sometimes
    a list, sometimes null. A plain string should pass through unchanged."""
    row = {"procore_id": 5004, "job_title": "Project Manager"}
    p = build_user_payload(row)
    assert p["job_title"] == "Project Manager"


def test_build_user_payload_job_title_none_stays_none():
    row = {"procore_id": 5005, "job_title": None}
    p = build_user_payload(row)
    assert p["job_title"] is None


def test_build_user_payload_job_title_empty_list_becomes_none():
    """A multiselect jsonb with zero entries is semantically 'no title'."""
    row = {"procore_id": 5006, "job_title": []}
    p = build_user_payload(row)
    assert p["job_title"] is None


def test_build_user_payload_job_title_empty_string_becomes_none():
    row = {"procore_id": 5007, "job_title": ""}
    p = build_user_payload(row)
    assert p["job_title"] is None


def test_build_user_payload_coerces_id_to_string():
    """procore_id is bigint; staging.source_id is text."""
    p = build_user_payload({"procore_id": 42})
    assert isinstance(p["id"], str)
    assert p["id"] == "42"


def test_build_user_payload_handles_null_timestamps():
    """Live Rex App DB has updated_at NULL for many users — exactly the
    reason we use procore_id as the cursor, not updated_at."""
    row = {
        "procore_id":    5008,
        "created_at":    None,
        "updated_at":    None,
        "last_login_at": None,
    }
    p = build_user_payload(row)
    assert p["created_at"] is None
    assert p["updated_at"] is None
    assert p["last_login_at"] is None


# ── build_vendor_payload ──────────────────────────────────────────────────


def test_build_vendor_payload_happy_path():
    row = {
        "procore_id":                     6001,
        "vendor_name":                    "Acme Subs LLC",
        "company_name":                   "Acme Subsidiary Holdings",
        "trade_name":                     "Electrical",
        "email_address":                  "contact@acme.example",
        "business_phone":                 "555-7000",
        "mobile_phone":                   "555-7001",
        "address":                        "500 Industrial Dr",
        "city":                           "Dallas",
        "state_code":                     "TX",
        "zip_code":                       "75201",
        "website":                        "https://acme.example",
        "is_active":                      True,
        "license_number":                 "TECL-12345",
        "insurance_expiration_date":      date(2027, 1, 31),
        "insurance_gl_expiration_date":   date(2027, 3, 15),
        "insurance_wc_expiration_date":   date(2027, 4, 30),
        "insurance_auto_expiration_date": date(2027, 5, 30),
        "created_at":                     datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at":                     datetime(2026, 4, 1, tzinfo=timezone.utc),
    }
    p = build_vendor_payload(row)
    assert p["id"] == "6001"
    assert p["project_source_id"] is None  # vendors are company-level
    assert p["vendor_name"] == "Acme Subs LLC"
    assert p["trade_name"] == "Electrical"
    assert p["email"] == "contact@acme.example"
    # business_phone wins over mobile_phone (company-first preference —
    # matches how the compliance action emails the vendor's front door,
    # not an individual's cell).
    assert p["phone"] == "555-7000"
    assert p["website"] == "https://acme.example"
    assert p["address"] == "500 Industrial Dr"
    assert p["city"] == "Dallas"
    assert p["state_code"] == "TX"
    assert p["zip_code"] == "75201"
    assert p["is_active"] is True
    assert p["license_number"] == "TECL-12345"
    assert p["insurance_expiration_date"] == "2027-01-31"
    assert p["insurance_gl_expiration_date"] == "2027-03-15"
    assert p["insurance_wc_expiration_date"] == "2027-04-30"
    assert p["insurance_auto_expiration_date"] == "2027-05-30"
    assert p["created_at"] == "2026-01-01T00:00:00+00:00"
    assert p["updated_at"] == "2026-04-01T00:00:00+00:00"


def test_build_vendor_payload_vendor_name_falls_back_to_company_name():
    """Some Procore rows have vendor_name NULL but company_name populated."""
    row = {
        "procore_id":   6002,
        "vendor_name":  None,
        "company_name": "Acme Subsidiary Holdings",
    }
    p = build_vendor_payload(row)
    assert p["vendor_name"] == "Acme Subsidiary Holdings"


def test_build_vendor_payload_phone_falls_back_to_mobile_when_business_missing():
    row = {
        "procore_id":     6003,
        "business_phone": None,
        "mobile_phone":   "555-7001",
    }
    p = build_vendor_payload(row)
    assert p["phone"] == "555-7001"


def test_build_vendor_payload_phone_none_when_both_missing():
    row = {"procore_id": 6004, "business_phone": None, "mobile_phone": None}
    p = build_vendor_payload(row)
    assert p["phone"] is None


def test_build_vendor_payload_coerces_id_to_string():
    """procore_id is bigint; staging.source_id is text."""
    p = build_vendor_payload({"procore_id": 42})
    assert isinstance(p["id"], str)
    assert p["id"] == "42"


def test_build_vendor_payload_project_source_id_always_none():
    """Vendors are company-level; project_source_id is None."""
    p = build_vendor_payload({"procore_id": 6005})
    assert p["project_source_id"] is None


def test_build_vendor_payload_handles_null_dates():
    """Live procore.vendors has some insurance-expiry columns null for
    most rows (many vendors never filled them in). All four must
    stringify to None rather than the literal 'None'."""
    row = {
        "procore_id":                     6006,
        "insurance_expiration_date":      None,
        "insurance_gl_expiration_date":   None,
        "insurance_wc_expiration_date":   None,
        "insurance_auto_expiration_date": None,
        "created_at":                     None,
        "updated_at":                     None,
    }
    p = build_vendor_payload(row)
    assert p["insurance_expiration_date"] is None
    assert p["insurance_gl_expiration_date"] is None
    assert p["insurance_wc_expiration_date"] is None
    assert p["insurance_auto_expiration_date"] is None
    assert p["created_at"] is None
    assert p["updated_at"] is None

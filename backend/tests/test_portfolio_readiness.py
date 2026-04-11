"""Portfolio-level closeout readiness rollup tests."""

import uuid
from httpx import AsyncClient

COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient, **kw) -> dict:
    payload = {"name": f"Port-{_uid()}", "status": "active"}
    payload.update(kw)
    r = await c.post("/api/projects/", json=payload)
    assert r.status_code == 201
    return r.json()


async def test_portfolio_returns_summary_and_projects(client: AsyncClient):
    """Portfolio endpoint returns both summary counts and project rows."""
    r = await client.get("/api/closeout-readiness/portfolio?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "projects" in body
    assert "total_projects" in body["summary"]
    assert "pass_count" in body["summary"]
    assert "warning_count" in body["summary"]
    assert "fail_count" in body["summary"]
    assert "not_started_count" in body["summary"]


async def test_portfolio_filter_by_project_type(client: AsyncClient):
    """Filter by project_type returns only matching projects."""
    # Create distinct project types
    p1 = await _project(client, project_type="commercial")
    p2 = await _project(client, project_type="industrial")

    r = await client.get("/api/closeout-readiness/portfolio?project_type=commercial&limit=500")
    body = r.json()
    types = {row["project_type"] for row in body["projects"]}
    assert types == {"commercial"}
    ids = {row["project_id"] for row in body["projects"]}
    assert p1["id"] in ids
    assert p2["id"] not in ids


async def test_portfolio_filter_by_state(client: AsyncClient):
    """Filter by state returns only matching projects."""
    p1 = await _project(client, state="WY")
    p2 = await _project(client, state="MT")

    r = await client.get("/api/closeout-readiness/portfolio?state=WY&limit=500")
    body = r.json()
    states = {row["state"] for row in body["projects"]}
    assert states == {"WY"}
    ids = {row["project_id"] for row in body["projects"]}
    assert p1["id"] in ids
    assert p2["id"] not in ids


async def test_portfolio_empty_when_no_match(client: AsyncClient):
    """Filter that matches nothing returns empty summary."""
    r = await client.get("/api/closeout-readiness/portfolio?city=NoSuchCity")
    body = r.json()
    assert body["summary"]["total_projects"] == 0
    assert body["projects"] == []


async def test_portfolio_row_has_expected_fields(client: AsyncClient):
    """Each project row contains all required fields."""
    p = await _project(client, project_type="retail", city="Austin", state="TX")

    r = await client.get(f"/api/closeout-readiness/portfolio?project_type=retail&city=Austin&limit=500")
    body = r.json()
    row = next(rw for rw in body["projects"] if rw["project_id"] == p["id"])

    expected_keys = {
        "project_id", "project_name", "project_number", "project_type",
        "city", "state", "project_status", "readiness_status", "summary_message",
        "best_checklist_percent", "achieved_milestones", "total_milestones",
        "holdback_gate_status", "claimed_warranty_count", "expiring_soon_count",
        "open_issue_count",
    }
    assert set(row.keys()) == expected_keys


async def test_portfolio_status_propagation_not_started(client: AsyncClient):
    """A project with no closeout artifacts shows up as not_started."""
    p = await _project(client, city=f"NotStarted-{_uid()}")
    r = await client.get(f"/api/closeout-readiness/portfolio?city={p['city']}")
    body = r.json()
    assert body["summary"]["total_projects"] == 1
    assert body["summary"]["not_started_count"] == 1
    assert body["projects"][0]["readiness_status"] == "not_started"


async def test_portfolio_status_propagation_fail(client: AsyncClient):
    """A project with claimed warranty propagates fail."""
    p = await _project(client, city=f"Fail-{_uid()}")
    # Add a milestone so the project is not "not_started"
    await client.post("/api/completion-milestones/", json={
        "project_id": p["id"], "milestone_type": "tco", "milestone_name": "TCO",
    })
    # Add claimed warranty -> fail
    await client.post("/api/warranties/", json={
        "project_id": p["id"], "company_id": COMPANY_REX,
        "scope_description": "Bad", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01", "status": "claimed",
    })

    r = await client.get(f"/api/closeout-readiness/portfolio?city={p['city']}")
    body = r.json()
    assert body["summary"]["fail_count"] == 1
    row = body["projects"][0]
    assert row["readiness_status"] == "fail"
    assert row["claimed_warranty_count"] == 1
    assert row["open_issue_count"] >= 1


async def test_portfolio_mixed_statuses(client: AsyncClient):
    """Filter scoped to a unique city, create a mix of pass/warning/fail/not_started."""
    city = f"Mixed-{_uid()}"

    # not_started: empty project
    await _project(client, city=city)

    # warning: partial checklist
    p_warn = await _project(client, city=city)
    await client.post("/api/closeout-checklists/", json={
        "project_id": p_warn["id"], "total_items": 10, "completed_items": 8, "percent_complete": 80,
    })

    # fail: claimed warranty
    p_fail = await _project(client, city=city)
    await client.post("/api/completion-milestones/", json={
        "project_id": p_fail["id"], "milestone_type": "tco", "milestone_name": "TCO",
    })
    await client.post("/api/warranties/", json={
        "project_id": p_fail["id"], "company_id": COMPANY_REX,
        "scope_description": "Bad", "warranty_type": "standard",
        "duration_months": 12, "start_date": "2025-01-01", "status": "claimed",
    })

    r = await client.get(f"/api/closeout-readiness/portfolio?city={city}")
    body = r.json()
    assert body["summary"]["total_projects"] == 3
    assert body["summary"]["not_started_count"] == 1
    assert body["summary"]["warning_count"] == 1
    assert body["summary"]["fail_count"] == 1


async def test_portfolio_limit_offset(client: AsyncClient):
    """Limit/offset works for pagination."""
    city = f"Page-{_uid()}"
    for _ in range(5):
        await _project(client, city=city)

    r = await client.get(f"/api/closeout-readiness/portfolio?city={city}&limit=2&offset=0")
    assert r.status_code == 200
    assert len(r.json()["projects"]) == 2

    r = await client.get(f"/api/closeout-readiness/portfolio?city={city}&limit=2&offset=2")
    assert len(r.json()["projects"]) == 2

    r = await client.get(f"/api/closeout-readiness/portfolio?city={city}&limit=10&offset=4")
    assert len(r.json()["projects"]) == 1

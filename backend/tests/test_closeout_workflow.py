"""Closeout workflow tests: create checklist from template + rollup.

Uses the 3 seeded closeout templates (Rex Standard 34-Item, Retail, Multifamily)
which each have 34 template items.
"""

import uuid
from datetime import date, timedelta

from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
# Seeded template IDs from rex2_business_seed.sql
TEMPLATE_STANDARD = "a0000001-0000-0000-0000-000000000001"
TEMPLATE_RETAIL = "a0000001-0000-0000-0000-000000000002"
TEMPLATE_MULTIFAMILY = "a0000001-0000-0000-0000-000000000003"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


# ═══════════════════════════════════════════════════════════════════════════
# Create checklist from template
# ═══════════════════════════════════════════════════════════════════════════

async def test_create_checklist_from_template_basic(client: AsyncClient):
    """Creates a checklist from the standard 34-item template."""
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["project_id"] == PROJECT_BISHOP
    assert body["template_id"] == TEMPLATE_STANDARD
    assert body["total_items"] == 34
    assert body["completed_items"] == 0
    assert body["percent_complete"] == 0


async def test_created_items_match_template(client: AsyncClient):
    """Verifies that all 34 template items were copied as checklist items."""
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_RETAIL,
    })
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    assert items.status_code == 200
    data = items.json()
    assert len(data) == 34

    # Verify item fields were copied
    categories = {i["category"] for i in data}
    assert categories == {"documentation", "general", "mep", "exterior", "interior"}

    # All items should be not_started
    assert all(i["status"] == "not_started" for i in data)


async def test_due_dates_computed_with_substantial_date(client: AsyncClient):
    """When substantial_completion_date is provided, due_dates are computed."""
    sub_date = date(2025, 12, 1)
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
        "substantial_completion_date": sub_date.isoformat(),
    })
    assert r.status_code == 201
    cl_id = r.json()["id"]
    assert r.json()["substantial_completion_date"] == "2025-12-01"

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    data = items.json()

    # Item 1 (As-built drawings submitted) has days_before_substantial=30
    item_1 = next(i for i in data if i["item_number"] == 1 and i["category"] == "documentation")
    expected_due = (sub_date - timedelta(days=30)).isoformat()
    assert item_1["due_date"] == expected_due

    # Item 16 (Final completion certified) has days_before_substantial=NULL -> no due_date
    item_16 = next(i for i in data if i["item_number"] == 16 and i["category"] == "general")
    assert item_16["due_date"] is None


async def test_due_dates_null_without_substantial_date(client: AsyncClient):
    """When no substantial_completion_date, all due_dates should be null."""
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_MULTIFAMILY,
    })
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    assert all(i["due_date"] is None for i in items.json())


async def test_bad_project_id_returns_404(client: AsyncClient):
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": BOGUS_UUID,
        "template_id": TEMPLATE_STANDARD,
    })
    assert r.status_code == 404
    assert "Project" in r.json()["detail"]


async def test_bad_template_id_returns_404(client: AsyncClient):
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": BOGUS_UUID,
    })
    assert r.status_code == 404
    assert "template" in r.json()["detail"].lower()


async def test_repeated_calls_create_multiple_checklists(client: AsyncClient):
    """Repeated calls are NOT deduplicated — each creates a new checklist."""
    r1 = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP, "template_id": TEMPLATE_STANDARD,
    })
    r2 = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP, "template_id": TEMPLATE_STANDARD,
    })
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


# ═══════════════════════════════════════════════════════════════════════════
# Rollup: checklist item PATCH triggers parent recompute
# ═══════════════════════════════════════════════════════════════════════════

async def test_rollup_on_item_completion(client: AsyncClient):
    """Completing a checklist item auto-updates parent checklist progress."""
    # Create a checklist from template
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
    })
    cl_id = r.json()["id"]
    assert r.json()["completed_items"] == 0

    # Get the first item
    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=1")
    first_item = items.json()[0]

    # Mark it complete
    await client.patch(f"/api/closeout-checklist-items/{first_item['id']}", json={
        "status": "complete",
    })

    # Check parent checklist was updated
    cl = await client.get(f"/api/closeout-checklists/{cl_id}")
    body = cl.json()
    assert body["completed_items"] == 1
    assert body["total_items"] == 34
    assert body["percent_complete"] == round(1 / 34 * 100, 2)


async def test_rollup_multiple_completions(client: AsyncClient):
    """Complete multiple items and verify rollup accuracy."""
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
    })
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    all_items = items.json()

    # Complete first 5 items
    for item in all_items[:5]:
        await client.patch(f"/api/closeout-checklist-items/{item['id']}", json={"status": "complete"})

    # Mark one as n_a (should not count as completed)
    await client.patch(f"/api/closeout-checklist-items/{all_items[5]['id']}", json={"status": "n_a"})

    cl = await client.get(f"/api/closeout-checklists/{cl_id}")
    body = cl.json()
    assert body["completed_items"] == 5  # n_a does not count as complete
    assert body["total_items"] == 34
    assert body["percent_complete"] == round(5 / 34 * 100, 2)

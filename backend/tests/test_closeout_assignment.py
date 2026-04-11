"""Closeout workflow tests: role-based assignee resolution.

Uses seeded Bishop Modern project which has these role assignments:
  vp          -> Andrew Roberts  (person 10..01, company 00..01)
  general_super -> Mitch Andersen (person 10..02, company 00..01)
  asst_super  -> Andrew Hudson   (person 10..03, company 00..01)
  accountant  -> Krystal Hernandez (person 10..04, company 00..01)

The standard 34-item template uses: vp(4), lead_super(17), asst_super(7), accountant(6).
Bishop Modern has NO lead_super member, so those 17 items should have null assignments.
"""

import uuid
from datetime import date, timedelta

from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
TEMPLATE_STANDARD = "a0000001-0000-0000-0000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"  # VP
PERSON_HUDSON = "10000000-0000-4000-a000-000000000003"   # asst_super
PERSON_KRYSTAL = "10000000-0000-4000-a000-000000000004"  # accountant
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def test_resolvable_roles_get_assigned(client: AsyncClient):
    """Items with vp/asst_super/accountant roles should get assigned person+company."""
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
        "substantial_completion_date": "2025-12-01",
    })
    assert r.status_code == 201
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    data = items.json()

    # Item 4 (Certificate of Occupancy uploaded) has default_assignee_role=vp
    vp_item = next(i for i in data if i["item_number"] == 4 and i["category"] == "documentation")
    assert vp_item["assigned_person_id"] == PERSON_ROBERTS
    assert vp_item["assigned_company_id"] == COMPANY_REX

    # Item 7 (Spare parts & attic stock) has default_assignee_role=asst_super
    asst_item = next(i for i in data if i["item_number"] == 7 and i["category"] == "documentation")
    assert asst_item["assigned_person_id"] == PERSON_HUDSON
    assert asst_item["assigned_company_id"] == COMPANY_REX

    # Item 2 (O&M manuals) has default_assignee_role=accountant
    acct_item = next(i for i in data if i["item_number"] == 2 and i["category"] == "documentation")
    assert acct_item["assigned_person_id"] == PERSON_KRYSTAL
    assert acct_item["assigned_company_id"] == COMPANY_REX


async def test_unresolvable_role_leaves_null(client: AsyncClient):
    """Items with lead_super role have no matching Bishop Modern member -> null."""
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
    })
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    data = items.json()

    # Item 1 (As-built drawings submitted) has default_assignee_role=lead_super
    lead_item = next(i for i in data if i["item_number"] == 1 and i["category"] == "documentation")
    assert lead_item["assigned_person_id"] is None
    assert lead_item["assigned_company_id"] is None

    # Count: all 17 lead_super items should be unassigned
    lead_items = [i for i in data if i["assigned_person_id"] is None]
    assert len(lead_items) == 17  # exactly the lead_super items


async def test_multiple_members_primary_wins(client: AsyncClient):
    """When multiple members have the same role, prefer is_primary=true."""
    # Create a fresh project with two VPs, one primary
    proj = await client.post("/api/projects/", json={"name": f"MultiVP-{_uid()}", "status": "active"})
    pid = proj.json()["id"]

    p1 = await client.post("/api/people/", json={"first_name": "VP1", "last_name": f"Test-{_uid()}", "role_type": "internal"})
    p2 = await client.post("/api/people/", json={"first_name": "VP2", "last_name": f"Test-{_uid()}", "role_type": "internal"})

    vp_role = "30000000-0000-4000-a000-000000000001"

    # Member 1: NOT primary
    await client.post("/api/project-members/", json={
        "project_id": pid, "person_id": p1.json()["id"],
        "role_template_id": vp_role, "is_primary": False,
    })
    # Member 2: IS primary
    await client.post("/api/project-members/", json={
        "project_id": pid, "person_id": p2.json()["id"],
        "role_template_id": vp_role, "is_primary": True,
    })

    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": pid,
        "template_id": TEMPLATE_STANDARD,
    })
    assert r.status_code == 201
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    data = items.json()

    # VP items should resolve to p2 (the primary)
    vp_item = next(i for i in data if i["item_number"] == 4 and i["category"] == "documentation")
    assert vp_item["assigned_person_id"] == p2.json()["id"]


async def test_multiple_members_no_primary_leaves_null(client: AsyncClient):
    """When multiple members have the same role and none is primary, leave null."""
    proj = await client.post("/api/projects/", json={"name": f"NoPrimary-{_uid()}", "status": "active"})
    pid = proj.json()["id"]

    p1 = await client.post("/api/people/", json={"first_name": "A1", "last_name": f"Test-{_uid()}", "role_type": "internal"})
    p2 = await client.post("/api/people/", json={"first_name": "A2", "last_name": f"Test-{_uid()}", "role_type": "internal"})

    vp_role = "30000000-0000-4000-a000-000000000001"

    await client.post("/api/project-members/", json={
        "project_id": pid, "person_id": p1.json()["id"],
        "role_template_id": vp_role, "is_primary": False,
    })
    await client.post("/api/project-members/", json={
        "project_id": pid, "person_id": p2.json()["id"],
        "role_template_id": vp_role, "is_primary": False,
    })

    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": pid,
        "template_id": TEMPLATE_STANDARD,
    })
    assert r.status_code == 201
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    data = items.json()

    # VP items should be null — two non-primary members, ambiguous
    vp_item = next(i for i in data if i["item_number"] == 4 and i["category"] == "documentation")
    assert vp_item["assigned_person_id"] is None


async def test_due_dates_still_work_with_assignments(client: AsyncClient):
    """Assignment resolution does not break due date computation."""
    sub_date = date(2025, 12, 1)
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
        "substantial_completion_date": sub_date.isoformat(),
    })
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    data = items.json()

    # Item 1: days_before_substantial=30, role=lead_super (unresolved)
    item_1 = next(i for i in data if i["item_number"] == 1 and i["category"] == "documentation")
    assert item_1["due_date"] == (sub_date - timedelta(days=30)).isoformat()
    assert item_1["assigned_person_id"] is None  # lead_super unresolvable

    # Item 4: days_before_substantial=7, role=vp (resolved)
    item_4 = next(i for i in data if i["item_number"] == 4 and i["category"] == "documentation")
    assert item_4["due_date"] == (sub_date - timedelta(days=7)).isoformat()
    assert item_4["assigned_person_id"] == PERSON_ROBERTS


async def test_checklist_total_unchanged_by_assignments(client: AsyncClient):
    """Assignment logic does not affect item counts or rollup."""
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": PROJECT_BISHOP,
        "template_id": TEMPLATE_STANDARD,
    })
    body = r.json()
    assert body["total_items"] == 34
    assert body["completed_items"] == 0
    assert body["percent_complete"] == 0

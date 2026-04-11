"""Project member primary-role integrity tests.

Ensures at most one active primary member per (project_id, role_template_id).
Uses seeded data + fresh projects/people to test edge cases.
"""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
ROLE_VP = "30000000-0000-4000-a000-000000000001"
ROLE_ACCOUNTANT = "30000000-0000-4000-a000-000000000006"
TEMPLATE_STANDARD = "a0000001-0000-0000-0000-000000000001"

def _uid(): return uuid.uuid4().hex[:8]


async def _person(c: AsyncClient) -> dict:
    r = await c.post("/api/people/", json={
        "first_name": f"P-{_uid()}", "last_name": f"Test-{_uid()}", "role_type": "internal",
    })
    assert r.status_code == 201
    return r.json()


async def _project(c: AsyncClient) -> dict:
    r = await c.post("/api/projects/", json={"name": f"Proj-{_uid()}", "status": "active"})
    assert r.status_code == 201
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Basic integrity
# ═══════════════════════════════════════════════════════════════════════════

async def test_one_active_primary_allowed(client: AsyncClient):
    """A single active primary for project+role is fine."""
    proj = await _project(client)
    p1 = await _person(client)
    r = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p1["id"],
        "role_template_id": ROLE_VP, "is_primary": True, "is_active": True,
    })
    assert r.status_code == 201
    assert r.json()["is_primary"] is True


async def test_second_active_primary_same_role_409(client: AsyncClient):
    """Two active primaries for the same project+role -> 409."""
    proj = await _project(client)
    p1 = await _person(client)
    p2 = await _person(client)

    r1 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p1["id"],
        "role_template_id": ROLE_VP, "is_primary": True, "is_active": True,
    })
    assert r1.status_code == 201

    r2 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p2["id"],
        "role_template_id": ROLE_VP, "is_primary": True, "is_active": True,
    })
    assert r2.status_code == 409


async def test_non_primary_rows_still_allowed(client: AsyncClient):
    """Multiple non-primary rows for the same project+role are fine."""
    proj = await _project(client)
    p1 = await _person(client)
    p2 = await _person(client)
    p3 = await _person(client)

    # One primary
    r1 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p1["id"],
        "role_template_id": ROLE_ACCOUNTANT, "is_primary": True,
    })
    assert r1.status_code == 201

    # Two non-primaries — both should succeed
    r2 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p2["id"],
        "role_template_id": ROLE_ACCOUNTANT, "is_primary": False,
    })
    assert r2.status_code == 201

    r3 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p3["id"],
        "role_template_id": ROLE_ACCOUNTANT, "is_primary": False,
    })
    assert r3.status_code == 201


async def test_inactive_primary_does_not_block(client: AsyncClient):
    """An inactive former primary does not block a new active primary."""
    proj = await _project(client)
    p1 = await _person(client)
    p2 = await _person(client)

    # First primary, then deactivate
    r1 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p1["id"],
        "role_template_id": ROLE_VP, "is_primary": True, "is_active": True,
    })
    assert r1.status_code == 201
    m1_id = r1.json()["id"]

    # Deactivate the first primary
    r_deactivate = await client.patch(f"/api/project-members/{m1_id}", json={"is_active": False})
    assert r_deactivate.status_code == 200

    # New active primary should succeed
    r2 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p2["id"],
        "role_template_id": ROLE_VP, "is_primary": True, "is_active": True,
    })
    assert r2.status_code == 201


async def test_different_roles_can_both_have_primaries(client: AsyncClient):
    """Different roles on the same project can each have an active primary."""
    proj = await _project(client)
    p1 = await _person(client)
    p2 = await _person(client)

    r1 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p1["id"],
        "role_template_id": ROLE_VP, "is_primary": True,
    })
    assert r1.status_code == 201

    r2 = await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p2["id"],
        "role_template_id": ROLE_ACCOUNTANT, "is_primary": True,
    })
    assert r2.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════
# Assignment resolver still works
# ═══════════════════════════════════════════════════════════════════════════

async def test_assignment_resolver_uses_guaranteed_primary(client: AsyncClient):
    """With the integrity rule, resolve_project_member_for_role always finds exactly one primary."""
    proj = await _project(client)
    p_vp = await _person(client)
    p_acct = await _person(client)

    await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p_vp["id"],
        "role_template_id": ROLE_VP, "is_primary": True,
    })
    await client.post("/api/project-members/", json={
        "project_id": proj["id"], "person_id": p_acct["id"],
        "role_template_id": ROLE_ACCOUNTANT, "is_primary": True,
    })

    # Create checklist from template — VP and accountant items should resolve
    r = await client.post("/api/closeout-checklists/from-template", json={
        "project_id": proj["id"],
        "template_id": TEMPLATE_STANDARD,
    })
    assert r.status_code == 201
    cl_id = r.json()["id"]

    items = await client.get(f"/api/closeout-checklist-items/?checklist_id={cl_id}&limit=200")
    data = items.json()

    # VP items should resolve to p_vp
    vp_item = next(i for i in data if i["item_number"] == 4 and i["category"] == "documentation")
    assert vp_item["assigned_person_id"] == p_vp["id"]

    # Accountant items should resolve to p_acct
    acct_item = next(i for i in data if i["item_number"] == 2 and i["category"] == "documentation")
    assert acct_item["assigned_person_id"] == p_acct["id"]

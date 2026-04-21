"""Foundation smoke tests.

Requires a running PostgreSQL with seeded rex_os database.
Run: cd backend && pytest tests/ -v
"""

import uuid

from httpx import AsyncClient

# ── Deterministic UUIDs from foundation bootstrap seed ──
PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
PROJECT_LAKEWOOD = "40000000-0000-4000-a000-000000000002"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
PERSON_MITCH = "10000000-0000-4000-a000-000000000002"
ROLE_VP = "30000000-0000-4000-a000-000000000001"
MEMBER_BISHOP_ROBERTS = "50000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


# ═══════════════════════════════════════════════════════════════════════════
# Projects
# ═══════════════════════════════════════════════════════════════════════════

async def test_list_projects(client: AsyncClient):
    r = await client.get("/api/projects/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 4
    names = {p["name"] for p in data}
    assert "Bishop Modern" in names


async def test_get_project(client: AsyncClient):
    r = await client.get(f"/api/projects/{PROJECT_BISHOP}")
    assert r.status_code == 200
    assert r.json()["name"] == "Bishop Modern"
    assert r.json()["project_type"] == "multifamily"


async def test_get_project_not_found(client: AsyncClient):
    r = await client.get(f"/api/projects/{BOGUS_UUID}")
    assert r.status_code == 404


async def test_create_project(client: AsyncClient):
    r = await client.post("/api/projects/", json={
        "name": "Smoke Test Project",
        "status": "pre_construction",
        "project_type": "commercial",
        "city": "Austin",
        "state": "TX",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Smoke Test Project"
    assert "id" in body
    assert "created_at" in body


async def test_patch_project(client: AsyncClient):
    r = await client.patch(f"/api/projects/{PROJECT_LAKEWOOD}", json={
        "description": "patched by smoke test",
    })
    assert r.status_code == 200
    assert r.json()["description"] == "patched by smoke test"


# ═══════════════════════════════════════════════════════════════════════════
# Companies
# ═══════════════════════════════════════════════════════════════════════════

async def test_list_companies(client: AsyncClient):
    r = await client.get("/api/companies/")
    assert r.status_code == 200
    assert len(r.json()) >= 2


async def test_get_company(client: AsyncClient):
    r = await client.get(f"/api/companies/{COMPANY_REX}")
    assert r.status_code == 200
    assert r.json()["name"] == "Rex Construction"
    assert r.json()["company_type"] == "gc"


async def test_create_company(client: AsyncClient):
    # rex.companies.name is UNIQUE (migration 027), so the test must use
    # a unique-per-run name to stay idempotent across re-runs on a shared
    # dev DB. Suffix with a short uuid to stay deterministic within a
    # single test run while not colliding with prior runs' residue.
    unique_name = f"Smoke Electric Co {uuid.uuid4().hex[:8]}"
    r = await client.post("/api/companies/", json={
        "name": unique_name,
        "company_type": "subcontractor",
        "trade": "electrical",
    })
    assert r.status_code == 201
    assert r.json()["trade"] == "electrical"


async def test_patch_company(client: AsyncClient):
    r = await client.patch(f"/api/companies/{COMPANY_REX}", json={
        "phone": "214-555-0100",
    })
    assert r.status_code == 200
    assert r.json()["phone"] == "214-555-0100"


# ═══════════════════════════════════════════════════════════════════════════
# People
# ═══════════════════════════════════════════════════════════════════════════

async def test_list_people(client: AsyncClient):
    r = await client.get("/api/people/")
    assert r.status_code == 200
    assert len(r.json()) >= 4


async def test_get_person(client: AsyncClient):
    r = await client.get(f"/api/people/{PERSON_ROBERTS}")
    assert r.status_code == 200
    assert r.json()["first_name"] == "Andrew"
    assert r.json()["last_name"] == "Roberts"


async def test_create_person(client: AsyncClient):
    r = await client.post("/api/people/", json={
        "first_name": "Smoke",
        "last_name": "Tester",
        "role_type": "external",
    })
    assert r.status_code == 201
    assert r.json()["role_type"] == "external"


async def test_patch_person(client: AsyncClient):
    r = await client.patch(f"/api/people/{PERSON_ROBERTS}", json={
        "phone": "214-555-0001",
    })
    assert r.status_code == 200
    assert r.json()["phone"] == "214-555-0001"


# ═══════════════════════════════════════════════════════════════════════════
# Role Templates
# ═══════════════════════════════════════════════════════════════════════════

async def test_list_role_templates(client: AsyncClient):
    r = await client.get("/api/role-templates/")
    assert r.status_code == 200
    slugs = {t["slug"] for t in r.json()}
    assert {"vp", "pm", "general_super", "lead_super", "asst_super", "accountant"} <= slugs


async def test_get_role_template(client: AsyncClient):
    r = await client.get(f"/api/role-templates/{ROLE_VP}")
    assert r.status_code == 200
    assert r.json()["slug"] == "vp"


async def test_create_role_template(client: AsyncClient):
    unique_slug = f"smoke_role_{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/role-templates/", json={
        "name": "Smoke Role",
        "slug": unique_slug,
        "default_access_level": "read_only",
    })
    assert r.status_code == 201
    assert r.json()["slug"] == unique_slug


async def test_patch_role_template(client: AsyncClient):
    r = await client.patch(f"/api/role-templates/{ROLE_VP}", json={
        "description": "patched by smoke test",
    })
    assert r.status_code == 200
    assert r.json()["description"] == "patched by smoke test"


# ═══════════════════════════════════════════════════════════════════════════
# Project Members
# ═══════════════════════════════════════════════════════════════════════════

async def test_list_project_members(client: AsyncClient):
    r = await client.get("/api/project-members/")
    assert r.status_code == 200
    assert len(r.json()) >= 16


async def test_get_project_member(client: AsyncClient):
    r = await client.get(f"/api/project-members/{MEMBER_BISHOP_ROBERTS}")
    assert r.status_code == 200
    assert r.json()["project_id"] == PROJECT_BISHOP
    assert r.json()["person_id"] == PERSON_ROBERTS


async def test_create_project_member(client: AsyncClient):
    # First create a fresh project + person to avoid unique constraint
    proj = await client.post("/api/projects/", json={
        "name": "Member Test Project",
        "status": "active",
    })
    person = await client.post("/api/people/", json={
        "first_name": "Member",
        "last_name": "Test",
        "role_type": "external",
    })
    r = await client.post("/api/project-members/", json={
        "project_id": proj.json()["id"],
        "person_id": person.json()["id"],
        "access_level": "read_only",
    })
    assert r.status_code == 201


async def test_patch_project_member(client: AsyncClient):
    r = await client.patch(f"/api/project-members/{MEMBER_BISHOP_ROBERTS}", json={
        "is_primary": True,
    })
    assert r.status_code == 200
    assert r.json()["is_primary"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Connector Mappings
# ═══════════════════════════════════════════════════════════════════════════

async def test_list_connector_mappings(client: AsyncClient):
    r = await client.get("/api/connector-mappings/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 5
    tables = {m["rex_table"] for m in data}
    assert "projects" in tables
    assert "people" in tables


async def test_get_connector_mapping(client: AsyncClient):
    r = await client.get("/api/connector-mappings/")
    first_id = r.json()[0]["id"]
    r2 = await client.get(f"/api/connector-mappings/{first_id}")
    assert r2.status_code == 200
    assert r2.json()["connector"] == "procore"


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════

async def test_duplicate_project_member_returns_409(client: AsyncClient):
    """Inserting the same (project_id, person_id) twice should 409."""
    r = await client.post("/api/project-members/", json={
        "project_id": PROJECT_BISHOP,
        "person_id": PERSON_ROBERTS,
    })
    # Already seeded — should conflict
    assert r.status_code == 409


async def test_not_found_returns_404(client: AsyncClient):
    r = await client.get(f"/api/companies/{BOGUS_UUID}")
    assert r.status_code == 404


async def test_invalid_fk_returns_422(client: AsyncClient):
    """Creating a project_member with a bogus person_id should 422."""
    r = await client.post("/api/project-members/", json={
        "project_id": PROJECT_BISHOP,
        "person_id": BOGUS_UUID,
    })
    assert r.status_code == 422

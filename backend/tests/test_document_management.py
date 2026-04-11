"""Document Management domain smoke tests.

Uses seeded Bishop Modern project.
Builds: drawing_area -> drawing -> revision, spec, rfi, submittal_package -> submittal, attachment, correspondence.
"""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _area(c: AsyncClient, **kw) -> dict:
    p = {"project_id": PROJECT_BISHOP, "name": f"Area-{_uid()}"}
    p.update(kw)
    r = await c.post("/api/drawing-areas/", json=p)
    assert r.status_code == 201, r.text
    return r.json()

async def _drawing(c: AsyncClient, area_id: str, **kw) -> dict:
    p = {"project_id": PROJECT_BISHOP, "drawing_area_id": area_id, "drawing_number": f"A-{_uid()}", "title": f"Dwg-{_uid()}", "discipline": "architectural"}
    p.update(kw)
    r = await c.post("/api/drawings/", json=p)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Drawing Areas
# ═══════════════════════════════════════════════════════════════════════════

async def test_drawing_area_crud(client: AsyncClient):
    area = await _area(client)
    r = await client.get(f"/api/drawing-areas/{area['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/drawing-areas/{area['id']}", json={"name": "Patched"})
    assert r.status_code == 200
    assert r.json()["name"] == "Patched"

async def test_list_drawing_areas(client: AsyncClient):
    r = await client.get(f"/api/drawing-areas/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Drawings
# ═══════════════════════════════════════════════════════════════════════════

async def test_drawing_crud(client: AsyncClient):
    area = await _area(client)
    dwg = await _drawing(client, area["id"])
    r = await client.get(f"/api/drawings/{dwg['id']}")
    assert r.status_code == 200
    r = await client.patch(f"/api/drawings/{dwg['id']}", json={"title": "Updated", "is_current": False})
    assert r.status_code == 200
    assert r.json()["is_current"] is False

async def test_list_drawings(client: AsyncClient):
    r = await client.get(f"/api/drawings/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_drawing_invalid_discipline(client: AsyncClient):
    area = await _area(client)
    r = await client.post("/api/drawings/", json={"project_id": PROJECT_BISHOP, "drawing_area_id": area["id"], "drawing_number": "X-1", "title": "Bad", "discipline": "bogus"})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Drawing Revisions
# ═══════════════════════════════════════════════════════════════════════════

async def test_drawing_revision_crud(client: AsyncClient):
    area = await _area(client)
    dwg = await _drawing(client, area["id"])
    r = await client.post("/api/drawing-revisions/", json={"drawing_id": dwg["id"], "revision_number": 1, "revision_date": "2025-06-01", "image_url": f"https://r2.example.com/{_uid()}.pdf"})
    assert r.status_code == 201
    rev_id = r.json()["id"]
    r = await client.get(f"/api/drawing-revisions/{rev_id}")
    assert r.status_code == 200

async def test_list_drawing_revisions(client: AsyncClient):
    r = await client.get("/api/drawing-revisions/")
    assert r.status_code == 200

async def test_drawing_revision_bad_fk(client: AsyncClient):
    r = await client.post("/api/drawing-revisions/", json={"drawing_id": BOGUS_UUID, "revision_number": 1, "revision_date": "2025-06-01", "image_url": "https://example.com/x.pdf"})
    assert r.status_code in (404, 422)  # write-scope resolves parent first → 404


# ═══════════════════════════════════════════════════════════════════════════
# Specifications
# ═══════════════════════════════════════════════════════════════════════════

async def test_specification_crud(client: AsyncClient):
    r = await client.post("/api/specifications/", json={"project_id": PROJECT_BISHOP, "section_number": f"03-{_uid()[:3]}", "title": f"Spec-{_uid()}", "division": "Division 03"})
    assert r.status_code == 201
    sid = r.json()["id"]
    r = await client.get(f"/api/specifications/{sid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/specifications/{sid}", json={"current_revision": 2})
    assert r.status_code == 200

async def test_list_specifications(client: AsyncClient):
    r = await client.get(f"/api/specifications/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# RFIs
# ═══════════════════════════════════════════════════════════════════════════

async def test_rfi_crud(client: AsyncClient):
    r = await client.post("/api/rfis/", json={"project_id": PROJECT_BISHOP, "rfi_number": f"RFI-{_uid()}", "subject": f"Subject-{_uid()}", "question": "What is the specified finish?"})
    assert r.status_code == 201
    rfi_id = r.json()["id"]
    r = await client.get(f"/api/rfis/{rfi_id}")
    assert r.status_code == 200
    r = await client.patch(f"/api/rfis/{rfi_id}", json={"status": "open", "answer": "Per spec section 09 91 00"})
    assert r.status_code == 200
    assert r.json()["answer"] is not None

async def test_list_rfis(client: AsyncClient):
    r = await client.get(f"/api/rfis/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_rfi_bad_fk(client: AsyncClient):
    r = await client.post("/api/rfis/", json={"project_id": BOGUS_UUID, "rfi_number": "BAD", "subject": "Bad", "question": "Bad?"})
    assert r.status_code == 422

async def test_rfi_invalid_status(client: AsyncClient):
    r = await client.post("/api/rfis/", json={"project_id": PROJECT_BISHOP, "rfi_number": "BAD", "subject": "Bad", "question": "Q?", "status": "bogus"})
    assert r.status_code == 422

async def test_rfi_invalid_priority(client: AsyncClient):
    r = await client.post("/api/rfis/", json={"project_id": PROJECT_BISHOP, "rfi_number": "BAD", "subject": "Bad", "question": "Q?", "priority": "bogus"})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Submittal Packages + Submittals
# ═══════════════════════════════════════════════════════════════════════════

async def test_submittal_package_crud(client: AsyncClient):
    r = await client.post("/api/submittal-packages/", json={"project_id": PROJECT_BISHOP, "package_number": f"SP-{_uid()}", "title": f"Pkg-{_uid()}"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = await client.get(f"/api/submittal-packages/{pid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/submittal-packages/{pid}", json={"status": "closed"})
    assert r.status_code == 200

async def test_list_submittal_packages(client: AsyncClient):
    r = await client.get(f"/api/submittal-packages/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_submittal_crud(client: AsyncClient):
    r = await client.post("/api/submittals/", json={"project_id": PROJECT_BISHOP, "submittal_number": f"SUB-{_uid()}", "title": f"Sub-{_uid()}", "submittal_type": "shop_drawing"})
    assert r.status_code == 201
    sid = r.json()["id"]
    r = await client.get(f"/api/submittals/{sid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/submittals/{sid}", json={"status": "submitted"})
    assert r.status_code == 200

async def test_list_submittals(client: AsyncClient):
    r = await client.get(f"/api/submittals/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_submittal_bad_fk(client: AsyncClient):
    r = await client.post("/api/submittals/", json={"project_id": BOGUS_UUID, "submittal_number": "BAD", "title": "Bad", "submittal_type": "shop_drawing"})
    assert r.status_code == 422

async def test_submittal_invalid_type(client: AsyncClient):
    r = await client.post("/api/submittals/", json={"project_id": PROJECT_BISHOP, "submittal_number": "BAD", "title": "Bad", "submittal_type": "bogus"})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Attachments
# ═══════════════════════════════════════════════════════════════════════════

async def test_attachment_crud(client: AsyncClient):
    r = await client.post("/api/attachments/", json={"project_id": PROJECT_BISHOP, "source_type": "rfi", "source_id": "00000000-0000-0000-0000-000000000099", "filename": f"doc-{_uid()}.pdf", "file_size": 1024, "content_type": "application/pdf", "storage_url": f"https://r2.example.com/{_uid()}", "storage_key": f"attachments/{_uid()}"})
    assert r.status_code == 201
    aid = r.json()["id"]
    r = await client.get(f"/api/attachments/{aid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/attachments/{aid}", json={"filename": "renamed.pdf"})
    assert r.status_code == 200

async def test_list_attachments(client: AsyncClient):
    r = await client.get(f"/api/attachments/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Correspondence
# ═══════════════════════════════════════════════════════════════════════════

async def test_correspondence_crud(client: AsyncClient):
    r = await client.post("/api/correspondence/", json={"project_id": PROJECT_BISHOP, "correspondence_number": f"COR-{_uid()}", "subject": f"Re: {_uid()}", "correspondence_type": "letter"})
    assert r.status_code == 201
    cid = r.json()["id"]
    r = await client.get(f"/api/correspondence/{cid}")
    assert r.status_code == 200
    r = await client.patch(f"/api/correspondence/{cid}", json={"status": "sent", "sent_date": "2025-07-01"})
    assert r.status_code == 200

async def test_list_correspondence(client: AsyncClient):
    r = await client.get(f"/api/correspondence/?project_id={PROJECT_BISHOP}")
    assert r.status_code == 200

async def test_correspondence_invalid_type(client: AsyncClient):
    r = await client.post("/api/correspondence/", json={"project_id": PROJECT_BISHOP, "correspondence_number": "BAD", "subject": "Bad", "correspondence_type": "bogus"})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════

async def test_not_found_404(client: AsyncClient):
    for path in ["/api/drawings/", "/api/rfis/", "/api/submittals/", "/api/correspondence/"]:
        r = await client.get(f"{path}{BOGUS_UUID}")
        assert r.status_code == 404, f"{path} should 404"

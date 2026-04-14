"""Photo metadata PATCH + upload tests.

Phase 51 release-convergence regression coverage for the PhotoUpdate schema
expansion. Previously the PhotoUpdate schema only accepted
album/description/tags/location — the frontend sent filename/taken_at/
latitude/longitude too, but Pydantic silently dropped them, so metadata
edits from the UI were lossy.

These tests lock in:
  - /api/photos/upload creates a Photo row with the image storage path
  - PATCH /api/photos/{id} persists the newly-allowed fields end-to-end
"""

import uuid
from datetime import datetime, timezone

from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _upload_photo(client: AsyncClient) -> dict:
    files = {"file": (f"site-{_uid()}.jpg", b"\xff\xd8\xff\xe0 fake jpeg body", "image/jpeg")}
    data = {"project_id": PROJECT_BISHOP}
    r = await client.post("/api/photos/upload", data=data, files=files)
    assert r.status_code == 201, r.text
    return r.json()


async def test_photo_upload_creates_row(client: AsyncClient):
    body = await _upload_photo(client)
    assert body["project_id"] == PROJECT_BISHOP
    assert body["filename"].startswith("site-")
    assert body["content_type"] == "image/jpeg"
    assert body["file_size"] > 0
    assert body["storage_key"]
    assert body["storage_url"]


async def test_photo_upload_rejects_non_image(client: AsyncClient):
    files = {"file": ("doc.pdf", b"%PDF-1.4 not really", "application/pdf")}
    data = {"project_id": PROJECT_BISHOP}
    r = await client.post("/api/photos/upload", data=data, files=files)
    assert r.status_code == 415
    assert "image" in r.json()["detail"].lower()


async def test_photo_upload_rejects_empty_file(client: AsyncClient):
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    data = {"project_id": PROJECT_BISHOP}
    r = await client.post("/api/photos/upload", data=data, files=files)
    assert r.status_code == 422


async def test_photo_patch_persists_all_metadata_fields(client: AsyncClient):
    """Regression: filename/taken_at/latitude/longitude were silently dropped
    until PhotoUpdate was expanded. Guarantee they survive a PATCH."""
    original = await _upload_photo(client)
    photo_id = original["id"]

    taken = datetime(2026, 3, 14, 9, 30, 0, tzinfo=timezone.utc).isoformat()
    payload = {
        "filename": "renamed-by-patch.jpg",
        "taken_at": taken,
        "latitude": 40.7128,
        "longitude": -74.0060,
        "description": "north elevation after rough-in",
        "location": "3rd floor",
    }
    r = await client.patch(f"/api/photos/{photo_id}", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["filename"] == "renamed-by-patch.jpg"
    assert body["taken_at"].startswith("2026-03-14")
    assert float(body["latitude"]) == 40.7128
    assert float(body["longitude"]) == -74.0060
    assert body["description"] == "north elevation after rough-in"
    assert body["location"] == "3rd floor"


async def test_photo_patch_partial_update_preserves_others(client: AsyncClient):
    """Sanity: setting only one field does not wipe the others thanks to
    exclude_unset=True in the service update path."""
    original = await _upload_photo(client)
    photo_id = original["id"]

    # First PATCH — set description + location
    await client.patch(
        f"/api/photos/{photo_id}",
        json={"description": "initial note", "location": "lobby"},
    )
    # Second PATCH — only touch filename
    r = await client.patch(
        f"/api/photos/{photo_id}",
        json={"filename": "renamed-second.jpg"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "renamed-second.jpg"
    # Prior fields must survive
    assert body["description"] == "initial note"
    assert body["location"] == "lobby"


async def test_photo_patch_accepts_date_only_taken_at(client: AsyncClient):
    """DateField in the UI emits YYYY-MM-DD; Pydantic should accept it for
    the datetime field and store midnight UTC."""
    original = await _upload_photo(client)
    r = await client.patch(
        f"/api/photos/{original['id']}",
        json={"taken_at": "2026-04-01"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["taken_at"].startswith("2026-04-01")

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


async def test_photo_bytes_endpoint_serves_uploaded_content(real_auth_client: AsyncClient):
    """Regression: without this route, <img src={storage_url}> would try
    to fetch a scheme identifier like ``local://...`` and render broken.
    The bytes endpoint is what makes the Photos page actually display.

    Uses ``real_auth_client`` so header + query auth paths are exercised
    end-to-end with a real token — the bytes endpoint does manual auth
    parsing, not ``Depends(get_current_user)``, so the default stub
    override doesn't apply.
    """
    # Get a real token via login
    r = await real_auth_client.post(
        "/api/auth/login",
        json={"email": "aroberts@exxircapital.com", "password": "rex2026!"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Upload a photo via the upload endpoint so we know the bytes exist.
    unique_marker = f"BYTES-{_uid()}"
    body_bytes = b"\xff\xd8\xff\xe0FAKE-JPEG-BYTES-" + unique_marker.encode()
    files = {"file": ("sample.jpg", body_bytes, "image/jpeg")}
    data = {"project_id": PROJECT_BISHOP}
    r = await real_auth_client.post(
        "/api/photos/upload", data=data, files=files, headers=auth_headers
    )
    assert r.status_code == 201, r.text
    photo = r.json()

    # 1) Header auth path
    r2 = await real_auth_client.get(
        f"/api/photos/{photo['id']}/bytes", headers=auth_headers
    )
    assert r2.status_code == 200, r2.text
    assert r2.headers["content-type"].startswith("image/jpeg")
    assert r2.content == body_bytes
    assert r2.headers.get("cache-control") == "private, max-age=300"
    assert "sample.jpg" in r2.headers.get("content-disposition", "")

    # 2) Query-param auth path — what <img src=?token=...> actually uses
    r3 = await real_auth_client.get(f"/api/photos/{photo['id']}/bytes?token={token}")
    assert r3.status_code == 200, r3.text
    assert r3.content == body_bytes

    # 3) No auth → 401
    r4 = await real_auth_client.get(f"/api/photos/{photo['id']}/bytes")
    assert r4.status_code == 401

    # 4) Bogus token → 401
    r5 = await real_auth_client.get(
        f"/api/photos/{photo['id']}/bytes?token=not-a-real-token"
    )
    assert r5.status_code == 401


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

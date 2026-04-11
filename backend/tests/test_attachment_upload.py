"""Attachment upload + storage boundary tests.

Uses the temp storage path set in conftest.py via REX_STORAGE_PATH.
The default test client is auto-authenticated as the stub admin.
"""

import os
import uuid
from pathlib import Path

from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def test_upload_creates_attachment_row(client: AsyncClient):
    file_content = b"PDF binary content here -- test fixture"
    files = {"file": (f"spec-{_uid()}.pdf", file_content, "application/pdf")}
    data = {
        "project_id": PROJECT_BISHOP,
        "source_type": "rfi",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["project_id"] == PROJECT_BISHOP
    assert body["source_type"] == "rfi"
    assert body["filename"].startswith("spec-")
    assert body["file_size"] == len(file_content)
    assert body["content_type"] == "application/pdf"
    assert body["storage_url"].startswith("local://")
    assert body["storage_key"].startswith("attachments/")


async def test_upload_persists_to_storage(client: AsyncClient):
    file_content = b"actual file body for storage check"
    files = {"file": (f"doc-{_uid()}.txt", file_content, "text/plain")}
    data = {
        "project_id": PROJECT_BISHOP,
        "source_type": "submittal",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 201

    storage_root = Path(os.environ["REX_STORAGE_PATH"])
    storage_key = r.json()["storage_key"]
    persisted = storage_root / storage_key
    assert persisted.is_file()
    assert persisted.read_bytes() == file_content


async def test_upload_rejects_empty_file(client: AsyncClient):
    files = {"file": ("empty.txt", b"", "text/plain")}
    data = {
        "project_id": PROJECT_BISHOP,
        "source_type": "rfi",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 422
    assert "empty" in r.json()["detail"].lower()


async def test_upload_rejects_missing_project_id(client: AsyncClient):
    files = {"file": ("doc.txt", b"content", "text/plain")}
    data = {"source_type": "rfi", "source_id": str(uuid.uuid4())}
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 422  # Pydantic / form validation


async def test_upload_metadata_returned_correctly(client: AsyncClient):
    file_content = b"x" * 1024  # 1KB
    files = {"file": ("photo.jpg", file_content, "image/jpeg")}
    data = {
        "project_id": PROJECT_BISHOP,
        "source_type": "punch_item",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    body = r.json()
    assert body["file_size"] == 1024
    assert body["content_type"] == "image/jpeg"
    assert body["filename"] == "photo.jpg"
    # uploaded_by populated from auth context (stub admin -> Andrew Roberts person_id)
    assert body["uploaded_by"] == "10000000-0000-4000-a000-000000000001"


async def test_upload_then_download(client: AsyncClient):
    file_content = b"round-trip content"
    files = {"file": ("rt.bin", file_content, "application/octet-stream")}
    data = {
        "project_id": PROJECT_BISHOP,
        "source_type": "rfi",
        "source_id": str(uuid.uuid4()),
    }
    upload = await client.post("/api/attachments/upload", data=data, files=files)
    aid = upload.json()["id"]

    r = await client.get(f"/api/attachments/{aid}/download")
    assert r.status_code == 200
    assert r.content == file_content
    assert r.headers["content-type"].startswith("application/octet-stream")


async def test_download_404_when_attachment_missing(client: AsyncClient):
    r = await client.get(f"/api/attachments/{BOGUS_UUID}/download")
    assert r.status_code == 404

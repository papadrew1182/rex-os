"""Sprint E: security and operability hardening tests.

Covers:
- Attachment download authorization (401, 403, 200, 404 missing-file)
- Attachment upload project-scoped enforcement
- Project-scoped helper (member allowed, non-member denied, admin bypass)
- Mutating routes require auth (smoke check across representative endpoints)
- Expired session token rejection
- Storage path traversal safety (LocalStorageAdapter)

Note: ``client`` is auto-authenticated as the stub admin via a global
dependency override. To test the *real* auth flow we temporarily pop that
override using ``_no_auth_override``. Tests that need both setup-as-admin
and a subsequent real-auth request use ``client`` for setup, then enter the
context manager to make the real call.
"""

import contextlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from httpx import AsyncClient

from app.dependencies import get_current_user
from app.services.auth import hash_token
from app.services.storage import LocalStorageAdapter
from main import app
from tests.helpers import PROJECT_BISHOP, uid

ADMIN_EMAIL = "aroberts@exxircapital.com"
NON_ADMIN_EMAIL = "mandersen@exxircapital.com"  # member of Bishop, no global role
PASSWORD = "rex2026!"


@contextlib.contextmanager
def _no_auth_override():
    """Temporarily remove the stub-admin override so requests hit the real auth flow."""
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def _login_token(client: AsyncClient, email: str, password: str = PASSWORD) -> str:
    """Login using the real flow. Caller must already be inside ``_no_auth_override``."""
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


async def _upload_to_project(
    client: AsyncClient, project_id: str, content: bytes = b"sprint-e payload"
) -> str:
    files = {"file": (f"sec-{uid()}.bin", content, "application/octet-stream")}
    data = {
        "project_id": project_id,
        "source_type": "rfi",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_orphan_project(client: AsyncClient) -> str:
    """Create a fresh project with no members so non-admins are denied."""
    r = await client.post(
        "/api/projects/",
        json={
            "project_number": f"SEC-{uid()}",
            "name": f"SprintE-Orphan-{uid()}",
            "status": "active",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Attachment download authorization ──────────────────────────────────────


async def test_download_unauthenticated_returns_401(client: AsyncClient):
    """No auth header → 401, never reaches the storage layer."""
    aid = await _upload_to_project(client, PROJECT_BISHOP)
    with _no_auth_override():
        r = await client.get(f"/api/attachments/{aid}/download")
    assert r.status_code == 401


async def test_download_non_member_returns_403(client: AsyncClient):
    """Non-admin user with no project membership is denied."""
    orphan_project = await _create_orphan_project(client)
    aid = await _upload_to_project(client, orphan_project)

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(
            f"/api/attachments/{aid}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 403


async def test_download_member_returns_200(client: AsyncClient):
    """Mitch is a member of Bishop with standard access — download succeeds."""
    payload = b"member-can-download"
    aid = await _upload_to_project(client, PROJECT_BISHOP, content=payload)

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(
            f"/api/attachments/{aid}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.content == payload


async def test_download_admin_bypass_returns_200(client: AsyncClient):
    """Admin/VP bypass project membership requirement entirely."""
    orphan_project = await _create_orphan_project(client)
    payload = b"admin-bypass-payload"
    aid = await _upload_to_project(client, orphan_project, content=payload)

    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)
        r = await client.get(
            f"/api/attachments/{aid}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.content == payload


async def test_download_missing_backing_file_returns_404(client: AsyncClient):
    """Auth+authz pass, but the file is gone from disk → safe 404, no traceback."""
    aid = await _upload_to_project(client, PROJECT_BISHOP)
    # Look up storage_key, then nuke the file from disk
    meta = await client.get(f"/api/attachments/{aid}")
    storage_key = meta.json()["storage_key"]
    storage_root = Path(os.environ["REX_STORAGE_PATH"])
    (storage_root / storage_key).unlink()

    r = await client.get(f"/api/attachments/{aid}/download")
    assert r.status_code == 404
    assert "missing" in r.json()["detail"].lower()


# ── Attachment upload authorization ────────────────────────────────────────


async def test_upload_non_member_returns_403(client: AsyncClient):
    """Non-member uploader gets 403 even with valid auth."""
    orphan_project = await _create_orphan_project(client)

    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        files = {"file": (f"reject-{uid()}.txt", b"data", "text/plain")}
        data = {
            "project_id": orphan_project,
            "source_type": "rfi",
            "source_id": str(uuid.uuid4()),
        }
        r = await client.post(
            "/api/attachments/upload",
            data=data,
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 403


async def test_upload_member_with_field_access_succeeds(client: AsyncClient):
    """Mitch (Bishop standard member) can upload to Bishop."""
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        files = {"file": (f"ok-{uid()}.txt", b"member upload", "text/plain")}
        data = {
            "project_id": PROJECT_BISHOP,
            "source_type": "rfi",
            "source_id": str(uuid.uuid4()),
        }
        r = await client.post(
            "/api/attachments/upload",
            data=data,
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 201, r.text


# ── Mutating-route auth smoke checks ───────────────────────────────────────


async def test_mutating_routes_require_auth(client: AsyncClient):
    """Representative subset of POST/PATCH routes return 401 unauthenticated."""
    bogus = str(uuid.uuid4())
    requests = [
        ("POST", "/api/projects/", {"project_number": "x", "name": "x", "status": "active"}),
        ("POST", "/api/people/", {"first_name": "x", "last_name": "x", "role_type": "internal"}),
        ("POST", "/api/companies/", {"name": "x", "company_type": "subcontractor"}),
        ("POST", "/api/rfis/", {"project_id": bogus, "rfi_number": "1", "subject": "x"}),
        ("POST", "/api/submittals/", {"project_id": bogus, "submittal_number": "1", "title": "x"}),
        ("POST", "/api/tasks/", {"project_id": bogus, "title": "x"}),
        ("POST", "/api/daily-logs/", {"project_id": bogus, "log_date": "2026-01-01"}),
        ("POST", "/api/inspections/", {"project_id": bogus, "inspection_type": "x"}),
        ("POST", "/api/punch-items/", {"project_id": bogus, "title": "x"}),
        ("POST", "/api/schedules/", {"project_id": bogus, "name": "x"}),
        ("POST", "/api/budget-line-items/", {"project_id": bogus, "cost_code_id": bogus, "amount": 0}),
        ("POST", "/api/commitments/", {"project_id": bogus, "vendor_id": bogus}),
        ("PATCH", f"/api/projects/{bogus}", {"name": "x"}),
        ("PATCH", f"/api/rfis/{bogus}", {"subject": "x"}),
        ("PATCH", f"/api/tasks/{bogus}", {"title": "x"}),
    ]
    with _no_auth_override():
        for method, path, body in requests:
            r = await client.request(method, path, json=body)
            assert r.status_code == 401, f"{method} {path} returned {r.status_code}, expected 401"


# ── Expired session rejection ──────────────────────────────────────────────


async def test_expired_session_token_rejected(client: AsyncClient):
    """A session row whose expires_at is in the past must not authenticate."""
    import db as legacy_db

    raw_token = f"expired-{uid()}-{uuid.uuid4().hex}"
    token_hash = hash_token(raw_token)
    expired_at = datetime.now(timezone.utc) - timedelta(days=1)

    pool = await legacy_db.get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT id FROM rex.user_accounts WHERE email = $1", ADMIN_EMAIL
        )
        await conn.execute(
            "INSERT INTO rex.sessions (user_account_id, token_hash, expires_at) "
            "VALUES ($1::uuid, $2, $3)",
            user_id, token_hash, expired_at,
        )

    with _no_auth_override():
        r = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {raw_token}"}
        )
    assert r.status_code == 401


async def test_expired_session_cleanup_runs(client: AsyncClient):
    """After a successful login, opportunistic cleanup removes the expired row."""
    import db as legacy_db
    from app.services import auth as auth_svc

    raw_token = f"expired2-{uid()}-{uuid.uuid4().hex}"
    token_hash = hash_token(raw_token)
    expired_at = datetime.now(timezone.utc) - timedelta(days=2)

    pool = await legacy_db.get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT id FROM rex.user_accounts WHERE email = $1", ADMIN_EMAIL
        )
        await conn.execute(
            "INSERT INTO rex.sessions (user_account_id, token_hash, expires_at) "
            "VALUES ($1::uuid, $2, $3)",
            user_id, token_hash, expired_at,
        )

    # Force the throttle to run
    auth_svc._last_expired_cleanup = None

    with _no_auth_override():
        fresh_token = await _login_token(client, ADMIN_EMAIL)
        r = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {fresh_token}"}
        )
    assert r.status_code == 200

    async with pool.acquire() as conn:
        still_there = await conn.fetchval(
            "SELECT 1 FROM rex.sessions WHERE token_hash = $1", token_hash
        )
    assert still_there is None, "Expired session row should have been cleaned up"


# ── Storage path traversal safety ──────────────────────────────────────────


def test_storage_rejects_path_traversal(tmp_path: Path):
    adapter = LocalStorageAdapter(tmp_path / "store")

    # Save legitimate content first so the root exists
    adapter.save(b"ok", "attachments/proj/file.bin")

    # Read with traversal key must NOT escape the root
    try:
        adapter.read("../../../etc/passwd")
    except (ValueError, FileNotFoundError):
        pass
    else:
        raise AssertionError("read() should refuse traversal keys")

    # Delete with traversal returns False, never touches outside root
    assert adapter.delete("../../../etc/passwd") is False

    # Save with traversal must also fail
    try:
        adapter.save(b"x", "../escape.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("save() should refuse traversal keys")


def test_storage_read_missing_returns_filenotfound(tmp_path: Path):
    adapter = LocalStorageAdapter(tmp_path / "store2")
    try:
        adapter.read("attachments/missing.bin")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("read() should raise FileNotFoundError on missing key")

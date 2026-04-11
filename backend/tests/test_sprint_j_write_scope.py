"""Sprint J: write-side project scoping and frontend integration prep tests.

Covers:
- Project member with standard access can write to their project
- Non-member is denied write (403)
- read_only member is denied write (403)
- field_only member can write field-ops routes
- field_only member is denied financials/closeout writes (standard required)
- Admin bypass on write
- CORS config
- Error shape consistency
"""

import contextlib
import uuid
from datetime import date, datetime, timezone

import bcrypt
from httpx import AsyncClient

from app.dependencies import get_current_user
from main import app, CORS_ORIGINS
from tests.helpers import PROJECT_BISHOP, uid

ADMIN_EMAIL = "aroberts@exxircapital.com"
NON_ADMIN_EMAIL = "mandersen@exxircapital.com"
PASSWORD = "rex2026!"


@contextlib.contextmanager
def _no_auth_override():
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def _login_token(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_orphan_project(client: AsyncClient) -> str:
    r = await client.post(
        "/api/projects/",
        json={"project_number": f"WS-{uid()}", "name": f"WS-Orphan-{uid()}", "status": "active"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_field_only_user(client: AsyncClient, project_id: str) -> str:
    """Create a person + user + project_member with access_level=field_only.

    Returns the email for login.
    """
    import db as legacy_db

    # Create person via API (admin stub is active)
    p = await client.post(
        "/api/people/",
        json={"first_name": "FieldOnly", "last_name": f"User-{uid()}", "role_type": "internal"},
    )
    assert p.status_code == 201, p.text
    person_id = p.json()["id"]

    # Create project_member with field_only access
    m = await client.post(
        "/api/project-members/",
        json={
            "project_id": project_id,
            "person_id": person_id,
            "access_level": "field_only",
            "is_active": True,
        },
    )
    assert m.status_code == 201, m.text

    # Insert user_account via legacy pool
    email = f"fo-{uid()}@test.invalid"
    pw_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    pool = await legacy_db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO rex.user_accounts (person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2, $3, true)",
            person_id, email, pw_hash,
        )
    return email


async def _create_read_only_user(client: AsyncClient, project_id: str) -> str:
    """Create a person + user + project_member with access_level=read_only."""
    import db as legacy_db

    p = await client.post(
        "/api/people/",
        json={"first_name": "ReadOnly", "last_name": f"User-{uid()}", "role_type": "internal"},
    )
    person_id = p.json()["id"]

    m = await client.post(
        "/api/project-members/",
        json={
            "project_id": project_id,
            "person_id": person_id,
            "access_level": "read_only",
            "is_active": True,
        },
    )
    assert m.status_code == 201, m.text

    email = f"ro-{uid()}@test.invalid"
    pw_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    pool = await legacy_db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO rex.user_accounts (person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2, $3, true)",
            person_id, email, pw_hash,
        )
    return email


# ── Standard member can write (field ops) ──────────────────────────────────


async def test_standard_member_can_create_daily_log(client: AsyncClient):
    """Mitch (standard on Bishop) can create a daily log on Bishop."""
    # Use a far-future random date to avoid collision with existing test data
    import random
    year = random.randint(7000, 8999)
    log_date = f"{year}-06-15"
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/daily-logs/",
            json={
                "project_id": PROJECT_BISHOP,
                "log_date": log_date,
                "weather_summary": "sunny",
            },
            headers=_auth(token),
        )
    # Date collision may cause 409, but auth must pass (not 401/403)
    assert r.status_code in (201, 409), f"Expected 201 or 409, got {r.status_code}: {r.text}"


# ── Non-member denied write ────────────────────────────────────────────────


async def test_non_member_denied_field_ops_write(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/punch-items/",
            json={
                "project_id": orphan,
                "punch_number": 99,
                "title": f"Denied-{uid()}",
                "status": "open",
                "priority": "medium",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_non_member_denied_schedule_write(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/schedules/",
            json={
                "project_id": orphan,
                "name": f"S-{uid()}",
                "schedule_type": "master",
                "start_date": "2026-01-01",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_non_member_denied_financials_write(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/cost-codes/",
            json={
                "project_id": orphan,
                "code": f"CC-{uid()}",
                "name": "X",
                "cost_type": "labor",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_non_member_denied_doc_mgmt_write(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/rfis/",
            json={
                "project_id": orphan,
                "rfi_number": f"RFI-{uid()}",
                "subject": "denied",
                "question": "?",
                "status": "open",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


async def test_non_member_denied_closeout_write(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    # Create company while stub admin is still active
    co = await client.post(
        "/api/companies/",
        json={"name": f"WrCo-{uid()}", "company_type": "subcontractor"},
    )
    assert co.status_code == 201, co.text
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/warranties/",
            json={
                "project_id": orphan,
                "company_id": co.json()["id"],
                "scope_description": "Test",
                "warranty_type": "standard",
                "duration_months": 12,
                "start_date": "2026-01-01",
                "status": "active",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


# ── read_only denied write ─────────────────────────────────────────────────


async def test_read_only_member_denied_write(client: AsyncClient):
    """read_only access on Bishop → 403 on field_only write."""
    ro_email = await _create_read_only_user(client, PROJECT_BISHOP)
    with _no_auth_override():
        token = await _login_token(client, ro_email)
        r = await client.post(
            "/api/punch-items/",
            json={
                "project_id": PROJECT_BISHOP,
                "punch_number": 98,
                "title": f"RO-Denied-{uid()}",
                "status": "open",
                "priority": "medium",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


# ── field_only can write field ops, denied financials ──────────────────────


async def test_field_only_allowed_field_ops(client: AsyncClient):
    fo_email = await _create_field_only_user(client, PROJECT_BISHOP)
    with _no_auth_override():
        token = await _login_token(client, fo_email)
        r = await client.post(
            "/api/punch-items/",
            json={
                "project_id": PROJECT_BISHOP,
                "punch_number": 97,
                "title": f"FO-OK-{uid()}",
                "status": "open",
                "priority": "medium",
            },
            headers=_auth(token),
        )
    assert r.status_code in (201, 409), f"Expected 201/409, got {r.status_code}: {r.text}"


async def test_field_only_denied_financials_write(client: AsyncClient):
    fo_email = await _create_field_only_user(client, PROJECT_BISHOP)
    with _no_auth_override():
        token = await _login_token(client, fo_email)
        r = await client.post(
            "/api/cost-codes/",
            json={
                "project_id": PROJECT_BISHOP,
                "code": f"CC-{uid()}",
                "name": "X",
                "cost_type": "labor",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403


# ── Admin bypass ───────────────────────────────────────────────────────────


async def test_admin_bypasses_write_scope(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, ADMIN_EMAIL)
        r = await client.post(
            "/api/rfis/",
            json={
                "project_id": orphan,
                "rfi_number": f"RFI-{uid()}",
                "subject": "admin-ok",
                "question": "?",
                "status": "open",
            },
            headers=_auth(token),
        )
    assert r.status_code == 201, r.text


# ── CORS config ────────────────────────────────────────────────────────────


def test_cors_origins_not_wildcard():
    """Default CORS does not include wildcard — fails closed."""
    assert "*" not in CORS_ORIGINS


def test_cors_origins_contains_local_dev():
    assert "http://localhost:5173" in CORS_ORIGINS


async def test_cors_preflight_allowed_origin(client: AsyncClient):
    """OPTIONS with an allowed origin returns proper CORS headers."""
    r = await client.options(
        "/api/projects/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert "http://localhost:5173" in r.headers.get("access-control-allow-origin", "")


async def test_cors_preflight_denied_origin(client: AsyncClient):
    """OPTIONS with an unlisted origin gets no allow-origin header."""
    r = await client.options(
        "/api/projects/",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "evil.example.com" not in r.headers.get("access-control-allow-origin", "")


# ── Error shape consistency ────────────────────────────────────────────────


async def test_401_error_shape(client: AsyncClient):
    with _no_auth_override():
        r = await client.get("/api/projects/")
    assert r.status_code == 401
    body = r.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)


async def test_403_write_error_shape(client: AsyncClient):
    orphan = await _create_orphan_project(client)
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.post(
            "/api/rfis/",
            json={
                "project_id": orphan,
                "rfi_number": f"RFI-{uid()}",
                "subject": "x",
                "question": "?",
                "status": "open",
            },
            headers=_auth(token),
        )
    assert r.status_code == 403
    body = r.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)


async def test_404_read_error_shape(client: AsyncClient):
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        orphan = str(uuid.uuid4())
        r = await client.get(f"/api/projects/{orphan}", headers=_auth(token))
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)

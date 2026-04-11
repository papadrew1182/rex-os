"""Authentication and session flow tests.

Uses the seeded user accounts (password: rex2026!) and bypasses the
default conftest auth override via the `real_auth_client` fixture.
"""

from httpx import AsyncClient

ADMIN_EMAIL = "aroberts@exxircapital.com"
INACTIVE_TEST_EMAIL = "inactive_test@example.invalid"  # placeholder if needed
PASSWORD = "rex2026!"


# ── Login ───────────────────────────────────────────────────────────────────

async def test_login_success(real_auth_client: AsyncClient):
    r = await real_auth_client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": PASSWORD,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body
    assert body["token_type"] == "bearer"
    assert body["email"] == ADMIN_EMAIL
    assert body["is_admin"] is True
    assert body["global_role"] == "vp"


async def test_login_bad_password(real_auth_client: AsyncClient):
    r = await real_auth_client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": "wrong-password",
    })
    assert r.status_code == 401
    assert "Invalid" in r.json()["detail"]


async def test_login_unknown_email(real_auth_client: AsyncClient):
    r = await real_auth_client.post("/api/auth/login", json={
        "email": "nobody@nowhere.test", "password": PASSWORD,
    })
    assert r.status_code == 401


async def test_login_inactive_user(real_auth_client: AsyncClient):
    """Deactivate a freshly-created user, then verify login is rejected."""
    # Need to authenticate first since POST /api/people/ now requires auth
    login = await real_auth_client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": PASSWORD,
    })
    admin_headers = {"Authorization": f"Bearer {login.json()['token']}"}
    # Create a fresh person + user via the existing CRUD
    p = await real_auth_client.post("/api/people/", json={
        "first_name": "Inactive", "last_name": "Test",
        "role_type": "internal",
    }, headers=admin_headers)
    person_id = p.json()["id"]

    # Direct DB insert for user_account is the simplest path; use raw asyncpg
    import db as legacy_db
    pool = await legacy_db.get_pool()
    import bcrypt
    pw_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    inactive_email = f"inactive-{person_id[:8]}@test.invalid"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO rex.user_accounts (person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2, $3, false)",
            person_id, inactive_email, pw_hash,
        )

    r = await real_auth_client.post("/api/auth/login", json={
        "email": inactive_email, "password": PASSWORD,
    })
    assert r.status_code == 401


# ── Me ──────────────────────────────────────────────────────────────────────

async def test_me_returns_user_context(real_auth_client: AsyncClient):
    login = await real_auth_client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": PASSWORD,
    })
    token = login.json()["token"]

    r = await real_auth_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["is_admin"] is True
    assert body["first_name"] == "Andrew"
    assert body["last_name"] == "Roberts"


async def test_me_unauthenticated(real_auth_client: AsyncClient):
    r = await real_auth_client.get("/api/auth/me")
    assert r.status_code == 401


async def test_me_invalid_token(real_auth_client: AsyncClient):
    r = await real_auth_client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


# ── Logout ──────────────────────────────────────────────────────────────────

async def test_logout_invalidates_session(real_auth_client: AsyncClient):
    login = await real_auth_client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": PASSWORD,
    })
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # me works before logout
    r = await real_auth_client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200

    # logout
    r = await real_auth_client.post("/api/auth/logout", headers=headers)
    assert r.status_code == 200
    assert r.json()["success"] is True

    # me fails after logout
    r = await real_auth_client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401


async def test_logout_unauthenticated(real_auth_client: AsyncClient):
    r = await real_auth_client.post("/api/auth/logout")
    assert r.status_code == 401

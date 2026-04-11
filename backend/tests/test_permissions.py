"""Permission enforcement tests on the focused subset of protected routes.

Uses real_auth_client to bypass the conftest stub-admin override.
Tests both 401 (unauthenticated) and 403 (insufficient role) paths.
"""

import uuid
import bcrypt
from httpx import AsyncClient

ADMIN_EMAIL = "aroberts@exxircapital.com"
PASSWORD = "rex2026!"

# Seeded non-admin: Mitch Andersen, no global_role, is_admin=False
NON_ADMIN_EMAIL = "mandersen@exxircapital.com"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _login_token(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ── 401: protected routes reject unauthenticated requests ───────────────────

async def test_certify_milestone_requires_auth(real_auth_client: AsyncClient):
    # No auth header
    r = await real_auth_client.post(
        f"/api/completion-milestones/{uuid.uuid4()}/certify",
        json={"certified_by": str(uuid.uuid4())},
    )
    assert r.status_code == 401


async def test_evaluate_gates_requires_auth(real_auth_client: AsyncClient):
    r = await real_auth_client.post(
        f"/api/completion-milestones/{uuid.uuid4()}/evaluate-gates"
    )
    assert r.status_code == 401


async def test_generate_alerts_requires_auth(real_auth_client: AsyncClient):
    r = await real_auth_client.post(
        f"/api/warranties/{uuid.uuid4()}/generate-alerts"
    )
    assert r.status_code == 401


async def test_warranty_refresh_status_requires_auth(real_auth_client: AsyncClient):
    r = await real_auth_client.post(
        f"/api/warranties/{uuid.uuid4()}/refresh-status"
    )
    assert r.status_code == 401


async def test_punch_refresh_aging_requires_auth(real_auth_client: AsyncClient):
    r = await real_auth_client.post(
        f"/api/punch-items/{uuid.uuid4()}/refresh-aging"
    )
    assert r.status_code == 401


async def test_budget_refresh_rollup_requires_auth(real_auth_client: AsyncClient):
    r = await real_auth_client.post(
        f"/api/budget-line-items/{uuid.uuid4()}/refresh-rollup"
    )
    assert r.status_code == 401


async def test_checklist_from_template_requires_auth(real_auth_client: AsyncClient):
    r = await real_auth_client.post(
        "/api/closeout-checklists/from-template",
        json={"project_id": str(uuid.uuid4()), "template_id": str(uuid.uuid4())},
    )
    assert r.status_code == 401


# ── 403: protected routes reject insufficient role ──────────────────────────

async def test_non_admin_rejected_403(real_auth_client: AsyncClient):
    """Mitch Andersen (no global_role, not admin) gets 403 on protected ops."""
    token = await _login_token(real_auth_client, NON_ADMIN_EMAIL, PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    r = await real_auth_client.post(
        f"/api/punch-items/{uuid.uuid4()}/refresh-aging",
        headers=headers,
    )
    assert r.status_code == 403


async def test_admin_allowed_through_protected_route(real_auth_client: AsyncClient):
    """Andrew Roberts (admin + vp) gets past auth to reach the actual handler.

    The handler will return 404 for the bogus warranty id — that's expected.
    The point is that 401/403 did NOT fire.
    """
    token = await _login_token(real_auth_client, ADMIN_EMAIL, PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    r = await real_auth_client.post(
        f"/api/warranties/{uuid.uuid4()}/refresh-status",
        headers=headers,
    )
    # 404 because the bogus UUID isn't a real warranty — but auth passed
    assert r.status_code == 404


async def test_vp_allowed(real_auth_client: AsyncClient):
    """A user with global_role='vp' but is_admin=False is also allowed."""
    # Need to authenticate first since POST /api/people/ now requires auth
    admin_token = await _login_token(real_auth_client, ADMIN_EMAIL, PASSWORD)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    # Create a fresh person + non-admin VP user
    p = await real_auth_client.post("/api/people/", json={
        "first_name": "VPOnly", "last_name": f"Test-{_uid()}",
        "role_type": "internal",
    }, headers=admin_headers)
    person_id = p.json()["id"]

    import db as legacy_db
    pool = await legacy_db.get_pool()
    pw_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    vp_email = f"vp-{_uid()}@test.invalid"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO rex.user_accounts (person_id, email, password_hash, "
            "global_role, is_admin, is_active) VALUES "
            "($1::uuid, $2, $3, 'vp', false, true)",
            person_id, vp_email, pw_hash,
        )

    token = await _login_token(real_auth_client, vp_email, PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    # Should pass auth and reach handler -> 404 for bogus id
    r = await real_auth_client.post(
        f"/api/warranties/{uuid.uuid4()}/refresh-status",
        headers=headers,
    )
    assert r.status_code == 404

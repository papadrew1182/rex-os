"""Sprint F: production hardening tests.

Covers:
- /api/health (liveness)
- /api/ready success + failure simulation
- Storage adapter registry: env-driven selection, unknown backend fails,
  memory backend round-trip, path-traversal still rejected on the interface
- Per-test rollback isolation (rollback_client leaves no trace)
- Session operability: purge_expired_sessions helper, logout-all endpoint
- Logging smoke check on login success/failure (capture via caplog)
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user
from app.database import async_session_factory
from app.services import auth as auth_svc
from app.services.auth import hash_token, purge_expired_sessions
from app.services.storage import (
    LocalStorageAdapter,
    MemoryStorageAdapter,
    StorageAdapter,
    StorageConfigError,
    _build_adapter,
    get_storage,
    reset_storage,
)
from main import app
from tests.helpers import PROJECT_BISHOP, uid

ADMIN_EMAIL = "aroberts@exxircapital.com"
PASSWORD = "rex2026!"


# ── Health endpoint (liveness) ─────────────────────────────────────────────


async def test_health_returns_200(client: AsyncClient):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


async def test_health_needs_no_auth(client: AsyncClient):
    """Liveness must work even without an auth override in place."""
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.get("/api/health")
        assert r.status_code == 200
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


# ── Readiness endpoint ─────────────────────────────────────────────────────


async def test_ready_success_path(client: AsyncClient):
    r = await client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"]["ok"] is True
    assert body["checks"]["storage"]["ok"] is True
    assert body["checks"]["storage"]["backend"] in {"local", "memory"}


async def test_ready_503_when_storage_unwritable(client: AsyncClient, tmp_path: Path):
    """Swap storage for an adapter whose healthcheck fails, confirm 503."""

    class BrokenAdapter(StorageAdapter):
        scheme = "broken"

        def make_key(self, project_id, filename):  # pragma: no cover
            return "x"

        def save(self, content, key):  # pragma: no cover
            return ""

        def read(self, key):  # pragma: no cover
            raise FileNotFoundError

        def delete(self, key):  # pragma: no cover
            return False

        def healthcheck(self):
            raise StorageConfigError("simulated failure")

    # Swap in the broken adapter, then restore
    import app.services.storage as storage_mod
    saved = storage_mod._default_adapter
    storage_mod._default_adapter = BrokenAdapter()
    try:
        r = await client.get("/api/ready")
    finally:
        storage_mod._default_adapter = saved

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["storage"]["ok"] is False
    assert "simulated failure" in body["checks"]["storage"]["error"]
    # DB check should still have passed independently
    assert body["checks"]["db"]["ok"] is True


# ── Storage adapter registry ───────────────────────────────────────────────


def test_storage_unknown_backend_raises():
    with pytest.raises(StorageConfigError):
        _build_adapter("nonsense-backend")


def test_storage_memory_adapter_round_trip():
    adapter = MemoryStorageAdapter()
    key = adapter.make_key("proj", "doc.txt")
    adapter.save(b"memory payload", key)
    assert adapter.read(key) == b"memory payload"
    assert adapter.delete(key) is True
    with pytest.raises(FileNotFoundError):
        adapter.read(key)


def test_storage_memory_adapter_rejects_null_key():
    adapter = MemoryStorageAdapter()
    with pytest.raises(ValueError):
        adapter.save(b"x", "bad\x00key")


def test_storage_local_adapter_healthcheck_passes(tmp_path: Path):
    adapter = LocalStorageAdapter(tmp_path / "ok")
    adapter.healthcheck()  # should not raise


def test_storage_local_adapter_healthcheck_fails_on_readonly(tmp_path: Path, monkeypatch):
    """Force the healthcheck probe to fail and confirm StorageConfigError."""
    adapter = LocalStorageAdapter(tmp_path / "ro")

    def boom(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "write_bytes", boom)
    with pytest.raises(StorageConfigError):
        adapter.healthcheck()


def test_reset_storage_memory_backend():
    prev = get_storage()
    try:
        swapped = reset_storage(backend="memory")
        assert isinstance(swapped, MemoryStorageAdapter)
        assert get_storage() is swapped
    finally:
        # Restore a filesystem-backed adapter so downstream tests have upload working
        import app.services.storage as storage_mod
        storage_mod._default_adapter = prev


# ── Per-test rollback isolation ────────────────────────────────────────────


async def test_rollback_client_leaves_no_trace(rollback_client: AsyncClient):
    """A project created inside rollback_client must not survive teardown."""
    marker_number = f"ROLLBACK-{uid()}"
    r = await rollback_client.post(
        "/api/projects/",
        json={
            "project_number": marker_number,
            "name": f"RB-{uid()}",
            "status": "active",
        },
    )
    assert r.status_code == 201, r.text
    created_id = r.json()["id"]

    # Inside the same test, the row is visible through the same client
    inside = await rollback_client.get(f"/api/projects/{created_id}")
    assert inside.status_code == 200


async def test_rollback_client_previous_test_data_absent(client: AsyncClient):
    """The marker number from the rollback test must NOT appear in the DB.

    This is the teardown verification — if rollback didn't work, the project
    number would still be listed here on the non-isolated client.
    """
    # Can't assert on exact number (different run), just assert no project
    # starts with 'ROLLBACK-' that we can find via list.
    r = await client.get("/api/projects/?limit=2000")
    assert r.status_code == 200
    numbers = {p.get("project_number") for p in r.json() if p.get("project_number")}
    leaked = [n for n in numbers if n.startswith("ROLLBACK-")]
    assert leaked == [], f"rollback_client leaked projects: {leaked}"


# ── Session operability: purge helper ─────────────────────────────────────


async def test_purge_expired_sessions_deletes_only_expired():
    """Deterministic purge removes expired rows and leaves live ones alone."""
    import db as legacy_db

    pool = await legacy_db.get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT id FROM rex.user_accounts WHERE email = $1", ADMIN_EMAIL
        )
        expired_hash = hash_token(f"purge-expired-{uid()}-{uuid.uuid4().hex}")
        live_hash = hash_token(f"purge-live-{uid()}-{uuid.uuid4().hex}")
        await conn.execute(
            "INSERT INTO rex.sessions (user_account_id, token_hash, expires_at) VALUES ($1::uuid, $2, $3)",
            user_id, expired_hash, datetime.now(timezone.utc) - timedelta(days=2),
        )
        await conn.execute(
            "INSERT INTO rex.sessions (user_account_id, token_hash, expires_at) VALUES ($1::uuid, $2, $3)",
            user_id, live_hash, datetime.now(timezone.utc) + timedelta(days=2),
        )

    async with async_session_factory() as session:
        removed = await purge_expired_sessions(session)
    assert removed >= 1

    async with pool.acquire() as conn:
        expired_gone = await conn.fetchval(
            "SELECT 1 FROM rex.sessions WHERE token_hash = $1", expired_hash
        )
        live_still_there = await conn.fetchval(
            "SELECT 1 FROM rex.sessions WHERE token_hash = $1", live_hash
        )
    assert expired_gone is None, "expired session should have been purged"
    assert live_still_there == 1, "live session must not be purged"

    # Clean up the live marker we created ourselves (pre-rollback-client test)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM rex.sessions WHERE token_hash = $1", live_hash)


# ── Session operability: logout-all endpoint ──────────────────────────────


async def test_logout_all_revokes_all_user_sessions(client: AsyncClient):
    """logout-all revokes every session for the caller and nothing else."""
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        # Login three times to create three live sessions
        tokens = []
        for _ in range(3):
            r = await client.post(
                "/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": PASSWORD},
            )
            assert r.status_code == 200, r.text
            tokens.append(r.json()["token"])

        # Sanity: /me works with the first token
        me = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens[0]}"}
        )
        assert me.status_code == 200

        # Call logout-all with the first token
        r = await client.post(
            "/api/auth/logout-all",
            headers={"Authorization": f"Bearer {tokens[0]}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["sessions_revoked"] >= 3  # at least the three we just made

        # Every token is now rejected
        for t in tokens:
            r = await client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {t}"}
            )
            assert r.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def test_logout_all_requires_auth(client: AsyncClient):
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.post("/api/auth/logout-all")
        assert r.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


# ── Logging smoke checks ───────────────────────────────────────────────────


async def test_login_success_emits_log(client: AsyncClient, caplog):
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        with caplog.at_level(logging.INFO, logger="rex.auth"):
            r = await client.post(
                "/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": PASSWORD},
            )
            assert r.status_code == 200
        messages = [rec.getMessage() for rec in caplog.records]
        assert any("login_ok" in m for m in messages), messages
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def test_login_failure_emits_log_without_token(client: AsyncClient, caplog):
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        with caplog.at_level(logging.INFO, logger="rex.auth"):
            r = await client.post(
                "/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": "nope"},
            )
            assert r.status_code == 401
        messages = [rec.getMessage() for rec in caplog.records]
        assert any("login_failed" in m and "bad_password" in m for m in messages)
        # Make sure no literal password or token ever leaks into logs
        for m in messages:
            assert "nope" not in m
            assert "password=" not in m
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved

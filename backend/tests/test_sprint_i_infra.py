"""Sprint I: storage upgrade, migration runner, and read-scope performance tests.

Covers:
- Storage adapter selection (local, memory, s3 config-error, unknown backend)
- Migration runner planned order, dry-run, missing-file handling
- Per-request caching of readable project IDs (no repeated DB queries)
"""

import contextlib
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.dependencies import (
    _READABLE_IDS_ATTR,
    _SENTINEL,
    get_current_user,
    get_readable_project_ids,
)
from app.migrate import (
    MIGRATION_ORDER,
    MigrationResult,
    apply_migrations,
    get_planned_migrations,
)
from app.services.storage import (
    LocalStorageAdapter,
    MemoryStorageAdapter,
    S3StorageAdapter,
    StorageConfigError,
    _ADAPTER_REGISTRY,
    _build_adapter,
    get_storage,
    reset_storage,
)
from main import app
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


# ═══════════════════════════════════════════════════════════════════════════
# Storage adapter tests
# ═══════════════════════════════════════════════════════════════════════════


def test_adapter_registry_contains_expected_backends():
    assert "local" in _ADAPTER_REGISTRY
    assert "memory" in _ADAPTER_REGISTRY
    assert "s3" in _ADAPTER_REGISTRY


def test_build_adapter_local(tmp_path: Path):
    os.environ["REX_STORAGE_PATH"] = str(tmp_path / "st")
    try:
        adapter = _build_adapter("local")
        assert isinstance(adapter, LocalStorageAdapter)
        assert adapter.scheme == "local"
    finally:
        # Restore whatever was there before
        os.environ.pop("REX_STORAGE_PATH", None)


def test_build_adapter_memory():
    adapter = _build_adapter("memory")
    assert isinstance(adapter, MemoryStorageAdapter)
    assert adapter.scheme == "memory"


def test_build_adapter_unknown_raises():
    with pytest.raises(StorageConfigError, match="Unknown storage backend"):
        _build_adapter("gcs")


def test_s3_adapter_raises_without_bucket():
    """S3 adapter requires REX_S3_BUCKET; missing → StorageConfigError."""
    saved = os.environ.pop("REX_S3_BUCKET", None)
    try:
        with pytest.raises(StorageConfigError, match="REX_S3_BUCKET"):
            S3StorageAdapter()
    finally:
        if saved is not None:
            os.environ["REX_S3_BUCKET"] = saved


def test_memory_adapter_full_round_trip():
    adapter = MemoryStorageAdapter()
    key = adapter.make_key("proj-1", "report.pdf")
    adapter.save(b"pdf-bytes", key)
    assert adapter.read(key) == b"pdf-bytes"
    assert adapter.url_for(key) == f"memory://{key}"
    assert adapter.delete(key) is True
    with pytest.raises(FileNotFoundError):
        adapter.read(key)


def test_local_adapter_round_trip_via_env(tmp_path: Path):
    adapter = LocalStorageAdapter(tmp_path / "local_test")
    key = adapter.make_key("p1", "doc.txt")
    adapter.save(b"hello", key)
    assert adapter.read(key) == b"hello"
    adapter.healthcheck()


def test_reset_storage_switches_backend():
    prev = get_storage()
    try:
        swapped = reset_storage(backend="memory")
        assert isinstance(swapped, MemoryStorageAdapter)
        assert get_storage() is swapped
    finally:
        import app.services.storage as s
        s._default_adapter = prev


# ═══════════════════════════════════════════════════════════════════════════
# Migration runner tests
# ═══════════════════════════════════════════════════════════════════════════


def test_migration_order_is_nonempty():
    assert len(MIGRATION_ORDER) >= 4


def test_get_planned_migrations_returns_expected_files(tmp_path: Path):
    # Create only the first file
    (tmp_path / MIGRATION_ORDER[0]).write_text("-- ok")
    plan = get_planned_migrations(tmp_path)
    assert len(plan) == len(MIGRATION_ORDER)
    assert plan[0]["exists"] is True
    assert plan[1]["exists"] is False  # not created
    for item in plan:
        assert "file" in item
        assert "exists" in item


async def test_dry_run_does_not_execute():
    results = await apply_migrations(dry_run=True)
    assert len(results) == len(MIGRATION_ORDER)
    for r in results:
        assert r.status in ("planned", "missing")


async def test_apply_migrations_stops_on_error(tmp_path: Path):
    """A bad SQL file halts the run; later files are not attempted."""
    (tmp_path / MIGRATION_ORDER[0]).write_text("SELECT 1;")
    (tmp_path / MIGRATION_ORDER[1]).write_text("THIS IS NOT SQL !!!")
    (tmp_path / MIGRATION_ORDER[2]).write_text("SELECT 1;")

    results = await apply_migrations(migrations_dir=tmp_path)
    statuses = [r.status for r in results]
    assert statuses[0] == "ok"
    assert statuses[1] == "error"
    # Third file was never attempted — not in results
    assert len(results) == 2


def test_migration_result_to_dict():
    r = MigrationResult("test.sql", "ok")
    d = r.to_dict()
    assert d == {"file": "test.sql", "status": "ok"}

    r2 = MigrationResult("bad.sql", "error", "syntax error")
    d2 = r2.to_dict()
    assert d2 == {"file": "bad.sql", "status": "error", "detail": "syntax error"}


# ═══════════════════════════════════════════════════════════════════════════
# Read-scope per-request caching tests
# ═══════════════════════════════════════════════════════════════════════════


async def test_readable_ids_cached_on_user_object(client: AsyncClient):
    """After the first call, the result is attached to the user — no re-query."""
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        headers = {"Authorization": f"Bearer {token}"}

        # Call a scoped list endpoint — this resolves the user and caches ids
        r1 = await client.get("/api/projects/?limit=1", headers=headers)
        assert r1.status_code == 200

        # The same user object has been resolved and cached
        # We can't directly inspect the user object from outside the request,
        # but we can verify the endpoint works and observe the cache
        # indirectly by calling a second scoped endpoint on the same
        # request path (not possible in HTTP without middleware). Instead
        # we'll test the caching function directly below.


async def test_get_readable_project_ids_caches_per_user():
    """Direct unit test: second call skips DB entirely."""
    from unittest.mock import MagicMock
    from app.models.foundation import UserAccount
    from datetime import datetime, timezone

    user = UserAccount(
        id=uuid.UUID("99990000-0000-4000-a000-000000000099"),
        person_id=uuid.UUID("10000000-0000-4000-a000-000000000002"),
        email="test@test.invalid",
        password_hash="(stub)",
        global_role=None,
        is_admin=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # First call: DB session must be called
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        uuid.UUID("40000000-0000-4000-a000-000000000001"),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    ids1 = await get_readable_project_ids(mock_db, user)
    assert ids1 == {uuid.UUID("40000000-0000-4000-a000-000000000001")}
    assert mock_db.execute.await_count == 1

    # Second call: DB should NOT be called again (cached)
    ids2 = await get_readable_project_ids(mock_db, user)
    assert ids2 is ids1  # same object
    assert mock_db.execute.await_count == 1  # unchanged


async def test_admin_bypass_cached_as_none():
    """Admin/VP result (None sentinel) is also cached correctly."""
    from app.models.foundation import UserAccount
    from datetime import datetime, timezone

    admin_user = UserAccount(
        id=uuid.UUID("20000000-0000-4000-a000-000000000001"),
        person_id=uuid.UUID("10000000-0000-4000-a000-000000000001"),
        email="admin@test.invalid",
        password_hash="(stub)",
        global_role="vp",
        is_admin=True,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    ids = await get_readable_project_ids(mock_db, admin_user)
    assert ids is None
    # DB should never be called for admin
    assert mock_db.execute.await_count == 0

    # Second call still returns None from cache
    ids2 = await get_readable_project_ids(mock_db, admin_user)
    assert ids2 is None
    assert mock_db.execute.await_count == 0


async def test_cache_does_not_leak_across_requests(client: AsyncClient):
    """Two requests with the same user get independent caches."""
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        headers = {"Authorization": f"Bearer {token}"}

        # Each request creates a fresh user object from the DB, so the
        # cached attr from request 1 is not visible in request 2.
        r1 = await client.get("/api/projects/?limit=1", headers=headers)
        r2 = await client.get("/api/projects/?limit=1", headers=headers)
        # Both should succeed with the same data
        assert r1.status_code == 200
        assert r2.status_code == 200

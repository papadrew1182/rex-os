"""Shared fixtures for quick-action handler tests.

Handlers read from `rex.*` via an `asyncpg.Connection` (not a SQLAlchemy
session). Tests that combine FastAPI's async `client` with SQLAlchemy
sessions triggered event-loop mismatch on Linux CI in Phase 4. We
sidestep that here by using raw asyncpg — one fresh connection per
test, bound to whichever loop pytest-asyncio hands us.
"""
from __future__ import annotations

import os
import ssl

import asyncpg
import pytest
import pytest_asyncio


def require_live_db():
    """Skip the current test if DATABASE_URL is not set in the environment."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def connect_raw() -> asyncpg.Connection:
    """Open a fresh raw asyncpg connection bound to the current event loop."""
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


@pytest_asyncio.fixture
async def raw_conn():
    """Yield a fresh raw asyncpg connection; close on teardown.

    Use this inside tests that need to query or verify rex.* data.
    Fixtures that seed data should open their own short-lived connection
    via `connect_raw()` — DO NOT share `raw_conn` across fixture + test,
    because each fixture teardown closes it and the test would inherit
    a stale handle.
    """
    require_live_db()
    conn = await connect_raw()
    try:
        yield conn
    finally:
        await conn.close()


__all__ = ["require_live_db", "connect_raw", "raw_conn"]

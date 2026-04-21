"""Dedicated asyncpg pool for the "Rex App" Railway Postgres.

This DB is a separate Railway project (under exxir's Railway org) from
Rex OS's own Postgres, so we cannot reach it over .railway.internal and
cannot use the main rex-os pool. Callers go through this module to get
a read-only handle. Never write to Rex App from Rex OS.
"""

from __future__ import annotations

import asyncpg
import os
import ssl

_pool: asyncpg.Pool | None = None


async def get_rex_app_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool

    url = os.environ.get("REX_APP_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "REX_APP_DATABASE_URL is not set. Point it at the public "
            "DATABASE_URL of the old rex-procore Railway Postgres "
            "(project 'Rex App' under exxir's Railway org)."
        )

    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ssl_ctx: ssl.SSLContext | None = None
    if use_ssl:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    _pool = await asyncpg.create_pool(
        url,
        ssl=ssl_ctx,
        min_size=1,
        max_size=5,
        server_settings={"search_path": "procore,public"},
    )
    return _pool


async def close_rex_app_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


__all__ = ["get_rex_app_pool", "close_rex_app_pool"]

import asyncpg
import os
import ssl
from dotenv import load_dotenv

load_dotenv()

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await _create_pool()
    return _pool


async def _create_pool() -> asyncpg.Pool:
    url = os.environ["DATABASE_URL"]
    use_ssl = "railway.internal" not in url and "localhost" not in url and "127.0.0.1" not in url

    ssl_ctx: ssl.SSLContext | None = None
    if use_ssl:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    return await asyncpg.create_pool(
        url,
        ssl=ssl_ctx,
        min_size=2,
        max_size=10,
        server_settings={"search_path": "rex,public"},
    )


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

import os
import pytest
from app.services.connectors.procore.rex_app_pool import (
    get_rex_app_pool,
    close_rex_app_pool,
)


@pytest.mark.asyncio
async def test_get_rex_app_pool_requires_env_var(monkeypatch):
    monkeypatch.delenv("REX_APP_DATABASE_URL", raising=False)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    with pytest.raises(RuntimeError, match="REX_APP_DATABASE_URL"):
        await get_rex_app_pool()


@pytest.mark.asyncio
async def test_get_rex_app_pool_uses_env_var(monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)

    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    pool = await get_rex_app_pool()
    assert pool is not None

    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT 1")
        assert val == 1

    await close_rex_app_pool()
    assert mod._pool is None

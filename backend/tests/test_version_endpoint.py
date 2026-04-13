"""Lock in the shape of /api/version so ops tooling and the deployed-smoke
workflow can rely on it without chasing field renames.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_version_endpoint_shape():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/version")

    assert r.status_code == 200
    body = r.json()

    # These four keys are the minimum contract. Adding more is fine;
    # removing one would break the deployed-smoke workflow.
    assert body["service"] == "rex-os-backend"
    assert isinstance(body["version"], str) and body["version"]
    assert isinstance(body["commit"], str) and body["commit"]
    assert "environment" in body

"""procore_api — minimal OAuth + answer_rfi client. httpx transport mocked."""
from __future__ import annotations

import httpx
import pytest

from app.services.ai.tools.procore_api import (
    ProcoreClient, ProcoreNotConfigured, ProcoreApiError,
)


@pytest.mark.asyncio
async def test_raises_when_not_configured(monkeypatch):
    for key in ("PROCORE_CLIENT_ID", "PROCORE_CLIENT_SECRET", "PROCORE_REFRESH_TOKEN", "PROCORE_COMPANY_ID"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ProcoreNotConfigured):
        ProcoreClient.from_env()


@pytest.mark.asyncio
async def test_answer_rfi_happy_path(monkeypatch):
    monkeypatch.setenv("PROCORE_CLIENT_ID", "cid")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PROCORE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("PROCORE_COMPANY_ID", "42")
    monkeypatch.setenv("PROCORE_BASE_URL", "https://api.procore.com")

    def _transport(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(
                200, json={"access_token": "abc", "expires_in": 3600, "token_type": "bearer"},
            )
        if request.url.path.endswith("/rfis/123"):
            return httpx.Response(
                200, json={"id": 123, "status": "closed", "answer": "Resolved."},
            )
        return httpx.Response(404)

    client = ProcoreClient.from_env(transport=httpx.MockTransport(_transport))
    try:
        result = await client.answer_rfi(rfi_procore_id=123, answer_text="Resolved.")
        assert result["id"] == 123
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_answer_rfi_api_error_surfaces(monkeypatch):
    monkeypatch.setenv("PROCORE_CLIENT_ID", "cid")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PROCORE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("PROCORE_COMPANY_ID", "42")

    def _transport(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "abc", "expires_in": 3600})
        return httpx.Response(500, json={"error": "server error"})

    client = ProcoreClient.from_env(transport=httpx.MockTransport(_transport))
    try:
        with pytest.raises(ProcoreApiError) as ei:
            await client.answer_rfi(rfi_procore_id=1, answer_text="x")
        assert "500" in str(ei.value)
    finally:
        await client.close()

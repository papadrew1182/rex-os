"""Minimal Procore REST API client for Phase 6 writeback.

Scope: only the endpoints Rex OS needs as a source of truth for the
approval-required tools. Starts with answer_rfi; future follow-up
lands submittal actions + pay-app etc.

OAuth: refresh-token flow. Env vars:
  PROCORE_CLIENT_ID         — OAuth app id
  PROCORE_CLIENT_SECRET     — OAuth app secret
  PROCORE_REFRESH_TOKEN     — long-lived refresh token
  PROCORE_COMPANY_ID        — company to scope API calls to
  PROCORE_BASE_URL          — optional, defaults to https://api.procore.com
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("rex.ai.tools.procore_api")


class ProcoreNotConfigured(RuntimeError):
    pass


class ProcoreApiError(RuntimeError):
    pass


@dataclass
class ProcoreClient:
    client_id: str
    client_secret: str
    refresh_token: str
    company_id: str
    base_url: str = "https://api.procore.com"
    _transport: httpx.AsyncBaseTransport | None = None
    _client: httpx.AsyncClient | None = None
    _access_token: str | None = None
    _token_expires_at: float = 0.0

    @classmethod
    def from_env(
        cls, transport: httpx.AsyncBaseTransport | None = None
    ) -> "ProcoreClient":
        required = [
            "PROCORE_CLIENT_ID",
            "PROCORE_CLIENT_SECRET",
            "PROCORE_REFRESH_TOKEN",
            "PROCORE_COMPANY_ID",
        ]
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            raise ProcoreNotConfigured(
                "Missing Procore OAuth env vars: " + ", ".join(missing)
            )
        return cls(
            client_id=os.environ["PROCORE_CLIENT_ID"],
            client_secret=os.environ["PROCORE_CLIENT_SECRET"],
            refresh_token=os.environ["PROCORE_REFRESH_TOKEN"],
            company_id=os.environ["PROCORE_COMPANY_ID"],
            base_url=os.environ.get("PROCORE_BASE_URL", "https://api.procore.com"),
            _transport=transport,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                transport=self._transport,
            )
        return self._client

    async def _ensure_token(self) -> str:
        now = time.time()
        if self._access_token and self._token_expires_at - now > 60:
            return self._access_token
        client = await self._get_client()
        r = await client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if r.status_code != 200:
            raise ProcoreApiError(
                f"OAuth refresh failed: HTTP {r.status_code}: {r.text[:200]}"
            )
        payload = r.json()
        self._access_token = payload["access_token"]
        self._token_expires_at = now + int(payload.get("expires_in", 3600))
        return self._access_token

    async def answer_rfi(
        self, *, rfi_procore_id: int, answer_text: str
    ) -> dict[str, Any]:
        """PATCH /rest/v1.0/rfis/{rfi_id} with the answer + status=closed.

        NOTE: Procore's exact RFI endpoint shape differs by v1.0 vs v1.1.
        This MVP uses v1.0's simple patch path. If your tenant needs v1.1's
        official_answer sub-object, adjust the payload shape here — the
        contract (rfi_procore_id, answer_text) stays the same.
        """
        token = await self._ensure_token()
        client = await self._get_client()
        r = await client.patch(
            f"/rest/v1.0/rfis/{rfi_procore_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Procore-Company-Id": self.company_id,
            },
            json={"rfi": {"answer": answer_text, "status": "closed"}},
        )
        if r.status_code // 100 != 2:
            raise ProcoreApiError(
                f"answer_rfi failed: HTTP {r.status_code}: {r.text[:200]}"
            )
        return r.json()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


__all__ = ["ProcoreClient", "ProcoreNotConfigured", "ProcoreApiError"]

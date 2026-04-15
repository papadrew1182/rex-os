"""Procore HTTP client skeleton.

Handles OAuth token refresh, base URL resolution, request retries, and
rate limiting. Stays as a skeleton here — actual HTTP calls go live in a
later Session 2 work block once credentials are wired.

Important: this is the ONLY module in the procore/ subpackage that
talks to the network. The adapter and mapper never call httpx directly.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("rex.connectors.procore.client")


class ProcoreClient:
    """Thin HTTP client for the Procore REST API.

    Construction is cheap — no network calls until a method is invoked.
    The client does NOT read secrets from the environment directly; it
    expects them to be passed in by the adapter, which resolved them
    via the credentials_ref on rex.connector_accounts.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.procore.com",
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        company_id: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.company_id = company_id

    # Real HTTP methods will land here in a later commit. For now the
    # adapter falls back to raising NotImplementedError on fetch methods,
    # which the sync service treats as an empty page.

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError(
            "ProcoreClient.get is a skeleton. Wire real httpx calls + OAuth "
            "refresh in a later Session 2 work block."
        )

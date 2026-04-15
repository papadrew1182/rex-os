"""Exxir HTTP client skeleton.

Same contract as ProcoreClient. Wiring lives in a later Session 2
work block once Exxir credentials are available.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("rex.connectors.exxir.client")


class ExxirClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError(
            "ExxirClient.get is a skeleton. Wire real httpx calls when "
            "Exxir credentials are provisioned."
        )

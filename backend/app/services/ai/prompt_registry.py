"""Thin service wrapper over ``PromptRepository``."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.repositories.prompt_repository import PromptRepository


@dataclass
class PromptRecord:
    prompt_key: str
    version: int
    prompt_type: str
    content: str


class PromptRegistryService:
    _CACHE_TTL_SECONDS = 60.0

    def __init__(self, repo: PromptRepository) -> None:
        self._repo = repo
        self._cache: dict[str, tuple[float, PromptRecord]] = {}

    async def get_active(self, prompt_key: str) -> PromptRecord | None:
        now = time.monotonic()
        cached = self._cache.get(prompt_key)
        if cached and now - cached[0] < self._CACHE_TTL_SECONDS:
            return cached[1]

        row = await self._repo.get_active(prompt_key)
        if row is None:
            return None
        record = PromptRecord(
            prompt_key=row["prompt_key"],
            version=row["version"],
            prompt_type=row["prompt_type"],
            content=row["content"],
        )
        self._cache[prompt_key] = (now, record)
        return record

    async def get_system_base(self) -> str:
        """Return the base assistant system prompt, with a hardcoded fallback."""
        record = await self.get_active("assistant.system.base")
        if record:
            return record.content
        return (
            "You are Rex, a multi-connector construction operations assistant. "
            "Answer using only curated rex.v_* views and respect the current "
            "user role and project context."
        )

    def clear_cache(self) -> None:
        self._cache.clear()

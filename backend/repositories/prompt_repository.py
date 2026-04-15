"""Prompt registry persistence against rex.ai_prompt_registry."""

from __future__ import annotations

import json
from typing import Any

import asyncpg


class PromptRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_active(self, prompt_key: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT prompt_key, version, prompt_type, content, is_active,
                       metadata, created_at
                FROM rex.ai_prompt_registry
                WHERE prompt_key = $1 AND is_active = true
                """,
                prompt_key,
            )
        return _row_to_prompt(row) if row else None

    async def list_by_type(self, prompt_type: str) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT prompt_key, version, prompt_type, content, is_active,
                       metadata, created_at
                FROM rex.ai_prompt_registry
                WHERE prompt_type = $1 AND is_active = true
                ORDER BY prompt_key
                """,
                prompt_type,
            )
        return [_row_to_prompt(r) for r in rows]


def _row_to_prompt(row: asyncpg.Record) -> dict[str, Any]:
    metadata = row["metadata"]
    if isinstance(metadata, (bytes, bytearray)):
        metadata = metadata.decode()
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            pass
    return {
        "prompt_key": row["prompt_key"],
        "version": row["version"],
        "prompt_type": row["prompt_type"],
        "content": row["content"],
        "is_active": row["is_active"],
        "metadata": metadata or {},
        "created_at": row["created_at"],
    }

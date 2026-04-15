"""Chat conversation + message persistence against rex.chat_* tables."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg


class ChatRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── conversations ─────────────────────────────────────────────────────
    async def create_conversation(
        self,
        *,
        user_id: UUID,
        title: str,
        project_id: UUID | None,
        active_action_slug: str | None,
        page_context: dict[str, Any],
        conversation_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO rex.chat_conversations
                    (user_id, title, project_id, active_action_slug,
                     page_context, conversation_metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                RETURNING *
                """,
                user_id,
                title,
                project_id,
                active_action_slug,
                json.dumps(page_context or {}),
                json.dumps(conversation_metadata or {}),
            )
        return _row_to_conversation(row)

    async def get_conversation(
        self, conversation_id: UUID, *, user_id: UUID
    ) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM rex.chat_conversations
                WHERE id = $1 AND user_id = $2 AND archived_at IS NULL
                """,
                conversation_id,
                user_id,
            )
        return _row_to_conversation(row) if row else None

    async def list_conversations(
        self, *, user_id: UUID, limit: int = 50
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.*,
                    (
                        SELECT left(m.content, 160) FROM rex.chat_messages m
                        WHERE m.conversation_id = c.id
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    ) AS last_message_preview
                FROM rex.chat_conversations c
                WHERE c.user_id = $1 AND c.archived_at IS NULL
                ORDER BY c.last_message_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
        return [_row_to_conversation_summary(r) for r in rows]

    async def archive_conversation(
        self, conversation_id: UUID, *, user_id: UUID
    ) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE rex.chat_conversations
                SET archived_at = now()
                WHERE id = $1 AND user_id = $2 AND archived_at IS NULL
                """,
                conversation_id,
                user_id,
            )
        return result.endswith(" 1")

    async def touch_conversation(
        self,
        conversation_id: UUID,
        *,
        title: str | None = None,
        active_action_slug: str | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE rex.chat_conversations
                SET last_message_at = now(),
                    title = COALESCE($2, title),
                    active_action_slug = COALESCE($3, active_action_slug)
                WHERE id = $1
                """,
                conversation_id,
                title,
                active_action_slug,
            )

    # ── messages ──────────────────────────────────────────────────────────
    async def append_message(
        self,
        *,
        conversation_id: UUID,
        sender_type: str,
        content: str,
        content_format: str = "markdown",
        structured_payload: dict[str, Any] | None = None,
        citations: list[dict[str, Any]] | None = None,
        model_key: str | None = None,
        prompt_key: str | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO rex.chat_messages
                    (conversation_id, sender_type, content, content_format,
                     structured_payload, citations, model_key, prompt_key,
                     token_usage)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9::jsonb)
                RETURNING *
                """,
                conversation_id,
                sender_type,
                content,
                content_format,
                json.dumps(structured_payload or {}),
                json.dumps(citations or []),
                model_key,
                prompt_key,
                json.dumps(token_usage or {}),
            )
        return _row_to_message(row)

    async def list_messages(
        self, conversation_id: UUID, *, limit: int = 500
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM rex.chat_messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                conversation_id,
                limit,
            )
        return [_row_to_message(r) for r in rows]


def _row_to_conversation(row: asyncpg.Record | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "project_id": row["project_id"],
        "active_action_slug": row["active_action_slug"],
        "page_context": _load_json(row["page_context"]),
        "conversation_metadata": _load_json(row["conversation_metadata"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_message_at": row["last_message_at"],
        "archived_at": row["archived_at"],
    }


def _row_to_conversation_summary(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "project_id": row["project_id"],
        "active_action_slug": row["active_action_slug"],
        "last_message_preview": row["last_message_preview"],
        "last_message_at": row["last_message_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_message(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "sender_type": row["sender_type"],
        "content": row["content"],
        "content_format": row["content_format"],
        "structured_payload": _load_json(row["structured_payload"]),
        "citations": _load_json(row["citations"]),
        "model_key": row["model_key"],
        "prompt_key": row["prompt_key"],
        "token_usage": _load_json(row["token_usage"]),
        "created_at": row["created_at"],
    }


def _load_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value

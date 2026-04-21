"""SQL CRUD for rex.action_queue. Pure SQL — no business logic."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ActionQueueRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def insert(
        self,
        *,
        id: UUID,
        user_account_id: UUID,
        requested_by_user_id: UUID | None,
        conversation_id: UUID | None,
        message_id: UUID | None,
        tool_slug: str,
        tool_args: dict,
        blast_radius: dict,
        requires_approval: bool,
        status: str,
        approver_role: str | None,
    ) -> None:
        await self._db.execute(
            text(
                """
                INSERT INTO rex.action_queue (
                    id, user_account_id, requested_by_user_id,
                    conversation_id, message_id,
                    tool_slug, tool_args, blast_radius, requires_approval,
                    status, approver_role, created_at, updated_at
                ) VALUES (
                    :id, :user_account_id,
                    :requested_by_user_id,
                    :conversation_id, :message_id,
                    :tool_slug,
                    CAST(:tool_args AS jsonb),
                    CAST(:blast_radius AS jsonb),
                    :requires_approval,
                    :status, :approver_role, now(), now()
                )
                """
            ),
            {
                "id": id,
                "user_account_id": user_account_id,
                "requested_by_user_id": requested_by_user_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "tool_slug": tool_slug,
                "tool_args": json.dumps(tool_args),
                "blast_radius": json.dumps(blast_radius),
                "requires_approval": requires_approval,
                "status": status,
                "approver_role": approver_role,
            },
        )
        await self._db.commit()

    async def get(self, action_id: UUID) -> dict | None:
        row = (
            await self._db.execute(
                text("SELECT * FROM rex.action_queue WHERE id = :id"),
                {"id": action_id},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def update_status(
        self,
        *,
        action_id: UUID,
        status: str,
        committed_at: bool = False,
        undone_at: bool = False,
        error_excerpt: str | None = None,
        result_payload: dict | None = None,
    ) -> None:
        sets: list[str] = ["status = :status", "updated_at = now()"]
        params: dict[str, Any] = {"id": action_id, "status": status}
        if committed_at:
            sets.append("committed_at = now()")
        if undone_at:
            sets.append("undone_at = now()")
        if error_excerpt is not None:
            sets.append("error_excerpt = :error_excerpt")
            params["error_excerpt"] = error_excerpt[:500]
        if result_payload is not None:
            sets.append("result_payload = CAST(:result_payload AS jsonb)")
            params["result_payload"] = json.dumps(result_payload)

        await self._db.execute(
            text(
                f"UPDATE rex.action_queue SET {', '.join(sets)} "
                f"WHERE id = :id"
            ),
            params,
        )
        await self._db.commit()

    async def list_pending_for_user(
        self, user_account_id: UUID, limit: int = 50
    ) -> list[dict]:
        rows = (
            await self._db.execute(
                text(
                    "SELECT * FROM rex.action_queue "
                    "WHERE user_account_id = :uid "
                    "AND status = 'pending_approval' "
                    "ORDER BY created_at DESC LIMIT :lim"
                ),
                {"uid": user_account_id, "lim": limit},
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    async def list_pending_by_role(
        self, approver_role: str, limit: int = 50
    ) -> list[dict]:
        rows = (
            await self._db.execute(
                text(
                    "SELECT * FROM rex.action_queue "
                    "WHERE approver_role = :role "
                    "AND status = 'pending_approval' "
                    "ORDER BY created_at DESC LIMIT :lim"
                ),
                {"role": approver_role, "lim": limit},
            )
        ).mappings().all()
        return [dict(r) for r in rows]


__all__ = ["ActionQueueRepository"]

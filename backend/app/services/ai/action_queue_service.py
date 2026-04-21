"""Phase 6 action queue orchestration.

Entry points:
- `enqueue`: called from chat_service when the LLM emits tool_use.
  Classifies the action, persists a row, and either commits (auto-pass)
  or waits for user approval.
- `commit`: called from /api/actions/{id}/approve. Transitions a
  pending_approval row to committed, running the handler in-band.
- `discard`: /api/actions/{id}/discard — pending_approval → dismissed.
- `undo`: /api/actions/{id}/undo — auto_committed → undone (60s window).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from app.repositories.action_queue_repository import ActionQueueRepository
from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import (
    ActionContext, ActionResult, ActionSpec,
)

log = logging.getLogger("rex.ai.action_queue_service")

UNDO_WINDOW_SECONDS = 60


@dataclass
class DispatchResult:
    """Result returned by enqueue/commit/undo/discard.
    status ∈ {auto_committed, pending_approval, committed, dismissed,
              undone, failed}."""
    action_id: UUID
    status: str
    requires_approval: bool
    blast_radius: dict
    result_payload: dict | None = None
    error_excerpt: str | None = None
    reasons: list[str] | None = None


class ActionQueueService:
    def __init__(
        self,
        *,
        repo: ActionQueueRepository,
        get_tool_by_slug: Callable[[str], ActionSpec | None],
        build_classify_ctx: Callable[[UUID], ClassifyContext],
        build_action_ctx: Callable[[Any, UUID, dict, UUID], ActionContext],
    ):
        self._repo = repo
        self._get_tool = get_tool_by_slug
        self._build_classify_ctx = build_classify_ctx
        self._build_action_ctx = build_action_ctx

    async def enqueue(
        self,
        *,
        conn,
        user_account_id: UUID,
        requested_by_user_id: UUID | None,
        conversation_id: UUID | None,
        message_id: UUID | None,
        tool_slug: str,
        tool_args: dict,
    ) -> DispatchResult:
        spec = self._get_tool(tool_slug)
        if spec is None:
            action_id = uuid4()
            await self._repo.insert(
                id=action_id,
                user_account_id=user_account_id,
                requested_by_user_id=requested_by_user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                tool_slug=tool_slug,
                tool_args=tool_args,
                blast_radius={},
                requires_approval=False,
                status="failed",
                approver_role=None,
            )
            await self._repo.update_status(
                action_id=action_id, status="failed",
                error_excerpt=f"Unknown tool slug: {tool_slug!r}",
            )
            return DispatchResult(
                action_id=action_id,
                status="failed",
                requires_approval=False,
                blast_radius={},
                error_excerpt=f"Unknown tool slug: {tool_slug!r}",
            )

        classify_ctx = self._build_classify_ctx(user_account_id)
        classify_ctx.conn = conn  # override to the live conn
        try:
            br: BlastRadius = await spec.classify(tool_args, classify_ctx)
        except Exception as e:
            log.exception("classify failed for %s", tool_slug)
            br = BlastRadius(
                audience='external',
                fires_external_effect=True,
                financial_dollar_amount=None,
                scope_size=1,
            )

        requires_approval = br.requires_approval()
        status = "pending_approval" if requires_approval else "auto_committed"

        action_id = uuid4()
        await self._repo.insert(
            id=action_id,
            user_account_id=user_account_id,
            requested_by_user_id=requested_by_user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            tool_slug=tool_slug,
            tool_args=tool_args,
            blast_radius=br.to_jsonb(),
            requires_approval=requires_approval,
            status=status,
            approver_role=None,
        )

        if requires_approval:
            return DispatchResult(
                action_id=action_id,
                status="pending_approval",
                requires_approval=True,
                blast_radius=br.to_jsonb(),
                reasons=br.reasons(),
            )

        return await self._run_handler(
            conn=conn, spec=spec, action_id=action_id,
            user_account_id=user_account_id, tool_args=tool_args,
            blast_radius=br.to_jsonb(),
            requires_approval=False,
            success_status="auto_committed",
        )

    async def commit(self, *, conn, action_id: UUID) -> DispatchResult:
        row = await self._repo.get(action_id)
        if row is None:
            return DispatchResult(
                action_id=action_id, status="failed",
                requires_approval=False, blast_radius={},
                error_excerpt="action not found",
            )
        if row["status"] != "pending_approval":
            return DispatchResult(
                action_id=action_id, status=row["status"],
                requires_approval=row["requires_approval"],
                blast_radius=row["blast_radius"],
                error_excerpt=f"cannot commit from status={row['status']!r}",
            )
        spec = self._get_tool(row["tool_slug"])
        if spec is None:
            await self._repo.update_status(
                action_id=action_id, status="failed",
                error_excerpt=f"Unknown tool slug: {row['tool_slug']!r}",
            )
            return DispatchResult(
                action_id=action_id, status="failed",
                requires_approval=False, blast_radius=row["blast_radius"],
                error_excerpt=f"Unknown tool slug: {row['tool_slug']!r}",
            )
        return await self._run_handler(
            conn=conn, spec=spec, action_id=action_id,
            user_account_id=row["user_account_id"],
            tool_args=row["tool_args"],
            blast_radius=row["blast_radius"],
            requires_approval=True,
            success_status="committed",
        )

    async def discard(self, *, action_id: UUID) -> DispatchResult:
        await self._repo.update_status(
            action_id=action_id, status="dismissed",
        )
        row = await self._repo.get(action_id)
        return DispatchResult(
            action_id=action_id,
            status="dismissed",
            requires_approval=bool(row.get("requires_approval")) if row else False,
            blast_radius=row.get("blast_radius", {}) if row else {},
        )

    async def undo(self, *, conn, action_id: UUID) -> DispatchResult:
        row = await self._repo.get(action_id)
        if row is None:
            return DispatchResult(
                action_id=action_id, status="failed",
                requires_approval=False, blast_radius={},
                error_excerpt="action not found",
            )
        if row["status"] != "auto_committed":
            return DispatchResult(
                action_id=action_id, status=row["status"],
                requires_approval=row["requires_approval"],
                blast_radius=row["blast_radius"],
                error_excerpt=f"cannot undo from status={row['status']!r}",
            )
        committed_at = row.get("committed_at")
        if committed_at is not None:
            elapsed = (datetime.now(timezone.utc) - committed_at).total_seconds()
            if elapsed > UNDO_WINDOW_SECONDS:
                return DispatchResult(
                    action_id=action_id, status=row["status"],
                    requires_approval=row["requires_approval"],
                    blast_radius=row["blast_radius"],
                    error_excerpt=f"undo window expired ({elapsed:.0f}s elapsed)",
                )

        spec = self._get_tool(row["tool_slug"])
        if spec is None or spec.compensator is None:
            return DispatchResult(
                action_id=action_id, status=row["status"],
                requires_approval=row["requires_approval"],
                blast_radius=row["blast_radius"],
                error_excerpt=(
                    f"not undoable: tool {row['tool_slug']!r} has no compensator"
                ),
            )

        undo_id = uuid4()
        undo_slug = f"{row['tool_slug']}__undo"
        await self._repo.insert(
            id=undo_id,
            user_account_id=row["user_account_id"],
            requested_by_user_id=row["user_account_id"],
            conversation_id=row.get("conversation_id"),
            message_id=row.get("message_id"),
            tool_slug=undo_slug,
            tool_args={},
            blast_radius=row["blast_radius"],
            requires_approval=False,
            status="auto_committed",
            approver_role=None,
            correction_of_id=action_id,
            committed_at_now=True,
        )

        original_result = row.get("result_payload") or {}
        ctx = self._build_action_ctx(conn, row["user_account_id"], {}, undo_id)
        ctx.original_result = original_result

        try:
            result: ActionResult = await spec.compensator(original_result, ctx)
        except Exception as e:
            log.exception("compensator %s failed", spec.slug)
            excerpt = str(e)[:500]
            await self._repo.update_status(
                action_id=undo_id, status="failed", error_excerpt=excerpt,
            )
            return DispatchResult(
                action_id=undo_id, status="failed",
                requires_approval=False,
                blast_radius=row["blast_radius"],
                error_excerpt=excerpt,
            )

        await self._repo.update_status(
            action_id=undo_id, status="committed",
            committed_at=True, result_payload=result.result_payload,
        )
        await self._repo.update_status(
            action_id=action_id, status="undone", undone_at=True,
        )
        return DispatchResult(
            action_id=action_id, status="undone",
            requires_approval=row["requires_approval"],
            blast_radius=row["blast_radius"],
            result_payload=result.result_payload,
        )

    async def _run_handler(
        self, *,
        conn,
        spec: ActionSpec,
        action_id: UUID,
        user_account_id: UUID,
        tool_args: dict,
        blast_radius: dict,
        requires_approval: bool,
        success_status: str,
    ) -> DispatchResult:
        action_ctx = self._build_action_ctx(
            conn, user_account_id, tool_args, action_id,
        )
        try:
            result: ActionResult = await spec.handler(action_ctx)
            await self._repo.update_status(
                action_id=action_id,
                status=success_status,
                committed_at=True,
                result_payload=result.result_payload,
            )
            return DispatchResult(
                action_id=action_id,
                status=success_status,
                requires_approval=requires_approval,
                blast_radius=blast_radius,
                result_payload=result.result_payload,
            )
        except Exception as e:
            log.exception("handler %s failed", spec.slug)
            excerpt = str(e)[:500]
            await self._repo.update_status(
                action_id=action_id,
                status="failed",
                error_excerpt=excerpt,
            )
            return DispatchResult(
                action_id=action_id,
                status="failed",
                requires_approval=requires_approval,
                blast_radius=blast_radius,
                error_excerpt=excerpt,
            )


__all__ = ["ActionQueueService", "DispatchResult", "UNDO_WINDOW_SECONDS"]

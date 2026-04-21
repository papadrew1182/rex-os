"""Phase 6: action queue HTTP surface — approve, discard, undo, pending.

Four endpoints wrap :class:`ActionQueueService`:

* ``POST /api/actions/{id}/approve`` — runs the pending handler in-band,
  transitioning ``pending_approval`` → ``committed``.
* ``POST /api/actions/{id}/discard`` — ``pending_approval`` → ``dismissed``.
* ``POST /api/actions/{id}/undo``    — ``auto_committed`` → ``undone`` within
  the 60s window.
* ``GET  /api/actions/pending``      — list this user's pending approvals.

All endpoints require an authenticated user (``get_current_user``). Approve
needs a live asyncpg connection so the tool handler can write; we borrow one
from the shared pool via :mod:`db` for the duration of the request.

The SQLAlchemy session used by :class:`ActionQueueRepository` is obtained via
FastAPI's ``get_db`` dependency so the session's engine pool is bound to the
same event loop as the request — minting a session directly via the
module-level factory caused cross-loop ``Future`` errors under pytest/anyio.
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import db as rex_db
from app.database import get_db
from app.dependencies import get_current_user
from app.models.foundation import UserAccount
from app.repositories.action_queue_repository import ActionQueueRepository
from app.schemas.actions import (
    ActionResponse,
    PendingActionListItem,
    PendingActionListResponse,
)
from app.services.ai.action_queue_service import (
    ActionQueueService,
    DispatchResult,
)
from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools import registry
from app.services.ai.tools.base import ActionContext

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _coerce_jsonb(value):
    """asyncpg sometimes returns jsonb as a str; normalize to a dict."""
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value


def _build_service(db: AsyncSession) -> ActionQueueService:
    """Construct a per-request :class:`ActionQueueService` bound to ``db``."""
    return ActionQueueService(
        repo=ActionQueueRepository(db),
        get_tool_by_slug=registry.get,
        build_classify_ctx=lambda uid: ClassifyContext(conn=None, user_account_id=uid),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )


@router.post("/{action_id}/approve", response_model=ActionResponse)
async def approve(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> ActionResponse:
    """Run a pending action's handler and mark it committed."""
    svc = _build_service(db)
    row = await svc._repo.get(action_id)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    pool = await rex_db.get_pool()
    async with pool.acquire() as conn:
        result: DispatchResult = await svc.commit(conn=conn, action_id=action_id)
    return ActionResponse(
        action_id=result.action_id,
        status=result.status,
        requires_approval=result.requires_approval,
        blast_radius=_coerce_jsonb(result.blast_radius),
        result_payload=result.result_payload,
        error_excerpt=result.error_excerpt,
    )


@router.post("/{action_id}/discard", response_model=ActionResponse)
async def discard(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> ActionResponse:
    """Discard a pending action without running its handler."""
    svc = _build_service(db)
    row = await svc._repo.get(action_id)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    result = await svc.discard(action_id=action_id)
    return ActionResponse(
        action_id=result.action_id,
        status=result.status,
        requires_approval=result.requires_approval,
        blast_radius=_coerce_jsonb(result.blast_radius),
    )


@router.post("/{action_id}/undo", response_model=ActionResponse)
async def undo(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> ActionResponse:
    """Undo an auto-committed action if still within the 60s window."""
    svc = _build_service(db)
    row = await svc._repo.get(action_id)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    result = await svc.undo(action_id=action_id)
    return ActionResponse(
        action_id=result.action_id,
        status=result.status,
        requires_approval=result.requires_approval,
        blast_radius=_coerce_jsonb(result.blast_radius),
        error_excerpt=result.error_excerpt,
    )


@router.get("/pending", response_model=PendingActionListResponse)
async def list_pending(
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> PendingActionListResponse:
    """List this user's pending-approval actions (most recent first)."""
    svc = _build_service(db)
    rows = await svc._repo.list_pending_for_user(user_account_id=user.id)
    return PendingActionListResponse(items=[
        PendingActionListItem(
            id=r["id"],
            tool_slug=r["tool_slug"],
            tool_args=_coerce_jsonb(r["tool_args"]),
            blast_radius=_coerce_jsonb(r["blast_radius"]),
            requires_approval=r["requires_approval"],
            status=r["status"],
            created_at=r["created_at"],
            conversation_id=r.get("conversation_id"),
        )
        for r in rows
    ])


__all__ = ["router"]

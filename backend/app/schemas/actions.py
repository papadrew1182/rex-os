"""Phase 6 action routes — Pydantic schemas for /api/actions."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActionResponse(BaseModel):
    action_id: UUID
    status: str
    requires_approval: bool
    blast_radius: dict
    result_payload: dict | None = None
    error_excerpt: str | None = None
    reasons: list[str] | None = None


class PendingActionListItem(BaseModel):
    id: UUID
    tool_slug: str
    tool_args: dict
    blast_radius: dict
    requires_approval: bool
    status: str
    created_at: datetime
    conversation_id: UUID | None = None


class PendingActionListResponse(BaseModel):
    items: list[PendingActionListItem]

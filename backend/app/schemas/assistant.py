"""Pydantic schemas for ``POST /api/assistant/chat`` request surface."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ChatMode = Literal["chat", "action", "command"]


class PageContext(BaseModel):
    route: str | None = None
    surface: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class ClientContext(BaseModel):
    selected_project_id: UUID | None = None
    route_name: str | None = None


class AssistantChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str
    project_id: UUID | None = None
    active_action_slug: str | None = None
    mode: ChatMode = "chat"
    params: dict[str, Any] = Field(default_factory=dict)
    page_context: PageContext = Field(default_factory=PageContext)
    client_context: ClientContext = Field(default_factory=ClientContext)
    stream: bool = True


class AssistantUser(BaseModel):
    """Role-normalized view of the current user.

    Session 2 owns the real identity endpoint; until it lands, this shape
    is built from the existing ``UserAccount.global_role`` via the context
    builder's ``normalize_role`` helper.
    """

    id: UUID
    email: str | None = None
    full_name: str | None = None
    primary_role_key: str
    role_keys: list[str] = Field(default_factory=list)
    legacy_role_aliases: list[str] = Field(default_factory=list)
    project_ids: list[UUID] = Field(default_factory=list)


class AssistantError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

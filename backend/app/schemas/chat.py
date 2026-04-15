"""Pydantic schemas for chat persistence (conversations + messages)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SenderType = Literal["user", "assistant", "system", "tool"]


class ChatMessage(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_type: SenderType
    content: str
    content_format: str = "markdown"
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    model_key: str | None = None
    prompt_key: str | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChatConversationSummary(BaseModel):
    id: UUID
    title: str
    project_id: UUID | None = None
    active_action_slug: str | None = None
    last_message_preview: str | None = None
    last_message_at: datetime
    updated_at: datetime


class ChatConversation(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    project_id: UUID | None = None
    active_action_slug: str | None = None
    page_context: dict[str, Any] = Field(default_factory=dict)
    conversation_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    archived_at: datetime | None = None


class ConversationListResponse(BaseModel):
    items: list[ChatConversationSummary]


class ConversationDetailResponse(BaseModel):
    conversation: ChatConversation
    messages: list[ChatMessage]

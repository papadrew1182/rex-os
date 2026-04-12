from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_account_id: UUID
    project_id: UUID | None
    domain: str
    notification_type: str
    severity: str
    title: str
    body: str | None
    source_type: str | None
    source_id: UUID | None
    action_path: str | None
    dedupe_key: str | None
    created_at: datetime
    read_at: datetime | None
    dismissed_at: datetime | None
    resolved_at: datetime | None


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationCreatePayload(BaseModel):
    """Internal payload used by jobs to upsert notifications.
    Not exposed via HTTP."""
    user_account_id: UUID
    project_id: UUID | None = None
    domain: str
    notification_type: str
    severity: str = "info"
    title: str
    body: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    action_path: str | None = None
    dedupe_key: str | None = None

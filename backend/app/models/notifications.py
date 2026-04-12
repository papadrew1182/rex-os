"""Generic in-app notification model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.foundation import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.user_accounts.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"))
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'info'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action_path: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    email_sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

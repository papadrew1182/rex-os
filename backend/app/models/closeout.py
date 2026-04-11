"""SQLAlchemy ORM models for Domain 6 — Closeout & Warranty (8 tables).

Maps exactly to rex2_canonical_ddl.sql tables 50-57.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, ForeignKey, Integer, Numeric, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.foundation import Base


class CloseoutTemplate(Base):
    __tablename__ = "closeout_templates"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    project_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class CloseoutTemplateItem(Base):
    __tablename__ = "closeout_template_items"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.closeout_templates.id"), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    default_assignee_role: Mapped[str | None] = mapped_column(Text)
    days_before_substantial: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class CloseoutChecklist(Base):
    __tablename__ = "closeout_checklists"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.closeout_templates.id"))
    substantial_completion_date: Mapped[date | None] = mapped_column(Date)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    percent_complete: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class CloseoutChecklistItem(Base):
    __tablename__ = "closeout_checklist_items"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.closeout_checklists.id"), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'not_started'"))
    assigned_company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.companies.id"))
    assigned_person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class Warranty(Base):
    __tablename__ = "warranties"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    commitment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.commitments.id"))
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.companies.id"), nullable=False)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.cost_codes.id"))
    scope_description: Mapped[str] = mapped_column(Text, nullable=False)
    warranty_type: Mapped[str] = mapped_column(Text, nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    is_letter_received: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_om_received: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class WarrantyClaim(Base):
    __tablename__ = "warranty_claims"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    warranty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.warranties.id"), nullable=False)
    claim_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'medium'"))
    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_date: Mapped[date | None] = mapped_column(Date)
    days_open: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(Text)
    cost_to_repair: Mapped[float | None] = mapped_column(Numeric)
    is_covered_by_warranty: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    reported_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class WarrantyAlert(Base):
    __tablename__ = "warranty_alerts"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    warranty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.warranties.id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(Text, nullable=False)
    alert_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class CompletionMilestone(Base):
    __tablename__ = "completion_milestones"
    __table_args__ = (
        UniqueConstraint("project_id", "milestone_type", name="uq_completion_milestones_project_type"),
        {"schema": "rex"},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    milestone_type: Mapped[str] = mapped_column(Text, nullable=False)
    milestone_name: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date)
    variance_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    is_evidence_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    evidence_requirements: Mapped[dict | None] = mapped_column(JSONB)
    certified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

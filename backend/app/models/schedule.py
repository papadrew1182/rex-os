"""SQLAlchemy ORM models for Domain 2 — Schedule (5 tables).

Maps exactly to rex2_canonical_ddl.sql tables 10-14.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.foundation import Base


# ── 10. schedules ───────────────────────────────────────────────────────────

class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.people.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    activities: Mapped[list["ScheduleActivity"]] = relationship(back_populates="schedule")


# ── 11. schedule_activities ─────────────────────────────────────────────────

class ScheduleActivity(Base):
    __tablename__ = "schedule_activities"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.schedules.id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.schedule_activities.id")
    )
    activity_number: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    percent_complete: Mapped[float] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_manually_scheduled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    baseline_start: Mapped[date | None] = mapped_column(Date)
    baseline_end: Mapped[date | None] = mapped_column(Date)
    variance_days: Mapped[int | None] = mapped_column(Integer)
    float_days: Mapped[int | None] = mapped_column(Integer)
    assigned_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.companies.id")
    )
    assigned_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.people.id")
    )
    # Deferred FK to rex.cost_codes — modeled as bare UUID, enforced at DB level
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_finish_date: Mapped[date | None] = mapped_column(Date)
    wbs_code: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    schedule: Mapped[Schedule] = relationship(back_populates="activities")
    parent: Mapped["ScheduleActivity | None"] = relationship(
        remote_side="ScheduleActivity.id"
    )


# ── 12. activity_links ─────────────────────────────────────────────────────

class ActivityLink(Base):
    __tablename__ = "activity_links"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.schedules.id"), nullable=False
    )
    from_activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.schedule_activities.id"), nullable=False
    )
    to_activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.schedule_activities.id"), nullable=False
    )
    link_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'fs'"))
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


# ── 13. schedule_constraints ───────────────────────────────────────────────

class ScheduleConstraint(Base):
    __tablename__ = "schedule_constraints"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.schedule_activities.id"), nullable=False
    )
    constraint_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.people.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


# ── 14. schedule_snapshots ─────────────────────────────────────────────────

class ScheduleSnapshot(Base):
    __tablename__ = "schedule_snapshots"
    __table_args__ = (
        UniqueConstraint("activity_id", "snapshot_date", name="uq_schedule_snapshots_activity_date"),
        {"schema": "rex"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.schedule_activities.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    percent_complete: Mapped[float] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    variance_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

"""SQLAlchemy ORM models for Domain 1 — Foundation (9 tables).

Maps exactly to rex2_canonical_ddl.sql. Field names, types, defaults,
constraints, and FK relationships match the DDL one-to-one.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── 1. projects ─────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    project_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    project_type: Mapped[str | None] = mapped_column(Text)
    address_line1: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    zip: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    contract_value: Mapped[float | None] = mapped_column(Numeric)
    square_footage: Mapped[float | None] = mapped_column(Numeric)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project")


# ── 2. companies ────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    trade: Mapped[str | None] = mapped_column(Text)
    company_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    address_line1: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    zip: Mapped[str | None] = mapped_column(Text)
    license_number: Mapped[str | None] = mapped_column(Text)
    insurance_expiry: Mapped[date | None] = mapped_column(Date)
    insurance_carrier: Mapped[str | None] = mapped_column(Text)
    bonding_capacity: Mapped[float | None] = mapped_column(Numeric)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    people: Mapped[list["Person"]] = relationship(back_populates="company")


# ── 3. people ───────────────────────────────────────────────────────────────

class Person(Base):
    __tablename__ = "people"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.companies.id")
    )
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    role_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    company: Mapped[Company | None] = relationship(back_populates="people")
    user_account: Mapped["UserAccount | None"] = relationship(back_populates="person")


# ── 4. user_accounts ────────────────────────────────────────────────────────

class UserAccount(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("person_id", name="uq_user_accounts_person_id"),
        UniqueConstraint("email", name="uq_user_accounts_email"),
        {"schema": "rex"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.people.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    global_role: Mapped[str | None] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    mfa_secret: Mapped[str | None] = mapped_column(Text)
    last_login: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    person: Mapped[Person] = relationship(back_populates="user_account")


# ── 5. sessions ─────────────────────────────────────────────────────────────

class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.user_accounts.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    device_info: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


# ── 6. role_templates ───────────────────────────────────────────────────────

class RoleTemplate(Base):
    __tablename__ = "role_templates"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    default_access_level: Mapped[str] = mapped_column(Text, nullable=False)
    visible_tools: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    visible_panels: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    quick_action_groups: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    can_write: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    can_approve: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    notification_defaults: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    home_screen: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'my_day'")
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


# ── 7. project_members ─────────────────────────────────────────────────────

class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "person_id", name="uq_project_members_project_person"),
        Index(
            "uq_project_members_active_primary",
            "project_id", "role_template_id",
            unique=True,
            postgresql_where=text("is_primary = true AND is_active = true"),
        ),
        {"schema": "rex"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.people.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.companies.id")
    )
    role_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.role_templates.id")
    )
    access_level: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    project: Mapped[Project] = relationship(back_populates="members")
    person: Mapped[Person] = relationship()
    company: Mapped[Company | None] = relationship()
    role_template: Mapped[RoleTemplate | None] = relationship()


# ── 8. role_template_overrides ──────────────────────────────────────────────

class RoleTemplateOverride(Base):
    __tablename__ = "role_template_overrides"
    __table_args__ = {"schema": "rex"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.project_members.id"), nullable=False
    )
    override_key: Mapped[str] = mapped_column(Text, nullable=False)
    override_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    override_mode: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rex.people.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


# ── 9. connector_mappings ──────────────────────────────────────────────────

class ConnectorMapping(Base):
    __tablename__ = "connector_mappings"
    __table_args__ = (
        UniqueConstraint("rex_table", "connector", "external_id", name="uq_connector_mapping"),
        {"schema": "rex"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    rex_table: Mapped[str] = mapped_column(Text, nullable=False)
    rex_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    connector: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_url: Mapped[str | None] = mapped_column(Text)
    synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


# ── 10. insurance_certificates ──────────────────────────────────────────────

class InsuranceCertificate(Base):
    __tablename__ = "insurance_certificates"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.companies.id"), nullable=False)
    policy_type: Mapped[str] = mapped_column(Text, nullable=False)  # gl|wc|auto|umbrella|other
    carrier: Mapped[str | None] = mapped_column(Text)
    policy_number: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    limit_amount: Mapped[float | None] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'current'"))
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # deferred FK
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


# ── 11. job_runs ─────────────────────────────────────────────────────────────

class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    job_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'system'"))
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.user_accounts.id"))
    summary: Mapped[str | None] = mapped_column(Text)
    error_excerpt: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))

"""SQLAlchemy ORM models for Domain 4 — Financials (14 tables).

Maps exactly to rex2_canonical_ddl.sql tables 27-40.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, ForeignKey, Integer, Numeric, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.foundation import Base


class CostCode(Base):
    __tablename__ = "cost_codes"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_cost_codes_project_code"),
        {"schema": "rex"},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.cost_codes.id"))
    cost_type: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    parent: Mapped["CostCode | None"] = relationship(remote_side="CostCode.id")


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.cost_codes.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    original_budget: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    approved_changes: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    revised_budget: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    committed_costs: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    direct_costs: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    pending_changes: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    projected_cost: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    over_under: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class BudgetSnapshot(Base):
    __tablename__ = "budget_snapshots"
    __table_args__ = (
        UniqueConstraint("budget_line_item_id", "snapshot_date", name="uq_budget_snapshots_item_date"),
        {"schema": "rex"},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    budget_line_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.budget_line_items.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    revised_budget: Mapped[float] = mapped_column(Numeric, nullable=False)
    projected_cost: Mapped[float] = mapped_column(Numeric, nullable=False)
    over_under: Mapped[float] = mapped_column(Numeric, nullable=False)
    committed_costs: Mapped[float] = mapped_column(Numeric, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class PrimeContract(Base):
    __tablename__ = "prime_contracts"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    contract_number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    original_value: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    approved_cos: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    revised_value: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    billed_to_date: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    retention_rate: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("10"))
    executed_date: Mapped[date | None] = mapped_column(Date)
    owner_company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.companies.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class Commitment(Base):
    __tablename__ = "commitments"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.companies.id"), nullable=False)
    commitment_number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    contract_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    executed_date: Mapped[date | None] = mapped_column(Date)
    original_value: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    approved_cos: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    revised_value: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    invoiced_to_date: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    remaining_to_invoice: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    retention_rate: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("10"))
    retention_held: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    scope_of_work: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    estimated_completion_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class CommitmentLineItem(Base):
    __tablename__ = "commitment_line_items"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    commitment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.commitments.id"), nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.cost_codes.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    unit: Mapped[str | None] = mapped_column(Text)
    unit_cost: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class ChangeEvent(Base):
    __tablename__ = "change_events"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    event_number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'tbd'"))
    estimated_amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    rfi_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # deferred FK to rfis
    prime_contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.prime_contracts.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class PotentialChangeOrder(Base):
    __tablename__ = "potential_change_orders"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    change_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.change_events.id"), nullable=False)
    commitment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.commitments.id"), nullable=False)
    pco_number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.cost_codes.id"))
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class CommitmentChangeOrder(Base):
    __tablename__ = "commitment_change_orders"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    commitment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.commitments.id"), nullable=False)
    cco_number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    total_amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    executed_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class PcoCcoLink(Base):
    __tablename__ = "pco_cco_links"
    __table_args__ = (
        UniqueConstraint("pco_id", "cco_id", name="pco_cco_links_pco_id_cco_id_key"),
        {"schema": "rex"},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    pco_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.potential_change_orders.id"), nullable=False)
    cco_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.commitment_change_orders.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class BillingPeriod(Base):
    __tablename__ = "billing_periods"
    __table_args__ = (
        UniqueConstraint("project_id", "period_number", name="uq_billing_periods_project_number"),
        {"schema": "rex"},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class DirectCost(Base):
    __tablename__ = "direct_costs"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.projects.id"), nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.cost_codes.id"), nullable=False)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.companies.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    direct_cost_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_number: Mapped[str | None] = mapped_column(Text)
    payment_method: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class PaymentApplication(Base):
    __tablename__ = "payment_applications"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    commitment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.commitments.id"), nullable=False)
    billing_period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.billing_periods.id"), nullable=False)
    pay_app_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    this_period_amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    total_completed: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    retention_held: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    retention_released: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    net_payment_due: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    submitted_date: Mapped[date | None] = mapped_column(Date)
    approved_date: Mapped[date | None] = mapped_column(Date)
    paid_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.people.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class LienWaiver(Base):
    __tablename__ = "lien_waivers"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    payment_application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.payment_applications.id"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.companies.id"), nullable=False)
    waiver_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    through_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_date: Mapped[date | None] = mapped_column(Date)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # deferred FK to attachments
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class ChangeEventLineItem(Base):
    __tablename__ = "change_event_line_items"
    __table_args__ = {"schema": "rex"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    change_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.change_events.id"), nullable=False)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rex.cost_codes.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

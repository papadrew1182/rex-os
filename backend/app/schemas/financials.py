"""Pydantic request/response schemas for Domain 4 — Financials."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

CostType = Literal["labor", "material", "equipment", "subcontract", "other"]
PrimeContractStatus = Literal["draft", "executed", "closed"]
CommitmentContractType = Literal["subcontract", "purchase_order", "service_agreement"]
CommitmentStatus = Literal["draft", "out_for_bid", "approved", "executed", "closed", "void"]
ChangeEventStatus = Literal["open", "pending", "approved", "closed", "void"]
ChangeReason = Literal["owner_change", "design_change", "unforeseen", "allowance", "contingency"]
EventType = Literal["tbd", "allowance", "contingency", "owner_change", "transfer"]
Scope = Literal["in_scope", "out_of_scope", "tbd"]
PcoStatus = Literal["draft", "pending", "approved", "rejected", "void"]
CcoStatus = Literal["draft", "pending", "approved", "executed", "void"]
BillingPeriodStatus = Literal["open", "locked", "closed"]
PaymentMethod = Literal["check", "ach", "credit_card", "wire"]
PayAppStatus = Literal["draft", "submitted", "under_review", "approved", "paid", "rejected"]
WaiverType = Literal["conditional_progress", "unconditional_progress", "conditional_final", "unconditional_final"]
WaiverStatus = Literal["pending", "received", "approved", "missing"]


# ═══════════════════════════════════════════════════════════════════════════
# Cost Codes
# ═══════════════════════════════════════════════════════════════════════════

class CostCodeCreate(BaseModel):
    project_id: UUID
    code: str
    name: str
    parent_id: UUID | None = None
    cost_type: CostType
    sort_order: int = 0
    is_active: bool = True

class CostCodeUpdate(BaseModel):
    name: str | None = None
    parent_id: UUID | None = None
    cost_type: CostType | None = None
    sort_order: int | None = None
    is_active: bool | None = None

class CostCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; code: str; name: str; parent_id: UUID | None
    cost_type: str; sort_order: int; is_active: bool; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Budget Line Items
# ═══════════════════════════════════════════════════════════════════════════

class BudgetLineItemCreate(BaseModel):
    project_id: UUID
    cost_code_id: UUID
    description: str | None = None
    original_budget: float = 0
    approved_changes: float = 0
    revised_budget: float = 0
    committed_costs: float = 0
    direct_costs: float = 0
    pending_changes: float = 0
    projected_cost: float = 0
    over_under: float = 0
    notes: str | None = None

class BudgetLineItemUpdate(BaseModel):
    description: str | None = None
    original_budget: float | None = None
    approved_changes: float | None = None
    revised_budget: float | None = None
    committed_costs: float | None = None
    direct_costs: float | None = None
    pending_changes: float | None = None
    projected_cost: float | None = None
    over_under: float | None = None
    notes: str | None = None

class BudgetLineItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; cost_code_id: UUID; description: str | None
    original_budget: float; approved_changes: float; revised_budget: float
    committed_costs: float; direct_costs: float; pending_changes: float
    projected_cost: float; over_under: float; notes: str | None
    created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Budget Snapshots
# ═══════════════════════════════════════════════════════════════════════════

class BudgetSnapshotCreate(BaseModel):
    project_id: UUID
    budget_line_item_id: UUID
    snapshot_date: date
    revised_budget: float
    projected_cost: float
    over_under: float
    committed_costs: float

class BudgetSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; budget_line_item_id: UUID; snapshot_date: date
    revised_budget: float; projected_cost: float; over_under: float; committed_costs: float
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Prime Contracts
# ═══════════════════════════════════════════════════════════════════════════

class PrimeContractCreate(BaseModel):
    project_id: UUID
    contract_number: str
    title: str
    status: PrimeContractStatus = "draft"
    original_value: float = 0
    approved_cos: float = 0
    revised_value: float = 0
    billed_to_date: float = 0
    retention_rate: float = 10
    executed_date: date | None = None
    owner_company_id: UUID | None = None

class PrimeContractUpdate(BaseModel):
    title: str | None = None
    status: PrimeContractStatus | None = None
    original_value: float | None = None
    approved_cos: float | None = None
    revised_value: float | None = None
    billed_to_date: float | None = None
    retention_rate: float | None = None
    executed_date: date | None = None
    owner_company_id: UUID | None = None

class PrimeContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; contract_number: str; title: str; status: str
    original_value: float; approved_cos: float; revised_value: float
    billed_to_date: float; retention_rate: float; executed_date: date | None
    owner_company_id: UUID | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Commitments
# ═══════════════════════════════════════════════════════════════════════════

class CommitmentCreate(BaseModel):
    project_id: UUID
    vendor_id: UUID
    commitment_number: str
    title: str
    contract_type: CommitmentContractType
    status: CommitmentStatus = "draft"
    executed_date: date | None = None
    original_value: float = 0
    scope_of_work: str | None = None
    notes: str | None = None
    created_by: UUID | None = None

class CommitmentUpdate(BaseModel):
    title: str | None = None
    status: CommitmentStatus | None = None
    executed_date: date | None = None
    original_value: float | None = None
    approved_cos: float | None = None
    revised_value: float | None = None
    invoiced_to_date: float | None = None
    remaining_to_invoice: float | None = None
    retention_rate: float | None = None
    retention_held: float | None = None
    scope_of_work: str | None = None
    notes: str | None = None

class CommitmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; vendor_id: UUID; commitment_number: str; title: str
    contract_type: str; status: str; executed_date: date | None
    original_value: float; approved_cos: float; revised_value: float
    invoiced_to_date: float; remaining_to_invoice: float; retention_rate: float; retention_held: float
    scope_of_work: str | None; notes: str | None; created_by: UUID | None
    created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Commitment Line Items
# ═══════════════════════════════════════════════════════════════════════════

class CommitmentLineItemCreate(BaseModel):
    commitment_id: UUID
    cost_code_id: UUID
    description: str
    quantity: float = 0
    unit: str | None = None
    unit_cost: float = 0
    amount: float = 0
    sort_order: int = 0

class CommitmentLineItemUpdate(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_cost: float | None = None
    amount: float | None = None
    sort_order: int | None = None

class CommitmentLineItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; commitment_id: UUID; cost_code_id: UUID; description: str
    quantity: float; unit: str | None; unit_cost: float; amount: float; sort_order: int
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Change Events
# ═══════════════════════════════════════════════════════════════════════════

class ChangeEventCreate(BaseModel):
    project_id: UUID
    event_number: str
    title: str
    description: str | None = None
    status: ChangeEventStatus = "open"
    change_reason: ChangeReason
    event_type: EventType
    scope: Scope = "tbd"
    estimated_amount: float = 0
    rfi_id: UUID | None = None
    prime_contract_id: UUID | None = None
    created_by: UUID | None = None

class ChangeEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: ChangeEventStatus | None = None
    scope: Scope | None = None
    estimated_amount: float | None = None
    rfi_id: UUID | None = None
    prime_contract_id: UUID | None = None

class ChangeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; event_number: str; title: str; description: str | None
    status: str; change_reason: str; event_type: str; scope: str; estimated_amount: float
    rfi_id: UUID | None; prime_contract_id: UUID | None; created_by: UUID | None
    created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Potential Change Orders
# ═══════════════════════════════════════════════════════════════════════════

class PotentialChangeOrderCreate(BaseModel):
    change_event_id: UUID
    commitment_id: UUID
    pco_number: str
    title: str
    status: PcoStatus = "draft"
    amount: float = 0
    cost_code_id: UUID | None = None
    description: str | None = None
    created_by: UUID | None = None

class PotentialChangeOrderUpdate(BaseModel):
    title: str | None = None
    status: PcoStatus | None = None
    amount: float | None = None
    cost_code_id: UUID | None = None
    description: str | None = None

class PotentialChangeOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; change_event_id: UUID; commitment_id: UUID; pco_number: str; title: str
    status: str; amount: float; cost_code_id: UUID | None; description: str | None
    created_by: UUID | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Commitment Change Orders
# ═══════════════════════════════════════════════════════════════════════════

class CommitmentChangeOrderCreate(BaseModel):
    commitment_id: UUID
    cco_number: str
    title: str
    status: CcoStatus = "draft"
    total_amount: float = 0
    executed_date: date | None = None
    description: str | None = None
    created_by: UUID | None = None

class CommitmentChangeOrderUpdate(BaseModel):
    title: str | None = None
    status: CcoStatus | None = None
    total_amount: float | None = None
    executed_date: date | None = None
    description: str | None = None

class CommitmentChangeOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; commitment_id: UUID; cco_number: str; title: str; status: str
    total_amount: float; executed_date: date | None; description: str | None
    created_by: UUID | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# PCO-CCO Links
# ═══════════════════════════════════════════════════════════════════════════

class PcoCcoLinkCreate(BaseModel):
    pco_id: UUID
    cco_id: UUID

class PcoCcoLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; pco_id: UUID; cco_id: UUID; created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Billing Periods
# ═══════════════════════════════════════════════════════════════════════════

class BillingPeriodCreate(BaseModel):
    project_id: UUID
    period_number: int
    start_date: date
    end_date: date
    due_date: date
    status: BillingPeriodStatus = "open"

class BillingPeriodUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    due_date: date | None = None
    status: BillingPeriodStatus | None = None

class BillingPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; period_number: int; start_date: date; end_date: date
    due_date: date; status: str; created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Direct Costs
# ═══════════════════════════════════════════════════════════════════════════

class DirectCostCreate(BaseModel):
    project_id: UUID
    cost_code_id: UUID
    vendor_id: UUID | None = None
    description: str
    amount: float = 0
    direct_cost_date: date
    invoice_number: str | None = None
    payment_method: PaymentMethod | None = None
    created_by: UUID | None = None

class DirectCostUpdate(BaseModel):
    description: str | None = None
    amount: float | None = None
    invoice_number: str | None = None
    payment_method: PaymentMethod | None = None

class DirectCostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; cost_code_id: UUID; vendor_id: UUID | None
    description: str; amount: float; direct_cost_date: date; invoice_number: str | None
    payment_method: str | None; created_by: UUID | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Payment Applications
# ═══════════════════════════════════════════════════════════════════════════

class PaymentApplicationCreate(BaseModel):
    commitment_id: UUID
    billing_period_id: UUID
    pay_app_number: int
    status: PayAppStatus = "draft"
    period_start: date
    period_end: date
    this_period_amount: float = 0
    total_completed: float = 0
    retention_held: float = 0
    retention_released: float = 0
    net_payment_due: float = 0
    created_by: UUID | None = None

class PaymentApplicationUpdate(BaseModel):
    status: PayAppStatus | None = None
    this_period_amount: float | None = None
    total_completed: float | None = None
    retention_held: float | None = None
    retention_released: float | None = None
    net_payment_due: float | None = None
    submitted_date: date | None = None
    approved_date: date | None = None
    paid_date: date | None = None

class PaymentApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; commitment_id: UUID; billing_period_id: UUID; pay_app_number: int; status: str
    period_start: date; period_end: date; this_period_amount: float; total_completed: float
    retention_held: float; retention_released: float; net_payment_due: float
    submitted_date: date | None; approved_date: date | None; paid_date: date | None
    created_by: UUID | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Lien Waivers
# ═══════════════════════════════════════════════════════════════════════════

class LienWaiverCreate(BaseModel):
    payment_application_id: UUID
    vendor_id: UUID
    waiver_type: WaiverType
    status: WaiverStatus = "pending"
    amount: float = 0
    through_date: date
    received_date: date | None = None
    attachment_id: UUID | None = None
    notes: str | None = None

class LienWaiverUpdate(BaseModel):
    status: WaiverStatus | None = None
    amount: float | None = None
    received_date: date | None = None
    attachment_id: UUID | None = None
    notes: str | None = None

class LienWaiverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; payment_application_id: UUID; vendor_id: UUID; waiver_type: str; status: str
    amount: float; through_date: date; received_date: date | None; attachment_id: UUID | None
    notes: str | None; created_at: datetime; updated_at: datetime


# ── Sprint B: Financial intelligence response models ───────────────────────

class BudgetLineItemRollupResponse(BaseModel):
    budget_line_item_id: UUID
    original_budget: float
    approved_changes: float
    committed_costs: float
    direct_costs: float
    pending_changes: float
    revised_budget: float
    projected_cost: float
    over_under: float


class BudgetRollupRefreshResponse(BaseModel):
    project_id: UUID
    total_line_items: int
    updated_count: int


class BillingPeriodSummaryResponse(BaseModel):
    billing_period_id: UUID
    project_id: UUID
    period_number: int
    start_date: date
    end_date: date
    due_date: date
    status: str
    pay_app_count: int
    total_this_period_amount: float
    total_completed: float
    total_retention_held: float
    total_approved_amount: float
    total_paid_amount: float
    counts_by_status: dict[str, int]


class ProjectBillingPeriodSummaryResponse(BaseModel):
    project_id: UUID
    total_periods: int
    grand_total_this_period: float
    grand_total_paid: float
    periods: list[BillingPeriodSummaryResponse]


class PaymentApplicationSummaryResponse(BaseModel):
    payment_application_id: UUID
    pay_app_number: int
    status: str
    period_start: date
    period_end: date
    this_period_amount: float
    total_completed: float
    retention_held: float
    retention_released: float
    net_payment_due: float
    submitted_date: date | None
    approved_date: date | None
    paid_date: date | None
    commitment_id: UUID
    commitment_number: str | None
    commitment_title: str | None
    vendor_id: UUID | None
    billing_period_id: UUID
    billing_period_number: int | None
    lien_waiver_count: int
    lien_waivers_by_status: dict[str, int]


class CommitmentSummaryResponse(BaseModel):
    commitment_id: UUID
    commitment_number: str
    title: str
    vendor_id: UUID
    contract_type: str
    status: str
    original_value: float
    approved_cos: float
    revised_value: float
    invoiced_to_date: float
    remaining_to_invoice: float
    retention_held: float
    pco_count: int
    pco_total_amount: float
    pco_counts_by_status: dict[str, int]
    cco_count: int
    cco_total_amount: float
    cco_counts_by_status: dict[str, int]
    linked_pco_to_cco_count: int
    pay_app_count: int

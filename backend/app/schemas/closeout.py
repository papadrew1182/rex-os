"""Pydantic request/response schemas for Domain 6 — Closeout & Warranty."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ProjectType = Literal["retail", "multifamily", "all"]
Category = Literal["documentation", "general", "mep", "exterior", "interior"]
AssigneeRole = Literal["vp", "general_super", "lead_super", "asst_super", "accountant"]
ChecklistItemStatus = Literal["not_started", "in_progress", "complete", "n_a"]
WarrantyType = Literal["standard", "extended", "manufacturer", "labor_only", "material_only"]
WarrantyStatus = Literal["active", "expiring_soon", "expired", "claimed"]
ClaimStatus = Literal["open", "in_progress", "resolved", "disputed", "closed"]
ClaimPriority = Literal["low", "medium", "high", "critical"]
AlertType = Literal["90_day", "30_day", "expired"]
MilestoneType = Literal[
    "substantial_completion", "final_completion", "tco", "final_co",
    "holdback_release", "rough_in", "sheetrock_prime",
    "foundation_podium", "topped_out", "first_turnover_tco",
]
MilestoneStatus = Literal["pending", "achieved", "overdue"]


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Templates
# ═══════════════════════════════════════════════════════════════════════════

class CloseoutTemplateCreate(BaseModel):
    name: str; project_type: ProjectType; is_default: bool = False; created_by: UUID | None = None

class CloseoutTemplateUpdate(BaseModel):
    name: str | None = None; project_type: ProjectType | None = None; is_default: bool | None = None

class CloseoutTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; name: str; project_type: str; is_default: bool; created_by: UUID | None
    created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Template Items
# ═══════════════════════════════════════════════════════════════════════════

class CloseoutTemplateItemCreate(BaseModel):
    template_id: UUID; category: Category; item_number: int; name: str
    default_assignee_role: AssigneeRole | None = None
    days_before_substantial: int | None = None; sort_order: int = 0

class CloseoutTemplateItemUpdate(BaseModel):
    name: str | None = None; default_assignee_role: AssigneeRole | None = None
    days_before_substantial: int | None = None; sort_order: int | None = None

class CloseoutTemplateItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; template_id: UUID; category: str; item_number: int; name: str
    default_assignee_role: str | None; days_before_substantial: int | None
    sort_order: int; created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Checklists
# ═══════════════════════════════════════════════════════════════════════════

class CloseoutChecklistCreate(BaseModel):
    project_id: UUID; template_id: UUID | None = None
    substantial_completion_date: date | None = None
    total_items: int = 0; completed_items: int = 0; percent_complete: float = 0
    created_by: UUID | None = None

class CloseoutChecklistUpdate(BaseModel):
    substantial_completion_date: date | None = None
    total_items: int | None = None; completed_items: int | None = None
    percent_complete: float | None = None

class CloseoutChecklistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; template_id: UUID | None
    substantial_completion_date: date | None; total_items: int; completed_items: int
    percent_complete: float; created_by: UUID | None; created_at: datetime; updated_at: datetime


class CreateChecklistFromTemplateRequest(BaseModel):
    project_id: UUID
    template_id: UUID
    substantial_completion_date: date | None = None


# ═══════════════════════════════════════════════════════════════════════════
# Closeout Checklist Items
# ═══════════════════════════════════════════════════════════════════════════

class CloseoutChecklistItemCreate(BaseModel):
    checklist_id: UUID; category: Category; item_number: int; name: str
    status: ChecklistItemStatus = "not_started"
    assigned_company_id: UUID | None = None; assigned_person_id: UUID | None = None
    due_date: date | None = None; notes: str | None = None; sort_order: int = 0
    spec_division: str | None = None
    spec_section: str | None = None

class CloseoutChecklistItemUpdate(BaseModel):
    status: ChecklistItemStatus | None = None
    assigned_company_id: UUID | None = None; assigned_person_id: UUID | None = None
    due_date: date | None = None; completed_date: date | None = None
    completed_by: UUID | None = None; notes: str | None = None; sort_order: int | None = None
    spec_division: str | None = None
    spec_section: str | None = None

class CloseoutChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; checklist_id: UUID; category: str; item_number: int; name: str; status: str
    assigned_company_id: UUID | None; assigned_person_id: UUID | None
    due_date: date | None; completed_date: date | None; completed_by: UUID | None
    notes: str | None; sort_order: int
    spec_division: str | None
    spec_section: str | None
    created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Warranties
# ═══════════════════════════════════════════════════════════════════════════

class WarrantyCreate(BaseModel):
    project_id: UUID; company_id: UUID; scope_description: str
    warranty_type: WarrantyType; duration_months: int; start_date: date
    expiration_date: date | None = None  # computed from start_date + duration_months if omitted
    commitment_id: UUID | None = None; cost_code_id: UUID | None = None
    status: WarrantyStatus = "active"; is_letter_received: bool = False
    is_om_received: bool = False; notes: str | None = None; created_by: UUID | None = None
    system_or_product: str | None = None; manufacturer: str | None = None

class WarrantyUpdate(BaseModel):
    status: WarrantyStatus | None = None; is_letter_received: bool | None = None
    is_om_received: bool | None = None; notes: str | None = None
    expiration_date: date | None = None
    system_or_product: str | None = None; manufacturer: str | None = None

class WarrantyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; commitment_id: UUID | None; company_id: UUID
    cost_code_id: UUID | None; scope_description: str; warranty_type: str
    duration_months: int; start_date: date; expiration_date: date; status: str
    is_letter_received: bool; is_om_received: bool; notes: str | None
    created_by: UUID | None; created_at: datetime; updated_at: datetime
    system_or_product: str | None; manufacturer: str | None


# ═══════════════════════════════════════════════════════════════════════════
# Warranty Claims
# ═══════════════════════════════════════════════════════════════════════════

class WarrantyClaimCreate(BaseModel):
    warranty_id: UUID; claim_number: int; title: str; description: str
    status: ClaimStatus = "open"; priority: ClaimPriority = "medium"
    reported_date: date; location: str | None = None
    cost_to_repair: float | None = None; is_covered_by_warranty: bool = True
    reported_by: UUID | None = None

class WarrantyClaimUpdate(BaseModel):
    title: str | None = None; status: ClaimStatus | None = None
    priority: ClaimPriority | None = None; resolved_date: date | None = None
    days_open: int | None = None; cost_to_repair: float | None = None
    is_covered_by_warranty: bool | None = None

class WarrantyClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; warranty_id: UUID; claim_number: int; title: str; description: str
    status: str; priority: str; reported_date: date; resolved_date: date | None
    days_open: int | None; location: str | None; cost_to_repair: float | None
    is_covered_by_warranty: bool; reported_by: UUID | None
    created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Warranty Alerts
# ═══════════════════════════════════════════════════════════════════════════

class WarrantyAlertCreate(BaseModel):
    warranty_id: UUID; alert_type: AlertType; alert_date: date
    is_sent: bool = False; sent_at: datetime | None = None; recipient_id: UUID | None = None

class WarrantyAlertUpdate(BaseModel):
    is_sent: bool | None = None; sent_at: datetime | None = None
    recipient_id: UUID | None = None

class WarrantyAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; warranty_id: UUID; alert_type: str; alert_date: date
    is_sent: bool; sent_at: datetime | None; recipient_id: UUID | None; created_at: datetime


class GenerateAlertsResponse(BaseModel):
    warranty_id: UUID
    alerts_created: int
    alerts: list[WarrantyAlertResponse]


# ═══════════════════════════════════════════════════════════════════════════
# Completion Milestones
# ═══════════════════════════════════════════════════════════════════════════

class CompletionMilestoneCreate(BaseModel):
    project_id: UUID; milestone_type: MilestoneType; milestone_name: str
    scheduled_date: date | None = None; actual_date: date | None = None
    forecast_date: date | None = None; percent_complete: float = 0
    variance_days: int | None = None; status: MilestoneStatus = "pending"
    is_evidence_complete: bool = False; evidence_requirements: Any | None = None
    certified_by: UUID | None = None; notes: str | None = None; sort_order: int = 0

class CompletionMilestoneUpdate(BaseModel):
    milestone_name: str | None = None; scheduled_date: date | None = None
    actual_date: date | None = None; variance_days: int | None = None
    forecast_date: date | None = None; percent_complete: float | None = None
    status: MilestoneStatus | None = None; is_evidence_complete: bool | None = None
    evidence_requirements: Any | None = None; certified_by: UUID | None = None
    notes: str | None = None; sort_order: int | None = None

class CompletionMilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; milestone_type: str; milestone_name: str
    scheduled_date: date | None; actual_date: date | None; variance_days: int | None
    forecast_date: date | None; percent_complete: float
    status: str; is_evidence_complete: bool; evidence_requirements: Any | None
    certified_by: UUID | None; notes: str | None; sort_order: int
    created_at: datetime; updated_at: datetime


class EvidenceChecklistItem(BaseModel):
    item: str
    source: str | None = None


class EvidenceChecklistResponse(BaseModel):
    milestone_id: UUID
    milestone_type: str
    milestone_name: str
    status: str
    is_evidence_complete: bool
    checklist: list[EvidenceChecklistItem]
    payout_percent: float | None = None
    holdback_percent: float | None = None
    gate_conditions: list[str] | None = None
    trigger_condition: str | None = None


class EvaluateEvidenceRequest(BaseModel):
    all_items_complete: bool
    notes: str | None = None


class EvaluateEvidenceResponse(BaseModel):
    milestone_id: UUID
    is_evidence_complete: bool
    notes: str | None


class CertifyMilestoneRequest(BaseModel):
    certified_by: UUID
    actual_date: date | None = None
    notes: str | None = None


class CertifyMilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    milestone_type: str
    milestone_name: str
    status: str
    certified_by: UUID | None
    actual_date: date | None
    is_evidence_complete: bool
    notes: str | None
    evidence_incomplete_warning: bool | None = None


GateStatus = Literal["pass", "warning", "fail", "not_applicable"]


class GateResultItem(BaseModel):
    code: str
    label: str
    status: GateStatus
    detail: str


class GateEvaluationResponse(BaseModel):
    milestone_id: UUID
    milestone_type: str
    gate_status: GateStatus
    gate_results: list[GateResultItem]
    summary_message: str


ReadinessStatus = Literal["pass", "warning", "fail", "not_started"]


class ChecklistSummary(BaseModel):
    checklist_count: int
    best_percent_complete: float
    total_items: int
    completed_items: int


class MilestoneSummaryItem(BaseModel):
    milestone_type: str
    milestone_name: str
    status: str
    is_evidence_complete: bool
    certified_by: UUID | None


class MilestoneSummary(BaseModel):
    total_milestones: int
    achieved_count: int
    evidence_complete_count: int
    certified_count: int
    milestones: list[MilestoneSummaryItem]


class HoldbackReleaseSummary(BaseModel):
    exists: bool
    status: str | None = None
    gate_status: str | None = None
    gate_summary: str | None = None


class WarrantySummary(BaseModel):
    total_warranties: int
    claimed_count: int
    expiring_soon_count: int
    alert_count: int


class OpenIssueItem(BaseModel):
    severity: str
    message: str


class ProjectCloseoutReadinessResponse(BaseModel):
    project_id: UUID
    project_name: str
    overall_status: ReadinessStatus
    summary_message: str
    checklist_summary: ChecklistSummary
    milestone_summary: MilestoneSummary
    holdback_release: HoldbackReleaseSummary
    warranty_summary: WarrantySummary
    open_issues: list[OpenIssueItem]


class PortfolioProjectRow(BaseModel):
    project_id: UUID
    project_name: str
    project_number: str | None
    project_type: str | None
    city: str | None
    state: str | None
    project_status: str
    readiness_status: ReadinessStatus
    summary_message: str
    best_checklist_percent: float
    achieved_milestones: int
    total_milestones: int
    holdback_gate_status: str | None
    claimed_warranty_count: int
    expiring_soon_count: int
    open_issue_count: int


class PortfolioReadinessSummary(BaseModel):
    total_projects: int
    pass_count: int
    warning_count: int
    fail_count: int
    not_started_count: int


class PortfolioReadinessResponse(BaseModel):
    summary: PortfolioReadinessSummary
    projects: list[PortfolioProjectRow]


class WarrantyStatusRefreshResponse(BaseModel):
    project_id: UUID
    total_warranties: int
    updated_count: int
    by_status: dict[str, int]


# ═══════════════════════════════════════════════════════════════════════════
# O&M Manuals
# ═══════════════════════════════════════════════════════════════════════════

OmManualStatus = Literal["pending", "partial", "received", "approved", "n_a"]


class OmManualCreate(BaseModel):
    project_id: UUID
    spec_section: str
    spec_title: str | None = None
    required_count: int = 1
    received_count: int = 0
    status: OmManualStatus = "pending"
    vendor_company_id: UUID | None = None
    notes: str | None = None


class OmManualUpdate(BaseModel):
    spec_section: str | None = None
    spec_title: str | None = None
    required_count: int | None = None
    received_count: int | None = None
    status: OmManualStatus | None = None
    vendor_company_id: UUID | None = None
    notes: str | None = None


class OmManualResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    spec_section: str
    spec_title: str | None
    required_count: int
    received_count: int
    status: str
    vendor_company_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

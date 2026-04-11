"""Pydantic request/response schemas for Domain 5 — Document Management."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

Discipline = Literal["architectural", "structural", "mechanical", "electrical", "plumbing", "civil"]
RfiStatus = Literal["draft", "open", "answered", "closed", "void"]
Priority = Literal["low", "medium", "high"]
ImpactChoice = Literal["yes", "no", "tbd"]
SubmittalPkgStatus = Literal["open", "closed"]
SubmittalStatus = Literal["draft", "pending", "submitted", "approved", "approved_as_noted", "rejected", "closed"]
SubmittalType = Literal["shop_drawing", "product_data", "sample", "mock_up", "test_report", "other"]
CorrespondenceType = Literal["letter", "email", "memo", "notice", "transmittal"]
CorrespondenceStatus = Literal["draft", "sent", "received", "closed"]


# ═══════════════════════════════════════════════════════════════════════════
# Drawing Areas
# ═══════════════════════════════════════════════════════════════════════════

class DrawingAreaCreate(BaseModel):
    project_id: UUID; name: str; sort_order: int = 0

class DrawingAreaUpdate(BaseModel):
    name: str | None = None; sort_order: int | None = None

class DrawingAreaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; name: str; sort_order: int; created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Drawings
# ═══════════════════════════════════════════════════════════════════════════

class DrawingCreate(BaseModel):
    project_id: UUID; drawing_area_id: UUID; drawing_number: str; title: str
    discipline: Discipline; current_revision: int = 0
    current_revision_date: date | None = None; is_current: bool = True; image_url: str | None = None

class DrawingUpdate(BaseModel):
    title: str | None = None; current_revision: int | None = None
    current_revision_date: date | None = None; is_current: bool | None = None; image_url: str | None = None

class DrawingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; drawing_area_id: UUID; drawing_number: str; title: str
    discipline: str; current_revision: int; current_revision_date: date | None
    is_current: bool; image_url: str | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Drawing Revisions
# ═══════════════════════════════════════════════════════════════════════════

class DrawingRevisionCreate(BaseModel):
    drawing_id: UUID; revision_number: int; revision_date: date
    description: str | None = None; image_url: str; uploaded_by: UUID | None = None

class DrawingRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; drawing_id: UUID; revision_number: int; revision_date: date
    description: str | None; image_url: str; uploaded_by: UUID | None; created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Specifications
# ═══════════════════════════════════════════════════════════════════════════

class SpecificationCreate(BaseModel):
    project_id: UUID; section_number: str; title: str; division: str
    current_revision: int = 0; revision_date: date | None = None; attachment_id: UUID | None = None

class SpecificationUpdate(BaseModel):
    title: str | None = None; current_revision: int | None = None
    revision_date: date | None = None; attachment_id: UUID | None = None

class SpecificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; section_number: str; title: str; division: str
    current_revision: int; revision_date: date | None; attachment_id: UUID | None
    created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# RFIs
# ═══════════════════════════════════════════════════════════════════════════

class RfiCreate(BaseModel):
    project_id: UUID; rfi_number: str; subject: str; question: str
    status: RfiStatus = "draft"; priority: Priority = "medium"
    cost_impact: ImpactChoice | None = None; schedule_impact: ImpactChoice | None = None
    cost_code_id: UUID | None = None; assigned_to: UUID | None = None
    ball_in_court: UUID | None = None; created_by: UUID | None = None
    due_date: date | None = None; drawing_id: UUID | None = None
    spec_section: str | None = None; location: str | None = None
    rfi_manager: UUID | None = None

class RfiUpdate(BaseModel):
    subject: str | None = None; status: RfiStatus | None = None; priority: Priority | None = None
    question: str | None = None; answer: str | None = None
    cost_impact: ImpactChoice | None = None; schedule_impact: ImpactChoice | None = None
    assigned_to: UUID | None = None; ball_in_court: UUID | None = None
    due_date: date | None = None; answered_date: date | None = None; days_open: int | None = None
    location: str | None = None
    rfi_manager: UUID | None = None

class RfiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; rfi_number: str; subject: str; status: str; priority: str
    question: str; answer: str | None; cost_impact: str | None; schedule_impact: str | None
    cost_code_id: UUID | None; assigned_to: UUID | None; ball_in_court: UUID | None
    created_by: UUID | None; rfi_manager: UUID | None; due_date: date | None; answered_date: date | None
    days_open: int | None; drawing_id: UUID | None; spec_section: str | None
    location: str | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Submittal Packages
# ═══════════════════════════════════════════════════════════════════════════

class SubmittalPackageCreate(BaseModel):
    project_id: UUID; package_number: str; title: str
    status: SubmittalPkgStatus = "open"; total_submittals: int = 0; approved_count: int = 0

class SubmittalPackageUpdate(BaseModel):
    title: str | None = None; status: SubmittalPkgStatus | None = None
    total_submittals: int | None = None; approved_count: int | None = None

class SubmittalPackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; package_number: str; title: str; status: str
    total_submittals: int; approved_count: int; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Submittals
# ═══════════════════════════════════════════════════════════════════════════

class SubmittalCreate(BaseModel):
    project_id: UUID; submittal_number: str; title: str; submittal_type: SubmittalType
    submittal_package_id: UUID | None = None; status: SubmittalStatus = "draft"
    spec_section: str | None = None; current_revision: int = 0
    cost_code_id: UUID | None = None; schedule_activity_id: UUID | None = None
    assigned_to: UUID | None = None; ball_in_court: UUID | None = None
    responsible_contractor: UUID | None = None; created_by: UUID | None = None
    due_date: date | None = None; lead_time_days: int | None = None
    required_on_site: date | None = None; location: str | None = None
    submittal_manager_id: UUID | None = None; is_critical_path: bool = False

class SubmittalUpdate(BaseModel):
    title: str | None = None; status: SubmittalStatus | None = None
    spec_section: str | None = None; current_revision: int | None = None
    assigned_to: UUID | None = None; ball_in_court: UUID | None = None
    due_date: date | None = None; submitted_date: date | None = None
    approved_date: date | None = None; lead_time_days: int | None = None
    required_on_site: date | None = None; location: str | None = None
    submittal_manager_id: UUID | None = None; is_critical_path: bool | None = None

class SubmittalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; submittal_package_id: UUID | None; submittal_number: str
    title: str; status: str; submittal_type: str; spec_section: str | None
    current_revision: int; cost_code_id: UUID | None; schedule_activity_id: UUID | None
    assigned_to: UUID | None; ball_in_court: UUID | None; responsible_contractor: UUID | None
    created_by: UUID | None; submittal_manager_id: UUID | None; is_critical_path: bool
    due_date: date | None; submitted_date: date | None
    approved_date: date | None; lead_time_days: int | None; required_on_site: date | None
    location: str | None; created_at: datetime; updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Attachments
# ═══════════════════════════════════════════════════════════════════════════

class AttachmentCreate(BaseModel):
    project_id: UUID; source_type: str; source_id: UUID
    filename: str; file_size: int; content_type: str
    storage_url: str; storage_key: str; uploaded_by: UUID | None = None

class AttachmentUpdate(BaseModel):
    filename: str | None = None; content_type: str | None = None

class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; source_type: str; source_id: UUID
    filename: str; file_size: int; content_type: str; storage_url: str; storage_key: str
    uploaded_by: UUID | None; created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Correspondence
# ═══════════════════════════════════════════════════════════════════════════

class CorrespondenceCreate(BaseModel):
    project_id: UUID; correspondence_number: str; subject: str
    correspondence_type: CorrespondenceType; status: CorrespondenceStatus = "draft"
    from_person_id: UUID | None = None; to_person_id: UUID | None = None
    body: str | None = None; created_by: UUID | None = None

class CorrespondenceUpdate(BaseModel):
    subject: str | None = None; status: CorrespondenceStatus | None = None
    body: str | None = None; sent_date: date | None = None; received_date: date | None = None

class CorrespondenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; project_id: UUID; correspondence_number: str; subject: str
    correspondence_type: str; status: str; from_person_id: UUID | None
    to_person_id: UUID | None; body: str | None; sent_date: date | None
    received_date: date | None; created_by: UUID | None; created_at: datetime; updated_at: datetime


class RfiAgingResponse(BaseModel):
    rfi_id: UUID
    rfi_number: str
    status: str
    is_open: bool
    days_open: int | None
    is_overdue: bool
    days_overdue: int
    due_date: date | None
    answered_date: date | None


class RfiAgingSummaryResponse(BaseModel):
    project_id: UUID
    total_rfis: int
    open_count: int
    overdue_count: int
    average_days_open: float
    items: list[RfiAgingResponse]


class SubmittalAgingResponse(BaseModel):
    submittal_id: UUID
    submittal_number: str
    status: str
    is_open: bool
    days_open: int | None
    is_overdue: bool
    days_overdue: int
    due_date: date | None
    required_on_site: date | None
    days_to_required_onsite: int | None


class SubmittalAgingSummaryResponse(BaseModel):
    project_id: UUID
    total_submittals: int
    open_count: int
    overdue_count: int
    average_days_open: float
    items: list[SubmittalAgingResponse]

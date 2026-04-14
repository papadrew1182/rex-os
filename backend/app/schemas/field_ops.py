"""Pydantic request/response schemas for Domain 3 — Field Ops."""

from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DailyLogStatus = Literal["draft", "submitted", "approved"]
PunchStatus = Literal["draft", "open", "work_required", "ready_for_review", "ready_to_close", "closed"]
Priority = Literal["low", "medium", "high"]
PriorityCritical = Literal["low", "medium", "high", "critical"]
ImpactChoice = Literal["yes", "no", "tbd"]
InspectionType = Literal["municipal", "quality", "safety", "pre_concrete", "framing", "mep_rough", "mep_final", "other"]
InspectionStatus = Literal["scheduled", "in_progress", "passed", "failed", "partial", "cancelled"]
InspectionResult = Literal["pass", "fail", "n_a", "not_inspected"]
ObservationType = Literal["safety", "quality", "housekeeping", "environmental", "commissioning"]
ObservationStatus = Literal["open", "in_progress", "closed"]
IncidentType = Literal["near_miss", "first_aid", "recordable", "lost_time", "property_damage", "environmental"]
IncidentSeverity = Literal["minor", "moderate", "serious", "critical"]
IncidentStatus = Literal["open", "under_investigation", "corrective_action", "closed"]
TaskStatus = Literal["open", "in_progress", "complete", "void"]
TaskCategory = Literal["safety", "quality", "coordination", "admin", "closeout", "hygiene"]
ActionItemStatus = Literal["open", "complete", "void"]


# ═══════════════════════════════════════════════════════════════════════════
# Daily Logs
# ═══════════════════════════════════════════════════════════════════════════

class DailyLogCreate(BaseModel):
    project_id: UUID
    log_date: date
    status: DailyLogStatus = "draft"
    weather_summary: str | None = None
    temp_high_f: int | None = None
    temp_low_f: int | None = None
    is_weather_delay: bool = False
    work_summary: str | None = None
    delay_notes: str | None = None
    safety_notes: str | None = None
    visitor_notes: str | None = None
    created_by: UUID | None = None


class DailyLogUpdate(BaseModel):
    status: DailyLogStatus | None = None
    weather_summary: str | None = None
    temp_high_f: int | None = None
    temp_low_f: int | None = None
    is_weather_delay: bool | None = None
    work_summary: str | None = None
    delay_notes: str | None = None
    safety_notes: str | None = None
    visitor_notes: str | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None


class DailyLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    log_date: date
    status: str
    weather_summary: str | None
    temp_high_f: int | None
    temp_low_f: int | None
    is_weather_delay: bool
    work_summary: str | None
    delay_notes: str | None
    safety_notes: str | None
    visitor_notes: str | None
    created_by: UUID | None
    approved_by: UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Manpower Entries
# ═══════════════════════════════════════════════════════════════════════════

class ManpowerEntryCreate(BaseModel):
    daily_log_id: UUID
    company_id: UUID
    worker_count: int
    hours: float
    description: str | None = None


class ManpowerEntryUpdate(BaseModel):
    worker_count: int | None = None
    hours: float | None = None
    description: str | None = None


class ManpowerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    daily_log_id: UUID
    company_id: UUID
    worker_count: int
    hours: float
    description: str | None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Punch Items
# ═══════════════════════════════════════════════════════════════════════════

class PunchItemCreate(BaseModel):
    project_id: UUID
    punch_number: int
    title: str
    description: str | None = None
    status: PunchStatus = "draft"
    priority: Priority = "medium"
    punch_type: str | None = None
    assigned_company_id: UUID | None = None
    assigned_to: UUID | None = None
    punch_manager_id: UUID | None = None
    final_approver_id: UUID | None = None
    location: str | None = None
    drawing_id: UUID | None = None
    cost_code_id: UUID | None = None
    cost_impact: ImpactChoice | None = None
    schedule_impact: ImpactChoice | None = None
    due_date: date | None = None
    created_by: UUID | None = None
    closed_by: UUID | None = None
    is_critical_path: bool = False


class PunchItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: PunchStatus | None = None
    priority: Priority | None = None
    punch_type: str | None = None
    assigned_company_id: UUID | None = None
    assigned_to: UUID | None = None
    punch_manager_id: UUID | None = None
    final_approver_id: UUID | None = None
    location: str | None = None
    drawing_id: UUID | None = None
    cost_code_id: UUID | None = None
    cost_impact: ImpactChoice | None = None
    schedule_impact: ImpactChoice | None = None
    due_date: date | None = None
    closed_date: date | None = None
    days_open: int | None = None
    closed_by: UUID | None = None
    is_critical_path: bool | None = None


class PunchItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    punch_number: int
    title: str
    description: str | None
    status: str
    priority: str
    punch_type: str | None
    assigned_company_id: UUID | None
    assigned_to: UUID | None
    punch_manager_id: UUID | None
    final_approver_id: UUID | None
    location: str | None
    drawing_id: UUID | None
    cost_code_id: UUID | None
    cost_impact: str | None
    schedule_impact: str | None
    due_date: date | None
    closed_date: date | None
    days_open: int | None
    created_by: UUID | None
    closed_by: UUID | None
    is_critical_path: bool
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Inspections
# ═══════════════════════════════════════════════════════════════════════════

class InspectionCreate(BaseModel):
    project_id: UUID
    inspection_number: str
    title: str
    inspection_type: InspectionType
    status: InspectionStatus = "scheduled"
    scheduled_date: date
    completed_date: date | None = None
    inspector_name: str | None = None
    inspecting_company_id: UUID | None = None
    responsible_person_id: UUID | None = None
    location: str | None = None
    activity_id: UUID | None = None
    comments: str | None = None
    created_by: UUID | None = None


class InspectionUpdate(BaseModel):
    title: str | None = None
    status: InspectionStatus | None = None
    scheduled_date: date | None = None
    completed_date: date | None = None
    inspector_name: str | None = None
    location: str | None = None
    comments: str | None = None


class InspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    inspection_number: str
    title: str
    inspection_type: str
    status: str
    scheduled_date: date
    completed_date: date | None
    inspector_name: str | None
    inspecting_company_id: UUID | None
    responsible_person_id: UUID | None
    location: str | None
    activity_id: UUID | None
    comments: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Inspection Items
# ═══════════════════════════════════════════════════════════════════════════

class InspectionItemCreate(BaseModel):
    inspection_id: UUID
    item_number: int
    description: str
    result: InspectionResult
    comments: str | None = None
    punch_item_id: UUID | None = None


class InspectionItemUpdate(BaseModel):
    description: str | None = None
    result: InspectionResult | None = None
    comments: str | None = None
    punch_item_id: UUID | None = None


class InspectionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    inspection_id: UUID
    item_number: int
    description: str
    result: str
    comments: str | None
    punch_item_id: UUID | None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Observations
# ═══════════════════════════════════════════════════════════════════════════

class ObservationCreate(BaseModel):
    project_id: UUID
    observation_number: int
    title: str
    observation_type: ObservationType
    status: ObservationStatus = "open"
    priority: PriorityCritical = "medium"
    description: str
    corrective_action: str | None = None
    location: str | None = None
    assigned_to: UUID | None = None
    assigned_company_id: UUID | None = None
    due_date: date | None = None
    created_by: UUID | None = None
    contributing_behavior: str | None = None
    contributing_condition: str | None = None


class ObservationUpdate(BaseModel):
    title: str | None = None
    status: ObservationStatus | None = None
    priority: PriorityCritical | None = None
    corrective_action: str | None = None
    location: str | None = None
    assigned_to: UUID | None = None
    assigned_company_id: UUID | None = None
    due_date: date | None = None
    closed_date: date | None = None
    contributing_behavior: str | None = None
    contributing_condition: str | None = None


class ObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    observation_number: int
    title: str
    observation_type: str
    status: str
    priority: str
    description: str
    corrective_action: str | None
    location: str | None
    assigned_to: UUID | None
    assigned_company_id: UUID | None
    due_date: date | None
    closed_date: date | None
    created_by: UUID | None
    contributing_behavior: str | None
    contributing_condition: str | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Safety Incidents
# ═══════════════════════════════════════════════════════════════════════════

class SafetyIncidentCreate(BaseModel):
    project_id: UUID
    incident_number: str
    title: str
    incident_type: IncidentType
    severity: IncidentSeverity
    status: IncidentStatus = "open"
    incident_date: date
    incident_time: time | None = None
    location: str | None = None
    description: str
    root_cause: str | None = None
    corrective_action: str | None = None
    affected_person_id: UUID | None = None
    affected_company_id: UUID | None = None
    reported_by: UUID | None = None
    is_osha_recordable: bool = False
    lost_time_days: int | None = None


class SafetyIncidentUpdate(BaseModel):
    title: str | None = None
    status: IncidentStatus | None = None
    severity: IncidentSeverity | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    is_osha_recordable: bool | None = None
    lost_time_days: int | None = None


class SafetyIncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    incident_number: str
    title: str
    incident_type: str
    severity: str
    status: str
    incident_date: date
    incident_time: time | None
    location: str | None
    description: str
    root_cause: str | None
    corrective_action: str | None
    affected_person_id: UUID | None
    affected_company_id: UUID | None
    reported_by: UUID | None
    is_osha_recordable: bool
    lost_time_days: int | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Photo Albums
# ═══════════════════════════════════════════════════════════════════════════

class PhotoAlbumCreate(BaseModel):
    project_id: UUID
    name: str
    description: str | None = None
    is_default: bool = False
    sort_order: int = 0
    created_by: UUID | None = None


class PhotoAlbumUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None
    sort_order: int | None = None


class PhotoAlbumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    is_default: bool
    sort_order: int
    created_by: UUID | None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Photos
# ═══════════════════════════════════════════════════════════════════════════

class PhotoCreate(BaseModel):
    project_id: UUID
    photo_album_id: UUID | None = None
    filename: str
    file_size: int
    content_type: str
    storage_url: str
    storage_key: str
    thumbnail_url: str | None = None
    taken_at: datetime | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    tags: Any | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    uploaded_by: UUID | None = None


class PhotoUpdate(BaseModel):
    # Metadata edit surface — mirrors the Photos.jsx FormDrawer exactly so
    # every field the user can touch in the UI is persisted on PATCH. Prior
    # to phase 51 this schema only accepted album/description/tags/location;
    # filename/taken_at/latitude/longitude were silently dropped by Pydantic.
    filename: str | None = None
    photo_album_id: UUID | None = None
    taken_at: datetime | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    tags: Any | None = None


class PhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    photo_album_id: UUID | None
    filename: str
    file_size: int
    content_type: str
    storage_url: str
    storage_key: str
    thumbnail_url: str | None
    taken_at: datetime | None
    location: str | None
    latitude: float | None
    longitude: float | None
    description: str | None
    tags: Any | None
    source_type: str | None
    source_id: UUID | None
    uploaded_by: UUID | None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════════════════════════════

class TaskCreate(BaseModel):
    project_id: UUID
    task_number: int
    title: str
    description: str | None = None
    status: TaskStatus = "open"
    priority: Priority = "medium"
    category: TaskCategory | None = None
    assigned_to: UUID | None = None
    assigned_company_id: UUID | None = None
    due_date: date
    created_by: UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    category: TaskCategory | None = None
    assigned_to: UUID | None = None
    assigned_company_id: UUID | None = None
    due_date: date | None = None
    completed_date: date | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    task_number: int
    title: str
    description: str | None
    status: str
    priority: str
    category: str | None
    assigned_to: UUID | None
    assigned_company_id: UUID | None
    due_date: date
    completed_date: date | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Meetings
# ═══════════════════════════════════════════════════════════════════════════

class MeetingCreate(BaseModel):
    project_id: UUID
    meeting_type: str
    title: str
    meeting_date: date
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    agenda: str | None = None
    minutes: str | None = None
    attendees: Any | None = None
    packet_url: str | None = None
    created_by: UUID | None = None


class MeetingUpdate(BaseModel):
    title: str | None = None
    meeting_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    agenda: str | None = None
    minutes: str | None = None
    attendees: Any | None = None
    packet_url: str | None = None


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    meeting_type: str
    title: str
    meeting_date: date
    start_time: time | None
    end_time: time | None
    location: str | None
    agenda: str | None
    minutes: str | None
    attendees: Any | None
    packet_url: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Meeting Action Items
# ═══════════════════════════════════════════════════════════════════════════

class MeetingActionItemCreate(BaseModel):
    meeting_id: UUID
    item_number: int
    description: str
    assigned_to: UUID | None = None
    due_date: date | None = None
    status: ActionItemStatus = "open"
    task_id: UUID | None = None


class MeetingActionItemUpdate(BaseModel):
    description: str | None = None
    assigned_to: UUID | None = None
    due_date: date | None = None
    status: ActionItemStatus | None = None
    task_id: UUID | None = None


class MeetingActionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    meeting_id: UUID
    item_number: int
    description: str
    assigned_to: UUID | None
    due_date: date | None
    status: str
    task_id: UUID | None
    created_at: datetime


class PunchAgingRefreshResponse(BaseModel):
    project_id: UUID
    total_punch_items: int
    updated_count: int


# ── Sprint C: daily log + manpower + inspection summaries ──────────────────

class DailyLogSummaryResponse(BaseModel):
    daily_log_id: UUID
    project_id: UUID
    log_date: date
    status: str
    weather_summary: str | None
    is_weather_delay: bool
    manpower_entry_count: int
    total_worker_count: int
    total_hours: float
    company_count: int


class ManpowerByCompanyItem(BaseModel):
    company_id: UUID
    worker_count: int
    hours: float
    entry_count: int


class ProjectManpowerSummaryResponse(BaseModel):
    project_id: UUID
    date_from: date | None
    date_to: date | None
    total_logs: int
    logs_with_manpower: int
    total_entries: int
    total_worker_count: int
    total_hours: float
    average_workers_per_log: float
    by_company: list[ManpowerByCompanyItem]


class InspectionSummaryResponse(BaseModel):
    inspection_id: UUID
    project_id: UUID
    inspection_number: str
    title: str
    inspection_type: str
    status: str
    scheduled_date: date
    completed_date: date | None
    total_items: int
    items_by_result: dict[str, int]
    failed_count: int
    linked_punch_count: int
    linked_punch_item_ids: list[UUID]
    has_unresolved_failures: bool


class ManpowerSnapshot(BaseModel):
    total_logs: int
    total_worker_count: int
    total_hours: float
    average_workers_per_log: float


class InspectionsSnapshot(BaseModel):
    total: int
    open_count: int
    failed_item_count: int


class PunchSnapshot(BaseModel):
    total: int
    open_count: int


class ProjectExecutionHealthResponse(BaseModel):
    project_id: UUID
    schedule_health_status: str
    schedule_active_constraints: int
    schedule_constraints_by_severity: dict[str, int]
    manpower: ManpowerSnapshot
    inspections: InspectionsSnapshot
    punch: PunchSnapshot
    tasks_by_status: dict[str, int]

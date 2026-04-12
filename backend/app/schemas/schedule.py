"""Pydantic request/response schemas for Domain 2 — Schedule."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ScheduleType = Literal["master", "baseline", "lookahead", "what_if"]
ScheduleStatus = Literal["active", "archived", "draft"]
ActivityType = Literal["task", "milestone", "section", "hammock"]
LinkType = Literal["fs", "ff", "ss", "sf"]
ConstraintType = Literal[
    "rfi_pending", "submittal_pending", "no_commitment",
    "insurance_expired", "permit_pending", "material_lead", "inspection_required",
]
SourceType = Literal["rfi", "submittal", "commitment", "insurance", "permit", "inspection"]
ConstraintStatus = Literal["active", "resolved", "overridden"]
Severity = Literal["green", "yellow", "red"]


# ═══════════════════════════════════════════════════════════════════════════
# Schedules
# ═══════════════════════════════════════════════════════════════════════════

class ScheduleCreate(BaseModel):
    project_id: UUID
    name: str
    schedule_type: ScheduleType
    status: ScheduleStatus = "active"
    start_date: date
    end_date: date | None = None
    created_by: UUID | None = None


class ScheduleUpdate(BaseModel):
    name: str | None = None
    schedule_type: ScheduleType | None = None
    status: ScheduleStatus | None = None
    start_date: date | None = None
    end_date: date | None = None


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    schedule_type: str
    status: str
    start_date: date
    end_date: date | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Schedule Activities
# ═══════════════════════════════════════════════════════════════════════════

class ScheduleActivityCreate(BaseModel):
    schedule_id: UUID
    parent_id: UUID | None = None
    activity_number: str | None = None
    name: str
    activity_type: ActivityType
    start_date: date
    end_date: date
    duration_days: int | None = None
    percent_complete: float = 0
    is_critical: bool = False
    is_manually_scheduled: bool = False
    baseline_start: date | None = None
    baseline_end: date | None = None
    variance_days: int | None = None
    float_days: int | None = None
    assigned_company_id: UUID | None = None
    assigned_person_id: UUID | None = None
    cost_code_id: UUID | None = None
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    wbs_code: str | None = None
    location: str | None = None
    notes: str | None = None
    sort_order: int = 0


class ScheduleActivityUpdate(BaseModel):
    parent_id: UUID | None = None
    activity_number: str | None = None
    name: str | None = None
    activity_type: ActivityType | None = None
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    percent_complete: float | None = None
    is_critical: bool | None = None
    is_manually_scheduled: bool | None = None
    baseline_start: date | None = None
    baseline_end: date | None = None
    variance_days: int | None = None
    float_days: int | None = None
    assigned_company_id: UUID | None = None
    assigned_person_id: UUID | None = None
    cost_code_id: UUID | None = None
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    wbs_code: str | None = None
    location: str | None = None
    notes: str | None = None
    sort_order: int | None = None


class ScheduleActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_id: UUID
    parent_id: UUID | None
    activity_number: str | None
    name: str
    activity_type: str
    start_date: date
    end_date: date
    duration_days: int | None
    percent_complete: float
    is_critical: bool
    is_manually_scheduled: bool
    baseline_start: date | None
    baseline_end: date | None
    variance_days: int | None
    float_days: int | None
    assigned_company_id: UUID | None
    assigned_person_id: UUID | None
    cost_code_id: UUID | None
    actual_start_date: date | None
    actual_finish_date: date | None
    wbs_code: str | None
    location: str | None
    notes: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Activity Links
# ═══════════════════════════════════════════════════════════════════════════

class ActivityLinkCreate(BaseModel):
    schedule_id: UUID
    from_activity_id: UUID
    to_activity_id: UUID
    link_type: LinkType = "fs"
    lag_days: int = 0


class ActivityLinkUpdate(BaseModel):
    link_type: LinkType | None = None
    lag_days: int | None = None


class ActivityLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_id: UUID
    from_activity_id: UUID
    to_activity_id: UUID
    link_type: str
    lag_days: int
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Schedule Constraints
# ═══════════════════════════════════════════════════════════════════════════

class ScheduleConstraintCreate(BaseModel):
    activity_id: UUID
    constraint_type: ConstraintType
    source_type: SourceType
    source_id: UUID | None = None
    status: ConstraintStatus = "active"
    severity: Severity
    notes: str | None = None


class ScheduleConstraintUpdate(BaseModel):
    status: ConstraintStatus | None = None
    severity: Severity | None = None
    notes: str | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None


class ScheduleConstraintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_id: UUID
    constraint_type: str
    source_type: str
    source_id: UUID | None
    status: str
    severity: str
    notes: str | None
    resolved_at: datetime | None
    resolved_by: UUID | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Schedule Snapshots
# ═══════════════════════════════════════════════════════════════════════════

class ScheduleSnapshotCreate(BaseModel):
    activity_id: UUID
    snapshot_date: date
    start_date: date
    end_date: date
    percent_complete: float = 0
    is_critical: bool = False
    variance_days: int | None = None


class ScheduleSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_id: UUID
    snapshot_date: date
    start_date: date
    end_date: date
    percent_complete: float
    is_critical: bool
    variance_days: int | None
    created_at: datetime


# ── Sprint C: drift / health summaries ─────────────────────────────────────

class WorstVarianceActivity(BaseModel):
    activity_id: UUID
    name: str
    variance_days: int


class ScheduleDriftSummaryResponse(BaseModel):
    schedule_id: UUID
    project_id: UUID
    schedule_name: str
    schedule_type: str
    status: str
    total_activities: int
    critical_count: int
    completed_count: int
    positive_variance_count: int
    negative_variance_count: int
    average_variance_days: float
    worst_variance_activity: WorstVarianceActivity | None
    snapshot_coverage_count: int
    active_constraint_count: int
    constraints_by_severity: dict[str, int]


class ProjectScheduleHealthSummaryResponse(BaseModel):
    project_id: UUID
    schedule_count: int
    total_activities: int
    critical_count: int
    completed_count: int
    active_constraint_count: int
    constraints_by_severity: dict[str, int]
    project_average_variance_days: float
    health_status: str
    schedules: list[ScheduleDriftSummaryResponse]

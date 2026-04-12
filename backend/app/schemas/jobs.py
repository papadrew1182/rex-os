from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class JobInfo(BaseModel):
    """Static metadata about a registered job."""
    job_key: str
    name: str
    description: str
    enabled: bool
    schedule: str | None  # human-readable cron expression or None


class JobRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_key: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    triggered_by: str
    triggered_by_user_id: UUID | None
    summary: str | None
    error_excerpt: str | None


class JobStatusResponse(BaseModel):
    """Combined job info + last run state for the admin UI."""
    job_key: str
    name: str
    description: str
    enabled: bool
    schedule: str | None
    last_run: JobRunResponse | None
    last_success: JobRunResponse | None
    last_failure: JobRunResponse | None
    is_running: bool


class RunNowResponse(BaseModel):
    job_key: str
    triggered: bool
    skipped_reason: str | None = None
    run_id: UUID | None = None

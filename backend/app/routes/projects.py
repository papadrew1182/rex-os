from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.foundation import Project
from app.schemas.foundation import ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.closeout import ProjectCloseoutReadinessResponse
from app.schemas.document_management import RfiAgingSummaryResponse, SubmittalAgingSummaryResponse
from app.schemas.financials import ProjectBillingPeriodSummaryResponse
from app.schemas.schedule import ProjectScheduleHealthSummaryResponse
from app.schemas.field_ops import ProjectExecutionHealthResponse, ProjectManpowerSummaryResponse
from app.services import foundation as svc
from app.services import closeout as closeout_svc
from app.services import document_management as doc_svc
from app.services import financials as fin_svc
from app.services import schedule as sched_svc
from app.services import field_ops as fo_svc

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    status: str | None = Query(None),
    project_type: str | None = Query(None),
    city: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_projects(
        db, status=status, project_type=project_type, city=city,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await svc.get_by_id(db, Project, project_id)

@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, Project, data)

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, Project, project_id, data)

@router.get("/{project_id}/closeout-readiness", response_model=ProjectCloseoutReadinessResponse)
async def get_closeout_readiness(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await closeout_svc.get_project_closeout_readiness(db, project_id)

@router.get("/{project_id}/rfi-aging", response_model=RfiAgingSummaryResponse)
async def get_project_rfi_aging(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await doc_svc.get_project_rfi_aging_summary(db, project_id)

@router.get("/{project_id}/submittal-aging", response_model=SubmittalAgingSummaryResponse)
async def get_project_submittal_aging(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await doc_svc.get_project_submittal_aging_summary(db, project_id)

@router.get("/{project_id}/billing-periods/summary", response_model=ProjectBillingPeriodSummaryResponse)
async def get_project_billing_period_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await fin_svc.get_project_billing_period_summary(db, project_id)

@router.get("/{project_id}/schedule-health", response_model=ProjectScheduleHealthSummaryResponse)
async def get_project_schedule_health(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await sched_svc.get_project_schedule_health_summary(db, project_id)

@router.get("/{project_id}/manpower-summary", response_model=ProjectManpowerSummaryResponse)
async def get_project_manpower_summary(
    project_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await fo_svc.get_project_manpower_summary(db, project_id, date_from=date_from, date_to=date_to)

@router.get("/{project_id}/execution-health", response_model=ProjectExecutionHealthResponse)
async def get_project_execution_health(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await fo_svc.get_project_execution_health(db, project_id)

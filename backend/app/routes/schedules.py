from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    reject_project_id_change,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.schedule import Schedule
from app.schemas.schedule import (
    ScheduleCreate, ScheduleDriftSummaryResponse, ScheduleResponse, ScheduleUpdate,
)
from app.services import schedule as svc

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("/", response_model=list[ScheduleResponse])
async def list_schedules(
    project_id: UUID | None = Query(None),
    status: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_schedules(
        db, project_id=project_id, status=status,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Schedule, schedule_id)
    await enforce_project_read(db, user, row.project_id)
    return row


@router.post("/", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Schedule, data)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    data: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Schedule, schedule_id)
    reject_project_id_change(data, row.project_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Schedule, schedule_id, data)


@router.get("/{schedule_id}/drift-summary", response_model=ScheduleDriftSummaryResponse)
async def get_drift_summary(schedule_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_schedule_drift_summary(db, schedule_id)

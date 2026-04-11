from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.schedule import Schedule, ScheduleActivity
from app.schemas.schedule import (
    ScheduleActivityCreate,
    ScheduleActivityResponse,
    ScheduleActivityUpdate,
)
from app.services import schedule as svc

router = APIRouter(prefix="/api/schedule-activities", tags=["schedule-activities"])


@router.get("/", response_model=list[ScheduleActivityResponse])
async def list_schedule_activities(
    schedule_id: UUID | None = Query(None),
    parent_id: UUID | None = Query(None),
    activity_type: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_activities(
        db, schedule_id=schedule_id, parent_id=parent_id,
        activity_type=activity_type, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )


@router.get("/{activity_id}", response_model=ScheduleActivityResponse)
async def get_schedule_activity(
    activity_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ScheduleActivity, activity_id)
    # ScheduleActivity has no project_id; resolve via parent Schedule.
    parent = await svc.get_by_id(db, Schedule, row.schedule_id)
    await enforce_project_read(db, user, parent.project_id)
    return row


@router.post("/", response_model=ScheduleActivityResponse, status_code=201)
async def create_schedule_activity(
    data: ScheduleActivityCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Schedule, data.schedule_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, ScheduleActivity, data)


@router.patch("/{activity_id}", response_model=ScheduleActivityResponse)
async def update_schedule_activity(
    activity_id: UUID,
    data: ScheduleActivityUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ScheduleActivity, activity_id)
    parent = await svc.get_by_id(db, Schedule, row.schedule_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, ScheduleActivity, activity_id, data)

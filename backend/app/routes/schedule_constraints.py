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
from app.models.schedule import Schedule, ScheduleActivity, ScheduleConstraint
from app.schemas.schedule import (
    ScheduleConstraintCreate,
    ScheduleConstraintResponse,
    ScheduleConstraintUpdate,
)
from app.services import schedule as svc

router = APIRouter(prefix="/api/schedule-constraints", tags=["schedule-constraints"])


@router.get("/", response_model=list[ScheduleConstraintResponse])
async def list_schedule_constraints(
    activity_id: UUID | None = Query(None),
    status: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_constraints(
        db, activity_id=activity_id, status=status,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )


@router.get("/{constraint_id}", response_model=ScheduleConstraintResponse)
async def get_schedule_constraint(
    constraint_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ScheduleConstraint, constraint_id)
    activity = await svc.get_by_id(db, ScheduleActivity, row.activity_id)
    schedule = await svc.get_by_id(db, Schedule, activity.schedule_id)
    await enforce_project_read(db, user, schedule.project_id)
    return row


@router.post("/", response_model=ScheduleConstraintResponse, status_code=201)
async def create_schedule_constraint(
    data: ScheduleConstraintCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    p0 = await svc.get_by_id(db, ScheduleActivity, data.activity_id)
    top = await svc.get_by_id(db, Schedule, p0.schedule_id)
    await assert_project_write(db, user, top.project_id)
    return await svc.create(db, ScheduleConstraint, data)


@router.patch("/{constraint_id}", response_model=ScheduleConstraintResponse)
async def update_schedule_constraint(
    constraint_id: UUID,
    data: ScheduleConstraintUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ScheduleConstraint, constraint_id)
    p0 = await svc.get_by_id(db, ScheduleActivity, row.activity_id)
    top = await svc.get_by_id(db, Schedule, p0.schedule_id)
    await assert_project_write(db, user, top.project_id)
    return await svc.update(db, ScheduleConstraint, constraint_id, data)

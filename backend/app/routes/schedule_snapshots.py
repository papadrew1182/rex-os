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
from app.models.schedule import Schedule, ScheduleActivity, ScheduleSnapshot
from app.schemas.schedule import ScheduleSnapshotCreate, ScheduleSnapshotResponse
from app.services import schedule as svc

router = APIRouter(prefix="/api/schedule-snapshots", tags=["schedule-snapshots"])


@router.get("/", response_model=list[ScheduleSnapshotResponse])
async def list_schedule_snapshots(
    activity_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_snapshots(
        db, activity_id=activity_id, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )


@router.get("/{snapshot_id}", response_model=ScheduleSnapshotResponse)
async def get_schedule_snapshot(
    snapshot_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ScheduleSnapshot, snapshot_id)
    activity = await svc.get_by_id(db, ScheduleActivity, row.activity_id)
    schedule = await svc.get_by_id(db, Schedule, activity.schedule_id)
    await enforce_project_read(db, user, schedule.project_id)
    return row


@router.post("/", response_model=ScheduleSnapshotResponse, status_code=201)
async def create_schedule_snapshot(
    data: ScheduleSnapshotCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    p0 = await svc.get_by_id(db, ScheduleActivity, data.activity_id)
    top = await svc.get_by_id(db, Schedule, p0.schedule_id)
    await assert_project_write(db, user, top.project_id)
    return await svc.create(db, ScheduleSnapshot, data)

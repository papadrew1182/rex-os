from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_field_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    reject_project_id_change,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.field_ops import DailyLog
from app.schemas.field_ops import (
    DailyLogCreate, DailyLogResponse, DailyLogSummaryResponse, DailyLogUpdate,
)
from app.services import field_ops as svc

router = APIRouter(prefix="/api/daily-logs", tags=["daily-logs"])

@router.get("/", response_model=list[DailyLogResponse])
async def list_daily_logs(
    project_id: UUID | None = Query(None),
    log_date: date | None = Query(None),
    status: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_daily_logs(
        db, project_id=project_id, log_date=log_date, status=status,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{daily_log_id}", response_model=DailyLogResponse)
async def get_daily_log(
    daily_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, DailyLog, daily_log_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=DailyLogResponse, status_code=201)
async def create_daily_log(
    data: DailyLogCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, DailyLog, data)

@router.patch("/{daily_log_id}", response_model=DailyLogResponse)
async def update_daily_log(
    daily_log_id: UUID,
    data: DailyLogUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, DailyLog, daily_log_id)
    reject_project_id_change(data, row.project_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, DailyLog, daily_log_id, data)

@router.get("/{daily_log_id}/summary", response_model=DailyLogSummaryResponse)
async def get_daily_log_summary(daily_log_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_daily_log_summary(db, daily_log_id)

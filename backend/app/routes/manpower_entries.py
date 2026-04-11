from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_field_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.field_ops import DailyLog, ManpowerEntry
from app.schemas.field_ops import ManpowerEntryCreate, ManpowerEntryResponse, ManpowerEntryUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/manpower-entries", tags=["manpower-entries"])

@router.get("/", response_model=list[ManpowerEntryResponse])
async def list_manpower_entries(
    daily_log_id: UUID | None = Query(None),
    company_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_manpower_entries(
        db, daily_log_id=daily_log_id, company_id=company_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=ManpowerEntryResponse)
async def get_manpower_entry(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ManpowerEntry, row_id)
    parent = await svc.get_by_id(db, DailyLog, row.daily_log_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=ManpowerEntryResponse, status_code=201)
async def create_manpower_entry(
    data: ManpowerEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, DailyLog, data.daily_log_id)
    await assert_field_write(db, user, parent.project_id)
    return await svc.create(db, ManpowerEntry, data)

@router.patch("/{row_id}", response_model=ManpowerEntryResponse)
async def update_manpower_entry(
    row_id: UUID,
    data: ManpowerEntryUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ManpowerEntry, row_id)
    parent = await svc.get_by_id(db, DailyLog, row.daily_log_id)
    await assert_field_write(db, user, parent.project_id)
    return await svc.update(db, ManpowerEntry, row_id, data)

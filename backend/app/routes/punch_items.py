from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_field_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_admin_or_vp,
    require_authenticated_user,
)
from app.models.field_ops import PunchItem
from app.models.foundation import UserAccount
from app.schemas.field_ops import (
    PunchAgingRefreshResponse, PunchItemCreate, PunchItemResponse, PunchItemUpdate,
)
from app.services import field_ops as svc

router = APIRouter(prefix="/api/punch-items", tags=["punch-items"])

@router.get("/", response_model=list[PunchItemResponse])
async def list_punch_items(
    project_id: UUID | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    assigned_company_id: UUID | None = Query(None),
    assigned_to: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_punch_items(
        db, project_id=project_id, status=status, priority=priority,
        assigned_company_id=assigned_company_id, assigned_to=assigned_to,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{punch_id}", response_model=PunchItemResponse)
async def get_punch_item(
    punch_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PunchItem, punch_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=PunchItemResponse, status_code=201)
async def create_punch_item(
    data: PunchItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, PunchItem, data)

@router.patch("/{punch_id}", response_model=PunchItemResponse)
async def update_punch_item(
    punch_id: UUID,
    data: PunchItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PunchItem, punch_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, PunchItem, punch_id, data)

@router.post("/{punch_id}/refresh-aging", response_model=PunchItemResponse)
async def refresh_punch_aging(
    punch_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: UserAccount = Depends(require_admin_or_vp),
):
    return await svc.refresh_punch_days_open(db, punch_id)

@router.post("/refresh-aging", response_model=PunchAgingRefreshResponse)
async def refresh_punch_aging_bulk(
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: UserAccount = Depends(require_admin_or_vp),
):
    return await svc.refresh_punch_days_open_for_project(db, project_id)

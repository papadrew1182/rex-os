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
from app.models.field_ops import Inspection, InspectionItem
from app.schemas.field_ops import InspectionItemCreate, InspectionItemResponse, InspectionItemUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/inspection-items", tags=["inspection-items"])

@router.get("/", response_model=list[InspectionItemResponse])
async def list_inspection_items(
    inspection_id: UUID | None = Query(None),
    result: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_inspection_items(
        db, inspection_id=inspection_id, result=result,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=InspectionItemResponse)
async def get_inspection_item(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, InspectionItem, row_id)
    parent = await svc.get_by_id(db, Inspection, row.inspection_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=InspectionItemResponse, status_code=201)
async def create_inspection_item(
    data: InspectionItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Inspection, data.inspection_id)
    await assert_field_write(db, user, parent.project_id)
    return await svc.create(db, InspectionItem, data)

@router.patch("/{row_id}", response_model=InspectionItemResponse)
async def update_inspection_item(
    row_id: UUID,
    data: InspectionItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, InspectionItem, row_id)
    parent = await svc.get_by_id(db, Inspection, row.inspection_id)
    await assert_field_write(db, user, parent.project_id)
    return await svc.update(db, InspectionItem, row_id, data)

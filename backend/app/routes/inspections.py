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
from app.models.field_ops import Inspection
from app.schemas.field_ops import (
    InspectionCreate, InspectionResponse, InspectionSummaryResponse, InspectionUpdate,
)
from app.services import field_ops as svc

router = APIRouter(prefix="/api/inspections", tags=["inspections"])

@router.get("/", response_model=list[InspectionResponse])
async def list_inspections(
    project_id: UUID | None = Query(None),
    inspection_type: str | None = Query(None),
    status: str | None = Query(None),
    activity_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_inspections(
        db, project_id=project_id, inspection_type=inspection_type,
        status=status, activity_id=activity_id, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{inspection_id}", response_model=InspectionResponse)
async def get_inspection(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Inspection, inspection_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=InspectionResponse, status_code=201)
async def create_inspection(
    data: InspectionCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, Inspection, data)

@router.patch("/{inspection_id}", response_model=InspectionResponse)
async def update_inspection(
    inspection_id: UUID,
    data: InspectionUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Inspection, inspection_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, Inspection, inspection_id, data)

@router.get("/{inspection_id}/summary", response_model=InspectionSummaryResponse)
async def get_inspection_summary(inspection_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_inspection_summary(db, inspection_id)

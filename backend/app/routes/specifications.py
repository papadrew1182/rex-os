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
from app.models.document_management import Specification
from app.schemas.document_management import SpecificationCreate, SpecificationResponse, SpecificationUpdate
from app.services import document_management as svc

router = APIRouter(prefix="/api/specifications", tags=["specifications"])

@router.get("/", response_model=list[SpecificationResponse])
async def list_specifications(
    project_id: UUID|None = Query(None),
    section_number: str|None = Query(None),
    division: str|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_specifications(
        db, project_id=project_id, section_number=section_number,
        division=division, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=SpecificationResponse)
async def get_specification(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Specification, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=SpecificationResponse, status_code=201)
async def create_specification(
    data: SpecificationCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Specification, data)

@router.patch("/{row_id}", response_model=SpecificationResponse)
async def update_specification(
    row_id: UUID,
    data: SpecificationUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Specification, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Specification, row_id, data)

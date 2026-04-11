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
from app.models.document_management import Drawing
from app.schemas.document_management import DrawingCreate, DrawingResponse, DrawingUpdate
from app.services import document_management as svc

router = APIRouter(prefix="/api/drawings", tags=["drawings"])

@router.get("/", response_model=list[DrawingResponse])
async def list_drawings(
    project_id: UUID|None = Query(None),
    drawing_area_id: UUID|None = Query(None),
    discipline: str|None = Query(None),
    is_current: bool|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_drawings(
        db, project_id=project_id, drawing_area_id=drawing_area_id,
        discipline=discipline, is_current=is_current,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=DrawingResponse)
async def get_drawing(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Drawing, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=DrawingResponse, status_code=201)
async def create_drawing(
    data: DrawingCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Drawing, data)

@router.patch("/{row_id}", response_model=DrawingResponse)
async def update_drawing(
    row_id: UUID,
    data: DrawingUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Drawing, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Drawing, row_id, data)

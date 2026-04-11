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
from app.models.document_management import Drawing, DrawingRevision
from app.schemas.document_management import DrawingRevisionCreate, DrawingRevisionResponse
from app.services import document_management as svc

router = APIRouter(prefix="/api/drawing-revisions", tags=["drawing-revisions"])

@router.get("/", response_model=list[DrawingRevisionResponse])
async def list_drawing_revisions(
    drawing_id: UUID|None = Query(None),
    revision_number: int|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_drawing_revisions(
        db, drawing_id=drawing_id, revision_number=revision_number,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=DrawingRevisionResponse)
async def get_drawing_revision(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, DrawingRevision, row_id)
    parent = await svc.get_by_id(db, Drawing, row.drawing_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=DrawingRevisionResponse, status_code=201)
async def create_drawing_revision(
    data: DrawingRevisionCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Drawing, data.drawing_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, DrawingRevision, data)

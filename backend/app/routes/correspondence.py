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
from app.models.document_management import Correspondence
from app.schemas.document_management import CorrespondenceCreate, CorrespondenceResponse, CorrespondenceUpdate
from app.services import document_management as svc

router = APIRouter(prefix="/api/correspondence", tags=["correspondence"])

@router.get("/", response_model=list[CorrespondenceResponse])
async def list_correspondence(
    project_id: UUID|None = Query(None),
    correspondence_type: str|None = Query(None),
    status: str|None = Query(None),
    from_person_id: UUID|None = Query(None),
    to_person_id: UUID|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_correspondence(
        db, project_id=project_id, correspondence_type=correspondence_type,
        status=status, from_person_id=from_person_id, to_person_id=to_person_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=CorrespondenceResponse)
async def get_correspondence(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Correspondence, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=CorrespondenceResponse, status_code=201)
async def create_correspondence(
    data: CorrespondenceCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Correspondence, data)

@router.patch("/{row_id}", response_model=CorrespondenceResponse)
async def update_correspondence(
    row_id: UUID,
    data: CorrespondenceUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Correspondence, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Correspondence, row_id, data)

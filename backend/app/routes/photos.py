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
from app.models.field_ops import Photo
from app.schemas.field_ops import PhotoCreate, PhotoResponse, PhotoUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/photos", tags=["photos"])

@router.get("/", response_model=list[PhotoResponse])
async def list_photos(
    project_id: UUID | None = Query(None),
    photo_album_id: UUID | None = Query(None),
    source_type: str | None = Query(None),
    source_id: UUID | None = Query(None),
    uploaded_by: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_photos(
        db, project_id=project_id, photo_album_id=photo_album_id,
        source_type=source_type, source_id=source_id, uploaded_by=uploaded_by,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=PhotoResponse)
async def get_photo(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Photo, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=PhotoResponse, status_code=201)
async def create_photo(
    data: PhotoCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, Photo, data)

@router.patch("/{row_id}", response_model=PhotoResponse)
async def update_photo(
    row_id: UUID,
    data: PhotoUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Photo, row_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, Photo, row_id, data)

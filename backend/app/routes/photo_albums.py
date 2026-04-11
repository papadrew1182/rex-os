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
from app.models.field_ops import PhotoAlbum
from app.schemas.field_ops import PhotoAlbumCreate, PhotoAlbumResponse, PhotoAlbumUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/photo-albums", tags=["photo-albums"])

@router.get("/", response_model=list[PhotoAlbumResponse])
async def list_photo_albums(
    project_id: UUID | None = Query(None),
    is_default: bool | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_photo_albums(
        db, project_id=project_id, is_default=is_default,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=PhotoAlbumResponse)
async def get_photo_album(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PhotoAlbum, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=PhotoAlbumResponse, status_code=201)
async def create_photo_album(
    data: PhotoAlbumCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, PhotoAlbum, data)

@router.patch("/{row_id}", response_model=PhotoAlbumResponse)
async def update_photo_album(
    row_id: UUID,
    data: PhotoAlbumUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PhotoAlbum, row_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, PhotoAlbum, row_id, data)

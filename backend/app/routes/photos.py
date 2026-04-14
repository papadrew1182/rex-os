import logging
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_field_write,
    assert_project_access,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.field_ops import Photo
from app.schemas.field_ops import PhotoCreate, PhotoResponse, PhotoUpdate
from app.services import field_ops as svc
from app.services.storage import get_storage

log = logging.getLogger("rex.photos")
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


@router.post("/upload", response_model=PhotoResponse, status_code=201)
async def upload_photo(
    project_id: UUID = Form(...),
    file: UploadFile = File(...),
    photo_album_id: UUID | None = Form(None),
    source_type: str | None = Form(None),
    source_id: UUID | None = Form(None),
    taken_at: datetime | None = Form(None),
    description: str | None = Form(None),
    location: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    tags: str | None = Form(None),
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Multipart photo upload.

    Mirrors ``/api/attachments/upload`` but stores a Photo row so the image
    appears in the Photo gallery. ``field_only`` access is sufficient, same
    threshold used for attachments upload. Rejects empty filenames or empty
    bodies with 422 so we don't create junk rows.
    """
    try:
        await assert_project_access(db, user, project_id, min_access_level="field_only")
    except HTTPException as exc:
        log.info(
            "photo_upload_denied user_id=%s project_id=%s status=%s",
            user.id, project_id, exc.status_code,
        )
        raise

    if not file.filename:
        raise HTTPException(status_code=422, detail="filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="file is empty")

    # Restrict to common image types — guards against accidentally using this
    # endpoint as a generic uploader and creating unreadable photo rows.
    ctype = (file.content_type or "").lower()
    if not ctype.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image/* content types are allowed")

    storage = get_storage()
    key = storage.make_key(f"{project_id}/photos", file.filename)
    storage.save(content, key)

    parsed_tags = None
    if tags:
        try:
            import json
            parsed_tags = json.loads(tags) if tags.strip().startswith(("{", "[")) else [t.strip() for t in tags.split(",") if t.strip()]
        except Exception:
            parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    photo = Photo(
        project_id=project_id,
        photo_album_id=photo_album_id,
        filename=file.filename,
        file_size=len(content),
        content_type=ctype or "application/octet-stream",
        storage_url=storage.url_for(key),
        storage_key=key,
        taken_at=taken_at,
        description=description,
        location=location,
        latitude=latitude,
        longitude=longitude,
        tags=parsed_tags,
        source_type=source_type,
        source_id=source_id,
        uploaded_by=user.person_id,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    log.info(
        "photo_upload_ok user_id=%s project_id=%s photo_id=%s size=%d",
        user.id, project_id, photo.id, len(content),
    )
    return photo

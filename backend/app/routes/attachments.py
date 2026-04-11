import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    assert_project_access,
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    reject_project_id_change,
    require_authenticated_user,
)
from app.models.document_management import Attachment
from app.models.foundation import UserAccount
from app.schemas.document_management import AttachmentCreate, AttachmentResponse, AttachmentUpdate
from app.services import document_management as svc
from app.services.storage import get_storage

log = logging.getLogger("rex.attachments")
router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.get("/", response_model=list[AttachmentResponse])
async def list_attachments(
    project_id: UUID | None = Query(None),
    source_type: str | None = Query(None),
    source_id: UUID | None = Query(None),
    uploaded_by: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_attachments(
        db, project_id=project_id, source_type=source_type,
        source_id=source_id, uploaded_by=uploaded_by,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )


@router.post("/upload", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    project_id: UUID = Form(...),
    source_type: str = Form(...),
    source_id: UUID = Form(...),
    file: UploadFile = File(...),
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Project-scoped authorization: must have at least field_only access to upload.
    try:
        await assert_project_access(db, user, project_id, min_access_level="field_only")
    except HTTPException as exc:
        log.info(
            "attachment_upload_denied user_id=%s project_id=%s status=%s",
            user.id, project_id, exc.status_code,
        )
        raise

    if not file.filename:
        raise HTTPException(status_code=422, detail="filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="file is empty")

    storage = get_storage()
    key = storage.make_key(str(project_id), file.filename)
    storage.save(content, key)

    attachment = Attachment(
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        filename=file.filename,
        file_size=len(content),
        content_type=file.content_type or "application/octet-stream",
        storage_url=storage.url_for(key),
        storage_key=key,
        uploaded_by=user.person_id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    log.info(
        "attachment_upload_ok user_id=%s project_id=%s attachment_id=%s size=%d",
        user.id, project_id, attachment.id, len(content),
    )
    return attachment


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: UUID,
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attachment = await svc.get_by_id(db, Attachment, attachment_id)
    # Enforce project-scoped read access on the resolved attachment.
    try:
        await assert_project_access(db, user, attachment.project_id, min_access_level="read_only")
    except HTTPException as exc:
        log.info(
            "attachment_download_denied user_id=%s attachment_id=%s project_id=%s status=%s",
            user.id, attachment_id, attachment.project_id, exc.status_code,
        )
        raise
    storage = get_storage()
    try:
        content = storage.read(attachment.storage_key)
    except FileNotFoundError:
        log.warning(
            "attachment_download_missing_file attachment_id=%s storage_key=%s",
            attachment_id, attachment.storage_key,
        )
        raise HTTPException(status_code=404, detail="File content missing from storage")
    return Response(
        content=content,
        media_type=attachment.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Attachment, attachment_id)
    await enforce_project_read(db, user, row.project_id)
    return row


@router.post("/", response_model=AttachmentResponse, status_code=201)
async def create_attachment(
    data: AttachmentCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Attachment, data)


@router.patch("/{attachment_id}", response_model=AttachmentResponse)
async def update_attachment(
    attachment_id: UUID,
    data: AttachmentUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Attachment, attachment_id)
    reject_project_id_change(data, row.project_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Attachment, attachment_id, data)

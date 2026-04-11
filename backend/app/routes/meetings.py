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
from app.models.field_ops import Meeting
from app.schemas.field_ops import MeetingCreate, MeetingResponse, MeetingUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

@router.get("/", response_model=list[MeetingResponse])
async def list_meetings(
    project_id: UUID | None = Query(None),
    meeting_type: str | None = Query(None),
    meeting_date: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_meetings(
        db, project_id=project_id, meeting_type=meeting_type,
        meeting_date=meeting_date, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=MeetingResponse)
async def get_meeting(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Meeting, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    data: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, Meeting, data)

@router.patch("/{row_id}", response_model=MeetingResponse)
async def update_meeting(
    row_id: UUID,
    data: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Meeting, row_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, Meeting, row_id, data)

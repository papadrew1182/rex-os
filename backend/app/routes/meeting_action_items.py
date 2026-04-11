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
from app.models.field_ops import Meeting, MeetingActionItem
from app.schemas.field_ops import MeetingActionItemCreate, MeetingActionItemResponse, MeetingActionItemUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/meeting-action-items", tags=["meeting-action-items"])

@router.get("/", response_model=list[MeetingActionItemResponse])
async def list_meeting_action_items(
    meeting_id: UUID | None = Query(None),
    status: str | None = Query(None),
    assigned_to: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_meeting_action_items(
        db, meeting_id=meeting_id, status=status, assigned_to=assigned_to,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=MeetingActionItemResponse)
async def get_meeting_action_item(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, MeetingActionItem, row_id)
    parent = await svc.get_by_id(db, Meeting, row.meeting_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=MeetingActionItemResponse, status_code=201)
async def create_meeting_action_item(
    data: MeetingActionItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Meeting, data.meeting_id)
    await assert_field_write(db, user, parent.project_id)
    return await svc.create(db, MeetingActionItem, data)

@router.patch("/{row_id}", response_model=MeetingActionItemResponse)
async def update_meeting_action_item(
    row_id: UUID,
    data: MeetingActionItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, MeetingActionItem, row_id)
    parent = await svc.get_by_id(db, Meeting, row.meeting_id)
    await assert_field_write(db, user, parent.project_id)
    return await svc.update(db, MeetingActionItem, row_id, data)

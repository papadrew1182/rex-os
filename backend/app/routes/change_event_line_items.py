from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
)
from app.models.foundation import UserAccount
from app.models.financials import ChangeEvent, ChangeEventLineItem
from app.schemas.financials import (
    ChangeEventLineItemCreate,
    ChangeEventLineItemResponse,
    ChangeEventLineItemUpdate,
    ChangeEventDetailResponse,
)
from app.services import financials as svc

router = APIRouter(prefix="/api/change-event-line-items", tags=["change-event-line-items"])


@router.get("/", response_model=list[ChangeEventLineItemResponse])
async def list_change_event_line_items(
    change_event_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_change_event_line_items(
        db, change_event_id=change_event_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )


@router.get("/{row_id}", response_model=ChangeEventLineItemResponse)
async def get_change_event_line_item(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ChangeEventLineItem, row_id)
    parent = await svc.get_by_id(db, ChangeEvent, row.change_event_id)
    await enforce_project_read(db, user, parent.project_id)
    return row


@router.post("/", response_model=ChangeEventLineItemResponse, status_code=201)
async def create_change_event_line_item(
    data: ChangeEventLineItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, ChangeEvent, data.change_event_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, ChangeEventLineItem, data)


@router.patch("/{row_id}", response_model=ChangeEventLineItemResponse)
async def update_change_event_line_item(
    row_id: UUID,
    data: ChangeEventLineItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ChangeEventLineItem, row_id)
    parent = await svc.get_by_id(db, ChangeEvent, row.change_event_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, ChangeEventLineItem, row_id, data)

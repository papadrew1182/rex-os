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
from app.models.schedule import ActivityLink, Schedule
from app.schemas.schedule import ActivityLinkCreate, ActivityLinkResponse, ActivityLinkUpdate
from app.services import schedule as svc

router = APIRouter(prefix="/api/activity-links", tags=["activity-links"])


@router.get("/", response_model=list[ActivityLinkResponse])
async def list_activity_links(
    schedule_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_activity_links(
        db, schedule_id=schedule_id, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )


@router.get("/{link_id}", response_model=ActivityLinkResponse)
async def get_activity_link(
    link_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ActivityLink, link_id)
    parent = await svc.get_by_id(db, Schedule, row.schedule_id)
    await enforce_project_read(db, user, parent.project_id)
    return row


@router.post("/", response_model=ActivityLinkResponse, status_code=201)
async def create_activity_link(
    data: ActivityLinkCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Schedule, data.schedule_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, ActivityLink, data)


@router.patch("/{link_id}", response_model=ActivityLinkResponse)
async def update_activity_link(
    link_id: UUID,
    data: ActivityLinkUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ActivityLink, link_id)
    parent = await svc.get_by_id(db, Schedule, row.schedule_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, ActivityLink, link_id, data)

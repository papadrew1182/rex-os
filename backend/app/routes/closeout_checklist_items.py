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
from app.models.closeout import CloseoutChecklist, CloseoutChecklistItem
from app.schemas.closeout import CloseoutChecklistItemCreate, CloseoutChecklistItemResponse, CloseoutChecklistItemUpdate
from app.services import closeout as svc

router = APIRouter(prefix="/api/closeout-checklist-items", tags=["closeout-checklist-items"])

@router.get("/", response_model=list[CloseoutChecklistItemResponse])
async def list_closeout_checklist_items(
    checklist_id: UUID | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
    assigned_company_id: UUID | None = Query(None),
    assigned_person_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_closeout_checklist_items(
        db, checklist_id=checklist_id, category=category, status=status,
        assigned_company_id=assigned_company_id, assigned_person_id=assigned_person_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=CloseoutChecklistItemResponse)
async def get_closeout_checklist_item(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CloseoutChecklistItem, row_id)
    parent = await svc.get_by_id(db, CloseoutChecklist, row.checklist_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=CloseoutChecklistItemResponse, status_code=201)
async def create_closeout_checklist_item(
    data: CloseoutChecklistItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, CloseoutChecklist, data.checklist_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, CloseoutChecklistItem, data)

@router.patch("/{row_id}", response_model=CloseoutChecklistItemResponse)
async def update_closeout_checklist_item(
    row_id: UUID,
    data: CloseoutChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CloseoutChecklistItem, row_id)
    parent = await svc.get_by_id(db, CloseoutChecklist, row.checklist_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update_checklist_item_with_rollup(db, row_id, data)

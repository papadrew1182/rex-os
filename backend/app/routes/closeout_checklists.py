import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_admin_or_vp,
    require_authenticated_user,
)
from app.models.closeout import CloseoutChecklist
from app.models.foundation import UserAccount
from app.schemas.closeout import (
    CloseoutChecklistCreate, CloseoutChecklistResponse, CloseoutChecklistUpdate,
    CreateChecklistFromTemplateRequest,
)
from app.services import closeout as svc

log = logging.getLogger("rex.closeout")
router = APIRouter(prefix="/api/closeout-checklists", tags=["closeout-checklists"])

@router.get("/", response_model=list[CloseoutChecklistResponse])
async def list_closeout_checklists(
    project_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_closeout_checklists(
        db, project_id=project_id, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=CloseoutChecklistResponse)
async def get_closeout_checklist(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CloseoutChecklist, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=CloseoutChecklistResponse, status_code=201)
async def create_closeout_checklist(
    data: CloseoutChecklistCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, CloseoutChecklist, data)

@router.post("/from-template", response_model=CloseoutChecklistResponse, status_code=201)
async def create_checklist_from_template(
    data: CreateChecklistFromTemplateRequest,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    result = await svc.create_checklist_from_template(
        db, project_id=data.project_id, template_id=data.template_id,
        substantial_completion_date=data.substantial_completion_date,
    )
    log.info(
        "checklist_from_template_ok user_id=%s project_id=%s template_id=%s checklist_id=%s",
        user.id, data.project_id, data.template_id, result.id,
    )
    return result

@router.patch("/{row_id}", response_model=CloseoutChecklistResponse)
async def update_closeout_checklist(
    row_id: UUID,
    data: CloseoutChecklistUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CloseoutChecklist, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, CloseoutChecklist, row_id, data)

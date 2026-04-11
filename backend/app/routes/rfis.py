from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    reject_project_id_change,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.document_management import Rfi
from app.schemas.document_management import (
    RfiAgingResponse, RfiAgingSummaryResponse, RfiCreate, RfiResponse, RfiUpdate,
)
from app.services import document_management as svc

router = APIRouter(prefix="/api/rfis", tags=["rfis"])

@router.get("/", response_model=list[RfiResponse])
async def list_rfis(
    project_id: UUID | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    cost_code_id: UUID | None = Query(None),
    assigned_to: UUID | None = Query(None),
    ball_in_court: UUID | None = Query(None),
    drawing_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_rfis(
        db, project_id=project_id, status=status, priority=priority,
        cost_code_id=cost_code_id, assigned_to=assigned_to,
        ball_in_court=ball_in_court, drawing_id=drawing_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{rfi_id}", response_model=RfiResponse)
async def get_rfi(
    rfi_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Rfi, rfi_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=RfiResponse, status_code=201)
async def create_rfi(
    data: RfiCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Rfi, data)

@router.patch("/{rfi_id}", response_model=RfiResponse)
async def update_rfi(
    rfi_id: UUID,
    data: RfiUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Rfi, rfi_id)
    reject_project_id_change(data, row.project_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Rfi, rfi_id, data)

@router.get("/{rfi_id}/aging", response_model=RfiAgingResponse)
async def get_rfi_aging(rfi_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_rfi_aging(db, rfi_id)

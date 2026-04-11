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
from app.models.financials import CostCode
from app.schemas.financials import CostCodeCreate, CostCodeResponse, CostCodeUpdate
from app.services import financials as svc

router = APIRouter(prefix="/api/cost-codes", tags=["cost-codes"])

@router.get("/", response_model=list[CostCodeResponse])
async def list_cost_codes(
    project_id: UUID|None = Query(None),
    parent_id: UUID|None = Query(None),
    cost_type: str|None = Query(None),
    is_active: bool|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_cost_codes(
        db, project_id=project_id, parent_id=parent_id, cost_type=cost_type,
        is_active=is_active, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=CostCodeResponse)
async def get_cost_code(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CostCode, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=CostCodeResponse, status_code=201)
async def create_cost_code(
    data: CostCodeCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, CostCode, data)

@router.patch("/{row_id}", response_model=CostCodeResponse)
async def update_cost_code(
    row_id: UUID,
    data: CostCodeUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CostCode, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, CostCode, row_id, data)

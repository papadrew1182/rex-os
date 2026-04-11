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
from app.models.financials import DirectCost
from app.schemas.financials import DirectCostCreate, DirectCostResponse, DirectCostUpdate
from app.services import financials as svc

router = APIRouter(prefix="/api/direct-costs", tags=["direct-costs"])

@router.get("/", response_model=list[DirectCostResponse])
async def list_direct_costs(
    project_id: UUID|None = Query(None),
    cost_code_id: UUID|None = Query(None),
    vendor_id: UUID|None = Query(None),
    payment_method: str|None = Query(None),
    direct_cost_date: str|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_direct_costs(
        db, project_id=project_id, cost_code_id=cost_code_id, vendor_id=vendor_id,
        payment_method=payment_method, direct_cost_date=direct_cost_date,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=DirectCostResponse)
async def get_direct_cost(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, DirectCost, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=DirectCostResponse, status_code=201)
async def create_direct_cost(
    data: DirectCostCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, DirectCost, data)

@router.patch("/{row_id}", response_model=DirectCostResponse)
async def update_direct_cost(
    row_id: UUID,
    data: DirectCostUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, DirectCost, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, DirectCost, row_id, data)

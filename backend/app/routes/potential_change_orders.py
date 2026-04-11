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
from app.models.financials import ChangeEvent, PotentialChangeOrder
from app.schemas.financials import PotentialChangeOrderCreate, PotentialChangeOrderResponse, PotentialChangeOrderUpdate
from app.services import financials as svc

router = APIRouter(prefix="/api/potential-change-orders", tags=["potential-change-orders"])

@router.get("/", response_model=list[PotentialChangeOrderResponse])
async def list_potential_change_orders(
    change_event_id: UUID|None = Query(None),
    commitment_id: UUID|None = Query(None),
    status: str|None = Query(None),
    cost_code_id: UUID|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_potential_change_orders(
        db, change_event_id=change_event_id, commitment_id=commitment_id,
        status=status, cost_code_id=cost_code_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=PotentialChangeOrderResponse)
async def get_potential_change_order(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PotentialChangeOrder, row_id)
    parent = await svc.get_by_id(db, ChangeEvent, row.change_event_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=PotentialChangeOrderResponse, status_code=201)
async def create_potential_change_order(
    data: PotentialChangeOrderCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, ChangeEvent, data.change_event_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, PotentialChangeOrder, data)

@router.patch("/{row_id}", response_model=PotentialChangeOrderResponse)
async def update_potential_change_order(
    row_id: UUID,
    data: PotentialChangeOrderUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PotentialChangeOrder, row_id)
    parent = await svc.get_by_id(db, ChangeEvent, row.change_event_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, PotentialChangeOrder, row_id, data)

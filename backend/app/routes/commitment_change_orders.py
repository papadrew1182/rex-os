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
from app.models.financials import Commitment, CommitmentChangeOrder
from app.schemas.financials import CommitmentChangeOrderCreate, CommitmentChangeOrderResponse, CommitmentChangeOrderUpdate
from app.services import financials as svc

router = APIRouter(prefix="/api/commitment-change-orders", tags=["commitment-change-orders"])

@router.get("/", response_model=list[CommitmentChangeOrderResponse])
async def list_commitment_change_orders(
    commitment_id: UUID|None = Query(None),
    status: str|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_commitment_change_orders(
        db, commitment_id=commitment_id, status=status,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=CommitmentChangeOrderResponse)
async def get_commitment_change_order(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CommitmentChangeOrder, row_id)
    parent = await svc.get_by_id(db, Commitment, row.commitment_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=CommitmentChangeOrderResponse, status_code=201)
async def create_commitment_change_order(
    data: CommitmentChangeOrderCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Commitment, data.commitment_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, CommitmentChangeOrder, data)

@router.patch("/{row_id}", response_model=CommitmentChangeOrderResponse)
async def update_commitment_change_order(
    row_id: UUID,
    data: CommitmentChangeOrderUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CommitmentChangeOrder, row_id)
    parent = await svc.get_by_id(db, Commitment, row.commitment_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, CommitmentChangeOrder, row_id, data)

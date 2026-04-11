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
from app.models.financials import Commitment, CommitmentLineItem
from app.schemas.financials import CommitmentLineItemCreate, CommitmentLineItemResponse, CommitmentLineItemUpdate
from app.services import financials as svc

router = APIRouter(prefix="/api/commitment-line-items", tags=["commitment-line-items"])

@router.get("/", response_model=list[CommitmentLineItemResponse])
async def list_commitment_line_items(
    commitment_id: UUID|None = Query(None),
    cost_code_id: UUID|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_commitment_line_items(
        db, commitment_id=commitment_id, cost_code_id=cost_code_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=CommitmentLineItemResponse)
async def get_commitment_line_item(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CommitmentLineItem, row_id)
    parent = await svc.get_by_id(db, Commitment, row.commitment_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=CommitmentLineItemResponse, status_code=201)
async def create_commitment_line_item(
    data: CommitmentLineItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Commitment, data.commitment_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, CommitmentLineItem, data)

@router.patch("/{row_id}", response_model=CommitmentLineItemResponse)
async def update_commitment_line_item(
    row_id: UUID,
    data: CommitmentLineItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CommitmentLineItem, row_id)
    parent = await svc.get_by_id(db, Commitment, row.commitment_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, CommitmentLineItem, row_id, data)

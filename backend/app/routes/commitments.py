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
from app.models.financials import Commitment
from app.schemas.financials import (
    CommitmentCreate, CommitmentResponse, CommitmentSummaryResponse, CommitmentUpdate,
)
from app.services import financials as svc

router = APIRouter(prefix="/api/commitments", tags=["commitments"])

@router.get("/", response_model=list[CommitmentResponse])
async def list_commitments(
    project_id: UUID | None = Query(None),
    vendor_id: UUID | None = Query(None),
    status: str | None = Query(None),
    contract_type: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_commitments(
        db, project_id=project_id, vendor_id=vendor_id, status=status,
        contract_type=contract_type, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{commitment_id}", response_model=CommitmentResponse)
async def get_commitment(
    commitment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Commitment, commitment_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=CommitmentResponse, status_code=201)
async def create_commitment(
    data: CommitmentCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Commitment, data)

@router.patch("/{commitment_id}", response_model=CommitmentResponse)
async def update_commitment(
    commitment_id: UUID,
    data: CommitmentUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Commitment, commitment_id)
    reject_project_id_change(data, row.project_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Commitment, commitment_id, data)

@router.get("/{commitment_id}/summary", response_model=CommitmentSummaryResponse)
async def get_commitment_summary(commitment_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_commitment_summary(db, commitment_id)

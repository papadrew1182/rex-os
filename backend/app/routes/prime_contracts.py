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
from app.models.financials import PrimeContract
from app.schemas.financials import PrimeContractCreate, PrimeContractResponse, PrimeContractUpdate
from app.services import financials as svc

router = APIRouter(prefix="/api/prime-contracts", tags=["prime-contracts"])

@router.get("/", response_model=list[PrimeContractResponse])
async def list_prime_contracts(
    project_id: UUID|None = Query(None),
    status: str|None = Query(None),
    owner_company_id: UUID|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_prime_contracts(
        db, project_id=project_id, status=status, owner_company_id=owner_company_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=PrimeContractResponse)
async def get_prime_contract(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PrimeContract, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=PrimeContractResponse, status_code=201)
async def create_prime_contract(
    data: PrimeContractCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, PrimeContract, data)

@router.patch("/{row_id}", response_model=PrimeContractResponse)
async def update_prime_contract(
    row_id: UUID,
    data: PrimeContractUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PrimeContract, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, PrimeContract, row_id, data)

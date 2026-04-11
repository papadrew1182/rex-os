from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import Company, UserAccount
from app.schemas.foundation import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services import foundation as svc

router = APIRouter(prefix="/api/companies", tags=["companies"])

@router.get("/", response_model=list[CompanyResponse])
async def list_companies(
    company_type: str | None = Query(None),
    status: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_companies(
        db, company_type=company_type, status=status, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    if not await svc.is_company_readable(db, company_id, accessible):
        raise HTTPException(status_code=404, detail="Not found")
    return await svc.get_by_id(db, Company, company_id)

@router.post("/", response_model=CompanyResponse, status_code=201)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, Company, data)

@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: UUID, data: CompanyUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, Company, company_id, data)

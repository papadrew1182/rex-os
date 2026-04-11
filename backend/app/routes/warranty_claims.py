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
from app.models.closeout import Warranty, WarrantyClaim
from app.schemas.closeout import WarrantyClaimCreate, WarrantyClaimResponse, WarrantyClaimUpdate
from app.services import closeout as svc

router = APIRouter(prefix="/api/warranty-claims", tags=["warranty-claims"])

@router.get("/", response_model=list[WarrantyClaimResponse])
async def list_warranty_claims(
    warranty_id: UUID|None = Query(None),
    status: str|None = Query(None),
    priority: str|None = Query(None),
    is_covered_by_warranty: bool|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_warranty_claims(
        db, warranty_id=warranty_id, status=status, priority=priority,
        is_covered_by_warranty=is_covered_by_warranty,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=WarrantyClaimResponse)
async def get_warranty_claim(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, WarrantyClaim, row_id)
    parent = await svc.get_by_id(db, Warranty, row.warranty_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=WarrantyClaimResponse, status_code=201)
async def create_warranty_claim(
    data: WarrantyClaimCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Warranty, data.warranty_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, WarrantyClaim, data)

@router.patch("/{row_id}", response_model=WarrantyClaimResponse)
async def update_warranty_claim(
    row_id: UUID,
    data: WarrantyClaimUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, WarrantyClaim, row_id)
    parent = await svc.get_by_id(db, Warranty, row.warranty_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, WarrantyClaim, row_id, data)

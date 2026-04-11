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
from app.models.financials import Commitment, LienWaiver, PaymentApplication
from app.schemas.financials import LienWaiverCreate, LienWaiverResponse, LienWaiverUpdate
from app.services import financials as svc

router = APIRouter(prefix="/api/lien-waivers", tags=["lien-waivers"])

@router.get("/", response_model=list[LienWaiverResponse])
async def list_lien_waivers(
    payment_application_id: UUID|None = Query(None),
    vendor_id: UUID|None = Query(None),
    waiver_type: str|None = Query(None),
    status: str|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_lien_waivers(
        db, payment_application_id=payment_application_id, vendor_id=vendor_id,
        waiver_type=waiver_type, status=status,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=LienWaiverResponse)
async def get_lien_waiver(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, LienWaiver, row_id)
    pa = await svc.get_by_id(db, PaymentApplication, row.payment_application_id)
    parent = await svc.get_by_id(db, Commitment, pa.commitment_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=LienWaiverResponse, status_code=201)
async def create_lien_waiver(
    data: LienWaiverCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    p0 = await svc.get_by_id(db, PaymentApplication, data.payment_application_id)
    top = await svc.get_by_id(db, Commitment, p0.commitment_id)
    await assert_project_write(db, user, top.project_id)
    return await svc.create(db, LienWaiver, data)

@router.patch("/{row_id}", response_model=LienWaiverResponse)
async def update_lien_waiver(
    row_id: UUID,
    data: LienWaiverUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, LienWaiver, row_id)
    p0 = await svc.get_by_id(db, PaymentApplication, row.payment_application_id)
    top = await svc.get_by_id(db, Commitment, p0.commitment_id)
    await assert_project_write(db, user, top.project_id)
    return await svc.update(db, LienWaiver, row_id, data)

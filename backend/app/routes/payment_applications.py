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
from app.models.financials import Commitment, PaymentApplication
from app.schemas.financials import (
    PaymentApplicationCreate, PaymentApplicationResponse, PaymentApplicationUpdate,
    PaymentApplicationSummaryResponse, ProjectPayAppSummaryResponse,
)
from app.services import financials as svc

router = APIRouter(prefix="/api/payment-applications", tags=["payment-applications"])
project_router = APIRouter(tags=["payment-applications"])

@router.get("/", response_model=list[PaymentApplicationResponse])
async def list_payment_applications(
    commitment_id: UUID | None = Query(None),
    billing_period_id: UUID | None = Query(None),
    status: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_payment_applications(
        db, commitment_id=commitment_id, billing_period_id=billing_period_id,
        status=status, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{pay_app_id}", response_model=PaymentApplicationResponse)
async def get_payment_application(
    pay_app_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PaymentApplication, pay_app_id)
    parent = await svc.get_by_id(db, Commitment, row.commitment_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=PaymentApplicationResponse, status_code=201)
async def create_payment_application(
    data: PaymentApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Commitment, data.commitment_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, PaymentApplication, data)

@router.patch("/{pay_app_id}", response_model=PaymentApplicationResponse)
async def update_payment_application(
    pay_app_id: UUID,
    data: PaymentApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PaymentApplication, pay_app_id)
    parent = await svc.get_by_id(db, Commitment, row.commitment_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, PaymentApplication, pay_app_id, data)

@router.get("/{pay_app_id}/summary", response_model=PaymentApplicationSummaryResponse)
async def get_payment_application_summary(
    pay_app_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PaymentApplication, pay_app_id)
    parent = await svc.get_by_id(db, Commitment, row.commitment_id)
    await enforce_project_read(db, user, parent.project_id)
    return await svc.get_payment_application_summary(db, pay_app_id)


@project_router.get("/api/projects/{project_id}/pay-app-summary", response_model=ProjectPayAppSummaryResponse)
async def get_project_pay_app_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await svc.get_project_pay_app_summary(db, project_id)

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
from app.models.financials import BillingPeriod
from app.schemas.financials import (
    BillingPeriodCreate, BillingPeriodResponse, BillingPeriodUpdate,
    BillingPeriodSummaryResponse,
)
from app.services import financials as svc

router = APIRouter(prefix="/api/billing-periods", tags=["billing-periods"])

@router.get("/", response_model=list[BillingPeriodResponse])
async def list_billing_periods(
    project_id: UUID | None = Query(None),
    status: str | None = Query(None),
    period_number: int | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_billing_periods(
        db, project_id=project_id, status=status, period_number=period_number,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{billing_period_id}", response_model=BillingPeriodResponse)
async def get_billing_period(
    billing_period_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, BillingPeriod, billing_period_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=BillingPeriodResponse, status_code=201)
async def create_billing_period(
    data: BillingPeriodCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, BillingPeriod, data)

@router.patch("/{billing_period_id}", response_model=BillingPeriodResponse)
async def update_billing_period(
    billing_period_id: UUID,
    data: BillingPeriodUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, BillingPeriod, billing_period_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, BillingPeriod, billing_period_id, data)

@router.get("/{billing_period_id}/summary", response_model=BillingPeriodSummaryResponse)
async def get_billing_period_summary(billing_period_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_billing_period_summary(db, billing_period_id)

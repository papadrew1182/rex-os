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
from app.models.financials import BudgetSnapshot
from app.schemas.financials import BudgetSnapshotCreate, BudgetSnapshotResponse
from app.services import financials as svc

router = APIRouter(prefix="/api/budget-snapshots", tags=["budget-snapshots"])

@router.get("/", response_model=list[BudgetSnapshotResponse])
async def list_budget_snapshots(
    project_id: UUID|None = Query(None),
    budget_line_item_id: UUID|None = Query(None),
    snapshot_date: str|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_budget_snapshots(
        db, project_id=project_id, budget_line_item_id=budget_line_item_id,
        snapshot_date=snapshot_date, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=BudgetSnapshotResponse)
async def get_budget_snapshot(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, BudgetSnapshot, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=BudgetSnapshotResponse, status_code=201)
async def create_budget_snapshot(
    data: BudgetSnapshotCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, BudgetSnapshot, data)

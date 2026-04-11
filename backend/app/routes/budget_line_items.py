from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_admin_or_vp,
    require_authenticated_user,
)
from app.models.financials import BudgetLineItem
from app.models.foundation import UserAccount
from app.schemas.financials import (
    BudgetLineItemCreate, BudgetLineItemResponse, BudgetLineItemUpdate,
    BudgetLineItemRollupResponse, BudgetRollupRefreshResponse,
)
from app.services import financials as svc

router = APIRouter(prefix="/api/budget-line-items", tags=["budget-line-items"])

@router.get("/", response_model=list[BudgetLineItemResponse])
async def list_budget_line_items(
    project_id: UUID | None = Query(None),
    cost_code_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_budget_line_items(
        db, project_id=project_id, cost_code_id=cost_code_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.post("/", response_model=BudgetLineItemResponse, status_code=201)
async def create_budget_line_item(
    data: BudgetLineItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, BudgetLineItem, data)

# Bulk refresh — must be declared before /{line_id} so the literal path wins
@router.post("/refresh-rollups", response_model=BudgetRollupRefreshResponse)
async def refresh_budget_rollups(
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, project_id)
    return await svc.refresh_budget_rollups_for_project(db, project_id)

@router.get("/{line_id}", response_model=BudgetLineItemResponse)
async def get_budget_line_item(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, BudgetLineItem, line_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.patch("/{line_id}", response_model=BudgetLineItemResponse)
async def update_budget_line_item(
    line_id: UUID,
    data: BudgetLineItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, BudgetLineItem, line_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, BudgetLineItem, line_id, data)

@router.get("/{line_id}/rollup", response_model=BudgetLineItemRollupResponse)
async def get_budget_line_item_rollup(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, BudgetLineItem, line_id)
    await enforce_project_read(db, user, row.project_id)
    return await svc.get_budget_line_item_rollup(db, line_id)

@router.post("/{line_id}/refresh-rollup", response_model=BudgetLineItemResponse)
async def refresh_budget_line_item_rollup(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: UserAccount = Depends(require_admin_or_vp),
):
    return await svc.refresh_budget_line_item_rollup(db, line_id)

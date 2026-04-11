from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import enforce_project_read, get_current_user
from app.models.foundation import UserAccount
from app.schemas.financials import ProjectBudgetSummaryResponse
from app.services import financials as svc

router = APIRouter(tags=["budget-summary"])


@router.get("/api/projects/{project_id}/budget-summary", response_model=ProjectBudgetSummaryResponse)
async def get_project_budget_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await enforce_project_read(db, user, project_id)
    return await svc.get_project_budget_summary(db, project_id)

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_readable_project_ids
from app.models.foundation import UserAccount
from app.schemas.closeout import PortfolioReadinessResponse
from app.services import closeout as svc

router = APIRouter(prefix="/api/closeout-readiness", tags=["closeout-readiness"])


@router.get("/portfolio", response_model=PortfolioReadinessResponse)
async def get_portfolio_readiness(
    project_status: str | None = Query(None),
    project_type: str | None = Query(None),
    city: str | None = Query(None),
    state: str | None = Query(None),
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.get_portfolio_closeout_readiness(
        db,
        project_status=project_status,
        project_type=project_type,
        city=city,
        state=state,
        limit=limit,
        offset=offset,
        accessible_project_ids=accessible,
    )

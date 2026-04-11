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
from app.models.document_management import Submittal
from app.schemas.document_management import (
    SubmittalAgingResponse, SubmittalCreate, SubmittalResponse, SubmittalUpdate,
)
from app.services import document_management as svc

router = APIRouter(prefix="/api/submittals", tags=["submittals"])

@router.get("/", response_model=list[SubmittalResponse])
async def list_submittals(
    project_id: UUID | None = Query(None),
    submittal_package_id: UUID | None = Query(None),
    status: str | None = Query(None),
    submittal_type: str | None = Query(None),
    cost_code_id: UUID | None = Query(None),
    schedule_activity_id: UUID | None = Query(None),
    assigned_to: UUID | None = Query(None),
    ball_in_court: UUID | None = Query(None),
    responsible_contractor: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_submittals(
        db, project_id=project_id, submittal_package_id=submittal_package_id,
        status=status, submittal_type=submittal_type, cost_code_id=cost_code_id,
        schedule_activity_id=schedule_activity_id, assigned_to=assigned_to,
        ball_in_court=ball_in_court, responsible_contractor=responsible_contractor,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{submittal_id}", response_model=SubmittalResponse)
async def get_submittal(
    submittal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Submittal, submittal_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=SubmittalResponse, status_code=201)
async def create_submittal(
    data: SubmittalCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, Submittal, data)

@router.patch("/{submittal_id}", response_model=SubmittalResponse)
async def update_submittal(
    submittal_id: UUID,
    data: SubmittalUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Submittal, submittal_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Submittal, submittal_id, data)

@router.get("/{submittal_id}/aging", response_model=SubmittalAgingResponse)
async def get_submittal_aging(submittal_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_submittal_aging(db, submittal_id)

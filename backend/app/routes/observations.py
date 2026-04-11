from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_field_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.field_ops import Observation
from app.schemas.field_ops import ObservationCreate, ObservationResponse, ObservationUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/observations", tags=["observations"])

@router.get("/", response_model=list[ObservationResponse])
async def list_observations(
    project_id: UUID | None = Query(None),
    observation_type: str | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_observations(
        db, project_id=project_id, observation_type=observation_type,
        status=status, priority=priority, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=ObservationResponse)
async def get_observation(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Observation, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=ObservationResponse, status_code=201)
async def create_observation(
    data: ObservationCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, Observation, data)

@router.patch("/{row_id}", response_model=ObservationResponse)
async def update_observation(
    row_id: UUID,
    data: ObservationUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Observation, row_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, Observation, row_id, data)

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
from app.models.field_ops import SafetyIncident
from app.schemas.field_ops import SafetyIncidentCreate, SafetyIncidentResponse, SafetyIncidentUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/safety-incidents", tags=["safety-incidents"])

@router.get("/", response_model=list[SafetyIncidentResponse])
async def list_safety_incidents(
    project_id: UUID | None = Query(None),
    incident_type: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    is_osha_recordable: bool | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_safety_incidents(
        db, project_id=project_id, incident_type=incident_type, status=status,
        severity=severity, is_osha_recordable=is_osha_recordable,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=SafetyIncidentResponse)
async def get_safety_incident(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, SafetyIncident, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=SafetyIncidentResponse, status_code=201)
async def create_safety_incident(
    data: SafetyIncidentCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, SafetyIncident, data)

@router.patch("/{row_id}", response_model=SafetyIncidentResponse)
async def update_safety_incident(
    row_id: UUID,
    data: SafetyIncidentUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, SafetyIncident, row_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, SafetyIncident, row_id, data)

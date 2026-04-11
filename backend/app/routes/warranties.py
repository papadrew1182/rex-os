import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    reject_project_id_change,
    require_admin_or_vp,
    require_authenticated_user,
)
from app.models.closeout import Warranty
from app.models.foundation import UserAccount
from app.schemas.closeout import (
    GenerateAlertsResponse, WarrantyCreate, WarrantyResponse, WarrantyStatusRefreshResponse, WarrantyUpdate,
)
from app.services import closeout as svc

log = logging.getLogger("rex.warranty")
router = APIRouter(prefix="/api/warranties", tags=["warranties"])

@router.get("/", response_model=list[WarrantyResponse])
async def list_warranties(
    project_id: UUID | None = Query(None),
    commitment_id: UUID | None = Query(None),
    company_id: UUID | None = Query(None),
    cost_code_id: UUID | None = Query(None),
    status: str | None = Query(None),
    warranty_type: str | None = Query(None),
    is_letter_received: bool | None = Query(None),
    is_om_received: bool | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_warranties(
        db, project_id=project_id, commitment_id=commitment_id,
        company_id=company_id, cost_code_id=cost_code_id, status=status,
        warranty_type=warranty_type, is_letter_received=is_letter_received,
        is_om_received=is_om_received, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{warranty_id}", response_model=WarrantyResponse)
async def get_warranty(
    warranty_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Warranty, warranty_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=WarrantyResponse, status_code=201)
async def create_warranty(
    data: WarrantyCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create_warranty_with_expiration(db, data)

@router.patch("/{warranty_id}", response_model=WarrantyResponse)
async def update_warranty(
    warranty_id: UUID,
    data: WarrantyUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Warranty, warranty_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, Warranty, warranty_id, data)

@router.post("/{warranty_id}/generate-alerts", response_model=GenerateAlertsResponse, status_code=201)
async def generate_alerts(
    warranty_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    alerts = await svc.generate_warranty_alerts(db, warranty_id)
    log.info(
        "warranty_alerts_generated user_id=%s warranty_id=%s alerts_created=%d",
        user.id, warranty_id, len(alerts),
    )
    return GenerateAlertsResponse(
        warranty_id=warranty_id,
        alerts_created=len(alerts),
        alerts=alerts,
    )

@router.post("/{warranty_id}/refresh-status", response_model=WarrantyResponse)
async def refresh_warranty_status(
    warranty_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    result = await svc.refresh_warranty_status(db, warranty_id)
    log.info(
        "warranty_status_refreshed user_id=%s warranty_id=%s status=%s",
        user.id, warranty_id, result.status,
    )
    return result

@router.post("/refresh-statuses", response_model=WarrantyStatusRefreshResponse)
async def refresh_warranty_statuses(
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    result = await svc.refresh_warranty_statuses_for_project(db, project_id)
    log.info(
        "warranty_statuses_refreshed user_id=%s project_id=%s",
        user.id, project_id,
    )
    return result

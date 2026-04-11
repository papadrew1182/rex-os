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
from app.models.closeout import Warranty, WarrantyAlert
from app.schemas.closeout import WarrantyAlertCreate, WarrantyAlertResponse, WarrantyAlertUpdate
from app.services import closeout as svc

router = APIRouter(prefix="/api/warranty-alerts", tags=["warranty-alerts"])

@router.get("/", response_model=list[WarrantyAlertResponse])
async def list_warranty_alerts(
    warranty_id: UUID|None = Query(None),
    alert_type: str|None = Query(None),
    is_sent: bool|None = Query(None),
    recipient_id: UUID|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_warranty_alerts(
        db, warranty_id=warranty_id, alert_type=alert_type, is_sent=is_sent,
        recipient_id=recipient_id, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=WarrantyAlertResponse)
async def get_warranty_alert(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, WarrantyAlert, row_id)
    parent = await svc.get_by_id(db, Warranty, row.warranty_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=WarrantyAlertResponse, status_code=201)
async def create_warranty_alert(
    data: WarrantyAlertCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    parent = await svc.get_by_id(db, Warranty, data.warranty_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.create(db, WarrantyAlert, data)

@router.patch("/{row_id}", response_model=WarrantyAlertResponse)
async def update_warranty_alert(
    row_id: UUID,
    data: WarrantyAlertUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, WarrantyAlert, row_id)
    parent = await svc.get_by_id(db, Warranty, row.warranty_id)
    await assert_project_write(db, user, parent.project_id)
    return await svc.update(db, WarrantyAlert, row_id, data)

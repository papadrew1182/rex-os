"""User-facing notification inbox endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_authenticated_user
from app.models.foundation import UserAccount
from app.schemas.notifications import NotificationResponse, UnreadCountResponse
from app.services import notifications as svc

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationResponse])
async def list_notifications(
    unread: bool = Query(False),
    domain: str | None = Query(None),
    project_id: UUID | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_authenticated_user),
):
    return await svc.list_for_user(
        db, user.id,
        unread_only=unread, domain=domain, project_id=project_id,
        severity=severity, limit=limit, offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_authenticated_user),
):
    n = await svc.unread_count_for_user(db, user.id)
    return {"unread_count": n}


@router.patch("/read-all")
async def read_all(
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_authenticated_user),
):
    n = await svc.mark_all_read(db, user.id)
    await db.commit()
    return {"updated": n}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_authenticated_user),
):
    ok = await svc.mark_read(db, user.id, notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"ok": True}


@router.patch("/{notification_id}/dismiss")
async def dismiss(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_authenticated_user),
):
    ok = await svc.dismiss(db, user.id, notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"ok": True}

from datetime import date, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    assert_project_write,
    get_current_user,
    require_admin_or_vp,
    require_authenticated_user,
)
from app.models.foundation import UserAccount, InsuranceCertificate
from app.schemas.insurance import (
    InsuranceCertificateCreate, InsuranceCertificateResponse, InsuranceCertificateUpdate,
    InsuranceCertificateSummaryResponse, InsuranceRefreshResponse,
)
from app.services.crud import create, get_by_id, update

router = APIRouter(prefix="/api/insurance-certificates", tags=["insurance-certificates"])


def _compute_status(cert: InsuranceCertificate, today: date | None = None) -> str:
    today = today or date.today()
    if cert.expiry_date is None:
        return "missing"
    if cert.expiry_date < today:
        return "expired"
    if (cert.expiry_date - today).days <= 60:
        return "expiring_soon"
    return "current"


@router.get("/", response_model=list[InsuranceCertificateResponse])
async def list_insurance_certificates(
    company_id: UUID | None = Query(None),
    policy_type: str | None = Query(None),
    status: str | None = Query(None),
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_authenticated_user),
):
    stmt = select(InsuranceCertificate)
    if company_id:
        stmt = stmt.where(InsuranceCertificate.company_id == company_id)
    if policy_type:
        stmt = stmt.where(InsuranceCertificate.policy_type == policy_type)
    if status:
        stmt = stmt.where(InsuranceCertificate.status == status)
    stmt = stmt.offset(skip).limit(limit).order_by(InsuranceCertificate.expiry_date.asc().nullslast())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/summary", response_model=InsuranceCertificateSummaryResponse)
async def insurance_summary(db: AsyncSession = Depends(get_db), user: UserAccount = Depends(require_authenticated_user)):
    result = await db.execute(select(InsuranceCertificate))
    certs = list(result.scalars().all())
    today = date.today()
    counts = {"total": len(certs), "current": 0, "expiring_soon": 0, "expired": 0, "missing": 0}
    for c in certs:
        s = _compute_status(c, today)
        counts[s] = counts.get(s, 0) + 1
    return counts


@router.get("/{cert_id}", response_model=InsuranceCertificateResponse)
async def get_certificate(cert_id: UUID, db: AsyncSession = Depends(get_db), user: UserAccount = Depends(require_authenticated_user)):
    return await get_by_id(db, InsuranceCertificate, cert_id)


@router.post("/", response_model=InsuranceCertificateResponse, status_code=201)
async def create_certificate(
    data: InsuranceCertificateCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    return await create(db, InsuranceCertificate, data)


@router.patch("/{cert_id}", response_model=InsuranceCertificateResponse)
async def update_certificate(
    cert_id: UUID,
    data: InsuranceCertificateUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    return await update(db, InsuranceCertificate, cert_id, data)


@router.post("/refresh-status", response_model=InsuranceRefreshResponse)
async def refresh_all_statuses(
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    result = await db.execute(select(InsuranceCertificate))
    certs = list(result.scalars().all())
    today = date.today()
    updated = 0
    counts = {"current": 0, "expiring_soon": 0, "expired": 0, "missing": 0}
    for c in certs:
        new_status = _compute_status(c, today)
        if c.status != new_status:
            c.status = new_status
            updated += 1
        counts[new_status] = counts.get(new_status, 0) + 1
    await db.commit()
    return {"total_certs": len(certs), "updated_count": updated, "by_status": counts}

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
)
from app.models.foundation import UserAccount
from app.models.closeout import OmManual
from app.schemas.closeout import OmManualCreate, OmManualResponse, OmManualUpdate
from app.services import crud

router = APIRouter(prefix="/api/om-manuals", tags=["om-manuals"])


@router.get("/", response_model=list[OmManualResponse])
async def list_om_manuals(
    project_id: UUID | None = Query(None),
    status: str | None = Query(None),
    spec_section: str | None = Query(None),
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    stmt = select(OmManual)
    if project_id is not None:
        stmt = stmt.where(OmManual.project_id == project_id)
    if status:
        stmt = stmt.where(OmManual.status == status)
    if spec_section:
        stmt = stmt.where(OmManual.spec_section == spec_section)
    if accessible is not None:
        if not accessible:
            return []
        stmt = stmt.where(OmManual.project_id.in_(accessible))
    stmt = stmt.offset(skip).limit(limit).order_by(OmManual.spec_section)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/{row_id}", response_model=OmManualResponse)
async def get_om_manual(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await crud.get_by_id(db, OmManual, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row


@router.post("/", response_model=OmManualResponse, status_code=201)
async def create_om_manual(
    data: OmManualCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await crud.create(db, OmManual, data)


@router.patch("/{row_id}", response_model=OmManualResponse)
async def update_om_manual(
    row_id: UUID,
    data: OmManualUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await crud.get_by_id(db, OmManual, row_id)
    await assert_project_write(db, user, row.project_id)
    return await crud.update(db, OmManual, row_id, data)

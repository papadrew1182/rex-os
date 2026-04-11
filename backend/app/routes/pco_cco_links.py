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
from app.models.financials import ChangeEvent, PcoCcoLink, PotentialChangeOrder
from app.schemas.financials import PcoCcoLinkCreate, PcoCcoLinkResponse
from app.services import financials as svc

router = APIRouter(prefix="/api/pco-cco-links", tags=["pco-cco-links"])

@router.get("/", response_model=list[PcoCcoLinkResponse])
async def list_pco_cco_links(
    pco_id: UUID|None = Query(None),
    cco_id: UUID|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_pco_cco_links(
        db, pco_id=pco_id, cco_id=cco_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=PcoCcoLinkResponse)
async def get_pco_cco_link(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, PcoCcoLink, row_id)
    pco = await svc.get_by_id(db, PotentialChangeOrder, row.pco_id)
    parent = await svc.get_by_id(db, ChangeEvent, pco.change_event_id)
    await enforce_project_read(db, user, parent.project_id)
    return row

@router.post("/", response_model=PcoCcoLinkResponse, status_code=201)
async def create_pco_cco_link(
    data: PcoCcoLinkCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    p0 = await svc.get_by_id(db, PotentialChangeOrder, data.pco_id)
    top = await svc.get_by_id(db, ChangeEvent, p0.change_event_id)
    await assert_project_write(db, user, top.project_id)
    return await svc.create(db, PcoCcoLink, data)

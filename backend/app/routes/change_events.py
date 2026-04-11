from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.financials import ChangeEvent
from app.schemas.financials import ChangeEventCreate, ChangeEventResponse, ChangeEventUpdate, ChangeEventDetailResponse
from app.services import financials as svc

router = APIRouter(prefix="/api/change-events", tags=["change-events"])

@router.get("/", response_model=list[ChangeEventResponse])
async def list_change_events(
    project_id: UUID|None = Query(None),
    status: str|None = Query(None),
    change_reason: str|None = Query(None),
    event_type: str|None = Query(None),
    scope: str|None = Query(None),
    prime_contract_id: UUID|None = Query(None),
    rfi_id: UUID|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_change_events(
        db, project_id=project_id, status=status, change_reason=change_reason,
        event_type=event_type, scope=scope, prime_contract_id=prime_contract_id,
        rfi_id=rfi_id, skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=ChangeEventResponse)
async def get_change_event(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ChangeEvent, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=ChangeEventResponse, status_code=201)
async def create_change_event(data: ChangeEventCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, ChangeEvent, data)

@router.patch("/{row_id}", response_model=ChangeEventResponse)
async def update_change_event(row_id: UUID, data: ChangeEventUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, ChangeEvent, row_id, data)


@router.get("/{row_id}/detail", response_model=ChangeEventDetailResponse)
async def get_change_event_detail(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ChangeEvent, row_id)
    await enforce_project_read(db, user, row.project_id)
    return await svc.get_change_event_detail(db, row_id)

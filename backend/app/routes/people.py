from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import Person, UserAccount
from app.schemas.foundation import PersonCreate, PersonResponse, PersonUpdate
from app.services import foundation as svc

router = APIRouter(prefix="/api/people", tags=["people"])

@router.get("/", response_model=list[PersonResponse])
async def list_people(
    company_id: UUID | None = Query(None),
    role_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_people(
        db, company_id=company_id, role_type=role_type, is_active=is_active,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    if not await svc.is_person_readable(db, person_id, accessible):
        raise HTTPException(status_code=404, detail="Not found")
    return await svc.get_by_id(db, Person, person_id)

@router.post("/", response_model=PersonResponse, status_code=201)
async def create_person(data: PersonCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, Person, data)

@router.patch("/{person_id}", response_model=PersonResponse)
async def update_person(person_id: UUID, data: PersonUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, Person, person_id, data)

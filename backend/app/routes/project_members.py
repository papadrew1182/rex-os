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
from app.models.foundation import ProjectMember
from app.schemas.foundation import ProjectMemberCreate, ProjectMemberResponse, ProjectMemberUpdate
from app.services import foundation as svc

router = APIRouter(prefix="/api/project-members", tags=["project-members"])

@router.get("/", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: UUID | None = Query(None),
    person_id: UUID | None = Query(None),
    role_template_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_project_members(
        db, project_id=project_id, person_id=person_id,
        role_template_id=role_template_id, is_active=is_active,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{member_id}", response_model=ProjectMemberResponse)
async def get_project_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, ProjectMember, member_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=ProjectMemberResponse, status_code=201)
async def create_project_member(data: ProjectMemberCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, ProjectMember, data)

@router.patch("/{member_id}", response_model=ProjectMemberResponse)
async def update_project_member(member_id: UUID, data: ProjectMemberUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, ProjectMember, member_id, data)

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import require_authenticated_user
from app.models.foundation import UserAccount
from app.models.foundation import RoleTemplate
from app.schemas.foundation import RoleTemplateCreate, RoleTemplateResponse, RoleTemplateUpdate
from app.services import foundation as svc

router = APIRouter(prefix="/api/role-templates", tags=["role-templates"])

@router.get("/", response_model=list[RoleTemplateResponse])
async def list_role_templates(
    is_internal: bool | None = Query(None),
    is_system: bool | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _auth_user: UserAccount = Depends(require_authenticated_user),
):
    # role_templates are intentionally readable to any authenticated user.
    # They're a small, slowly-changing global directory and the read policy
    # explicitly allows this in Sprint G/H scope.
    return await svc.list_role_templates(db, is_internal=is_internal, is_system=is_system, skip=skip, limit=limit)

@router.get("/{template_id}", response_model=RoleTemplateResponse)
async def get_role_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    _auth_user: UserAccount = Depends(require_authenticated_user),
):
    return await svc.get_by_id(db, RoleTemplate, template_id)

@router.post("/", response_model=RoleTemplateResponse, status_code=201)
async def create_role_template(data: RoleTemplateCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, RoleTemplate, data)

@router.patch("/{template_id}", response_model=RoleTemplateResponse)
async def update_role_template(template_id: UUID, data: RoleTemplateUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, RoleTemplate, template_id, data)

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import require_authenticated_user
from app.models.foundation import UserAccount
from app.models.closeout import CloseoutTemplate
from app.schemas.closeout import CloseoutTemplateCreate, CloseoutTemplateResponse, CloseoutTemplateUpdate
from app.services import closeout as svc

router = APIRouter(prefix="/api/closeout-templates", tags=["closeout-templates"])

@router.get("/", response_model=list[CloseoutTemplateResponse])
async def list_closeout_templates(project_type: str|None = Query(None), is_default: bool|None = Query(None), skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    return await svc.list_closeout_templates(db, project_type=project_type, is_default=is_default, skip=skip, limit=limit)

@router.get("/{row_id}", response_model=CloseoutTemplateResponse)
async def get_closeout_template(row_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_by_id(db, CloseoutTemplate, row_id)

@router.post("/", response_model=CloseoutTemplateResponse, status_code=201)
async def create_closeout_template(data: CloseoutTemplateCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, CloseoutTemplate, data)

@router.patch("/{row_id}", response_model=CloseoutTemplateResponse)
async def update_closeout_template(row_id: UUID, data: CloseoutTemplateUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, CloseoutTemplate, row_id, data)

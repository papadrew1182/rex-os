from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import require_authenticated_user
from app.models.foundation import UserAccount
from app.models.closeout import CloseoutTemplateItem
from app.schemas.closeout import CloseoutTemplateItemCreate, CloseoutTemplateItemResponse, CloseoutTemplateItemUpdate
from app.services import closeout as svc

router = APIRouter(prefix="/api/closeout-template-items", tags=["closeout-template-items"])

@router.get("/", response_model=list[CloseoutTemplateItemResponse])
async def list_closeout_template_items(template_id: UUID|None = Query(None), category: str|None = Query(None), default_assignee_role: str|None = Query(None), skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    return await svc.list_closeout_template_items(db, template_id=template_id, category=category, default_assignee_role=default_assignee_role, skip=skip, limit=limit)

@router.get("/{row_id}", response_model=CloseoutTemplateItemResponse)
async def get_closeout_template_item(row_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_by_id(db, CloseoutTemplateItem, row_id)

@router.post("/", response_model=CloseoutTemplateItemResponse, status_code=201)
async def create_closeout_template_item(data: CloseoutTemplateItemCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, CloseoutTemplateItem, data)

@router.patch("/{row_id}", response_model=CloseoutTemplateItemResponse)
async def update_closeout_template_item(row_id: UUID, data: CloseoutTemplateItemUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, CloseoutTemplateItem, row_id, data)

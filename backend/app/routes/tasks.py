from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_field_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_authenticated_user,
)
from app.models.foundation import UserAccount
from app.models.field_ops import Task
from app.schemas.field_ops import TaskCreate, TaskResponse, TaskUpdate
from app.services import field_ops as svc

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    project_id: UUID | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    category: str | None = Query(None),
    assigned_to: UUID | None = Query(None),
    assigned_company_id: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_tasks(
        db, project_id=project_id, status=status, priority=priority,
        category=category, assigned_to=assigned_to,
        assigned_company_id=assigned_company_id,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=TaskResponse)
async def get_task(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Task, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_field_write(db, user, data.project_id)
    return await svc.create(db, Task, data)

@router.patch("/{row_id}", response_model=TaskResponse)
async def update_task(
    row_id: UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, Task, row_id)
    await assert_field_write(db, user, row.project_id)
    return await svc.update(db, Task, row_id, data)

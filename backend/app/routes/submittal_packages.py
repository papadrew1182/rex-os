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
from app.models.document_management import SubmittalPackage
from app.schemas.document_management import SubmittalPackageCreate, SubmittalPackageResponse, SubmittalPackageUpdate
from app.services import document_management as svc

router = APIRouter(prefix="/api/submittal-packages", tags=["submittal-packages"])

@router.get("/", response_model=list[SubmittalPackageResponse])
async def list_submittal_packages(
    project_id: UUID|None = Query(None),
    status: str|None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_submittal_packages(
        db, project_id=project_id, status=status,
        skip=skip, limit=limit, accessible_project_ids=accessible,
    )

@router.get("/{row_id}", response_model=SubmittalPackageResponse)
async def get_submittal_package(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, SubmittalPackage, row_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=SubmittalPackageResponse, status_code=201)
async def create_submittal_package(
    data: SubmittalPackageCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, SubmittalPackage, data)

@router.patch("/{row_id}", response_model=SubmittalPackageResponse)
async def update_submittal_package(
    row_id: UUID,
    data: SubmittalPackageUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, SubmittalPackage, row_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, SubmittalPackage, row_id, data)

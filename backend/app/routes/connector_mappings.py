from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import require_authenticated_user
from app.models.foundation import UserAccount
from app.models.foundation import ConnectorMapping
from app.schemas.foundation import ConnectorMappingCreate, ConnectorMappingResponse, ConnectorMappingUpdate
from app.services import foundation as svc

router = APIRouter(prefix="/api/connector-mappings", tags=["connector-mappings"])

@router.get("/", response_model=list[ConnectorMappingResponse])
async def list_connector_mappings(rex_table: str | None = Query(None), connector: str | None = Query(None), rex_id: UUID | None = Query(None), skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    return await svc.list_connector_mappings(db, rex_table=rex_table, connector=connector, rex_id=rex_id, skip=skip, limit=limit)

@router.get("/{mapping_id}", response_model=ConnectorMappingResponse)
async def get_connector_mapping(mapping_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_by_id(db, ConnectorMapping, mapping_id)

@router.post("/", response_model=ConnectorMappingResponse, status_code=201)
async def create_connector_mapping(data: ConnectorMappingCreate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.create(db, ConnectorMapping, data)

@router.patch("/{mapping_id}", response_model=ConnectorMappingResponse)
async def update_connector_mapping(mapping_id: UUID, data: ConnectorMappingUpdate, db: AsyncSession = Depends(get_db), _auth_user: UserAccount = Depends(require_authenticated_user)):
    return await svc.update(db, ConnectorMapping, mapping_id, data)

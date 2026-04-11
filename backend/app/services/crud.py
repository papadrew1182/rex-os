"""Shared async CRUD helpers used by all domain services.

Persistence boundary:
  - All domain CRUD uses SQLAlchemy async sessions (app.database.get_db).
  - Legacy admin/migration endpoints use raw asyncpg (backend/db.py).
  - New domain CRUD should use these helpers unless explicitly justified.
"""

import re
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foundation import Base

# asyncpg SQLSTATE codes surfaced through IntegrityError.orig
_UNIQUE_VIOLATION = "23505"
_FK_VIOLATION = "23503"
_CHECK_VIOLATION = "23514"

# Pattern to extract constraint name or column detail from asyncpg messages
_DETAIL_RE = re.compile(r"Key \((.+?)\)")


def _classify_integrity_error(exc: IntegrityError) -> HTTPException:
    """Map a DB integrity error to an appropriate HTTP status with a clean message."""
    pgcode = getattr(exc.orig, "sqlstate", None) or ""
    raw = str(exc.orig) if exc.orig else str(exc)

    # Extract the useful part (e.g. column names from "Key (project_id, person_id)=...")
    match = _DETAIL_RE.search(raw)
    key_hint = match.group(1) if match else None

    if pgcode == _UNIQUE_VIOLATION:
        detail = f"Duplicate value on ({key_hint})" if key_hint else "Duplicate record"
        return HTTPException(status_code=409, detail=detail)
    if pgcode == _FK_VIOLATION:
        detail = f"Referenced record not found for ({key_hint})" if key_hint else "Invalid reference"
        return HTTPException(status_code=422, detail=detail)
    if pgcode == _CHECK_VIOLATION:
        detail = f"Value violates constraint on ({key_hint})" if key_hint else "Constraint violation"
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=500, detail="Database integrity error")


async def get_all(
    db: AsyncSession,
    model: type[Base],
    *,
    skip: int = 0,
    limit: int = 100,
) -> list[Base]:
    result = await db.execute(
        select(model).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def get_by_id(
    db: AsyncSession,
    model: type[Base],
    row_id: UUID,
) -> Base:
    row = await db.get(model, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{model.__tablename__} not found")
    return row


async def create(
    db: AsyncSession,
    model: type[Base],
    data: BaseModel,
) -> Base:
    row = model(**data.model_dump(exclude_unset=True))
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)
    await db.refresh(row)
    return row


async def update(
    db: AsyncSession,
    model: type[Base],
    row_id: UUID,
    data: BaseModel,
) -> Base:
    row = await db.get(model, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{model.__tablename__} not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)
    await db.refresh(row)
    return row

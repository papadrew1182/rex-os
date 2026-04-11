"""Foundation domain service layer.

Provides filtered list queries for Foundation tables plus re-exports
shared CRUD helpers, matching the pattern used by all other domains.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foundation import (
    Company, ConnectorMapping, Person, Project, ProjectMember, RoleTemplate,
)
from app.services.crud import create, get_by_id, update  # noqa: F401


def _apply(stmt, model, col, val):
    return stmt.where(getattr(model, col) == val) if val is not None else stmt


async def _flist(
    db: AsyncSession,
    model,
    filters: dict,
    skip: int,
    limit: int,
    *,
    accessible_project_ids: set[UUID] | None = None,
    project_id_attr: str = "project_id",
):
    stmt = select(model)
    for col, val in filters.items():
        stmt = _apply(stmt, model, col, val)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.where(getattr(model, project_id_attr).in_(accessible_project_ids))
    return list((await db.execute(stmt.offset(skip).limit(limit))).scalars().all())


async def list_projects(db: AsyncSession, *, status: str | None = None, project_type: str | None = None, city: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    # Project model's primary key is `id`, not `project_id` — scope on `id` directly.
    return await _flist(
        db, Project, {"status": status, "project_type": project_type, "city": city},
        skip, limit, accessible_project_ids=accessible_project_ids, project_id_attr="id",
    )

async def list_companies(db: AsyncSession, *, company_type: str | None = None, status: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """Companies visible to the caller.

    Scoping rule: a company is visible if it has at least one ``project_members``
    row on a project the caller can read. Admins/VPs (sentinel ``None``) bypass.
    """
    stmt = select(Company).distinct()
    if company_type is not None:
        stmt = stmt.where(Company.company_type == company_type)
    if status is not None:
        stmt = stmt.where(Company.status == status)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(
            ProjectMember,
            (ProjectMember.company_id == Company.id) & (ProjectMember.is_active.is_(True)),
        ).where(ProjectMember.project_id.in_(accessible_project_ids))
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())

async def list_people(db: AsyncSession, *, company_id: UUID | None = None, role_type: str | None = None, is_active: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """People visible to the caller.

    Scoping rule: a person is visible if they have at least one active
    ``project_members`` row on a project the caller can read. Admins/VPs
    (sentinel ``None``) bypass.
    """
    stmt = select(Person).distinct()
    if company_id is not None:
        stmt = stmt.where(Person.company_id == company_id)
    if role_type is not None:
        stmt = stmt.where(Person.role_type == role_type)
    if is_active is not None:
        stmt = stmt.where(Person.is_active == is_active)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(
            ProjectMember,
            (ProjectMember.person_id == Person.id) & (ProjectMember.is_active.is_(True)),
        ).where(ProjectMember.project_id.in_(accessible_project_ids))
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


# ── Read-side detail enforcement helpers (Sprint H) ────────────────────────


async def is_person_readable(
    db: AsyncSession,
    person_id: UUID,
    accessible_project_ids: set[UUID] | None,
) -> bool:
    """True if the caller can read this person under read-scoping rules.

    Admin/VP (sentinel None) → always True. Empty allow-list → always False.
    """
    if accessible_project_ids is None:
        return True
    if not accessible_project_ids:
        return False
    stmt = (
        select(ProjectMember.id)
        .where(
            ProjectMember.person_id == person_id,
            ProjectMember.project_id.in_(accessible_project_ids),
            ProjectMember.is_active.is_(True),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def is_company_readable(
    db: AsyncSession,
    company_id: UUID,
    accessible_project_ids: set[UUID] | None,
) -> bool:
    if accessible_project_ids is None:
        return True
    if not accessible_project_ids:
        return False
    stmt = (
        select(ProjectMember.id)
        .where(
            ProjectMember.company_id == company_id,
            ProjectMember.project_id.in_(accessible_project_ids),
            ProjectMember.is_active.is_(True),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None

async def list_role_templates(db: AsyncSession, *, is_internal: bool | None = None, is_system: bool | None = None, skip: int = 0, limit: int = 100):
    return await _flist(db, RoleTemplate, {"is_internal": is_internal, "is_system": is_system}, skip, limit)

async def list_project_members(db: AsyncSession, *, project_id: UUID | None = None, person_id: UUID | None = None, role_template_id: UUID | None = None, is_active: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(
        db, ProjectMember,
        {"project_id": project_id, "person_id": person_id, "role_template_id": role_template_id, "is_active": is_active},
        skip, limit, accessible_project_ids=accessible_project_ids,
    )

async def list_connector_mappings(db: AsyncSession, *, rex_table: str | None = None, connector: str | None = None, rex_id: UUID | None = None, skip: int = 0, limit: int = 100):
    return await _flist(db, ConnectorMapping, {"rex_table": rex_table, "connector": connector, "rex_id": rex_id}, skip, limit)

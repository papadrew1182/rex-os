"""Identity / RBAC repository helpers.

Thin SQL wrappers so routes and services can resolve RBAC info without
inlining SQL. Accepts an AsyncSession and returns plain dicts / lists.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_permissions(db: AsyncSession, user_account_id: UUID) -> list[str]:
    rows = (await db.execute(
        text(
            """
            SELECT DISTINCT p.slug
            FROM rex.user_roles ur
            JOIN rex.role_permissions rp ON rp.role_id = ur.role_id
            JOIN rex.permissions p ON p.id = rp.permission_id
            WHERE ur.user_account_id = :uid
            ORDER BY p.slug
            """
        ),
        {"uid": user_account_id},
    )).mappings().all()
    return [r["slug"] for r in rows]


async def get_user_roles(db: AsyncSession, user_account_id: UUID) -> list[dict]:
    rows = (await db.execute(
        text(
            """
            SELECT r.id, r.slug, r.display_name, ur.is_primary, ur.granted_at
            FROM rex.user_roles ur
            JOIN rex.roles r ON r.id = ur.role_id
            WHERE ur.user_account_id = :uid
            ORDER BY ur.is_primary DESC, r.sort_order, r.slug
            """
        ),
        {"uid": user_account_id},
    )).mappings().all()
    return [dict(r) for r in rows]


async def resolve_role_alias(db: AsyncSession, alias: str) -> str | None:
    """Return the canonical role slug for a legacy alias, or None."""
    if not alias:
        return None
    row = (await db.execute(
        text(
            """
            SELECT canonical_role_slug
            FROM rex.role_aliases
            WHERE alias = :alias
            LIMIT 1
            """
        ),
        {"alias": alias},
    )).mappings().first()
    return row["canonical_role_slug"] if row else None


__all__ = ["get_user_permissions", "get_user_roles", "resolve_role_alias"]

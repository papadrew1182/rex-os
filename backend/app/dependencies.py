"""FastAPI auth dependencies.

Establishes the reusable pattern for protecting routes:
- get_current_user: resolves bearer token to UserAccount
- require_authenticated_user: 401 if no/invalid session
- require_admin_or_vp: 403 if not admin or global_role=vp
- require_project_access: 403 if not a member of the project (admins/VPs bypass)
- assert_project_access: imperative check used when project_id is not a path param
- assert_project_write: convenience for mutating routes (min_access_level=standard)
- assert_field_write: convenience for field-ops mutating routes (min_access_level=field_only)
- get_readable_project_ids: project-id allowlist for *read* scoping (Sprint G)
- enforce_project_read: imperative read-side gate, 404 to avoid leaking existence
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.foundation import ProjectMember, UserAccount
from app.services.auth import get_user_from_token


# Access level hierarchy (numerically ordered, higher is more privileged).
ACCESS_LEVEL_RANK = {
    "read_only": 1,
    "field_only": 2,
    "standard": 3,
    "admin": 4,
}


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> UserAccount:
    """Resolve a bearer token to an active user. 401 on failure."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await get_user_from_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def require_authenticated_user(
    user: UserAccount = Depends(get_current_user),
) -> UserAccount:
    """Pass-through dependency: any valid authenticated user is allowed."""
    return user


def require_admin_or_vp(
    user: UserAccount = Depends(get_current_user),
) -> UserAccount:
    """Allow admins and global VPs. 403 otherwise."""
    if user.is_admin or user.global_role == "vp":
        return user
    raise HTTPException(status_code=403, detail="Insufficient permissions")


async def assert_project_access(
    db: AsyncSession,
    user: UserAccount,
    project_id: UUID,
    min_access_level: str = "read_only",
) -> None:
    """Raise 403 unless ``user`` has at least ``min_access_level`` on ``project_id``.

    Admins and global VPs always pass. Non-members and members whose access
    level is below the requested minimum are denied with 403.
    """
    if user.is_admin or user.global_role == "vp":
        return

    if user.person_id is None:
        raise HTTPException(status_code=403, detail="No project access")

    required_rank = ACCESS_LEVEL_RANK.get(min_access_level)
    if required_rank is None:
        raise ValueError(f"Unknown access level: {min_access_level}")

    stmt = select(ProjectMember.access_level).where(
        ProjectMember.project_id == project_id,
        ProjectMember.person_id == user.person_id,
        ProjectMember.is_active.is_(True),
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=403, detail="No project access")

    best_rank = max(
        (ACCESS_LEVEL_RANK.get(level, 0) for level in rows),
        default=0,
    )
    if best_rank < required_rank:
        raise HTTPException(status_code=403, detail="Insufficient project access")


def reject_project_id_change(
    data: object,
    existing_project_id: UUID,
) -> None:
    """Raise 422 if the PATCH body attempts to change ``project_id``.

    Construction management records are bound to their project for life.
    A PATCH that tries to move a record to a different project is always
    a client bug, never a legitimate operation.
    """
    new_pid = getattr(data, "project_id", None)
    if new_pid is not None and new_pid != existing_project_id:
        raise HTTPException(
            status_code=422,
            detail="Cannot move resource to a different project",
        )


async def assert_project_write(
    db: AsyncSession,
    user: UserAccount,
    project_id: UUID,
) -> None:
    """Convenience: enforce ``standard`` write access on ``project_id``.

    Allows admin, vp, and project members with access_level ∈ {admin, standard}.
    Denies ``read_only`` and ``field_only``. Use :func:`assert_field_write`
    for field-appropriate routes that should admit ``field_only`` callers.
    """
    await assert_project_access(db, user, project_id, min_access_level="standard")


async def assert_field_write(
    db: AsyncSession,
    user: UserAccount,
    project_id: UUID,
) -> None:
    """Convenience: enforce ``field_only`` write access on ``project_id``.

    Like :func:`assert_project_write` but also admits ``field_only`` members.
    Appropriate for field-ops routes (daily logs, punch items, inspections,
    tasks, meetings, observations, safety incidents, photos).
    """
    await assert_project_access(db, user, project_id, min_access_level="field_only")


def require_project_access(min_access_level: str = "read_only"):
    """Factory: returns a dependency that enforces project access via path ``project_id``.

    Use on routes where ``project_id`` is in the path or query string. For
    routes where the project is derived from another resource, call
    :func:`assert_project_access` directly inside the handler.
    """

    async def _dep(
        project_id: UUID,
        user: UserAccount = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> UserAccount:
        await assert_project_access(db, user, project_id, min_access_level)
        return user

    return _dep


# ── Read-side scoping (Sprint G; per-request cache Sprint I) ─────────────


# Per-request cache key attached to the user object.
_READABLE_IDS_ATTR = "_rex_readable_project_ids"


async def get_readable_project_ids(
    db: AsyncSession,
    user: UserAccount,
) -> set[UUID] | None:
    """Return the set of project IDs ``user`` can read.

    Sentinel: ``None`` means *no filter* — admins and global VPs can read
    everything. An empty set means the user has zero active project
    memberships and should see nothing.

    **Sprint I**: the result is cached on the ``user`` object for the
    duration of the request. Because ``get_current_user`` resolves once
    per request (FastAPI's dependency cache), subsequent calls within the
    same request hit the cached value and skip the DB entirely. The cache
    is never shared across requests.
    """
    cached = getattr(user, _READABLE_IDS_ATTR, _SENTINEL)
    if cached is not _SENTINEL:
        return cached  # type: ignore[return-value]

    if user.is_admin or user.global_role == "vp":
        result_val: set[UUID] | None = None
    elif user.person_id is None:
        result_val = set()
    else:
        stmt = select(ProjectMember.project_id).where(
            ProjectMember.person_id == user.person_id,
            ProjectMember.is_active.is_(True),
        )
        result = await db.execute(stmt)
        result_val = set(result.scalars().all())

    # Cache on the user object — lives only as long as this request's
    # resolved ``user`` instance.
    object.__setattr__(user, _READABLE_IDS_ATTR, result_val)
    return result_val


# Sentinel to distinguish "not cached yet" from a cached ``None`` (admin).
_SENTINEL = object()


async def enforce_project_read(
    db: AsyncSession,
    user: UserAccount,
    project_id: UUID,
) -> None:
    """Raise ``404`` if ``user`` cannot read project ``project_id``.

    We deliberately use 404 (not 403) so the existence of a project is not
    leaked to non-members. Admins and VPs always pass.

    **Sprint I**: uses the per-request cache from :func:`get_readable_project_ids`
    so detail handlers on the same request avoid re-querying the membership set.
    """
    accessible = await get_readable_project_ids(db, user)
    if accessible is None:
        return  # admin/vp bypass
    if project_id in accessible:
        return
    raise HTTPException(status_code=404, detail="Not found")

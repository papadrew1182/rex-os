"""Generic notification service.

Provides:
  - upsert_notification: dedupe-aware insert/update
  - resolve_notifications_by_dedupe: mark stale alerts cleared
  - list_for_user, mark_read, dismiss, mark_all_read
  - fanout_to_project_users: helper for jobs that need project-wide alerts
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foundation import ProjectMember, UserAccount
from app.models.notifications import Notification


async def upsert_notification(
    db: AsyncSession,
    *,
    user_account_id: UUID,
    domain: str,
    notification_type: str,
    title: str,
    body: str | None = None,
    severity: str = "info",
    project_id: UUID | None = None,
    source_type: str | None = None,
    source_id: UUID | None = None,
    action_path: str | None = None,
    dedupe_key: str | None = None,
    metadata: dict | None = None,
) -> Notification:
    """If dedupe_key is set and an unresolved/non-dismissed notification exists
    for (user, dedupe_key), update it in place. Otherwise insert a new one."""
    existing = None
    if dedupe_key is not None:
        stmt = select(Notification).where(
            Notification.user_account_id == user_account_id,
            Notification.dedupe_key == dedupe_key,
            Notification.dismissed_at.is_(None),
            Notification.resolved_at.is_(None),
        ).limit(1)
        existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.title = title
        existing.body = body
        existing.severity = severity
        existing.notification_type = notification_type
        existing.source_type = source_type
        existing.source_id = source_id
        existing.action_path = action_path
        if metadata is not None:
            existing.metadata_json = metadata
        return existing

    notif = Notification(
        user_account_id=user_account_id,
        project_id=project_id,
        domain=domain,
        notification_type=notification_type,
        severity=severity,
        title=title,
        body=body,
        source_type=source_type,
        source_id=source_id,
        action_path=action_path,
        dedupe_key=dedupe_key,
        metadata_json=metadata or {},
    )
    db.add(notif)
    await db.flush()
    return notif


async def resolve_notifications_by_dedupe_prefix(
    db: AsyncSession,
    *,
    dedupe_prefix: str,
    keep_keys: set[str],
) -> int:
    """Resolve any unresolved notifications whose dedupe_key starts with prefix
    but is not in the keep set. Used by jobs to clear stale alerts."""
    stmt = select(Notification).where(
        Notification.dedupe_key.like(f"{dedupe_prefix}%"),
        Notification.resolved_at.is_(None),
        Notification.dismissed_at.is_(None),
    )
    rows = (await db.execute(stmt)).scalars().all()
    cleared = 0
    now = datetime.now(timezone.utc)
    for n in rows:
        if n.dedupe_key not in keep_keys:
            n.resolved_at = now
            cleared += 1
    return cleared


async def get_admin_and_vp_user_ids(db: AsyncSession) -> list[UUID]:
    stmt = select(UserAccount.id).where(
        UserAccount.is_active == True,  # noqa: E712
        ((UserAccount.is_admin == True) | (UserAccount.global_role == "vp")),  # noqa: E712
    )
    return [r[0] for r in (await db.execute(stmt)).all()]


async def get_project_user_ids(db: AsyncSession, project_id: UUID) -> list[UUID]:
    """Return user_account_ids for users who can read this project.
    Includes admins, VPs, and active project members."""
    # Active project members -> people -> user_accounts
    member_stmt = (
        select(UserAccount.id)
        .join(UserAccount.person)
        .join(ProjectMember, ProjectMember.person_id == UserAccount.person_id)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.is_active == True,  # noqa: E712
            UserAccount.is_active == True,  # noqa: E712
        )
    )
    member_ids = {r[0] for r in (await db.execute(member_stmt)).all()}
    admin_ids = set(await get_admin_and_vp_user_ids(db))
    return list(member_ids | admin_ids)


# ── User-facing query helpers ─────────────────────────────────────────────

async def list_for_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    unread_only: bool = False,
    domain: str | None = None,
    project_id: UUID | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.user_account_id == user_id,
        Notification.dismissed_at.is_(None),
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if domain:
        stmt = stmt.where(Notification.domain == domain)
    if project_id:
        stmt = stmt.where(Notification.project_id == project_id)
    if severity:
        stmt = stmt.where(Notification.severity == severity)
    stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def unread_count_for_user(db: AsyncSession, user_id: UUID) -> int:
    from sqlalchemy import func
    stmt = select(func.count(Notification.id)).where(
        Notification.user_account_id == user_id,
        Notification.read_at.is_(None),
        Notification.dismissed_at.is_(None),
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def mark_read(db: AsyncSession, user_id: UUID, notification_id: UUID) -> bool:
    stmt = update(Notification).where(
        Notification.id == notification_id,
        Notification.user_account_id == user_id,
    ).values(read_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def dismiss(db: AsyncSession, user_id: UUID, notification_id: UUID) -> bool:
    stmt = update(Notification).where(
        Notification.id == notification_id,
        Notification.user_account_id == user_id,
    ).values(dismissed_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession, user_id: UUID) -> int:
    stmt = update(Notification).where(
        Notification.user_account_id == user_id,
        Notification.read_at.is_(None),
        Notification.dismissed_at.is_(None),
    ).values(read_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False)
    result = await db.execute(stmt)
    return result.rowcount

"""Refresh warranty statuses + create user notifications."""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import register_job
from app.models.closeout import Warranty
from app.services.notifications import (
    get_admin_and_vp_user_ids,
    get_project_user_ids,
    resolve_notifications_by_dedupe_prefix,
    upsert_notification,
)


def _new_status(w: Warranty, today: date) -> str:
    if w.status == "claimed":
        return "claimed"
    if w.expiration_date and w.expiration_date < today:
        return "expired"
    if w.expiration_date and (w.expiration_date - today).days <= 90:
        return "expiring_soon"
    return "active"


@register_job(
    job_key="warranty_refresh",
    name="Warranty status refresh",
    description="Recompute warranty statuses and emit expiry notifications.",
    cron="0 6 * * *",  # daily 06:00 UTC
)
async def warranty_refresh_job(db: AsyncSession) -> str:
    today = date.today()
    rows = (await db.execute(select(Warranty))).scalars().all()

    updated_status = 0
    notif_created = 0
    keep_keys: set[str] = set()

    for w in rows:
        new_st = _new_status(w, today)
        if w.status != new_st:
            w.status = new_st
            updated_status += 1

        if not w.expiration_date:
            continue
        days = (w.expiration_date - today).days

        # Determine which alert tier applies, if any
        tier = None
        severity = "info"
        if days < 0:
            tier = "expired"; severity = "critical"
        elif days <= 30:
            tier = "30_day"; severity = "warning"
        elif days <= 90:
            tier = "90_day"; severity = "info"

        if tier is None:
            continue

        # Recipients: project members + admins/VPs
        recipients = await get_project_user_ids(db, w.project_id)
        title_text = (
            f"Warranty expired: {w.scope_description}" if tier == "expired"
            else f"Warranty expiring in {days}d: {w.scope_description}"
        )
        body_text = (
            f"{w.system_or_product or w.warranty_type} warranty expires {w.expiration_date.isoformat()}"
        )

        for user_id in recipients:
            dedupe = f"warranty:{w.id}:{tier}"
            keep_keys.add(dedupe)
            await upsert_notification(
                db,
                user_account_id=user_id,
                project_id=w.project_id,
                domain="closeout",
                notification_type="warranty_expiry",
                severity=severity,
                title=title_text,
                body=body_text,
                source_type="warranty",
                source_id=w.id,
                action_path=f"/#/warranties?status=expired" if tier == "expired" else "/#/warranties?status=expiring_soon",
                dedupe_key=dedupe,
            )
            notif_created += 1

    # Resolve any stale warranty notifications that no longer match
    cleared = await resolve_notifications_by_dedupe_prefix(
        db, dedupe_prefix="warranty:", keep_keys=keep_keys,
    )

    return f"warranties={len(rows)} status_updated={updated_status} notifications={notif_created} cleared={cleared}"

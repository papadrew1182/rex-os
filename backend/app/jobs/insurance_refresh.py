"""Refresh insurance certificate statuses + create user notifications."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import register_job
from app.models.foundation import InsuranceCertificate
from app.services.notifications import (
    get_admin_and_vp_user_ids,
    resolve_notifications_by_dedupe_prefix,
    upsert_notification,
)


def _new_status(c: InsuranceCertificate, today: date) -> str:
    if c.expiry_date is None:
        return "missing"
    if c.expiry_date < today:
        return "expired"
    if (c.expiry_date - today).days <= 60:
        return "expiring_soon"
    return "current"


@register_job(
    job_key="insurance_refresh",
    name="Insurance certificate refresh",
    description="Recompute insurance statuses and emit expiry notifications.",
    cron="15 6 * * *",  # daily 06:15 UTC
)
async def insurance_refresh_job(db: AsyncSession) -> str:
    today = date.today()
    certs = (await db.execute(select(InsuranceCertificate))).scalars().all()

    updated_status = 0
    notif_created = 0
    keep_keys: set[str] = set()

    # Insurance is global to companies; recipients = admin/VP only
    recipients = await get_admin_and_vp_user_ids(db)

    for c in certs:
        new_st = _new_status(c, today)
        if c.status != new_st:
            c.status = new_st
            updated_status += 1

        if c.expiry_date is None:
            continue
        days = (c.expiry_date - today).days
        tier = None
        severity = "info"
        if days < 0:
            tier = "expired"; severity = "critical"
        elif days <= 30:
            tier = "30_day"; severity = "critical"
        elif days <= 60:
            tier = "60_day"; severity = "warning"
        elif days <= 90:
            tier = "90_day"; severity = "info"

        if tier is None:
            continue

        title = (
            f"Insurance expired: {c.policy_type.upper()}" if tier == "expired"
            else f"Insurance {c.policy_type.upper()} expiring in {days}d"
        )
        body = f"Carrier {c.carrier or '—'} · policy {c.policy_number or '—'} · expires {c.expiry_date.isoformat()}"

        for user_id in recipients:
            dedupe = f"insurance:{c.id}:{tier}"
            keep_keys.add(dedupe)
            await upsert_notification(
                db,
                user_account_id=user_id,
                project_id=None,
                domain="foundation",
                notification_type="insurance_expiry",
                severity=severity,
                title=title,
                body=body,
                source_type="insurance_certificate",
                source_id=c.id,
                action_path="/#/insurance",
                dedupe_key=dedupe,
            )
            notif_created += 1

    cleared = await resolve_notifications_by_dedupe_prefix(
        db, dedupe_prefix="insurance:", keep_keys=keep_keys,
    )
    return f"certs={len(certs)} status_updated={updated_status} notifications={notif_created} cleared={cleared}"

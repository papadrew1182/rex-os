"""Snapshot active schedules + emit drift notifications."""

import os
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import register_job
from app.models.schedule import Schedule, ScheduleActivity, ScheduleSnapshot
from app.services.notifications import (
    get_project_user_ids,
    resolve_notifications_by_dedupe_prefix,
    upsert_notification,
)

CRITICAL_DRIFT_THRESHOLD = int(os.getenv("REX_DRIFT_CRITICAL_DAYS", "5"))
NEAR_CRITICAL_DRIFT_THRESHOLD = int(os.getenv("REX_DRIFT_WARNING_DAYS", "2"))


@register_job(
    job_key="schedule_snapshot",
    name="Schedule snapshot + drift",
    description="Snapshot active schedules and emit drift alerts.",
    cron="30 6 * * *",  # daily 06:30 UTC
)
async def schedule_snapshot_job(db: AsyncSession) -> str:
    today = date.today()

    schedules = (await db.execute(select(Schedule).where(Schedule.status == "active"))).scalars().all()
    activity_count = 0
    snapshot_count = 0
    notif_count = 0
    keep_keys: set[str] = set()

    for sched in schedules:
        activities = (
            await db.execute(select(ScheduleActivity).where(ScheduleActivity.schedule_id == sched.id))
        ).scalars().all()
        activity_count += len(activities)

        # Snapshot each activity (idempotent: skip if already exists for today)
        for a in activities:
            existing = await db.execute(
                select(ScheduleSnapshot).where(
                    ScheduleSnapshot.activity_id == a.id,
                    ScheduleSnapshot.snapshot_date == today,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            snap = ScheduleSnapshot(
                activity_id=a.id,
                snapshot_date=today,
                start_date=a.start_date,
                end_date=a.end_date,
                percent_complete=a.percent_complete or 0,
                is_critical=a.is_critical,
                variance_days=a.variance_days,
            )
            db.add(snap)
            snapshot_count += 1

        # Compute drift on critical activities
        critical = [a for a in activities if a.is_critical]
        worst_drift = max(((a.variance_days or 0) for a in critical), default=0)
        if worst_drift >= CRITICAL_DRIFT_THRESHOLD:
            severity = "critical"
            tier = "critical_drift"
        elif worst_drift >= NEAR_CRITICAL_DRIFT_THRESHOLD:
            severity = "warning"
            tier = "warning_drift"
        else:
            continue

        recipients = await get_project_user_ids(db, sched.project_id)
        for user_id in recipients:
            dedupe = f"schedule_drift:{sched.id}:{tier}"
            keep_keys.add(dedupe)
            await upsert_notification(
                db,
                user_account_id=user_id,
                project_id=sched.project_id,
                domain="schedule",
                notification_type="schedule_drift",
                severity=severity,
                title=f"Critical path drift: +{worst_drift}d",
                body=f"Schedule '{sched.name}' has worst critical drift of {worst_drift}d.",
                source_type="schedule",
                source_id=sched.id,
                action_path="/#/schedule",
                dedupe_key=dedupe,
            )
            notif_count += 1

    cleared = await resolve_notifications_by_dedupe_prefix(
        db, dedupe_prefix="schedule_drift:", keep_keys=keep_keys,
    )
    return f"schedules={len(schedules)} activities={activity_count} snapshots={snapshot_count} notifications={notif_count} cleared={cleared}"

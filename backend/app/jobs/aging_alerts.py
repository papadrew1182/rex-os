"""Project-level aging summaries for RFIs/Submittals/Punch Items."""

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import register_job
from app.models.document_management import Rfi, Submittal
from app.models.field_ops import PunchItem
from app.models.foundation import Project
from app.services.notifications import (
    get_project_user_ids,
    resolve_notifications_by_dedupe_prefix,
    upsert_notification,
)

AGING_THRESHOLD_DAYS = 21


@register_job(
    job_key="aging_alerts",
    name="Aging RFI/Submittal/Punch summaries",
    description="Project-level summaries of overdue RFIs, submittals, and punch items.",
    cron="45 6 * * *",  # daily 06:45 UTC
)
async def aging_alerts_job(db: AsyncSession) -> str:
    today = date.today()

    projects = (await db.execute(select(Project))).scalars().all()
    notif_count = 0
    keep_keys: set[str] = set()

    for p in projects:
        # RFIs: open + overdue (due_date < today)
        rfis = (await db.execute(
            select(Rfi).where(
                Rfi.project_id == p.id,
                Rfi.status.in_(["draft", "open"]),
            )
        )).scalars().all()
        overdue_rfis = [r for r in rfis if r.due_date and r.due_date < today]

        # Submittals: open + overdue
        subs = (await db.execute(
            select(Submittal).where(
                Submittal.project_id == p.id,
                Submittal.status.in_(["draft", "pending", "submitted"]),
            )
        )).scalars().all()
        overdue_subs = [s for s in subs if s.due_date and s.due_date < today]

        # Punch items: open + aged > threshold
        punches = (await db.execute(
            select(PunchItem).where(
                PunchItem.project_id == p.id,
                PunchItem.status != "closed",
            )
        )).scalars().all()
        aged_punches = []
        for pt in punches:
            if pt.created_at:
                age = (datetime.now(timezone.utc) - pt.created_at).days
                if age >= AGING_THRESHOLD_DAYS:
                    aged_punches.append(pt)

        # If nothing aging, skip emitting (the resolve step will clear stale)
        if not (overdue_rfis or overdue_subs or aged_punches):
            continue

        recipients = await get_project_user_ids(db, p.id)

        # RFI aging summary
        if overdue_rfis:
            for user_id in recipients:
                dedupe = f"aging:rfi:{p.id}"
                keep_keys.add(dedupe)
                await upsert_notification(
                    db,
                    user_account_id=user_id,
                    project_id=p.id,
                    domain="field_ops",
                    notification_type="aging_summary_rfi",
                    severity="warning",
                    title=f"{len(overdue_rfis)} overdue RFI{'s' if len(overdue_rfis) != 1 else ''}: {p.name}",
                    body=f"{len(overdue_rfis)} RFI{'s' if len(overdue_rfis) != 1 else ''} past due_date",
                    source_type="project",
                    source_id=p.id,
                    action_path="/#/rfis?status=open",
                    dedupe_key=dedupe,
                    metadata={"overdue_rfi_count": len(overdue_rfis)},
                )
                notif_count += 1

        # Submittal aging summary
        if overdue_subs:
            for user_id in recipients:
                dedupe = f"aging:submittal:{p.id}"
                keep_keys.add(dedupe)
                await upsert_notification(
                    db,
                    user_account_id=user_id,
                    project_id=p.id,
                    domain="field_ops",
                    notification_type="aging_summary_submittal",
                    severity="warning",
                    title=f"{len(overdue_subs)} overdue submittal{'s' if len(overdue_subs) != 1 else ''}: {p.name}",
                    body=f"{len(overdue_subs)} submittal{'s' if len(overdue_subs) != 1 else ''} past due_date",
                    source_type="project",
                    source_id=p.id,
                    action_path="/#/submittals?status=submitted",
                    dedupe_key=dedupe,
                    metadata={"overdue_submittal_count": len(overdue_subs)},
                )
                notif_count += 1

        # Punch aging summary
        if aged_punches:
            for user_id in recipients:
                dedupe = f"aging:punch:{p.id}"
                keep_keys.add(dedupe)
                await upsert_notification(
                    db,
                    user_account_id=user_id,
                    project_id=p.id,
                    domain="field_ops",
                    notification_type="aging_summary_punch",
                    severity="info",
                    title=f"{len(aged_punches)} aged punch item{'s' if len(aged_punches) != 1 else ''}: {p.name}",
                    body=f"{len(aged_punches)} punch item{'s' if len(aged_punches) != 1 else ''} open over {AGING_THRESHOLD_DAYS} days",
                    source_type="project",
                    source_id=p.id,
                    action_path="/#/punch-list?status=open",
                    dedupe_key=dedupe,
                    metadata={"aged_punch_count": len(aged_punches)},
                )
                notif_count += 1

    cleared = await resolve_notifications_by_dedupe_prefix(
        db, dedupe_prefix="aging:", keep_keys=keep_keys,
    )
    return f"projects={len(projects)} notifications={notif_count} cleared={cleared}"

"""Schedule domain service layer.

Provides filtered list queries for Schedule tables plus re-exports
shared CRUD helpers, plus drift and project-level health summaries.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import (
    ActivityLink,
    Schedule,
    ScheduleActivity,
    ScheduleConstraint,
    ScheduleSnapshot,
)
from app.services.crud import create, get_by_id, update  # noqa: F401


async def list_schedules(
    db: AsyncSession,
    *,
    project_id: UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    accessible_project_ids: set[UUID] | None = None,
) -> list[Schedule]:
    stmt = select(Schedule)
    if project_id:
        stmt = stmt.where(Schedule.project_id == project_id)
    if status:
        stmt = stmt.where(Schedule.status == status)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.where(Schedule.project_id.in_(accessible_project_ids))
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def list_activities(
    db: AsyncSession,
    *,
    schedule_id: UUID | None = None,
    parent_id: UUID | None = None,
    activity_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
    accessible_project_ids: set[UUID] | None = None,
) -> list[ScheduleActivity]:
    stmt = select(ScheduleActivity)
    if schedule_id:
        stmt = stmt.where(ScheduleActivity.schedule_id == schedule_id)
    if parent_id:
        stmt = stmt.where(ScheduleActivity.parent_id == parent_id)
    if activity_type:
        stmt = stmt.where(ScheduleActivity.activity_type == activity_type)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        # ScheduleActivity has no direct project_id; scope via Schedule join.
        stmt = stmt.join(Schedule, ScheduleActivity.schedule_id == Schedule.id).where(
            Schedule.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def list_activity_links(
    db: AsyncSession,
    *,
    schedule_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    accessible_project_ids: set[UUID] | None = None,
) -> list[ActivityLink]:
    stmt = select(ActivityLink)
    if schedule_id:
        stmt = stmt.where(ActivityLink.schedule_id == schedule_id)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(Schedule, ActivityLink.schedule_id == Schedule.id).where(
            Schedule.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def list_constraints(
    db: AsyncSession,
    *,
    activity_id: UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    accessible_project_ids: set[UUID] | None = None,
) -> list[ScheduleConstraint]:
    """Scoped via Activity → Schedule → project_id."""
    stmt = select(ScheduleConstraint)
    if activity_id:
        stmt = stmt.where(ScheduleConstraint.activity_id == activity_id)
    if status:
        stmt = stmt.where(ScheduleConstraint.status == status)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = (
            stmt.join(ScheduleActivity, ScheduleConstraint.activity_id == ScheduleActivity.id)
            .join(Schedule, ScheduleActivity.schedule_id == Schedule.id)
            .where(Schedule.project_id.in_(accessible_project_ids))
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def list_snapshots(
    db: AsyncSession,
    *,
    activity_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    accessible_project_ids: set[UUID] | None = None,
) -> list[ScheduleSnapshot]:
    """Scoped via Activity → Schedule → project_id."""
    stmt = select(ScheduleSnapshot)
    if activity_id:
        stmt = stmt.where(ScheduleSnapshot.activity_id == activity_id)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = (
            stmt.join(ScheduleActivity, ScheduleSnapshot.activity_id == ScheduleActivity.id)
            .join(Schedule, ScheduleActivity.schedule_id == Schedule.id)
            .where(Schedule.project_id.in_(accessible_project_ids))
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


# ── Schedule drift summary ──────────────────────────────────────────────────

async def get_schedule_drift_summary(db: AsyncSession, schedule_id: UUID) -> dict:
    """Aggregate drift metrics for a single schedule.

    Read-only. Uses stored variance_days, is_critical, percent_complete on activities;
    counts active constraints by severity; reports snapshot coverage.
    """
    schedule = await db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Activities
    act_result = await db.execute(
        select(ScheduleActivity).where(ScheduleActivity.schedule_id == schedule_id)
    )
    activities = list(act_result.scalars().all())

    total = len(activities)
    critical = [a for a in activities if a.is_critical]
    completed = [a for a in activities if float(a.percent_complete or 0) >= 100]
    with_variance = [a for a in activities if a.variance_days is not None]
    positive_variance = [a for a in with_variance if a.variance_days > 0]
    negative_variance = [a for a in with_variance if a.variance_days < 0]

    variance_values = [a.variance_days for a in with_variance]
    avg_variance = round(sum(variance_values) / len(variance_values), 2) if variance_values else 0

    worst = None
    if with_variance:
        worst_act = max(with_variance, key=lambda a: a.variance_days)
        worst = {
            "activity_id": worst_act.id,
            "name": worst_act.name,
            "variance_days": worst_act.variance_days,
        }

    # Snapshots — count distinct activity_id coverage
    activity_ids = [a.id for a in activities]
    if activity_ids:
        snap_result = await db.execute(
            select(func.count(func.distinct(ScheduleSnapshot.activity_id)))
            .where(ScheduleSnapshot.activity_id.in_(activity_ids))
        )
        snapshot_coverage = snap_result.scalar() or 0
    else:
        snapshot_coverage = 0

    # Constraints — by severity, only active ones
    if activity_ids:
        constraint_result = await db.execute(
            select(ScheduleConstraint).where(
                ScheduleConstraint.activity_id.in_(activity_ids),
                ScheduleConstraint.status == "active",
            )
        )
        constraints = list(constraint_result.scalars().all())
    else:
        constraints = []

    by_severity: dict[str, int] = {"green": 0, "yellow": 0, "red": 0}
    for c in constraints:
        by_severity[c.severity] = by_severity.get(c.severity, 0) + 1

    return {
        "schedule_id": schedule.id,
        "project_id": schedule.project_id,
        "schedule_name": schedule.name,
        "schedule_type": schedule.schedule_type,
        "status": schedule.status,
        "total_activities": total,
        "critical_count": len(critical),
        "completed_count": len(completed),
        "positive_variance_count": len(positive_variance),
        "negative_variance_count": len(negative_variance),
        "average_variance_days": avg_variance,
        "worst_variance_activity": worst,
        "snapshot_coverage_count": snapshot_coverage,
        "active_constraint_count": len(constraints),
        "constraints_by_severity": by_severity,
    }


async def get_project_schedule_health_summary(db: AsyncSession, project_id: UUID) -> dict:
    """Aggregate schedule health across all schedules on a project."""
    result = await db.execute(
        select(Schedule).where(Schedule.project_id == project_id)
    )
    schedules = list(result.scalars().all())

    schedule_summaries = []
    total_activities = 0
    total_critical = 0
    total_completed = 0
    total_constraints = 0
    severity_totals: dict[str, int] = {"green": 0, "yellow": 0, "red": 0}
    all_variance: list[int] = []

    for s in schedules:
        summary = await get_schedule_drift_summary(db, s.id)
        schedule_summaries.append(summary)
        total_activities += summary["total_activities"]
        total_critical += summary["critical_count"]
        total_completed += summary["completed_count"]
        total_constraints += summary["active_constraint_count"]
        for sev, n in summary["constraints_by_severity"].items():
            severity_totals[sev] = severity_totals.get(sev, 0) + n

    # Compute project-wide average variance from per-schedule values
    schedules_with_variance = [s for s in schedule_summaries
                               if s["positive_variance_count"] + s["negative_variance_count"] > 0]
    if schedules_with_variance:
        avg = sum(s["average_variance_days"] for s in schedules_with_variance) / len(schedules_with_variance)
        project_avg_variance = round(avg, 2)
    else:
        project_avg_variance = 0

    # Health rollup
    if not schedules:
        health_status = "not_started"
    elif severity_totals["red"] > 0 or any(s["positive_variance_count"] > 0 for s in schedule_summaries) and project_avg_variance > 14:
        health_status = "fail"
    elif severity_totals["yellow"] > 0 or project_avg_variance > 0:
        health_status = "warning"
    else:
        health_status = "pass"

    return {
        "project_id": project_id,
        "schedule_count": len(schedules),
        "total_activities": total_activities,
        "critical_count": total_critical,
        "completed_count": total_completed,
        "active_constraint_count": total_constraints,
        "constraints_by_severity": severity_totals,
        "project_average_variance_days": project_avg_variance,
        "health_status": health_status,
        "schedules": schedule_summaries,
    }

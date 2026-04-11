"""Field Ops domain service layer.

Provides filtered list queries for all 12 Field Ops tables
plus re-exports shared CRUD helpers.
"""

from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field_ops import (
    DailyLog, ManpowerEntry, PunchItem, Inspection, InspectionItem,
    Observation, SafetyIncident, PhotoAlbum, Photo, Task, Meeting, MeetingActionItem,
)
from app.services.crud import _classify_integrity_error, create, get_by_id, update  # noqa: F401

_PUNCH_CLOSED_STATUSES = {"closed"}


def _apply(stmt, model, col: str, val):
    if val is not None:
        return stmt.where(getattr(model, col) == val)
    return stmt


async def _filtered_list(
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
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def _filtered_list_join_parent(
    db: AsyncSession,
    model,
    parent_model,
    join_on,
    filters: dict,
    skip: int,
    limit: int,
    *,
    accessible_project_ids: set[UUID] | None,
):
    """List ``model`` rows scoped via a parent model that carries ``project_id``.

    Used for child collections like ``inspection_items`` (parent=Inspection),
    ``manpower_entries`` (parent=DailyLog), ``meeting_action_items`` (parent=Meeting).
    """
    stmt = select(model)
    for col, val in filters.items():
        stmt = _apply(stmt, model, col, val)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(parent_model, join_on).where(
            parent_model.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def list_daily_logs(db: AsyncSession, *, project_id: UUID | None = None, log_date: date | None = None, status: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, DailyLog, {"project_id": project_id, "log_date": log_date, "status": status}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_manpower_entries(db: AsyncSession, *, daily_log_id: UUID | None = None, company_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list_join_parent(
        db, ManpowerEntry, DailyLog, ManpowerEntry.daily_log_id == DailyLog.id,
        {"daily_log_id": daily_log_id, "company_id": company_id},
        skip, limit, accessible_project_ids=accessible_project_ids,
    )


async def list_punch_items(db: AsyncSession, *, project_id: UUID | None = None, status: str | None = None, priority: str | None = None, assigned_company_id: UUID | None = None, assigned_to: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, PunchItem, {"project_id": project_id, "status": status, "priority": priority, "assigned_company_id": assigned_company_id, "assigned_to": assigned_to}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_inspections(db: AsyncSession, *, project_id: UUID | None = None, inspection_type: str | None = None, status: str | None = None, activity_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, Inspection, {"project_id": project_id, "inspection_type": inspection_type, "status": status, "activity_id": activity_id}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_inspection_items(db: AsyncSession, *, inspection_id: UUID | None = None, result: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list_join_parent(
        db, InspectionItem, Inspection, InspectionItem.inspection_id == Inspection.id,
        {"inspection_id": inspection_id, "result": result},
        skip, limit, accessible_project_ids=accessible_project_ids,
    )


async def list_observations(db: AsyncSession, *, project_id: UUID | None = None, observation_type: str | None = None, status: str | None = None, priority: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, Observation, {"project_id": project_id, "observation_type": observation_type, "status": status, "priority": priority}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_safety_incidents(db: AsyncSession, *, project_id: UUID | None = None, incident_type: str | None = None, status: str | None = None, severity: str | None = None, is_osha_recordable: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, SafetyIncident, {"project_id": project_id, "incident_type": incident_type, "status": status, "severity": severity, "is_osha_recordable": is_osha_recordable}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_photo_albums(db: AsyncSession, *, project_id: UUID | None = None, is_default: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, PhotoAlbum, {"project_id": project_id, "is_default": is_default}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_photos(db: AsyncSession, *, project_id: UUID | None = None, photo_album_id: UUID | None = None, source_type: str | None = None, source_id: UUID | None = None, uploaded_by: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, Photo, {"project_id": project_id, "photo_album_id": photo_album_id, "source_type": source_type, "source_id": source_id, "uploaded_by": uploaded_by}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_tasks(db: AsyncSession, *, project_id: UUID | None = None, status: str | None = None, priority: str | None = None, category: str | None = None, assigned_to: UUID | None = None, assigned_company_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, Task, {"project_id": project_id, "status": status, "priority": priority, "category": category, "assigned_to": assigned_to, "assigned_company_id": assigned_company_id}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_meetings(db: AsyncSession, *, project_id: UUID | None = None, meeting_type: str | None = None, meeting_date: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list(db, Meeting, {"project_id": project_id, "meeting_type": meeting_type, "meeting_date": meeting_date}, skip, limit, accessible_project_ids=accessible_project_ids)


async def list_meeting_action_items(db: AsyncSession, *, meeting_id: UUID | None = None, status: str | None = None, assigned_to: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _filtered_list_join_parent(
        db, MeetingActionItem, Meeting, MeetingActionItem.meeting_id == Meeting.id,
        {"meeting_id": meeting_id, "status": status, "assigned_to": assigned_to},
        skip, limit, accessible_project_ids=accessible_project_ids,
    )


# ── Punch aging helpers ─────────────────────────────────────────────────────

def compute_punch_days_open(punch: PunchItem, today: date | None = None) -> int | None:
    """Compute days_open for a punch item from created_at to closed_date or today.

    Returns None only if created_at is missing.
    Always non-None for any real punch row.
    """
    if punch.created_at is None:
        return None
    if today is None:
        today = date.today()
    created_d = punch.created_at.date()

    if punch.status in _PUNCH_CLOSED_STATUSES and punch.closed_date:
        end_d = punch.closed_date
    else:
        end_d = today

    return max(0, (end_d - created_d).days)


async def refresh_punch_days_open(db: AsyncSession, punch_id: UUID) -> PunchItem:
    """Recompute and persist days_open for a single punch item."""
    punch = await db.get(PunchItem, punch_id)
    if punch is None:
        raise HTTPException(status_code=404, detail="Punch item not found")

    new_value = compute_punch_days_open(punch)
    if new_value != punch.days_open:
        punch.days_open = new_value
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise _classify_integrity_error(e)
        await db.refresh(punch)
    return punch


async def refresh_punch_days_open_for_project(db: AsyncSession, project_id: UUID) -> dict:
    """Bulk-refresh days_open for all punch items on a project."""
    result = await db.execute(select(PunchItem).where(PunchItem.project_id == project_id))
    punches = list(result.scalars().all())
    today = date.today()
    updated = 0
    for p in punches:
        new_value = compute_punch_days_open(p, today)
        if new_value != p.days_open:
            p.days_open = new_value
            updated += 1
    if updated:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise _classify_integrity_error(e)
    return {
        "project_id": project_id,
        "total_punch_items": len(punches),
        "updated_count": updated,
    }


# ── Daily log + manpower summary helpers ────────────────────────────────────

async def get_daily_log_summary(db: AsyncSession, daily_log_id: UUID) -> dict:
    """Aggregate manpower metrics for a single daily log."""
    log = await db.get(DailyLog, daily_log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Daily log not found")

    result = await db.execute(
        select(ManpowerEntry).where(ManpowerEntry.daily_log_id == daily_log_id)
    )
    entries = list(result.scalars().all())

    total_workers = sum(e.worker_count or 0 for e in entries)
    total_hours = sum(float(e.hours or 0) for e in entries)
    company_count = len({e.company_id for e in entries})

    return {
        "daily_log_id": log.id,
        "project_id": log.project_id,
        "log_date": log.log_date,
        "status": log.status,
        "weather_summary": log.weather_summary,
        "is_weather_delay": log.is_weather_delay,
        "manpower_entry_count": len(entries),
        "total_worker_count": total_workers,
        "total_hours": total_hours,
        "company_count": company_count,
    }


async def get_project_manpower_summary(
    db: AsyncSession,
    project_id: UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Aggregate manpower across daily logs on a project, optionally date-filtered."""
    stmt = select(DailyLog).where(DailyLog.project_id == project_id)
    if date_from:
        stmt = stmt.where(DailyLog.log_date >= date_from)
    if date_to:
        stmt = stmt.where(DailyLog.log_date <= date_to)

    log_result = await db.execute(stmt)
    logs = list(log_result.scalars().all())
    log_ids = [log.id for log in logs]

    if log_ids:
        entry_result = await db.execute(
            select(ManpowerEntry).where(ManpowerEntry.daily_log_id.in_(log_ids))
        )
        entries = list(entry_result.scalars().all())
    else:
        entries = []

    total_workers = sum(e.worker_count or 0 for e in entries)
    total_hours = sum(float(e.hours or 0) for e in entries)

    # Per-company rollup
    by_company: dict[str, dict] = {}
    for e in entries:
        cid = str(e.company_id)
        if cid not in by_company:
            by_company[cid] = {"company_id": e.company_id, "worker_count": 0, "hours": 0.0, "entry_count": 0}
        by_company[cid]["worker_count"] += e.worker_count or 0
        by_company[cid]["hours"] += float(e.hours or 0)
        by_company[cid]["entry_count"] += 1

    # Average workers per log (only logs that had entries)
    logs_with_entries = {e.daily_log_id for e in entries}
    avg_workers_per_log = (
        round(total_workers / len(logs_with_entries), 2) if logs_with_entries else 0
    )

    return {
        "project_id": project_id,
        "date_from": date_from,
        "date_to": date_to,
        "total_logs": len(logs),
        "logs_with_manpower": len(logs_with_entries),
        "total_entries": len(entries),
        "total_worker_count": total_workers,
        "total_hours": total_hours,
        "average_workers_per_log": avg_workers_per_log,
        "by_company": list(by_company.values()),
    }


# ── Inspection summary helper ───────────────────────────────────────────────

async def get_project_execution_health(db: AsyncSession, project_id: UUID) -> dict:
    """Cross-domain execution snapshot: schedule health + field ops counts.

    Read-only. Combines schedule drift, manpower totals, open inspections,
    open punch items, and task counts by status into one project-level view.
    """
    from app.services.schedule import get_project_schedule_health_summary

    # Schedule health (reuses other helper)
    schedule_health = await get_project_schedule_health_summary(db, project_id)

    # Manpower snapshot (no date filter — lifetime totals)
    manpower = await get_project_manpower_summary(db, project_id)

    # Open inspections + failed item count
    insp_result = await db.execute(
        select(Inspection).where(Inspection.project_id == project_id)
    )
    inspections = list(insp_result.scalars().all())
    open_inspections = [i for i in inspections if i.status not in ("passed", "cancelled")]
    if inspections:
        item_result = await db.execute(
            select(InspectionItem)
            .join(Inspection, InspectionItem.inspection_id == Inspection.id)
            .where(Inspection.project_id == project_id, InspectionItem.result == "fail")
        )
        failed_items = list(item_result.scalars().all())
    else:
        failed_items = []

    # Open punch items
    punch_result = await db.execute(
        select(PunchItem).where(PunchItem.project_id == project_id)
    )
    all_punch = list(punch_result.scalars().all())
    open_punch = [p for p in all_punch if p.status != "closed"]

    # Tasks by status
    task_result = await db.execute(
        select(Task).where(Task.project_id == project_id)
    )
    tasks = list(task_result.scalars().all())
    tasks_by_status: dict[str, int] = {}
    for t in tasks:
        tasks_by_status[t.status] = tasks_by_status.get(t.status, 0) + 1

    return {
        "project_id": project_id,
        "schedule_health_status": schedule_health["health_status"],
        "schedule_active_constraints": schedule_health["active_constraint_count"],
        "schedule_constraints_by_severity": schedule_health["constraints_by_severity"],
        "manpower": {
            "total_logs": manpower["total_logs"],
            "total_worker_count": manpower["total_worker_count"],
            "total_hours": manpower["total_hours"],
            "average_workers_per_log": manpower["average_workers_per_log"],
        },
        "inspections": {
            "total": len(inspections),
            "open_count": len(open_inspections),
            "failed_item_count": len(failed_items),
        },
        "punch": {
            "total": len(all_punch),
            "open_count": len(open_punch),
        },
        "tasks_by_status": tasks_by_status,
    }


async def get_inspection_summary(db: AsyncSession, inspection_id: UUID) -> dict:
    """Aggregate inspection item results and linked punch item visibility."""
    inspection = await db.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found")

    result = await db.execute(
        select(InspectionItem).where(InspectionItem.inspection_id == inspection_id)
    )
    items = list(result.scalars().all())

    by_result: dict[str, int] = {"pass": 0, "fail": 0, "n_a": 0, "not_inspected": 0}
    for it in items:
        by_result[it.result] = by_result.get(it.result, 0) + 1

    failed_items = [it for it in items if it.result == "fail"]
    linked_punch_ids = [it.punch_item_id for it in items if it.punch_item_id is not None]
    failed_unlinked = [it for it in failed_items if it.punch_item_id is None]

    return {
        "inspection_id": inspection.id,
        "project_id": inspection.project_id,
        "inspection_number": inspection.inspection_number,
        "title": inspection.title,
        "inspection_type": inspection.inspection_type,
        "status": inspection.status,
        "scheduled_date": inspection.scheduled_date,
        "completed_date": inspection.completed_date,
        "total_items": len(items),
        "items_by_result": by_result,
        "failed_count": len(failed_items),
        "linked_punch_count": len(linked_punch_ids),
        "linked_punch_item_ids": linked_punch_ids,
        "has_unresolved_failures": len(failed_unlinked) > 0,
    }

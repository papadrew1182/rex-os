"""Document Management domain service layer."""

from datetime import date, datetime, timezone
from uuid import UUID


def _today_utc() -> date:
    """UTC-anchored 'today' for aging math.

    ``created_at`` columns are timezone-aware (UTC). Comparing them against
    ``date.today()`` (local) caused intermittent off-by-one days late in the
    local evening when UTC had rolled to the next day. Always anchor to UTC.
    """
    return datetime.now(timezone.utc).date()

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_management import (
    Attachment, Correspondence, Drawing, DrawingArea, DrawingRevision,
    Rfi, Specification, Submittal, SubmittalPackage,
)
from app.services.crud import create, get_by_id, update  # noqa: F401

_RFI_OPEN_STATUSES = {"draft", "open"}
_RFI_CLOSED_STATUSES = {"answered", "closed"}
_SUBMITTAL_OPEN_STATUSES = {"draft", "pending", "submitted"}
_SUBMITTAL_CLOSED_STATUSES = {"approved", "approved_as_noted", "rejected", "closed"}


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


async def list_drawing_areas(db: AsyncSession, *, project_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, DrawingArea, {"project_id": project_id}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_drawings(db: AsyncSession, *, project_id: UUID | None = None, drawing_area_id: UUID | None = None, discipline: str | None = None, is_current: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Drawing, {"project_id": project_id, "drawing_area_id": drawing_area_id, "discipline": discipline, "is_current": is_current}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_drawing_revisions(db: AsyncSession, *, drawing_id: UUID | None = None, revision_number: int | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """Scoped via parent Drawing → project_id."""
    stmt = select(DrawingRevision)
    if drawing_id is not None:
        stmt = stmt.where(DrawingRevision.drawing_id == drawing_id)
    if revision_number is not None:
        stmt = stmt.where(DrawingRevision.revision_number == revision_number)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(Drawing, DrawingRevision.drawing_id == Drawing.id).where(
            Drawing.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())

async def list_specifications(db: AsyncSession, *, project_id: UUID | None = None, section_number: str | None = None, division: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Specification, {"project_id": project_id, "section_number": section_number, "division": division}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_rfis(db: AsyncSession, *, project_id: UUID | None = None, status: str | None = None, priority: str | None = None, cost_code_id: UUID | None = None, assigned_to: UUID | None = None, ball_in_court: UUID | None = None, drawing_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Rfi, {"project_id": project_id, "status": status, "priority": priority, "cost_code_id": cost_code_id, "assigned_to": assigned_to, "ball_in_court": ball_in_court, "drawing_id": drawing_id}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_submittal_packages(db: AsyncSession, *, project_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, SubmittalPackage, {"project_id": project_id, "status": status}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_submittals(db: AsyncSession, *, project_id: UUID | None = None, submittal_package_id: UUID | None = None, status: str | None = None, submittal_type: str | None = None, cost_code_id: UUID | None = None, schedule_activity_id: UUID | None = None, assigned_to: UUID | None = None, ball_in_court: UUID | None = None, responsible_contractor: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Submittal, {"project_id": project_id, "submittal_package_id": submittal_package_id, "status": status, "submittal_type": submittal_type, "cost_code_id": cost_code_id, "schedule_activity_id": schedule_activity_id, "assigned_to": assigned_to, "ball_in_court": ball_in_court, "responsible_contractor": responsible_contractor}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_attachments(db: AsyncSession, *, project_id: UUID | None = None, source_type: str | None = None, source_id: UUID | None = None, uploaded_by: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Attachment, {"project_id": project_id, "source_type": source_type, "source_id": source_id, "uploaded_by": uploaded_by}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_correspondence(db: AsyncSession, *, project_id: UUID | None = None, correspondence_type: str | None = None, status: str | None = None, from_person_id: UUID | None = None, to_person_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Correspondence, {"project_id": project_id, "correspondence_type": correspondence_type, "status": status, "from_person_id": from_person_id, "to_person_id": to_person_id}, skip, limit, accessible_project_ids=accessible_project_ids)


# ── RFI aging helpers ───────────────────────────────────────────────────────

def compute_rfi_aging(rfi: Rfi, today: date | None = None) -> dict:
    """Compute aging metrics for an RFI at read time.

    days_open: from created_at to (answered_date if answered, else today)
    is_open: status in {draft, open}
    is_overdue: open AND today > due_date
    days_overdue: max(0, today - due_date) if open and overdue
    """
    if today is None:
        today = _today_utc()

    created_d = rfi.created_at.date() if rfi.created_at else None
    is_open = rfi.status in _RFI_OPEN_STATUSES

    end_date: date | None = None
    if rfi.status in _RFI_CLOSED_STATUSES and rfi.answered_date:
        end_date = rfi.answered_date
    elif is_open:
        end_date = today

    days_open = (end_date - created_d).days if (created_d and end_date) else None

    is_overdue = False
    days_overdue = 0
    if is_open and rfi.due_date and today > rfi.due_date:
        is_overdue = True
        days_overdue = (today - rfi.due_date).days

    return {
        "rfi_id": rfi.id,
        "rfi_number": rfi.rfi_number,
        "status": rfi.status,
        "is_open": is_open,
        "days_open": days_open,
        "is_overdue": is_overdue,
        "days_overdue": days_overdue,
        "due_date": rfi.due_date,
        "answered_date": rfi.answered_date,
    }


async def get_rfi_aging(db: AsyncSession, rfi_id: UUID) -> dict:
    rfi = await db.get(Rfi, rfi_id)
    if rfi is None:
        raise HTTPException(status_code=404, detail="RFI not found")
    return compute_rfi_aging(rfi)


async def get_project_rfi_aging_summary(db: AsyncSession, project_id: UUID) -> dict:
    """Aggregate RFI aging across a project."""
    result = await db.execute(select(Rfi).where(Rfi.project_id == project_id))
    rfis = list(result.scalars().all())
    today = _today_utc()

    aged_items = [compute_rfi_aging(r, today) for r in rfis]
    open_items = [a for a in aged_items if a["is_open"]]
    overdue_items = [a for a in open_items if a["is_overdue"]]
    open_ages = [a["days_open"] for a in open_items if a["days_open"] is not None]
    avg_age = round(sum(open_ages) / len(open_ages), 1) if open_ages else 0

    return {
        "project_id": project_id,
        "total_rfis": len(rfis),
        "open_count": len(open_items),
        "overdue_count": len(overdue_items),
        "average_days_open": avg_age,
        "items": aged_items,
    }


# ── Submittal aging helpers ─────────────────────────────────────────────────

def compute_submittal_aging(submittal: Submittal, today: date | None = None) -> dict:
    """Compute aging metrics for a submittal at read time."""
    if today is None:
        today = _today_utc()

    created_d = submittal.created_at.date() if submittal.created_at else None
    is_open = submittal.status in _SUBMITTAL_OPEN_STATUSES

    end_date: date | None = None
    if submittal.status in _SUBMITTAL_CLOSED_STATUSES and submittal.approved_date:
        end_date = submittal.approved_date
    elif is_open:
        end_date = today

    days_open = (end_date - created_d).days if (created_d and end_date) else None

    is_overdue = False
    days_overdue = 0
    if is_open and submittal.due_date and today > submittal.due_date:
        is_overdue = True
        days_overdue = (today - submittal.due_date).days

    days_to_required_onsite = None
    if submittal.required_on_site:
        days_to_required_onsite = (submittal.required_on_site - today).days

    return {
        "submittal_id": submittal.id,
        "submittal_number": submittal.submittal_number,
        "status": submittal.status,
        "is_open": is_open,
        "days_open": days_open,
        "is_overdue": is_overdue,
        "days_overdue": days_overdue,
        "due_date": submittal.due_date,
        "required_on_site": submittal.required_on_site,
        "days_to_required_onsite": days_to_required_onsite,
    }


async def get_submittal_aging(db: AsyncSession, submittal_id: UUID) -> dict:
    submittal = await db.get(Submittal, submittal_id)
    if submittal is None:
        raise HTTPException(status_code=404, detail="Submittal not found")
    return compute_submittal_aging(submittal)


async def get_project_submittal_aging_summary(db: AsyncSession, project_id: UUID) -> dict:
    result = await db.execute(select(Submittal).where(Submittal.project_id == project_id))
    submittals = list(result.scalars().all())
    today = _today_utc()

    aged_items = [compute_submittal_aging(s, today) for s in submittals]
    open_items = [a for a in aged_items if a["is_open"]]
    overdue_items = [a for a in open_items if a["is_overdue"]]
    open_ages = [a["days_open"] for a in open_items if a["days_open"] is not None]
    avg_age = round(sum(open_ages) / len(open_ages), 1) if open_ages else 0

    return {
        "project_id": project_id,
        "total_submittals": len(submittals),
        "open_count": len(open_items),
        "overdue_count": len(overdue_items),
        "average_days_open": avg_age,
        "items": aged_items,
    }

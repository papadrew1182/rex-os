"""Closeout & Warranty domain service layer.

Includes filtered list queries, workflow functions (create from template,
rollup), and re-exports shared CRUD helpers.
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.closeout import (
    CloseoutChecklist, CloseoutChecklistItem, CloseoutTemplate, CloseoutTemplateItem,
    CompletionMilestone, Warranty, WarrantyAlert, WarrantyClaim,
)
from app.models.foundation import Project, ProjectMember, RoleTemplate
from app.services.crud import create, get_by_id, update, _classify_integrity_error  # noqa: F401


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


# ── Filtered list queries ───────────────────────────────────────────────────

async def list_closeout_templates(db: AsyncSession, *, project_type: str | None = None, is_default: bool | None = None, skip: int = 0, limit: int = 100):
    return await _flist(db, CloseoutTemplate, {"project_type": project_type, "is_default": is_default}, skip, limit)

async def list_closeout_template_items(db: AsyncSession, *, template_id: UUID | None = None, category: str | None = None, default_assignee_role: str | None = None, skip: int = 0, limit: int = 100):
    return await _flist(db, CloseoutTemplateItem, {"template_id": template_id, "category": category, "default_assignee_role": default_assignee_role}, skip, limit)

async def list_closeout_checklists(db: AsyncSession, *, project_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, CloseoutChecklist, {"project_id": project_id}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_closeout_checklist_items(db: AsyncSession, *, checklist_id: UUID | None = None, category: str | None = None, status: str | None = None, assigned_company_id: UUID | None = None, assigned_person_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """Scoped via parent CloseoutChecklist → project_id."""
    stmt = select(CloseoutChecklistItem)
    if checklist_id is not None:
        stmt = stmt.where(CloseoutChecklistItem.checklist_id == checklist_id)
    if category is not None:
        stmt = stmt.where(CloseoutChecklistItem.category == category)
    if status is not None:
        stmt = stmt.where(CloseoutChecklistItem.status == status)
    if assigned_company_id is not None:
        stmt = stmt.where(CloseoutChecklistItem.assigned_company_id == assigned_company_id)
    if assigned_person_id is not None:
        stmt = stmt.where(CloseoutChecklistItem.assigned_person_id == assigned_person_id)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(
            CloseoutChecklist, CloseoutChecklistItem.checklist_id == CloseoutChecklist.id,
        ).where(CloseoutChecklist.project_id.in_(accessible_project_ids))
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())

async def list_warranties(db: AsyncSession, *, project_id: UUID | None = None, commitment_id: UUID | None = None, company_id: UUID | None = None, cost_code_id: UUID | None = None, status: str | None = None, warranty_type: str | None = None, is_letter_received: bool | None = None, is_om_received: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Warranty, {"project_id": project_id, "commitment_id": commitment_id, "company_id": company_id, "cost_code_id": cost_code_id, "status": status, "warranty_type": warranty_type, "is_letter_received": is_letter_received, "is_om_received": is_om_received}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_warranty_claims(db: AsyncSession, *, warranty_id: UUID | None = None, status: str | None = None, priority: str | None = None, is_covered_by_warranty: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """Scoped via parent Warranty → project_id."""
    stmt = select(WarrantyClaim)
    if warranty_id is not None:
        stmt = stmt.where(WarrantyClaim.warranty_id == warranty_id)
    if status is not None:
        stmt = stmt.where(WarrantyClaim.status == status)
    if priority is not None:
        stmt = stmt.where(WarrantyClaim.priority == priority)
    if is_covered_by_warranty is not None:
        stmt = stmt.where(WarrantyClaim.is_covered_by_warranty == is_covered_by_warranty)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(Warranty, WarrantyClaim.warranty_id == Warranty.id).where(
            Warranty.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())

async def list_warranty_alerts(db: AsyncSession, *, warranty_id: UUID | None = None, alert_type: str | None = None, is_sent: bool | None = None, recipient_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """Scoped via parent Warranty → project_id."""
    stmt = select(WarrantyAlert)
    if warranty_id is not None:
        stmt = stmt.where(WarrantyAlert.warranty_id == warranty_id)
    if alert_type is not None:
        stmt = stmt.where(WarrantyAlert.alert_type == alert_type)
    if is_sent is not None:
        stmt = stmt.where(WarrantyAlert.is_sent == is_sent)
    if recipient_id is not None:
        stmt = stmt.where(WarrantyAlert.recipient_id == recipient_id)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(Warranty, WarrantyAlert.warranty_id == Warranty.id).where(
            Warranty.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())

async def list_completion_milestones(db: AsyncSession, *, project_id: UUID | None = None, milestone_type: str | None = None, status: str | None = None, is_evidence_complete: bool | None = None, certified_by: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, CompletionMilestone, {"project_id": project_id, "milestone_type": milestone_type, "status": status, "is_evidence_complete": is_evidence_complete, "certified_by": certified_by}, skip, limit, accessible_project_ids=accessible_project_ids)


# ── Helper: resolve project member for a role slug ──────────────────────────

async def resolve_project_member_for_role(
    db: AsyncSession,
    project_id: UUID,
    role_slug: str,
) -> ProjectMember | None:
    """Find the best project member matching a role slug on a project.

    Resolution rule:
    1. Match active project_members whose role_template.slug == role_slug
    2. If exactly one match, return it
    3. If multiple, prefer is_primary=True
    4. If still ambiguous (multiple primaries or no primary), return None
    """
    result = await db.execute(
        select(ProjectMember)
        .join(RoleTemplate, ProjectMember.role_template_id == RoleTemplate.id)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.is_active == True,  # noqa: E712
            RoleTemplate.slug == role_slug,
        )
    )
    members = list(result.scalars().all())

    if len(members) == 1:
        return members[0]
    if len(members) == 0:
        return None

    # Multiple matches — prefer is_primary
    primaries = [m for m in members if m.is_primary]
    if len(primaries) == 1:
        return primaries[0]

    # Still ambiguous — don't guess
    return None


# ── Workflow: create checklist from template ────────────────────────────────

async def create_checklist_from_template(
    db: AsyncSession,
    *,
    project_id: UUID,
    template_id: UUID,
    substantial_completion_date: date | None = None,
) -> CloseoutChecklist:
    """Create a closeout checklist by copying items from a template.

    - Validates project and template exist
    - Creates checklist row with total_items populated
    - Creates one checklist item per template item
    - Computes due_date from days_before_substantial when date is provided
    """
    # Validate FK targets exist
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    template = await db.get(CloseoutTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Closeout template not found")

    # Fetch all template items
    result = await db.execute(
        select(CloseoutTemplateItem)
        .where(CloseoutTemplateItem.template_id == template_id)
        .order_by(CloseoutTemplateItem.sort_order)
    )
    template_items = list(result.scalars().all())

    # Pre-resolve role assignments: one lookup per unique role slug
    unique_roles = {ti.default_assignee_role for ti in template_items if ti.default_assignee_role}
    role_to_member: dict[str, ProjectMember | None] = {}
    for slug in unique_roles:
        role_to_member[slug] = await resolve_project_member_for_role(db, project_id, slug)

    # Create the checklist
    checklist = CloseoutChecklist(
        project_id=project_id,
        template_id=template_id,
        substantial_completion_date=substantial_completion_date,
        total_items=len(template_items),
        completed_items=0,
        percent_complete=0,
    )
    db.add(checklist)
    try:
        await db.flush()  # get checklist.id without committing
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)

    # Create checklist items from template items
    for ti in template_items:
        due = None
        if substantial_completion_date and ti.days_before_substantial is not None:
            due = substantial_completion_date - timedelta(days=ti.days_before_substantial)

        # Resolve assignee from role
        assigned_person_id = None
        assigned_company_id = None
        if ti.default_assignee_role:
            member = role_to_member.get(ti.default_assignee_role)
            if member:
                assigned_person_id = member.person_id
                assigned_company_id = member.company_id

        item = CloseoutChecklistItem(
            checklist_id=checklist.id,
            category=ti.category,
            item_number=ti.item_number,
            name=ti.name,
            sort_order=ti.sort_order,
            due_date=due,
            status="not_started",
            assigned_person_id=assigned_person_id,
            assigned_company_id=assigned_company_id,
        )
        db.add(item)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)

    await db.refresh(checklist)
    return checklist


# ── Workflow: rollup checklist progress ─────────────────────────────────────

async def rollup_checklist(db: AsyncSession, checklist_id: UUID) -> CloseoutChecklist:
    """Recompute total_items, completed_items, and percent_complete from child items."""
    checklist = await db.get(CloseoutChecklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checklist not found")

    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(CloseoutChecklistItem.status == "complete").label("completed"),
        ).where(CloseoutChecklistItem.checklist_id == checklist_id)
    )
    row = result.one()
    total = row.total
    completed = row.completed

    checklist.total_items = total
    checklist.completed_items = completed
    checklist.percent_complete = round((completed / total * 100) if total > 0 else 0, 2)

    await db.commit()
    await db.refresh(checklist)
    return checklist


# ── Workflow: update checklist item with auto-rollup ────────────────────────

async def update_checklist_item_with_rollup(
    db: AsyncSession,
    item_id: UUID,
    data,
) -> CloseoutChecklistItem:
    """Update a checklist item and recompute parent checklist progress."""
    from pydantic import BaseModel
    item = await db.get(CloseoutChecklistItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="closeout_checklist_items not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)

    await db.refresh(item)

    # Auto-rollup parent checklist
    await rollup_checklist(db, item.checklist_id)

    return item


# ── Warranty helpers ────────────────────────────────────────────────────────

def compute_warranty_expiration(start_date: date, duration_months: int) -> date:
    """Compute expiration_date = start_date + duration_months.

    Handles month overflow correctly (e.g. Jan 31 + 1 month = Feb 28).
    """
    year = start_date.year + (start_date.month - 1 + duration_months) // 12
    month = (start_date.month - 1 + duration_months) % 12 + 1
    # Clamp day to valid range for target month
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day = min(start_date.day, max_day)
    return date(year, month, day)


async def create_warranty_with_expiration(
    db: AsyncSession,
    data: Any,
) -> Warranty:
    """Create a warranty, computing expiration_date if not provided."""
    fields = data.model_dump(exclude_unset=True)

    if "expiration_date" not in fields or fields.get("expiration_date") is None:
        sd = fields.get("start_date")
        dm = fields.get("duration_months")
        if sd and dm:
            fields["expiration_date"] = compute_warranty_expiration(sd, dm)

    if fields.get("expiration_date") is None:
        raise HTTPException(
            status_code=422,
            detail="expiration_date is required when it cannot be computed from start_date + duration_months",
        )

    row = Warranty(**fields)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)
    await db.refresh(row)
    return row


async def generate_warranty_alerts(
    db: AsyncSession,
    warranty_id: UUID,
) -> list[WarrantyAlert]:
    """Generate standard 90-day, 30-day, and expired alerts for a warranty.

    Idempotent: skips alert types that already exist for this warranty.
    Skips alerts whose date falls before the warranty start_date.
    """
    warranty = await db.get(Warranty, warranty_id)
    if warranty is None:
        raise HTTPException(status_code=404, detail="Warranty not found")

    if warranty.expiration_date is None:
        return []

    # Check which alert types already exist
    result = await db.execute(
        select(WarrantyAlert.alert_type)
        .where(WarrantyAlert.warranty_id == warranty_id)
    )
    existing_types = {row[0] for row in result.all()}

    # Define the 3 standard alert dates
    alert_specs = [
        ("90_day", warranty.expiration_date - timedelta(days=90)),
        ("30_day", warranty.expiration_date - timedelta(days=30)),
        ("expired", warranty.expiration_date),
    ]

    created = []
    for alert_type, alert_date in alert_specs:
        # Skip if already exists
        if alert_type in existing_types:
            continue
        # Skip if alert date is before warranty start (nonsensical)
        if alert_date < warranty.start_date:
            continue

        alert = WarrantyAlert(
            warranty_id=warranty_id,
            alert_type=alert_type,
            alert_date=alert_date,
        )
        db.add(alert)
        created.append(alert)

    if created:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise _classify_integrity_error(e)
        for a in created:
            await db.refresh(a)

    return created


# ── Milestone evidence helpers ──────────────────────────────────────────────

def _parse_evidence_requirements(raw: Any) -> dict:
    """Safely parse evidence_requirements JSONB into a normalized dict.

    Returns a dict with keys: checklist, payout_percent, holdback_percent,
    gate_conditions, trigger_condition. Missing/malformed data yields safe defaults.
    """
    if not isinstance(raw, dict):
        return {
            "checklist": [],
            "payout_percent": None,
            "holdback_percent": None,
            "gate_conditions": None,
            "trigger_condition": None,
        }
    checklist = raw.get("checklist", [])
    if not isinstance(checklist, list):
        checklist = []
    return {
        "checklist": [
            {"item": item.get("item", ""), "source": item.get("source")}
            for item in checklist
            if isinstance(item, dict)
        ],
        "payout_percent": raw.get("payout_percent"),
        "holdback_percent": raw.get("holdback_percent"),
        "gate_conditions": raw.get("gate_conditions"),
        "trigger_condition": raw.get("trigger_condition"),
    }


async def get_milestone_evidence_checklist(
    db: AsyncSession,
    milestone_id: UUID,
) -> dict:
    """Return a milestone with its evidence requirements normalized."""
    milestone = await db.get(CompletionMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Completion milestone not found")

    parsed = _parse_evidence_requirements(milestone.evidence_requirements)
    return {
        "milestone_id": milestone.id,
        "milestone_type": milestone.milestone_type,
        "milestone_name": milestone.milestone_name,
        "status": milestone.status,
        "is_evidence_complete": milestone.is_evidence_complete,
        **parsed,
    }


async def evaluate_milestone_evidence(
    db: AsyncSession,
    milestone_id: UUID,
    *,
    all_items_complete: bool,
    notes: str | None = None,
) -> CompletionMilestone:
    """Set is_evidence_complete based on explicit confirmation."""
    milestone = await db.get(CompletionMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Completion milestone not found")

    milestone.is_evidence_complete = all_items_complete
    if notes is not None:
        milestone.notes = notes

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)

    await db.refresh(milestone)
    return milestone


# ── Milestone certification ─────────────────────────────────────────────────

async def certify_milestone(
    db: AsyncSession,
    milestone_id: UUID,
    *,
    certified_by: UUID,
    actual_date: date | None = None,
    notes: str | None = None,
) -> tuple[CompletionMilestone, bool]:
    """Certify a milestone as achieved.

    Returns (milestone, evidence_incomplete_warning).
    The warning is True if is_evidence_complete was False at certification time.
    Certification proceeds regardless — the warning is informational only.
    """
    from app.models.foundation import Person

    milestone = await db.get(CompletionMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Completion milestone not found")

    person = await db.get(Person, certified_by)
    if person is None:
        raise HTTPException(status_code=422, detail="certified_by person not found")

    evidence_warning = not milestone.is_evidence_complete

    milestone.status = "achieved"
    milestone.certified_by = certified_by
    if actual_date is not None:
        milestone.actual_date = actual_date
    if notes is not None:
        milestone.notes = notes

    # Compute variance if both dates are present
    if milestone.actual_date and milestone.scheduled_date:
        milestone.variance_days = (milestone.actual_date - milestone.scheduled_date).days

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)

    await db.refresh(milestone)
    return milestone, evidence_warning


# ── Milestone gate evaluation ───────────────────────────────────────────────

# Time trigger patterns: (condition_string, required_days, base_date_source)
# base_date_source values: "final_co_actual", "own_actual"
_TIME_TRIGGERS = {
    "45_days_post_final_co": (45, "final_co_actual"),
    "45_days_post_opening": (45, "own_actual"),
}


async def _evaluate_time_trigger(
    db: AsyncSession,
    milestone: CompletionMilestone,
    trigger: str,
) -> dict | None:
    """Evaluate a time-based trigger condition.

    Returns a gate dict or None if the trigger is unknown.
    """
    if trigger not in _TIME_TRIGGERS:
        return None

    required_days, base_source = _TIME_TRIGGERS[trigger]
    today = date.today()
    label = "Time Elapsed"
    code = "time_elapsed"

    # Resolve the base date
    base_date: date | None = None
    base_label = ""
    if base_source == "final_co_actual":
        result = await db.execute(
            select(CompletionMilestone)
            .where(
                CompletionMilestone.project_id == milestone.project_id,
                CompletionMilestone.milestone_type == "final_co",
            )
        )
        final_co = result.scalar_one_or_none()
        if final_co and final_co.actual_date:
            base_date = final_co.actual_date
            base_label = "Final CO actual date"
    elif base_source == "own_actual":
        if milestone.actual_date:
            base_date = milestone.actual_date
            base_label = "Opening (own actual) date"

    if base_date is None:
        return {
            "code": code,
            "label": label,
            "status": "warning",
            "detail": f"Base date missing for trigger '{trigger}'; cannot evaluate {required_days}-day requirement",
        }

    days_elapsed = (today - base_date).days
    if days_elapsed >= required_days:
        return {
            "code": code,
            "label": label,
            "status": "pass",
            "detail": f"{base_label} {base_date.isoformat()}, {days_elapsed} days elapsed (>= {required_days} required)",
        }
    else:
        return {
            "code": code,
            "label": label,
            "status": "fail",
            "detail": f"{base_label} {base_date.isoformat()}, only {days_elapsed} days elapsed ({required_days} required)",
        }


async def evaluate_milestone_gates(
    db: AsyncSession,
    milestone_id: UUID,
) -> dict:
    """Evaluate whether a milestone passes its release gates.

    Read-only. Returns structured gate results without mutating any data.
    """
    milestone = await db.get(CompletionMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Completion milestone not found")

    gates: list[dict] = []

    # Gate 1: milestone is certified (status = achieved)
    if milestone.status == "achieved":
        gates.append({"code": "certified", "label": "Milestone certified", "status": "pass", "detail": "Status is achieved"})
    else:
        gates.append({"code": "certified", "label": "Milestone certified", "status": "fail", "detail": f"Status is {milestone.status}, not achieved"})

    # Gate 2: evidence complete
    if milestone.is_evidence_complete:
        gates.append({"code": "evidence_complete", "label": "Evidence complete", "status": "pass", "detail": "All evidence confirmed"})
    else:
        gates.append({"code": "evidence_complete", "label": "Evidence complete", "status": "fail", "detail": "Evidence not yet confirmed complete"})

    # Gate 3: closeout checklist status (project-level)
    checklists = await _flist(db, CloseoutChecklist, {"project_id": milestone.project_id}, 0, 100)
    if not checklists:
        gates.append({"code": "closeout_checklist", "label": "Closeout checklist", "status": "warning", "detail": "No closeout checklist found for this project"})
    else:
        best = max(checklists, key=lambda c: c.percent_complete)
        pct = float(best.percent_complete)
        if pct >= 100:
            gates.append({"code": "closeout_checklist", "label": "Closeout checklist", "status": "pass", "detail": f"Checklist {pct:.0f}% complete"})
        elif pct >= 80:
            gates.append({"code": "closeout_checklist", "label": "Closeout checklist", "status": "warning", "detail": f"Checklist {pct:.0f}% complete (high but not 100%)"})
        else:
            gates.append({"code": "closeout_checklist", "label": "Closeout checklist", "status": "fail", "detail": f"Checklist only {pct:.0f}% complete"})

    # Gate 4: holdback-specific — warranty status
    if milestone.milestone_type == "holdback_release":
        from app.models.closeout import Warranty
        warranties = await _flist(db, Warranty, {"project_id": milestone.project_id}, 0, 500)
        if not warranties:
            gates.append({"code": "warranty_status", "label": "Warranty status", "status": "warning", "detail": "No warranties found for this project"})
        else:
            claimed = [w for w in warranties if w.status == "claimed"]
            if claimed:
                gates.append({"code": "warranty_status", "label": "Warranty status", "status": "fail", "detail": f"{len(claimed)} warranty(ies) have active claims"})
            else:
                gates.append({"code": "warranty_status", "label": "Warranty status", "status": "pass", "detail": f"All {len(warranties)} warranties clear of active claims"})

        # Gate 4b: punch aging — uses read-time computed days_open, not stored value
        from app.models.field_ops import PunchItem
        from app.services.field_ops import compute_punch_days_open
        _CLOSED_STATUSES = {"closed"}
        result = await db.execute(
            select(PunchItem).where(PunchItem.project_id == milestone.project_id)
        )
        all_punch = list(result.scalars().all())
        open_punch = [p for p in all_punch if p.status not in _CLOSED_STATUSES]

        if not all_punch:
            gates.append({"code": "punch_aging", "label": "Punch Aging", "status": "warning", "detail": "No punch items found for this project"})
        elif not open_punch:
            gates.append({"code": "punch_aging", "label": "Punch Aging", "status": "pass", "detail": f"All {len(all_punch)} punch item(s) closed"})
        else:
            today = date.today()
            ages = [compute_punch_days_open(p, today) for p in open_punch]
            ages = [a for a in ages if a is not None]
            avg_age = round(sum(ages) / len(ages), 1) if ages else 0
            aged_30 = sum(1 for a in ages if a > 30)
            open_count = len(open_punch)
            detail = f"{open_count} open item(s), avg age {avg_age} days, {aged_30} item(s) > 30 days"

            # Deterministic thresholds:
            # fail: >10 open items OR any aged >30 exceeding 10% of open items OR avg age > 21
            # warning: 1-10 open items with moderate aging
            # pass: 0 open items (handled above)
            aged_pct = (aged_30 / open_count) if open_count > 0 else 0
            if open_count > 10 or aged_pct > 0.10 or avg_age > 21:
                status = "fail"
            else:
                status = "warning"

            gates.append({
                "code": "punch_aging", "label": "Punch Aging", "status": status, "detail": detail,
            })

    # Gate 4c: time-elapsed trigger condition
    parsed = _parse_evidence_requirements(milestone.evidence_requirements)
    trigger = parsed.get("trigger_condition")
    if trigger:
        time_gate = await _evaluate_time_trigger(db, milestone, trigger)
        if time_gate is not None:
            gates.append(time_gate)

    # Gate 5: surface gate_conditions from evidence_requirements as metadata
    gate_conditions = parsed.get("gate_conditions")
    if gate_conditions and isinstance(gate_conditions, list):
        for gc in gate_conditions:
            gates.append({
                "code": f"evidence_gate:{gc}",
                "label": gc.replace("_", " ").title(),
                "status": "not_applicable",
                "detail": "Defined in evidence requirements; manual verification required",
            })

    # Compute overall status
    statuses = [g["status"] for g in gates]
    if "fail" in statuses:
        overall = "fail"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "pass"

    fail_count = statuses.count("fail")
    warn_count = statuses.count("warning")
    if overall == "pass":
        summary = "All gates passed"
    elif overall == "warning":
        summary = f"{warn_count} warning(s), no failures"
    else:
        summary = f"{fail_count} gate(s) failed, {warn_count} warning(s)"

    return {
        "milestone_id": milestone.id,
        "milestone_type": milestone.milestone_type,
        "gate_status": overall,
        "gate_results": gates,
        "summary_message": summary,
    }


# ── Project closeout readiness ──────────────────────────────────────────────

async def get_project_closeout_readiness(db: AsyncSession, project_id: UUID) -> dict:
    """Compute a project-level closeout readiness summary.

    Read-only. Aggregates checklists, milestones, warranties, and holdback
    gate evaluation into a single structured response.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    issues: list[dict] = []

    # ── Checklists ──
    checklists = await _flist(db, CloseoutChecklist, {"project_id": project_id}, 0, 100)
    if checklists:
        best = max(checklists, key=lambda c: c.percent_complete)
        cl_summary = {
            "checklist_count": len(checklists),
            "best_percent_complete": float(best.percent_complete),
            "total_items": best.total_items,
            "completed_items": best.completed_items,
        }
        if best.percent_complete < 100:
            issues.append({"severity": "warning" if best.percent_complete >= 80 else "fail",
                           "message": f"Closeout checklist is {best.percent_complete:.0f}% complete"})
    else:
        cl_summary = {"checklist_count": 0, "best_percent_complete": 0, "total_items": 0, "completed_items": 0}

    # ── Milestones ──
    milestones = await _flist(db, CompletionMilestone, {"project_id": project_id}, 0, 100)
    achieved = [m for m in milestones if m.status == "achieved"]
    ev_complete = [m for m in milestones if m.is_evidence_complete]
    certified = [m for m in milestones if m.certified_by is not None]
    ms_summary = {
        "total_milestones": len(milestones),
        "achieved_count": len(achieved),
        "evidence_complete_count": len(ev_complete),
        "certified_count": len(certified),
        "milestones": [
            {"milestone_type": m.milestone_type, "milestone_name": m.milestone_name,
             "status": m.status, "is_evidence_complete": m.is_evidence_complete,
             "certified_by": m.certified_by}
            for m in milestones
        ],
    }
    pending = [m for m in milestones if m.status == "pending"]
    if pending:
        issues.append({"severity": "warning",
                       "message": f"{len(pending)} milestone(s) still pending"})
    not_evidenced = [m for m in milestones if not m.is_evidence_complete]
    if not_evidenced:
        issues.append({"severity": "warning",
                       "message": f"{len(not_evidenced)} milestone(s) missing evidence confirmation"})

    # ── Holdback release ──
    holdback = next((m for m in milestones if m.milestone_type == "holdback_release"), None)
    if holdback:
        gate_result = await evaluate_milestone_gates(db, holdback.id)
        hb_summary = {
            "exists": True,
            "status": holdback.status,
            "gate_status": gate_result["gate_status"],
            "gate_summary": gate_result["summary_message"],
        }
        if gate_result["gate_status"] == "fail":
            issues.append({"severity": "fail", "message": f"Holdback release gates: {gate_result['summary_message']}"})
        elif gate_result["gate_status"] == "warning":
            issues.append({"severity": "warning", "message": f"Holdback release gates: {gate_result['summary_message']}"})
    else:
        hb_summary = {"exists": False, "status": None, "gate_status": None, "gate_summary": None}

    # ── Warranties ──
    warranties = await _flist(db, Warranty, {"project_id": project_id}, 0, 500)
    claimed = [w for w in warranties if w.status == "claimed"]
    expiring = [w for w in warranties if w.status == "expiring_soon"]
    alert_result = await db.execute(
        select(func.count()).select_from(WarrantyAlert)
        .join(Warranty, WarrantyAlert.warranty_id == Warranty.id)
        .where(Warranty.project_id == project_id, WarrantyAlert.is_sent == False)  # noqa: E712
    )
    unsent_alerts = alert_result.scalar() or 0
    w_summary = {
        "total_warranties": len(warranties),
        "claimed_count": len(claimed),
        "expiring_soon_count": len(expiring),
        "alert_count": unsent_alerts,
    }
    if claimed:
        issues.append({"severity": "fail", "message": f"{len(claimed)} warranty(ies) have active claims"})
    if expiring:
        issues.append({"severity": "warning", "message": f"{len(expiring)} warranty(ies) expiring soon"})

    # ── Overall status ──
    has_artifacts = bool(checklists or milestones)
    if not has_artifacts:
        overall = "not_started"
        summary_msg = "No closeout artifacts found for this project"
    else:
        severities = [i["severity"] for i in issues]
        if "fail" in severities:
            overall = "fail"
            fail_n = severities.count("fail")
            warn_n = severities.count("warning")
            summary_msg = f"{fail_n} blocker(s), {warn_n} warning(s)"
        elif "warning" in severities:
            overall = "warning"
            summary_msg = f"{len(issues)} warning(s), no blockers"
        else:
            overall = "pass"
            summary_msg = "Project closeout is in strong shape"

    return {
        "project_id": project.id,
        "project_name": project.name,
        "overall_status": overall,
        "summary_message": summary_msg,
        "checklist_summary": cl_summary,
        "milestone_summary": ms_summary,
        "holdback_release": hb_summary,
        "warranty_summary": w_summary,
        "open_issues": issues,
    }


# ── Portfolio readiness rollup ──────────────────────────────────────────────

async def get_portfolio_closeout_readiness(
    db: AsyncSession,
    *,
    project_status: str | None = None,
    project_type: str | None = None,
    city: str | None = None,
    state: str | None = None,
    limit: int = 100,
    offset: int = 0,
    accessible_project_ids: set[UUID] | None = None,
) -> dict:
    """Aggregate closeout readiness across multiple projects.

    Reuses get_project_closeout_readiness() per project.
    First-pass implementation is N+1 — acceptable for portfolio sizes <100.
    """
    # Filter projects
    stmt = select(Project)
    if project_status:
        stmt = stmt.where(Project.status == project_status)
    if project_type:
        stmt = stmt.where(Project.project_type == project_type)
    if city:
        stmt = stmt.where(Project.city == city)
    if state:
        stmt = stmt.where(Project.state == state)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return {
                "summary": {"total_projects": 0, "pass_count": 0, "warning_count": 0, "fail_count": 0, "not_started_count": 0},
                "projects": [],
            }
        stmt = stmt.where(Project.id.in_(accessible_project_ids))
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    projects = list(result.scalars().all())

    rows: list[dict] = []
    counts = {"pass": 0, "warning": 0, "fail": 0, "not_started": 0}

    for p in projects:
        readiness = await get_project_closeout_readiness(db, p.id)
        status = readiness["overall_status"]
        counts[status] += 1

        rows.append({
            "project_id": p.id,
            "project_name": p.name,
            "project_number": p.project_number,
            "project_type": p.project_type,
            "city": p.city,
            "state": p.state,
            "project_status": p.status,
            "readiness_status": status,
            "summary_message": readiness["summary_message"],
            "best_checklist_percent": readiness["checklist_summary"]["best_percent_complete"],
            "achieved_milestones": readiness["milestone_summary"]["achieved_count"],
            "total_milestones": readiness["milestone_summary"]["total_milestones"],
            "holdback_gate_status": readiness["holdback_release"]["gate_status"],
            "claimed_warranty_count": readiness["warranty_summary"]["claimed_count"],
            "expiring_soon_count": readiness["warranty_summary"]["expiring_soon_count"],
            "open_issue_count": len(readiness["open_issues"]),
        })

    return {
        "summary": {
            "total_projects": len(projects),
            "pass_count": counts["pass"],
            "warning_count": counts["warning"],
            "fail_count": counts["fail"],
            "not_started_count": counts["not_started"],
        },
        "projects": rows,
    }


# ── Warranty auto-status transitions ────────────────────────────────────────

_EXPIRING_SOON_WINDOW_DAYS = 90


def compute_warranty_status_for_date(
    expiration_date: date,
    current_status: str,
    today: date | None = None,
) -> str:
    """Compute the correct warranty status from expiration_date vs today.

    Rules:
    - 'claimed' is preserved (manual state, never auto-overridden)
    - today >= expiration_date -> 'expired'
    - today >= expiration_date - 90 days -> 'expiring_soon'
    - otherwise -> 'active'
    """
    if current_status == "claimed":
        return "claimed"
    if today is None:
        today = date.today()
    if today >= expiration_date:
        return "expired"
    if today >= expiration_date - timedelta(days=_EXPIRING_SOON_WINDOW_DAYS):
        return "expiring_soon"
    return "active"


async def refresh_warranty_status(db: AsyncSession, warranty_id: UUID) -> Warranty:
    """Recompute and persist a single warranty's status."""
    warranty = await db.get(Warranty, warranty_id)
    if warranty is None:
        raise HTTPException(status_code=404, detail="Warranty not found")

    new_status = compute_warranty_status_for_date(warranty.expiration_date, warranty.status)
    if new_status != warranty.status:
        warranty.status = new_status
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise _classify_integrity_error(e)
        await db.refresh(warranty)
    return warranty


async def refresh_warranty_statuses_for_project(
    db: AsyncSession, project_id: UUID
) -> dict:
    """Bulk-refresh statuses for all warranties on a project. Returns counts."""
    result = await db.execute(
        select(Warranty).where(Warranty.project_id == project_id)
    )
    warranties = list(result.scalars().all())

    updated = 0
    by_status: dict[str, int] = {"active": 0, "expiring_soon": 0, "expired": 0, "claimed": 0}
    for w in warranties:
        new_status = compute_warranty_status_for_date(w.expiration_date, w.status)
        if new_status != w.status:
            w.status = new_status
            updated += 1
        by_status[new_status] = by_status.get(new_status, 0) + 1

    if updated:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise _classify_integrity_error(e)

    return {
        "project_id": project_id,
        "total_warranties": len(warranties),
        "updated_count": updated,
        "by_status": by_status,
    }

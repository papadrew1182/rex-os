"""Financials domain service layer.

Provides filtered list queries for all 14 Financials tables,
budget rollup math, billing/pay-app/commitment summary read models,
plus re-exports shared CRUD helpers.
"""

from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financials import (
    BillingPeriod, BudgetLineItem, BudgetSnapshot, ChangeEvent, Commitment,
    CommitmentChangeOrder, CommitmentLineItem, CostCode, DirectCost,
    LienWaiver, PaymentApplication, PcoCcoLink, PotentialChangeOrder, PrimeContract,
)
from app.services.crud import _classify_integrity_error, create, get_by_id, update  # noqa: F401


def _apply(stmt, model, col: str, val):
    if val is not None:
        return stmt.where(getattr(model, col) == val)
    return stmt


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
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def _flist_via_commitment(
    db: AsyncSession,
    model,
    join_on,
    filters: dict,
    skip: int,
    limit: int,
    *,
    accessible_project_ids: set[UUID] | None,
):
    """List child rows scoped via a JOIN to ``Commitment.project_id``."""
    stmt = select(model)
    for col, val in filters.items():
        stmt = _apply(stmt, model, col, val)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(Commitment, join_on).where(
            Commitment.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def _flist_via_change_event(
    db: AsyncSession,
    model,
    join_on,
    filters: dict,
    skip: int,
    limit: int,
    *,
    accessible_project_ids: set[UUID] | None,
):
    """List child rows scoped via a JOIN to ``ChangeEvent.project_id``."""
    stmt = select(model)
    for col, val in filters.items():
        stmt = _apply(stmt, model, col, val)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = stmt.join(ChangeEvent, join_on).where(
            ChangeEvent.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


async def list_cost_codes(db: AsyncSession, *, project_id: UUID | None = None, parent_id: UUID | None = None, cost_type: str | None = None, is_active: bool | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, CostCode, {"project_id": project_id, "parent_id": parent_id, "cost_type": cost_type, "is_active": is_active}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_budget_line_items(db: AsyncSession, *, project_id: UUID | None = None, cost_code_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, BudgetLineItem, {"project_id": project_id, "cost_code_id": cost_code_id}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_budget_snapshots(db: AsyncSession, *, project_id: UUID | None = None, budget_line_item_id: UUID | None = None, snapshot_date: date | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, BudgetSnapshot, {"project_id": project_id, "budget_line_item_id": budget_line_item_id, "snapshot_date": snapshot_date}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_prime_contracts(db: AsyncSession, *, project_id: UUID | None = None, status: str | None = None, owner_company_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, PrimeContract, {"project_id": project_id, "status": status, "owner_company_id": owner_company_id}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_commitments(db: AsyncSession, *, project_id: UUID | None = None, vendor_id: UUID | None = None, status: str | None = None, contract_type: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, Commitment, {"project_id": project_id, "vendor_id": vendor_id, "status": status, "contract_type": contract_type}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_commitment_line_items(db: AsyncSession, *, commitment_id: UUID | None = None, cost_code_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist_via_commitment(
        db, CommitmentLineItem,
        CommitmentLineItem.commitment_id == Commitment.id,
        {"commitment_id": commitment_id, "cost_code_id": cost_code_id},
        skip, limit, accessible_project_ids=accessible_project_ids,
    )

async def list_change_events(db: AsyncSession, *, project_id: UUID | None = None, status: str | None = None, change_reason: str | None = None, event_type: str | None = None, scope: str | None = None, prime_contract_id: UUID | None = None, rfi_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, ChangeEvent, {"project_id": project_id, "status": status, "change_reason": change_reason, "event_type": event_type, "scope": scope, "prime_contract_id": prime_contract_id, "rfi_id": rfi_id}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_potential_change_orders(db: AsyncSession, *, change_event_id: UUID | None = None, commitment_id: UUID | None = None, status: str | None = None, cost_code_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist_via_change_event(
        db, PotentialChangeOrder,
        PotentialChangeOrder.change_event_id == ChangeEvent.id,
        {"change_event_id": change_event_id, "commitment_id": commitment_id, "status": status, "cost_code_id": cost_code_id},
        skip, limit, accessible_project_ids=accessible_project_ids,
    )

async def list_commitment_change_orders(db: AsyncSession, *, commitment_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist_via_commitment(
        db, CommitmentChangeOrder,
        CommitmentChangeOrder.commitment_id == Commitment.id,
        {"commitment_id": commitment_id, "status": status},
        skip, limit, accessible_project_ids=accessible_project_ids,
    )

async def list_pco_cco_links(db: AsyncSession, *, pco_id: UUID | None = None, cco_id: UUID | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """Scoped via PotentialChangeOrder → ChangeEvent → project_id.

    A pco_cco_link is visible if its underlying PCO sits on a readable project.
    """
    stmt = select(PcoCcoLink)
    if pco_id is not None:
        stmt = stmt.where(PcoCcoLink.pco_id == pco_id)
    if cco_id is not None:
        stmt = stmt.where(PcoCcoLink.cco_id == cco_id)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = (
            stmt.join(PotentialChangeOrder, PcoCcoLink.pco_id == PotentialChangeOrder.id)
            .join(ChangeEvent, PotentialChangeOrder.change_event_id == ChangeEvent.id)
            .where(ChangeEvent.project_id.in_(accessible_project_ids))
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())

async def list_billing_periods(db: AsyncSession, *, project_id: UUID | None = None, status: str | None = None, period_number: int | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, BillingPeriod, {"project_id": project_id, "status": status, "period_number": period_number}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_direct_costs(db: AsyncSession, *, project_id: UUID | None = None, cost_code_id: UUID | None = None, vendor_id: UUID | None = None, payment_method: str | None = None, direct_cost_date: date | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    return await _flist(db, DirectCost, {"project_id": project_id, "cost_code_id": cost_code_id, "vendor_id": vendor_id, "payment_method": payment_method, "direct_cost_date": direct_cost_date}, skip, limit, accessible_project_ids=accessible_project_ids)

async def list_payment_applications(db: AsyncSession, *, commitment_id: UUID | None = None, billing_period_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    stmt = select(PaymentApplication)
    if commitment_id is not None:
        stmt = stmt.where(PaymentApplication.commitment_id == commitment_id)
    if billing_period_id is not None:
        stmt = stmt.where(PaymentApplication.billing_period_id == billing_period_id)
    if status is not None:
        stmt = stmt.where(PaymentApplication.status == status)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        # PaymentApplication has no direct project_id; scope via Commitment join.
        stmt = stmt.join(Commitment, PaymentApplication.commitment_id == Commitment.id).where(
            Commitment.project_id.in_(accessible_project_ids)
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())

async def list_lien_waivers(db: AsyncSession, *, payment_application_id: UUID | None = None, vendor_id: UUID | None = None, waiver_type: str | None = None, status: str | None = None, skip: int = 0, limit: int = 100, accessible_project_ids: set[UUID] | None = None):
    """Scoped via PaymentApplication → Commitment → project_id."""
    stmt = select(LienWaiver)
    if payment_application_id is not None:
        stmt = stmt.where(LienWaiver.payment_application_id == payment_application_id)
    if vendor_id is not None:
        stmt = stmt.where(LienWaiver.vendor_id == vendor_id)
    if waiver_type is not None:
        stmt = stmt.where(LienWaiver.waiver_type == waiver_type)
    if status is not None:
        stmt = stmt.where(LienWaiver.status == status)
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        stmt = (
            stmt.join(PaymentApplication, LienWaiver.payment_application_id == PaymentApplication.id)
            .join(Commitment, PaymentApplication.commitment_id == Commitment.id)
            .where(Commitment.project_id.in_(accessible_project_ids))
        )
    result = await db.execute(stmt.offset(skip).limit(limit))
    return list(result.scalars().all())


# ── Budget rollup math ──────────────────────────────────────────────────────

def compute_budget_line_item_rollup(line: BudgetLineItem) -> dict:
    """Compute rollup values for a budget line item from its component fields.

    Formulas:
        revised_budget = original_budget + approved_changes
        projected_cost = committed_costs + direct_costs + pending_changes
        over_under     = revised_budget - projected_cost
    """
    original = float(line.original_budget or 0)
    approved = float(line.approved_changes or 0)
    committed = float(line.committed_costs or 0)
    direct = float(line.direct_costs or 0)
    pending = float(line.pending_changes or 0)

    revised = original + approved
    projected = committed + direct + pending
    over_under = revised - projected

    return {
        "budget_line_item_id": line.id,
        "original_budget": original,
        "approved_changes": approved,
        "committed_costs": committed,
        "direct_costs": direct,
        "pending_changes": pending,
        "revised_budget": revised,
        "projected_cost": projected,
        "over_under": over_under,
    }


async def get_budget_line_item_rollup(db: AsyncSession, line_id: UUID) -> dict:
    """Read-only rollup. Computes from stored components without persisting."""
    line = await db.get(BudgetLineItem, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Budget line item not found")
    return compute_budget_line_item_rollup(line)


async def refresh_budget_line_item_rollup(db: AsyncSession, line_id: UUID) -> BudgetLineItem:
    """Recompute and persist rollup values for a single budget line item."""
    line = await db.get(BudgetLineItem, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Budget line item not found")

    rollup = compute_budget_line_item_rollup(line)
    line.revised_budget = rollup["revised_budget"]
    line.projected_cost = rollup["projected_cost"]
    line.over_under = rollup["over_under"]

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _classify_integrity_error(e)
    await db.refresh(line)
    return line


async def refresh_budget_rollups_for_project(db: AsyncSession, project_id: UUID) -> dict:
    """Bulk-refresh all budget line items for a project."""
    result = await db.execute(
        select(BudgetLineItem).where(BudgetLineItem.project_id == project_id)
    )
    lines = list(result.scalars().all())

    updated = 0
    for line in lines:
        rollup = compute_budget_line_item_rollup(line)
        if (
            float(line.revised_budget or 0) != rollup["revised_budget"]
            or float(line.projected_cost or 0) != rollup["projected_cost"]
            or float(line.over_under or 0) != rollup["over_under"]
        ):
            line.revised_budget = rollup["revised_budget"]
            line.projected_cost = rollup["projected_cost"]
            line.over_under = rollup["over_under"]
            updated += 1

    if updated:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise _classify_integrity_error(e)

    return {
        "project_id": project_id,
        "total_line_items": len(lines),
        "updated_count": updated,
    }


# ── Billing period summaries ────────────────────────────────────────────────

async def get_billing_period_summary(db: AsyncSession, billing_period_id: UUID) -> dict:
    """Aggregate pay app metrics for a single billing period."""
    bp = await db.get(BillingPeriod, billing_period_id)
    if bp is None:
        raise HTTPException(status_code=404, detail="Billing period not found")

    result = await db.execute(
        select(PaymentApplication).where(PaymentApplication.billing_period_id == billing_period_id)
    )
    pay_apps = list(result.scalars().all())

    total_this_period = sum(float(p.this_period_amount or 0) for p in pay_apps)
    total_completed = sum(float(p.total_completed or 0) for p in pay_apps)
    total_retention_held = sum(float(p.retention_held or 0) for p in pay_apps)
    approved = [p for p in pay_apps if p.status == "approved"]
    paid = [p for p in pay_apps if p.status == "paid"]
    total_approved = sum(float(p.this_period_amount or 0) for p in approved)
    total_paid = sum(float(p.this_period_amount or 0) for p in paid)

    by_status: dict[str, int] = {}
    for p in pay_apps:
        by_status[p.status] = by_status.get(p.status, 0) + 1

    return {
        "billing_period_id": bp.id,
        "project_id": bp.project_id,
        "period_number": bp.period_number,
        "start_date": bp.start_date,
        "end_date": bp.end_date,
        "due_date": bp.due_date,
        "status": bp.status,
        "pay_app_count": len(pay_apps),
        "total_this_period_amount": total_this_period,
        "total_completed": total_completed,
        "total_retention_held": total_retention_held,
        "total_approved_amount": total_approved,
        "total_paid_amount": total_paid,
        "counts_by_status": by_status,
    }


async def get_project_billing_period_summary(db: AsyncSession, project_id: UUID) -> dict:
    """Aggregate billing period summaries across a project."""
    result = await db.execute(
        select(BillingPeriod).where(BillingPeriod.project_id == project_id)
        .order_by(BillingPeriod.period_number)
    )
    periods = list(result.scalars().all())

    period_summaries = []
    grand_total_this_period = 0.0
    grand_total_paid = 0.0
    for bp in periods:
        s = await get_billing_period_summary(db, bp.id)
        period_summaries.append(s)
        grand_total_this_period += s["total_this_period_amount"]
        grand_total_paid += s["total_paid_amount"]

    return {
        "project_id": project_id,
        "total_periods": len(periods),
        "grand_total_this_period": grand_total_this_period,
        "grand_total_paid": grand_total_paid,
        "periods": period_summaries,
    }


# ── Payment application summary ─────────────────────────────────────────────

async def get_payment_application_summary(db: AsyncSession, pay_app_id: UUID) -> dict:
    """Read-only summary including linked commitment, billing period, lien waivers."""
    pay_app = await db.get(PaymentApplication, pay_app_id)
    if pay_app is None:
        raise HTTPException(status_code=404, detail="Payment application not found")

    commitment = await db.get(Commitment, pay_app.commitment_id)
    billing_period = await db.get(BillingPeriod, pay_app.billing_period_id)

    lw_result = await db.execute(
        select(LienWaiver).where(LienWaiver.payment_application_id == pay_app_id)
    )
    lien_waivers = list(lw_result.scalars().all())
    lw_by_status: dict[str, int] = {}
    for lw in lien_waivers:
        lw_by_status[lw.status] = lw_by_status.get(lw.status, 0) + 1

    return {
        "payment_application_id": pay_app.id,
        "pay_app_number": pay_app.pay_app_number,
        "status": pay_app.status,
        "period_start": pay_app.period_start,
        "period_end": pay_app.period_end,
        "this_period_amount": float(pay_app.this_period_amount or 0),
        "total_completed": float(pay_app.total_completed or 0),
        "retention_held": float(pay_app.retention_held or 0),
        "retention_released": float(pay_app.retention_released or 0),
        "net_payment_due": float(pay_app.net_payment_due or 0),
        "submitted_date": pay_app.submitted_date,
        "approved_date": pay_app.approved_date,
        "paid_date": pay_app.paid_date,
        "commitment_id": pay_app.commitment_id,
        "commitment_number": commitment.commitment_number if commitment else None,
        "commitment_title": commitment.title if commitment else None,
        "vendor_id": commitment.vendor_id if commitment else None,
        "billing_period_id": pay_app.billing_period_id,
        "billing_period_number": billing_period.period_number if billing_period else None,
        "lien_waiver_count": len(lien_waivers),
        "lien_waivers_by_status": lw_by_status,
    }


# ── Commitment / PCO / CCO summary ──────────────────────────────────────────

async def get_commitment_summary(db: AsyncSession, commitment_id: UUID) -> dict:
    """Aggregate financial picture for a commitment including PCOs, CCOs, links."""
    commitment = await db.get(Commitment, commitment_id)
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")

    # PCOs against this commitment
    pco_result = await db.execute(
        select(PotentialChangeOrder).where(PotentialChangeOrder.commitment_id == commitment_id)
    )
    pcos = list(pco_result.scalars().all())
    pco_total = sum(float(p.amount or 0) for p in pcos)
    pco_by_status: dict[str, int] = {}
    for p in pcos:
        pco_by_status[p.status] = pco_by_status.get(p.status, 0) + 1

    # CCOs against this commitment
    cco_result = await db.execute(
        select(CommitmentChangeOrder).where(CommitmentChangeOrder.commitment_id == commitment_id)
    )
    ccos = list(cco_result.scalars().all())
    cco_total = sum(float(c.total_amount or 0) for c in ccos)
    cco_by_status: dict[str, int] = {}
    for c in ccos:
        cco_by_status[c.status] = cco_by_status.get(c.status, 0) + 1

    # Linked PCO->CCO chain count
    if pcos:
        pco_ids = [p.id for p in pcos]
        link_result = await db.execute(
            select(func.count()).select_from(PcoCcoLink).where(PcoCcoLink.pco_id.in_(pco_ids))
        )
        linked_pco_count = link_result.scalar() or 0
    else:
        linked_pco_count = 0

    # Pay apps against this commitment
    pa_result = await db.execute(
        select(func.count()).select_from(PaymentApplication)
        .where(PaymentApplication.commitment_id == commitment_id)
    )
    pay_app_count = pa_result.scalar() or 0

    return {
        "commitment_id": commitment.id,
        "commitment_number": commitment.commitment_number,
        "title": commitment.title,
        "vendor_id": commitment.vendor_id,
        "contract_type": commitment.contract_type,
        "status": commitment.status,
        "original_value": float(commitment.original_value or 0),
        "approved_cos": float(commitment.approved_cos or 0),
        "revised_value": float(commitment.revised_value or 0),
        "invoiced_to_date": float(commitment.invoiced_to_date or 0),
        "remaining_to_invoice": float(commitment.remaining_to_invoice or 0),
        "retention_held": float(commitment.retention_held or 0),
        "pco_count": len(pcos),
        "pco_total_amount": pco_total,
        "pco_counts_by_status": pco_by_status,
        "cco_count": len(ccos),
        "cco_total_amount": cco_total,
        "cco_counts_by_status": cco_by_status,
        "linked_pco_to_cco_count": linked_pco_count,
        "pay_app_count": pay_app_count,
    }

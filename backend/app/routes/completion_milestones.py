import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import (
    assert_project_write,
    enforce_project_read,
    get_current_user,
    get_readable_project_ids,
    require_admin_or_vp,
    require_authenticated_user,
)
from app.models.closeout import CompletionMilestone
from app.models.foundation import UserAccount
from app.schemas.closeout import (
    CertifyMilestoneRequest, CertifyMilestoneResponse,
    CompletionMilestoneCreate, CompletionMilestoneResponse, CompletionMilestoneUpdate,
    EvaluateEvidenceRequest, EvaluateEvidenceResponse, EvidenceChecklistResponse,
    GateEvaluationResponse,
)
from app.services import closeout as svc

log = logging.getLogger("rex.milestones")
router = APIRouter(prefix="/api/completion-milestones", tags=["completion-milestones"])

@router.get("/", response_model=list[CompletionMilestoneResponse])
async def list_completion_milestones(
    project_id: UUID | None = Query(None),
    milestone_type: str | None = Query(None),
    status: str | None = Query(None),
    is_evidence_complete: bool | None = Query(None),
    certified_by: UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    accessible = await get_readable_project_ids(db, user)
    return await svc.list_completion_milestones(
        db, project_id=project_id, milestone_type=milestone_type,
        status=status, is_evidence_complete=is_evidence_complete,
        certified_by=certified_by, skip=skip, limit=limit,
        accessible_project_ids=accessible,
    )

@router.get("/{milestone_id}", response_model=CompletionMilestoneResponse)
async def get_completion_milestone(
    milestone_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CompletionMilestone, milestone_id)
    await enforce_project_read(db, user, row.project_id)
    return row

@router.post("/", response_model=CompletionMilestoneResponse, status_code=201)
async def create_completion_milestone(
    data: CompletionMilestoneCreate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    await assert_project_write(db, user, data.project_id)
    return await svc.create(db, CompletionMilestone, data)

@router.patch("/{milestone_id}", response_model=CompletionMilestoneResponse)
async def update_completion_milestone(
    milestone_id: UUID,
    data: CompletionMilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CompletionMilestone, milestone_id)
    await assert_project_write(db, user, row.project_id)
    return await svc.update(db, CompletionMilestone, milestone_id, data)

@router.get("/{milestone_id}/evidence-checklist", response_model=EvidenceChecklistResponse)
async def get_evidence_checklist(milestone_id: UUID, db: AsyncSession = Depends(get_db)):
    return await svc.get_milestone_evidence_checklist(db, milestone_id)

@router.post("/{milestone_id}/evaluate-evidence", response_model=EvaluateEvidenceResponse)
async def evaluate_evidence(
    milestone_id: UUID,
    data: EvaluateEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    row = await svc.get_by_id(db, CompletionMilestone, milestone_id)
    await assert_project_write(db, user, row.project_id)
    milestone = await svc.evaluate_milestone_evidence(
        db, milestone_id, all_items_complete=data.all_items_complete, notes=data.notes,
    )
    return EvaluateEvidenceResponse(
        milestone_id=milestone.id,
        is_evidence_complete=milestone.is_evidence_complete,
        notes=milestone.notes,
    )

@router.post("/{milestone_id}/certify", response_model=CertifyMilestoneResponse)
async def certify_milestone(
    milestone_id: UUID,
    data: CertifyMilestoneRequest,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    milestone, evidence_warning = await svc.certify_milestone(
        db, milestone_id, certified_by=data.certified_by,
        actual_date=data.actual_date, notes=data.notes,
    )
    log.info(
        "milestone_certified user_id=%s milestone_id=%s type=%s certified_by=%s evidence_warning=%s",
        user.id, milestone.id, milestone.milestone_type, data.certified_by, bool(evidence_warning),
    )
    return CertifyMilestoneResponse(
        id=milestone.id,
        milestone_type=milestone.milestone_type,
        milestone_name=milestone.milestone_name,
        status=milestone.status,
        certified_by=milestone.certified_by,
        actual_date=milestone.actual_date,
        is_evidence_complete=milestone.is_evidence_complete,
        notes=milestone.notes,
        evidence_incomplete_warning=evidence_warning if evidence_warning else None,
    )

@router.post("/{milestone_id}/evaluate-gates", response_model=GateEvaluationResponse)
async def evaluate_gates(
    milestone_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: UserAccount = Depends(require_admin_or_vp),
):
    return await svc.evaluate_milestone_gates(db, milestone_id)

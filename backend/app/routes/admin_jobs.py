"""Admin/VP-only job inspection and run-now endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin_or_vp
from app.jobs.runner import JOB_REGISTRY, get_last_run, get_last_run_with_status, run_job_now
from app.models.foundation import JobRun, UserAccount
from app.schemas.jobs import JobRunResponse, JobStatusResponse, RunNowResponse

router = APIRouter(prefix="/api/admin", tags=["admin-jobs"])


@router.get("/jobs", response_model=list[JobStatusResponse])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    out = []
    for job in JOB_REGISTRY.values():
        last = await get_last_run(db, job.job_key)
        last_success = await get_last_run_with_status(db, job.job_key, "succeeded")
        last_failure = await get_last_run_with_status(db, job.job_key, "failed")
        out.append(JobStatusResponse(
            job_key=job.job_key,
            name=job.name,
            description=job.description,
            enabled=job.enabled,
            schedule=job.cron or (f"every {job.interval_seconds}s" if job.interval_seconds else None),
            last_run=JobRunResponse.model_validate(last) if last else None,
            last_success=JobRunResponse.model_validate(last_success) if last_success else None,
            last_failure=JobRunResponse.model_validate(last_failure) if last_failure else None,
            is_running=(last is not None and last.status == "running"),
        ))
    return out


@router.get("/job-runs", response_model=list[JobRunResponse])
async def list_job_runs(
    job_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    stmt = select(JobRun)
    if job_key:
        stmt = stmt.where(JobRun.job_key == job_key)
    stmt = stmt.order_by(JobRun.started_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/jobs/{job_key}/run", response_model=RunNowResponse)
async def run_job(
    job_key: str,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
):
    if job_key not in JOB_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown job")
    triggered, reason, run_id = await run_job_now(
        job_key, triggered_by="manual", triggered_by_user_id=user.id,
    )
    return RunNowResponse(job_key=job_key, triggered=triggered, skipped_reason=reason, run_id=run_id)

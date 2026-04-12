"""Background job runner with DB-backed run history and in-process locking."""

import logging
import os
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.foundation import JobRun

log = logging.getLogger("rex.jobs")

# In-process guard: tracks which job_keys are currently executing in this process.
# This is the primary concurrency guard for single-process deployments (dev, test, typical prod).
_RUNNING_JOBS: set[str] = set()


# A job function takes an AsyncSession and returns a summary string.
JobFunc = Callable[[AsyncSession], Awaitable[str]]


@dataclass
class JobDefinition:
    job_key: str
    name: str
    description: str
    fn: JobFunc
    enabled: bool = True
    cron: str | None = None  # apscheduler cron expression
    interval_seconds: int | None = None  # alternative to cron


JOB_REGISTRY: dict[str, JobDefinition] = {}


def register_job(
    job_key: str,
    *,
    name: str,
    description: str,
    cron: str | None = None,
    interval_seconds: int | None = None,
    enabled: bool = True,
) -> Callable[[JobFunc], JobFunc]:
    """Decorator: register a job function in the global registry."""
    def deco(fn: JobFunc) -> JobFunc:
        if job_key in JOB_REGISTRY:
            raise ValueError(f"Duplicate job_key: {job_key}")
        JOB_REGISTRY[job_key] = JobDefinition(
            job_key=job_key,
            name=name,
            description=description,
            fn=fn,
            enabled=enabled,
            cron=cron,
            interval_seconds=interval_seconds,
        )
        return fn
    return deco


async def run_job_now(
    job_key: str,
    *,
    triggered_by: str = "manual",
    triggered_by_user_id: UUID | None = None,
) -> tuple[bool, str | None, UUID | None]:
    """Execute a job. Returns (triggered, skipped_reason, run_id).

    Uses an in-process guard (_RUNNING_JOBS) as the primary concurrency
    control. This works correctly for single-process deployments (dev, test,
    typical prod). For multi-process deployments, the DB 'running' status
    provides visibility, but cross-process deduplication is best handled via
    the scheduler's coalesce+max_instances=1 config.

    Uses a fresh session so it can be called both from the scheduler and
    from HTTP handlers safely.
    """
    job = JOB_REGISTRY.get(job_key)
    if job is None:
        return False, f"Unknown job: {job_key}", None
    if not job.enabled:
        return False, "Job is disabled", None

    # In-process concurrency guard
    if job_key in _RUNNING_JOBS:
        log.info("job_skipped reason=already_running job_key=%s", job_key)
        async with async_session_factory() as session:
            run = JobRun(
                job_key=job_key,
                status="skipped",
                triggered_by=triggered_by,
                triggered_by_user_id=triggered_by_user_id,
                summary="Skipped: job already running in this process",
                finished_at=datetime.now(timezone.utc),
                duration_ms=0,
            )
            session.add(run)
            await session.commit()
            return False, "Job already running", run.id

    _RUNNING_JOBS.add(job_key)
    run_id: UUID | None = None
    try:
        # Phase 1: record "running" row
        async with async_session_factory() as session:
            run = JobRun(
                job_key=job_key,
                status="running",
                triggered_by=triggered_by,
                triggered_by_user_id=triggered_by_user_id,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id
            started = run.started_at or datetime.now(timezone.utc)

        log.info("job_started job_key=%s run_id=%s triggered_by=%s", job_key, run_id, triggered_by)

        # Phase 2: run the job function in a fresh session
        async with async_session_factory() as session:
            try:
                summary = await job.fn(session)
                await session.commit()
                finished = datetime.now(timezone.utc)
                duration = int((finished - started).total_seconds() * 1000)
                run.status = "succeeded"
                run.finished_at = finished
                run.duration_ms = duration
                run.summary = (summary or "")[:2000]
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                finished = datetime.now(timezone.utc)
                duration = int((finished - started).total_seconds() * 1000)
                tb = traceback.format_exc()
                log.error("job_failed job_key=%s run_id=%s error=%r", job_key, run_id, exc)
                run.status = "failed"
                run.finished_at = finished
                run.duration_ms = duration
                run.error_excerpt = (str(exc) + "\n\n" + tb)[:4000]

        # Phase 3: persist final status in its own session
        async with async_session_factory() as session:
            final_run = await session.get(JobRun, run_id)
            if final_run is not None:
                final_run.status = run.status
                final_run.finished_at = run.finished_at
                final_run.duration_ms = run.duration_ms
                if run.status == "succeeded":
                    final_run.summary = run.summary
                else:
                    final_run.error_excerpt = run.error_excerpt
                await session.commit()

        if run.status == "succeeded":
            log.info("job_succeeded job_key=%s run_id=%s duration_ms=%d", job_key, run_id, run.duration_ms)
        return True, None, run_id

    finally:
        _RUNNING_JOBS.discard(job_key)


# ── Scheduler bootstrap ───────────────────────────────────────────────────

_scheduler = None


def is_scheduler_enabled() -> bool:
    """Read from REX_ENABLE_SCHEDULER. Default off in test, on in prod."""
    val = os.getenv("REX_ENABLE_SCHEDULER", "").strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    return False


async def start_scheduler() -> None:
    """Boot the AsyncIOScheduler. Idempotent. Safe in dev/test/prod."""
    global _scheduler
    if not is_scheduler_enabled():
        log.info("scheduler_disabled REX_ENABLE_SCHEDULER not set")
        return
    if _scheduler is not None:
        log.info("scheduler_already_started")
        return

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        log.warning("scheduler_skipped apscheduler not installed")
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")

    for job_def in JOB_REGISTRY.values():
        if not job_def.enabled:
            continue
        if job_def.cron:
            try:
                trigger = CronTrigger.from_crontab(job_def.cron, timezone="UTC")
            except Exception as exc:  # noqa: BLE001
                log.error("scheduler_invalid_cron job_key=%s cron=%s error=%r", job_def.job_key, job_def.cron, exc)
                continue
        elif job_def.interval_seconds:
            trigger = IntervalTrigger(seconds=job_def.interval_seconds)
        else:
            continue

        async def _wrapped(jk=job_def.job_key):
            await run_job_now(jk, triggered_by="system")

        _scheduler.add_job(
            _wrapped,
            trigger=trigger,
            id=job_def.job_key,
            name=job_def.name,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    _scheduler.start()
    log.info("scheduler_started job_count=%d", len(JOB_REGISTRY))


async def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler_stopped")


# ── Last-run query helpers (used by admin endpoint) ───────────────────────

async def get_last_run(session: AsyncSession, job_key: str) -> JobRun | None:
    stmt = select(JobRun).where(JobRun.job_key == job_key).order_by(JobRun.started_at.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_last_run_with_status(session: AsyncSession, job_key: str, status: str) -> JobRun | None:
    stmt = select(JobRun).where(JobRun.job_key == job_key, JobRun.status == status).order_by(JobRun.started_at.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()

"""Background job runner with DB-backed run history and Postgres advisory locks.

Cross-instance safe: each job is protected by pg_try_advisory_xact_lock so
that two Railway instances cannot run the same job simultaneously. The lock is
transaction-scoped — held on a dedicated connection for the duration of the
job and released automatically when that transaction commits or rolls back.
No pool-leak risk; no explicit pg_advisory_unlock needed.
"""

import logging
import os
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.foundation import JobRun

log = logging.getLogger("rex.jobs")


# A job function takes an AsyncSession and returns a summary string.
JobFunc = Callable[[AsyncSession], Awaitable[str]]


def _job_lock_key(job_key: str) -> int:
    """Stable signed 32-bit int for pg_try_advisory_lock from a job_key string."""
    h = 0
    for c in job_key:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    if h >= 2**31:
        h -= 2**32
    return h


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
    """Execute a job under a Postgres transaction-level advisory lock.

    Cross-instance safe: if another Railway instance is currently running the
    same job, this call records a 'skipped' run and returns immediately. The
    lock (pg_try_advisory_xact_lock) is held for the duration of a single
    transaction on a dedicated connection and is released automatically when
    that transaction commits or rolls back — no explicit unlock needed and
    no pool-leak risk.
    """
    job = JOB_REGISTRY.get(job_key)
    if job is None:
        return False, f"Unknown job: {job_key}", None
    if not job.enabled:
        return False, "Job is disabled", None

    lock_key = _job_lock_key(job_key)

    # Use pg_try_advisory_xact_lock (transaction-scoped) so the lock is
    # released automatically when the transaction ends — whether by commit,
    # rollback, or connection loss. This avoids session-level lock leaks in
    # the connection pool: no explicit pg_advisory_unlock is needed.
    #
    # We hold an open connection (lock_conn) with an open transaction for the
    # entire job duration. The lock is held for exactly that span, then freed
    # when the transaction commits/rolls back as the context exits.
    from app.database import engine

    async with engine.connect() as lock_conn:
        async with lock_conn.begin():
            # pg_try_advisory_xact_lock is transaction-scoped: the lock is held
            # for as long as this transaction is open, and released automatically
            # when the transaction commits or rolls back. No explicit unlock
            # needed, and no pool-leak risk.
            result = await lock_conn.execute(
                sql_text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": lock_key}
            )
            acquired = bool(result.scalar())

            if not acquired:
                log.info("job_skipped reason=lock_held job_key=%s", job_key)
                # Persist the skipped run for visibility — use a separate session.
                async with async_session_factory() as session:
                    run = JobRun(
                        job_key=job_key,
                        status="skipped",
                        triggered_by=triggered_by,
                        triggered_by_user_id=triggered_by_user_id,
                        summary="Skipped: another instance holds the advisory lock",
                        finished_at=datetime.now(timezone.utc),
                        duration_ms=0,
                    )
                    session.add(run)
                    await session.commit()
                    return False, "Lock held by another runner", run.id

            # We hold the lock for the duration of this transaction context.
            run_id: UUID | None = None

            # Phase 1: record running row (separate session)
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
            final_status = "succeeded"
            final_summary = ""
            final_error = None
            async with async_session_factory() as session:
                try:
                    summary = await job.fn(session)
                    await session.commit()
                    final_summary = (summary or "")[:2000]
                except Exception as exc:  # noqa: BLE001
                    await session.rollback()
                    tb = traceback.format_exc()
                    log.error("job_failed job_key=%s run_id=%s error=%r", job_key, run_id, exc)
                    final_status = "failed"
                    final_error = (str(exc) + "\n\n" + tb)[:4000]

            finished = datetime.now(timezone.utc)
            duration = int((finished - started).total_seconds() * 1000)

            # Phase 3: persist final status (separate session)
            async with async_session_factory() as session:
                final_run = await session.get(JobRun, run_id)
                if final_run is not None:
                    final_run.status = final_status
                    final_run.finished_at = finished
                    final_run.duration_ms = duration
                    if final_status == "succeeded":
                        final_run.summary = final_summary
                    else:
                        final_run.error_excerpt = final_error
                    await session.commit()

            if final_status == "succeeded":
                log.info("job_succeeded job_key=%s run_id=%s duration_ms=%d", job_key, run_id, duration)
            # The `async with lock_conn.begin()` context commits here,
            # releasing the xact advisory lock automatically.
            return True, None, run_id


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

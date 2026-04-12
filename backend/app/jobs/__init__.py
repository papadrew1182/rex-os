"""Background job runner.

Public API:
    JOB_REGISTRY: dict mapping job_key -> JobDefinition
    register_job(): decorator to register a job
    run_job_now(db, job_key, user_id=None): manually trigger
    start_scheduler(): boot the apscheduler instance (lifespan-only)
    shutdown_scheduler(): stop it
"""
from app.jobs.runner import (
    JOB_REGISTRY,
    JobDefinition,
    register_job,
    run_job_now,
    start_scheduler,
    shutdown_scheduler,
)

# Import job definitions to trigger registration
from app.jobs import warranty_refresh  # noqa: F401
from app.jobs import insurance_refresh  # noqa: F401
from app.jobs import schedule_snapshot  # noqa: F401
from app.jobs import aging_alerts  # noqa: F401
from app.jobs import session_purge  # noqa: F401

__all__ = [
    "JOB_REGISTRY",
    "JobDefinition",
    "register_job",
    "run_job_now",
    "start_scheduler",
    "shutdown_scheduler",
]

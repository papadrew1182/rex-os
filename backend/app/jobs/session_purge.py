"""Purge expired auth sessions."""

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import register_job
from app.models.foundation import Session


@register_job(
    job_key="session_purge",
    name="Expired session purge",
    description="Delete auth sessions whose expires_at has passed.",
    cron="0 */2 * * *",  # every 2 hours
)
async def session_purge_job(db: AsyncSession) -> str:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        delete(Session).where(Session.expires_at < now).execution_options(synchronize_session=False)
    )
    return f"sessions_purged={result.rowcount}"

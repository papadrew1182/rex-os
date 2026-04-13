"""Phase 36 — Postgres advisory lock tests for the job runner.

Tests:
1. test_advisory_lock_key_stable            — _job_lock_key returns stable value
2. test_advisory_lock_acquired_on_first_run — first run succeeds (not skipped)
3. test_advisory_lock_blocks_concurrent_run — concurrent second call is skipped
4. test_advisory_lock_released_on_exception — lock released after failure; re-run works
5. test_run_now_uses_same_lock_path         — two sequential runs both succeed
"""

import asyncio
import uuid

import pytest

from app.database import async_session_factory
from app.jobs.runner import JOB_REGISTRY, _job_lock_key, register_job, run_job_now
from app.models.foundation import JobRun
from sqlalchemy import delete, select

# ── Register phase-36-specific test jobs (module-level, registry is global) ──
# Use unique keys so they never collide with the 5 production jobs.

_PH36_SLOW = "ph36_test_slow"
_PH36_FAST = "ph36_test_fast"
_PH36_FAIL = "ph36_test_fail"

_SLOW_SECONDS = 0.25  # long enough to hold the lock while the second call fires


def _safe_register(job_key, **kwargs):
    """Skip registration if already registered (e.g. test re-import)."""
    if job_key not in JOB_REGISTRY:
        register_job(job_key, **kwargs)(kwargs.pop("fn", None) or (lambda db: None))


# Register via decorator so the fn is correctly wired.
if _PH36_SLOW not in JOB_REGISTRY:
    @register_job(
        job_key=_PH36_SLOW,
        name="Phase 36 slow test",
        description="Holds lock briefly for concurrency test",
    )
    async def _ph36_slow(db):
        await asyncio.sleep(_SLOW_SECONDS)
        return "ok"

if _PH36_FAST not in JOB_REGISTRY:
    @register_job(
        job_key=_PH36_FAST,
        name="Phase 36 fast test",
        description="No-op job for basic lock test",
    )
    async def _ph36_fast(db):
        return "ok"

if _PH36_FAIL not in JOB_REGISTRY:
    @register_job(
        job_key=_PH36_FAIL,
        name="Phase 36 failing test",
        description="Always raises to test lock release on exception",
    )
    async def _ph36_fail(db):
        raise RuntimeError("intentional ph36 test failure")


# ── Helpers ────────────────────────────────────────────────────────────────

async def _cleanup(*job_keys: str) -> None:
    """Delete all JobRun rows for the given job_keys."""
    async with async_session_factory() as session:
        for jk in job_keys:
            await session.execute(delete(JobRun).where(JobRun.job_key == jk))
        await session.commit()


async def _get_runs(job_key: str) -> list[JobRun]:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(JobRun)
                .where(JobRun.job_key == job_key)
                .order_by(JobRun.started_at.asc())
            )
        ).scalars().all()
        return list(rows)


# ── 1. Stable hash ─────────────────────────────────────────────────────────

def test_advisory_lock_key_stable():
    """_job_lock_key must return the same int across repeated calls."""
    key = "warranty_refresh"
    v1 = _job_lock_key(key)
    v2 = _job_lock_key(key)
    assert v1 == v2, "Lock key is not stable across calls"
    # Must be a signed 32-bit integer
    assert isinstance(v1, int)
    assert -(2**31) <= v1 < 2**31, f"Value {v1} out of signed 32-bit range"


# ── 2. First run succeeds ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_advisory_lock_acquired_on_first_run():
    """run_job_now on a fresh job_key should succeed, not be skipped."""
    try:
        triggered, reason, run_id = await run_job_now(_PH36_FAST, triggered_by="test")
        assert triggered is True, f"Expected triggered=True, got reason={reason!r}"
        assert run_id is not None

        # Verify the persisted run has status=succeeded
        runs = await _get_runs(_PH36_FAST)
        succeeded = [r for r in runs if r.status == "succeeded"]
        assert len(succeeded) >= 1, f"No succeeded run found; runs={[(r.status, r.id) for r in runs]}"
    finally:
        await _cleanup(_PH36_FAST)


# ── 3. Concurrent second call is skipped ──────────────────────────────────

@pytest.mark.anyio
async def test_advisory_lock_blocks_concurrent_run():
    """While job 1 holds the advisory lock, a second call should be skipped."""
    try:
        # Fire the slow job as a background task
        task = asyncio.create_task(
            run_job_now(_PH36_SLOW, triggered_by="test_bg")
        )

        # Give the task a moment to acquire the lock before we race it.
        # 50 ms is enough for the lock acquisition; the job sleeps 250 ms.
        await asyncio.sleep(0.05)

        # Second call — should find the lock held and return skipped
        triggered2, reason2, run_id2 = await run_job_now(_PH36_SLOW, triggered_by="test_fg")

        # Wait for the background task to finish
        triggered1, reason1, run_id1 = await task

        # First call must have succeeded
        assert triggered1 is True, f"Background task failed: reason={reason1!r}"

        # Second call must have been skipped
        assert triggered2 is False, "Expected second call to be skipped"
        assert reason2 == "Lock held by another runner", f"Unexpected reason: {reason2!r}"
        assert run_id2 is not None, "Skipped run should still persist a JobRun row"

        # Verify the skipped run is in the DB
        runs = await _get_runs(_PH36_SLOW)
        statuses = [r.status for r in runs]
        assert "skipped" in statuses, f"Expected a skipped run; got statuses={statuses}"
        assert "succeeded" in statuses, f"Expected a succeeded run; got statuses={statuses}"
    finally:
        await _cleanup(_PH36_SLOW)


# ── 4. Lock released on exception ─────────────────────────────────────────

@pytest.mark.anyio
async def test_advisory_lock_released_on_exception():
    """After a failing job the advisory lock must be released so the next run proceeds."""
    try:
        # First run — should fail but release the lock
        triggered1, reason1, run_id1 = await run_job_now(_PH36_FAIL, triggered_by="test_1")
        assert run_id1 is not None

        # Second run — must also run (not skip), so the lock was released
        triggered2, reason2, run_id2 = await run_job_now(_PH36_FAIL, triggered_by="test_2")
        assert run_id2 is not None

        # Both runs should appear as 'failed', not 'skipped'
        runs = await _get_runs(_PH36_FAIL)
        statuses = [r.status for r in runs]
        assert "skipped" not in statuses, f"Lock was NOT released after exception; statuses={statuses}"
        failed_runs = [r for r in runs if r.status == "failed"]
        assert len(failed_runs) >= 2, f"Expected 2 failed runs, got statuses={statuses}"
    finally:
        await _cleanup(_PH36_FAIL)


# ── 5. Two sequential runs both succeed ───────────────────────────────────

@pytest.mark.anyio
async def test_run_now_uses_same_lock_path():
    """Two consecutive run_job_now calls on the fast job must both succeed."""
    try:
        t1, r1, id1 = await run_job_now(_PH36_FAST, triggered_by="seq_1")
        t2, r2, id2 = await run_job_now(_PH36_FAST, triggered_by="seq_2")

        assert t1 is True, f"First run failed: {r1!r}"
        assert t2 is True, f"Second run failed: {r2!r}"
        assert id1 != id2, "Expected distinct run_ids for sequential runs"

        runs = await _get_runs(_PH36_FAST)
        succeeded = [r for r in runs if r.status == "succeeded"]
        assert len(succeeded) >= 2, f"Expected at least 2 succeeded runs; got statuses={[r.status for r in runs]}"
    finally:
        await _cleanup(_PH36_FAST)

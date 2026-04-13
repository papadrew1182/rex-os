"""Validates that ``migrations/rex2_demo_seed.sql`` is well-formed and
actually executes against the live schema.

Phase 41 introduces the demo seed. If any column gets renamed or a CHECK
constraint drifts, we want CI to catch it the moment the seed SQL stops
matching the DDL — not on a Railway demo deploy. This test runs the seed
inside an explicit transaction and rolls back, so it never pollutes the
test DB.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.migrate import DEMO_SEED_FILE, MIGRATIONS_DIR


@pytest.mark.asyncio
async def test_demo_seed_sql_applies_cleanly_and_rolls_back():
    import db as legacy_db

    seed_path: Path = MIGRATIONS_DIR / DEMO_SEED_FILE
    assert seed_path.is_file(), f"demo seed file missing: {seed_path}"

    sql = seed_path.read_text(encoding="utf-8")
    assert "Bishop Modern" in sql or "40000000-0000-4000-a000-000000000001" in sql, (
        "demo seed no longer references the canonical Bishop Modern project"
    )

    pool = await legacy_db.get_pool()
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            # Execute the whole seed file. Any schema drift (missing column,
            # bad CHECK constraint) will raise here and fail the test.
            await conn.execute(sql)

            # Spot-check a handful of rows to confirm the seed actually
            # inserted representative data rather than no-op'ing.
            counts: dict[str, int] = {}
            for table in (
                "rex.rfis",
                "rex.punch_items",
                "rex.submittals",
                "rex.commitments",
                "rex.change_events",
                "rex.payment_applications",
                "rex.daily_logs",
                "rex.inspections",
                "rex.tasks",
                "rex.meetings",
                "rex.observations",
                "rex.safety_incidents",
                "rex.drawings",
                "rex.specifications",
                "rex.correspondence",
                "rex.photos",
                "rex.attachments",
                "rex.warranties",
                "rex.insurance_certificates",
                "rex.om_manuals",
                "rex.schedule_activities",
                "rex.schedule_constraints",
            ):
                row = await conn.fetchrow(
                    f"SELECT count(*)::int AS n FROM {table} "
                    "WHERE id::text LIKE '60000000-%'"
                )
                counts[table] = row["n"] if row else 0

            # Every target surface must get at least one representative row.
            missing = [t for t, n in counts.items() if n == 0]
            assert not missing, f"demo seed produced no rows for: {missing}"
        finally:
            # Always roll back so other tests see the truncated state the
            # session-start scrubber set up.
            await tx.rollback()

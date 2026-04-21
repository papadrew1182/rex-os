"""Local end-to-end smoke for Phase 4 Procore read path.

Wires:
- Local Rex OS dev DB (via DATABASE_URL) as the canonical write target.
- Rex App Railway DB (via REX_APP_DATABASE_URL) as the Procore source.

Steps:
 1. Ensure migration 024 is applied locally (unique constraint on rex.rfis).
 2. Seed a rex.connector_accounts row for the procore connector (or reuse).
 3. Seed a rex.connector_mappings row pointing Bishop Modern (canonical)
    at procore project_id=562949954604699 ('procore.projects', scope='procore').
 4. Call the orchestrator's sync_resource(account_id, 'rfis') — this hits
    the real Rex App DB through RexAppDbClient, lands 3 TEST RFIs in
    connector_procore.rfis_raw, and canonicalizes them into rex.rfis.
 5. Assert the data landed and print a summary.

Run from worktree root: py scripts/local_phase4_smoke.py

Cleans up after itself (delete connector_mappings + rex.rfis rows it created)
unless KEEP_SMOKE_DATA=1 is set.
"""

import asyncio
import os
import sys
from uuid import uuid4

# Make sure the backend package is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import text  # noqa: E402

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)
# Also set REX_APP_DATABASE_URL if not already set — point at the real Rex App.
if not os.environ.get("REX_APP_DATABASE_URL"):
    os.environ["REX_APP_DATABASE_URL"] = (
        "postgresql://postgres:gQRjluVUzevGsJcBPkrHHhHiwEsZxTeB@switchback.proxy.rlwy.net:19009/railway"
    )


BISHOP_CANONICAL_ID = "40000000-0000-4000-a000-000000000001"
BISHOP_PROCORE_ID = "562949954604699"


async def amain():
    from app.database import async_session_factory  # noqa: E402
    from app.services.connectors.procore.orchestrator import sync_resource  # noqa: E402
    from app.services.connectors.procore.rex_app_pool import (  # noqa: E402
        close_rex_app_pool,
    )

    # Step 1 — Ensure migration 024 exists locally.
    async with async_session_factory() as s:
        exists = await s.execute(text(
            "SELECT 1 FROM pg_constraint WHERE conname = 'rex_rfis_project_rfi_number_uniq'"
        ))
        if exists.scalar_one_or_none() is None:
            print("!! migration 024 missing — applying now")
            await s.execute(text("""
                DO $$
                BEGIN
                    ALTER TABLE rex.rfis ADD CONSTRAINT rex_rfis_project_rfi_number_uniq
                        UNIQUE (project_id, rfi_number);
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                    WHEN duplicate_table  THEN NULL;
                    WHEN unique_violation THEN RAISE NOTICE 'duplicate rows prevent constraint — dedupe first';
                END
                $$;
            """))
            await s.commit()
        else:
            print("OK migration 024 already applied locally")

    # Step 2 — Seed a procore connector_account if needed.
    async with async_session_factory() as s:
        row = (await s.execute(text("""
            SELECT a.id FROM rex.connector_accounts a
            JOIN rex.connectors c ON c.id = a.connector_id
            WHERE c.connector_key = 'procore'
            ORDER BY a.created_at DESC LIMIT 1
        """))).first()
        if row:
            account_id = row[0]
            print(f"OK using existing procore connector_account {account_id}")
        else:
            account_id = uuid4()
            procore_connector_id = (await s.execute(text(
                "SELECT id FROM rex.connectors WHERE connector_key = 'procore'"
            ))).scalar_one()
            await s.execute(text("""
                INSERT INTO rex.connector_accounts
                    (id, connector_id, label, environment, status, created_at, updated_at)
                VALUES
                    (:id, :cid, 'Phase4 Smoke Account', 'development', 'connected', now(), now())
            """), {"id": account_id, "cid": procore_connector_id})
            await s.commit()
            print(f"OK seeded new procore connector_account {account_id}")

    # Step 3 — Seed a rex.connector_mappings row for Bishop Modern.
    async with async_session_factory() as s:
        await s.execute(text("""
            INSERT INTO rex.connector_mappings
                (rex_table, rex_id, connector, external_id, source_table, synced_at)
            VALUES
                ('rex.projects', :rex_id, 'procore', :ext_id, 'procore.projects', now())
            ON CONFLICT (rex_table, connector, external_id) DO UPDATE SET
                rex_id = EXCLUDED.rex_id, synced_at = now()
        """), {"rex_id": BISHOP_CANONICAL_ID, "ext_id": BISHOP_PROCORE_ID})
        await s.commit()
        print(f"OK seeded source_link rex.projects/{BISHOP_CANONICAL_ID} <-> procore.projects/{BISHOP_PROCORE_ID}")

    # Step 4 — Run sync_resource.
    print()
    print("=== Running sync_resource(procore, rfis) ===")
    async with async_session_factory() as s:
        try:
            result = await sync_resource(s, account_id=account_id, resource_type="rfis")
            print(f"RESULT: {result}")
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {e}")
            raise
        finally:
            await close_rex_app_pool()

    # Step 5 — Assertions.
    print()
    print("=== Verifying data landed ===")
    async with async_session_factory() as s:
        raw = await s.execute(text(
            "SELECT source_id, payload->>'subject' AS subj, payload->>'status' AS st "
            "FROM connector_procore.rfis_raw WHERE account_id = :a ORDER BY source_id"
        ), {"a": account_id})
        print("connector_procore.rfis_raw:")
        for r in raw.mappings().all():
            print(f"  source_id={r['source_id']}  status={r['st']}  subject={r['subj']!r}")

        canon = await s.execute(text(
            "SELECT rfi_number, subject, status, priority, assigned_to, ball_in_court "
            "FROM rex.rfis WHERE project_id = :p ORDER BY rfi_number"
        ), {"p": BISHOP_CANONICAL_ID})
        print()
        print("rex.rfis:")
        for r in canon.mappings().all():
            print(f"  num={r['rfi_number']}  status={r['status']}  priority={r['priority']}  "
                  f"assigned_to={r['assigned_to']}  ball_in_court={r['ball_in_court']}  subject={r['subject']!r}")

        sl = await s.execute(text(
            "SELECT COUNT(*) FROM rex.connector_mappings "
            "WHERE connector='procore' AND source_table='procore.rfis'"
        ))
        print()
        print(f"rex.connector_mappings (source_table=procore.rfis): {sl.scalar_one()} rows")

        sr = await s.execute(text(
            "SELECT status, rows_fetched, rows_upserted FROM rex.sync_runs "
            "WHERE connector_account_id = :a AND resource_type='rfis' "
            "ORDER BY started_at DESC LIMIT 1"
        ), {"a": account_id})
        sr_row = sr.mappings().first()
        print(f"rex.sync_runs latest: {dict(sr_row) if sr_row else None}")

        cur = await s.execute(text(
            "SELECT cursor_value FROM rex.sync_cursors "
            "WHERE connector_account_id = :a AND resource_type='rfis'"
        ), {"a": account_id})
        print(f"rex.sync_cursors: cursor_value={cur.scalar_one_or_none()}")

    # Step 6 — Optional cleanup (default ON).
    if os.environ.get("KEEP_SMOKE_DATA") == "1":
        print()
        print("(KEEP_SMOKE_DATA=1 — skipping cleanup)")
        return

    print()
    print("=== Cleaning up smoke data ===")
    async with async_session_factory() as s:
        await s.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' AND source_table='procore.rfis'"
        ))
        await s.execute(text(
            "DELETE FROM rex.connector_mappings "
            "WHERE connector='procore' AND source_table='procore.projects' AND external_id = :e"
        ), {"e": BISHOP_PROCORE_ID})
        await s.execute(text(
            "DELETE FROM rex.rfis WHERE project_id = :p AND subject LIKE 'TEST - %'"
        ), {"p": BISHOP_CANONICAL_ID})
        await s.execute(text(
            "DELETE FROM connector_procore.rfis_raw WHERE account_id = :a"
        ), {"a": account_id})
        await s.execute(text(
            "DELETE FROM rex.sync_cursors WHERE connector_account_id = :a"
        ), {"a": account_id})
        await s.execute(text(
            "DELETE FROM rex.sync_runs WHERE connector_account_id = :a"
        ), {"a": account_id})
        await s.execute(text(
            "DELETE FROM rex.connector_accounts WHERE id = :a AND label='Phase4 Smoke Account'"
        ), {"a": account_id})
        await s.commit()
        print("OK cleaned up")


asyncio.run(amain())

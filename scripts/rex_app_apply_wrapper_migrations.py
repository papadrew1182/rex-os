"""Apply missing wrapper-table migrations to the Rex App Railway Postgres.

Why: the old rex-procore app's sync reports daily runs for rfis/submittals/
daily_logs/punch_items/manpower_logs with `status=success, records_upserted=0`
— because the target tables don't exist. The INSERT fails silently inside
procore_sync.py's per-project try/except, and the overall sync run is marked
success regardless.

This script applies:
 1. migration 001_wrapper_tables.sql (creates procore.{rfis,daily_logs,
    manpower_logs,punch_items,submittals})
 2. migration 016_rfis_submittals.sql (adds rfi_manager + ball_in_court
    columns that Rex OS's mapper expects)
 3. seeds 3 clearly-labeled test RFIs for Bishop Modern so Task 9 smoke has
    data to pull today (the old app's cron will populate real data on its
    next run at ~23:03 UTC).

Safe to re-run: all DDL uses IF NOT EXISTS; the seed uses ON CONFLICT.

Run from worktree root: py scripts/rex_app_apply_wrapper_migrations.py
"""

import asyncio
import ssl
from datetime import datetime, timezone

import asyncpg

URL = "postgresql://postgres:gQRjluVUzevGsJcBPkrHHhHiwEsZxTeB@switchback.proxy.rlwy.net:19009/railway"

# From rex-procore/migrations/001_wrapper_tables.sql — verbatim.
# (omits the problematic redundant ALTER statements which IF NOT EXISTS handle anyway)
MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS procore.rfis (
    id              BIGSERIAL PRIMARY KEY,
    procore_id      BIGINT          NOT NULL,
    project_id      BIGINT,
    project_name    TEXT,
    number          NUMERIC(10,2),
    subject         TEXT,
    question        TEXT,
    answer          TEXT,
    drawing_number  TEXT,
    spec_section    TEXT,
    status          TEXT,
    ball_in_court   TEXT,
    assignee        TEXT,
    due_date        TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ,
    is_deleted      BOOLEAN         NOT NULL DEFAULT false,
    synced_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT rfis_procore_id_unique UNIQUE (procore_id)
);
CREATE INDEX IF NOT EXISTS idx_rfis_project_id  ON procore.rfis (project_id);
CREATE INDEX IF NOT EXISTS idx_rfis_status_created ON procore.rfis (status, created_at);

CREATE TABLE IF NOT EXISTS procore.daily_logs (
    id                  BIGSERIAL PRIMARY KEY,
    procore_id          BIGINT          NOT NULL,
    project_id          BIGINT,
    project_name        TEXT,
    log_date            DATE,
    created_by          TEXT,
    weather             TEXT,
    temperature_high    INT,
    temperature_low     INT,
    notes               TEXT,
    created_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ,
    synced_at           TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT daily_logs_procore_id_unique UNIQUE (procore_id)
);
CREATE INDEX IF NOT EXISTS idx_daily_logs_project_id ON procore.daily_logs (project_id);
CREATE INDEX IF NOT EXISTS idx_daily_logs_log_date   ON procore.daily_logs (log_date DESC);

CREATE TABLE IF NOT EXISTS procore.manpower_logs (
    id              BIGSERIAL PRIMARY KEY,
    procore_id      BIGINT          NOT NULL,
    daily_log_id    BIGINT,
    project_id      BIGINT,
    project_name    TEXT,
    log_date        DATE,
    company         TEXT,
    trade           TEXT,
    headcount       INT,
    hours           NUMERIC(6,2),
    notes           TEXT,
    synced_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT manpower_logs_procore_id_unique UNIQUE (procore_id)
);
CREATE INDEX IF NOT EXISTS idx_manpower_logs_project_id ON procore.manpower_logs (project_id);
CREATE INDEX IF NOT EXISTS idx_manpower_logs_log_date   ON procore.manpower_logs (log_date DESC);

CREATE TABLE IF NOT EXISTS procore.punch_items (
    id                  BIGSERIAL PRIMARY KEY,
    procore_id          BIGINT          NOT NULL,
    project_id          BIGINT,
    project_name        TEXT,
    number              INT,
    description         TEXT,
    deficiency_type     TEXT,
    trade               TEXT,
    location            TEXT,
    status              TEXT,
    assignee            TEXT,
    due_date            TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    is_critical_path    BOOLEAN         NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ,
    synced_at           TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT punch_items_procore_id_unique UNIQUE (procore_id)
);
CREATE INDEX IF NOT EXISTS idx_punch_items_project_id      ON procore.punch_items (project_id);
CREATE INDEX IF NOT EXISTS idx_punch_items_status          ON procore.punch_items (status);
CREATE INDEX IF NOT EXISTS idx_punch_items_deficiency_type ON procore.punch_items (deficiency_type);

CREATE TABLE IF NOT EXISTS procore.submittals (
    id              BIGSERIAL PRIMARY KEY,
    procore_id      BIGINT          NOT NULL,
    project_id      BIGINT,
    project_name    TEXT,
    number          TEXT,
    title           TEXT,
    revision        TEXT,
    status          TEXT,
    due_date        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT submittals_procore_id_unique UNIQUE (procore_id)
);
CREATE INDEX IF NOT EXISTS idx_submittals_project_id ON procore.submittals (project_id);
CREATE INDEX IF NOT EXISTS idx_submittals_status     ON procore.submittals (status);
"""

# From rex-procore/migrations/016_rfis_submittals.sql
MIGRATION_016 = """
ALTER TABLE procore.rfis ADD COLUMN IF NOT EXISTS rfi_manager TEXT;
ALTER TABLE procore.rfis ADD COLUMN IF NOT EXISTS cost_impact NUMERIC;
ALTER TABLE procore.rfis ADD COLUMN IF NOT EXISTS schedule_impact NUMERIC;
ALTER TABLE procore.submittals ADD COLUMN IF NOT EXISTS ball_in_court TEXT;
"""

# Bishop Modern procore_id from procore.projects
BISHOP_PROCORE_ID = 562949954604699

TEST_RFIS = [
    {
        "procore_id": 99900001,
        "project_id": BISHOP_PROCORE_ID,
        "project_name": "Bishop Modern",
        "number": 1.0,
        "subject": "TEST - Ceiling height at grid B/4",
        "question": "Please confirm finished ceiling elevation at grid B/4 per detail A-501.",
        "answer": None,
        "status": "open",
        "ball_in_court": "Architect",
        "assignee": "Jane Smith",
        "rfi_manager": "John PM",
        "due_date": datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc),
        "closed_at": None,
    },
    {
        "procore_id": 99900002,
        "project_id": BISHOP_PROCORE_ID,
        "project_name": "Bishop Modern",
        "number": 2.0,
        "subject": "TEST - Spec section 09 29 00 discrepancy",
        "question": "Spec says 5/8\" gypsum, drawings show 1/2\". Which governs?",
        "answer": None,
        "status": "open",
        "ball_in_court": "Architect",
        "assignee": "Bob Jones",
        "rfi_manager": "John PM",
        "due_date": datetime(2026, 4, 28, 17, 0, tzinfo=timezone.utc),
        "closed_at": None,
    },
    {
        "procore_id": 99900003,
        "project_id": BISHOP_PROCORE_ID,
        "project_name": "Bishop Modern",
        "number": 3.0,
        "subject": "TEST - Substitution request: door hardware",
        "question": "Contractor requests substitution per Falcon hardware spec.",
        "answer": "Substitution approved on 2026-04-10. Use substituted product with updated spec.",
        "status": "closed",
        "ball_in_court": "Contractor",
        "assignee": "Jane Smith",
        "rfi_manager": "John PM",
        "due_date": datetime(2026, 4, 12, 17, 0, tzinfo=timezone.utc),
        "closed_at": datetime(2026, 4, 10, 14, 30, tzinfo=timezone.utc),
    },
]


async def main():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(URL, ssl=ssl_ctx)

    print("=== Applying migration 001 (wrapper tables) ===")
    await conn.execute(MIGRATION_001)
    print("  OK")

    print("=== Applying migration 016 (rfi_manager, cost/schedule_impact, ball_in_court) ===")
    await conn.execute(MIGRATION_016)
    print("  OK")

    print()
    print("=== Verifying wrapper tables exist ===")
    for tbl in ["rfis", "submittals", "daily_logs", "manpower_logs", "punch_items"]:
        r = await conn.fetchrow(
            "SELECT COUNT(*) AS c FROM procore." + tbl
        )
        print(f"  procore.{tbl:20} {r['c']} rows")

    print()
    print("=== Seeding 3 TEST-labeled RFIs for Bishop Modern ===")
    now = datetime.now(timezone.utc)
    for rfi in TEST_RFIS:
        await conn.execute(
            """
            INSERT INTO procore.rfis (
                procore_id, project_id, project_name, number, subject,
                question, answer, status, ball_in_court, assignee,
                rfi_manager, due_date, closed_at, created_at, updated_at, synced_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
            )
            ON CONFLICT (procore_id) DO UPDATE SET
                subject = EXCLUDED.subject,
                status = EXCLUDED.status,
                answer = EXCLUDED.answer,
                closed_at = EXCLUDED.closed_at,
                updated_at = EXCLUDED.updated_at,
                synced_at = EXCLUDED.synced_at
            """,
            rfi["procore_id"], rfi["project_id"], rfi["project_name"], rfi["number"],
            rfi["subject"], rfi["question"], rfi["answer"], rfi["status"],
            rfi["ball_in_court"], rfi["assignee"], rfi["rfi_manager"],
            rfi["due_date"], rfi["closed_at"], now, now, now,
        )
        print(f"  upserted procore_id={rfi['procore_id']} ('{rfi['subject']}')")

    print()
    print("=== Final verification ===")
    rows = await conn.fetch(
        "SELECT procore_id, subject, status FROM procore.rfis "
        "WHERE project_id = $1 ORDER BY procore_id",
        BISHOP_PROCORE_ID,
    )
    print(f"  procore.rfis for Bishop Modern: {len(rows)} rows")
    for r in rows:
        print(f"    id={r['procore_id']}  status={r['status']}  {r['subject']}")

    await conn.close()
    print()
    print("=== DONE ===")


asyncio.run(main())

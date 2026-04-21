"""Diagnostic script — understand why Rex App's sync reports 0 rows.

Run from worktree root: py scripts/rex_app_diagnosis.py
"""
import asyncio
import ssl
import asyncpg

URL = "postgresql://postgres:gQRjluVUzevGsJcBPkrHHhHiwEsZxTeB@switchback.proxy.rlwy.net:19009/railway"


async def main():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(URL, ssl=ssl_ctx)

    # Migration tracking?
    rows = await conn.fetch(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_name ILIKE '%migration%' OR table_name ILIKE '%schema_version%'"
    )
    print("=== migration tracking tables ===")
    for r in rows:
        print(f"  {r['table_schema']}.{r['table_name']}")

    print()
    print("=== sync_log stats per table ===")
    for tbl in ["rfis", "submittals", "daily_logs", "punch_items", "manpower_logs",
                "commitments", "tasks", "change_events", "projects", "vendors", "users",
                "photos", "productivity", "lookaheads", "incidents",
                "budget_variance_snapshots"]:
        r = await conn.fetchrow(
            "SELECT COUNT(*) AS runs, "
            "COALESCE(SUM(records_upserted),0) AS total_up, "
            "COALESCE(MAX(records_upserted),0) AS max_up, "
            "MAX(started_at) AS last_run, "
            "COUNT(*) FILTER (WHERE status='error') AS err "
            "FROM procore.sync_log WHERE table_name = $1",
            tbl,
        )
        print(f"  {tbl:30} runs={r['runs']:5}  total_up={r['total_up']:6}  "
              f"max_up={r['max_up']:4}  last={r['last_run']}  err={r['err']}")

    print()
    print("=== any sync_log rows with error_message ===")
    rows = await conn.fetch(
        "SELECT table_name, started_at, status, error_message FROM procore.sync_log "
        "WHERE error_message IS NOT NULL OR status='error' ORDER BY started_at DESC LIMIT 10"
    )
    if not rows:
        print("  (none — every run reports status=success)")
    for r in rows:
        err = (r["error_message"] or "")[:300]
        print(f"  {r['started_at']}  {r['table_name']}  {r['status']}  {err}")

    print()
    print("=== sample of RFI sync rows (last 5, any detail cols) ===")
    rows = await conn.fetch(
        "SELECT * FROM procore.sync_log WHERE table_name='rfis' "
        "ORDER BY started_at DESC LIMIT 5"
    )
    for r in rows:
        d = dict(r)
        print("  " + "  ".join(f"{k}={v!r}" for k, v in d.items() if v is not None))

    print()
    print("=== does procore.projects have a procore_id col? schema ===")
    rows = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='procore' AND table_name='projects' ORDER BY ordinal_position"
    )
    for r in rows:
        print(f"  {r['column_name']:25}  {r['data_type']}")

    print()
    print("=== procore.projects rows (company + activity) ===")
    rows = await conn.fetch(
        "SELECT procore_id, company_id, project_name, status, start_date, completion_date, updated_at, synced_at FROM procore.projects ORDER BY project_name"
    )
    for r in rows:
        print(f"  id={r['procore_id']}  company={r['company_id']}  name={r['project_name']}  "
              f"status={r['status']}  synced={r['synced_at']}")

    await conn.close()


asyncio.run(main())

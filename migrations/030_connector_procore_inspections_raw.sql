-- ============================================================
-- Migration 030 -- Phase 4 Wave 2: direct-Procore-API read sync
-- ============================================================
--
-- (1) Adds the one Procore staging table that migration 013 didn't
--     create (the other 4 Wave 2 staging tables — submittals_raw,
--     daily_logs_raw, change_events_raw, schedule_tasks_raw —
--     already exist from 013).
-- (2) Adds a per-run cursor_watermark column to rex.sync_runs so the
--     30-min scheduler can pass `updated_since` to the Procore API
--     using the MAX(cursor_watermark) of the last successful run
--     for (resource_type, connector_account_id).
--
-- Idempotent: CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS
-- and ADD COLUMN IF NOT EXISTS.
-- Depends on: 012 (rex.connector_accounts), 013 (connector_procore schema),
--            015 (rex.sync_runs).
-- ============================================================


-- 1. connector_procore.inspections_raw --------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.inspections_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    project_source_id   text NOT NULL,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_cp_inspections_raw_project
    ON connector_procore.inspections_raw (project_source_id);
CREATE INDEX IF NOT EXISTS idx_cp_inspections_raw_updated
    ON connector_procore.inspections_raw (source_updated_at DESC);


-- 2. rex.sync_runs: add per-run cursor tracking -----------------------
ALTER TABLE rex.sync_runs
    ADD COLUMN IF NOT EXISTS cursor_watermark timestamptz;

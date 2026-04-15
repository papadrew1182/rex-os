-- ============================================================
-- Migration 015 -- Sync runs, cursors, event log, source_links
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 008_source_links_sync_runs.sql
-- Real-repo slot: 015
--
-- Adds the control-plane objects that make connector sync observable
-- and replayable, plus the rex.source_links contract that every
-- canonical-entity-from-a-connector must go through.
--
-- Four pieces:
--
--   rex.sync_runs           -- one row per sync execution. Status,
--                              started/finished, counts, error.
--   rex.sync_cursors        -- per (connector_account, resource_type)
--                              pagination cursor. Updated at successful
--                              page write.
--   rex.connector_event_log -- append-only event stream for webhooks,
--                              adapter errors, status transitions.
--   rex.source_links (view) -- charter contract exposed as a view over
--                              the existing rex.connector_mappings. The
--                              underlying table is extended with
--                              source_table / project_id / metadata
--                              columns (all nullable) so the view can
--                              project a clean charter shape without
--                              breaking the phase-1-53 readers.
--
-- Idempotent: CREATE IF NOT EXISTS + CREATE OR REPLACE VIEW +
--   ALTER TABLE ADD COLUMN IF NOT EXISTS.
-- Depends on: 012 (rex.connector_accounts), rex2_canonical_ddl
--   (rex.connector_mappings), rex.projects.
-- ============================================================


-- 1. rex.sync_runs -----------------------------------------------------
-- One row per attempted sync. `resource_type` is the staging table the
-- sync targeted ('rfis', 'commitments', etc). `summary` jsonb lets
-- adapters stash whatever extra health info they want without a schema
-- change.
CREATE TABLE IF NOT EXISTS rex.sync_runs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    resource_type       text NOT NULL,
    status              text NOT NULL DEFAULT 'running'
                          CHECK (status IN ('running','succeeded','failed','cancelled')),
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,
    duration_ms         int,
    rows_fetched        int NOT NULL DEFAULT 0,
    rows_upserted       int NOT NULL DEFAULT 0,
    rows_skipped        int NOT NULL DEFAULT 0,
    error_excerpt       text,
    summary             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rex_sync_runs_account ON rex.sync_runs (connector_account_id);
CREATE INDEX IF NOT EXISTS idx_rex_sync_runs_status ON rex.sync_runs (status);
CREATE INDEX IF NOT EXISTS idx_rex_sync_runs_started ON rex.sync_runs (started_at DESC);


-- 2. rex.sync_cursors --------------------------------------------------
-- Stable per-(account, resource_type) cursor. The sync_service advances
-- it only on a successful batch write. If a sync is interrupted, the
-- next run resumes from this cursor.
CREATE TABLE IF NOT EXISTS rex.sync_cursors (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    resource_type       text NOT NULL,
    cursor_value        text,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (connector_account_id, resource_type)
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_sync_cursors_updated_at') THEN
        CREATE TRIGGER trg_rex_sync_cursors_updated_at
            BEFORE UPDATE ON rex.sync_cursors
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;


-- 3. rex.connector_event_log ------------------------------------------
-- Append-only. Webhook receipts, OAuth token refresh events, sync
-- status transitions, adapter errors. Operators read this to answer
-- "what did Procore do at 2:17am".
CREATE TABLE IF NOT EXISTS rex.connector_event_log (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id uuid REFERENCES rex.connector_accounts(id) ON DELETE SET NULL,
    event_type          text NOT NULL,
    severity            text NOT NULL DEFAULT 'info'
                          CHECK (severity IN ('debug','info','warning','error','critical')),
    message             text,
    payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rex_connector_event_log_account ON rex.connector_event_log (connector_account_id);
CREATE INDEX IF NOT EXISTS idx_rex_connector_event_log_occurred ON rex.connector_event_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_rex_connector_event_log_severity ON rex.connector_event_log (severity);


-- 4. Extend rex.connector_mappings for the source_links contract ------
-- Three new columns, all nullable, all IF NOT EXISTS. Phase 1-53 readers
-- of connector_mappings remain correct; Session 2 writers set the new
-- columns going forward.
ALTER TABLE rex.connector_mappings
    ADD COLUMN IF NOT EXISTS source_table text;
ALTER TABLE rex.connector_mappings
    ADD COLUMN IF NOT EXISTS project_id uuid REFERENCES rex.projects(id);
ALTER TABLE rex.connector_mappings
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_rex_connector_mappings_source_table
    ON rex.connector_mappings (source_table);
CREATE INDEX IF NOT EXISTS idx_rex_connector_mappings_project
    ON rex.connector_mappings (project_id);


-- 5. rex.source_links -- charter-shaped view over connector_mappings ---
-- The charter contract exposes:
--   (id, connector_key, source_table, source_id, canonical_table,
--    canonical_id, project_id, metadata)
-- with a unique constraint on (connector_key, source_table, source_id).
-- The underlying rex.connector_mappings already enforces the effective
-- equivalent via (rex_table, connector, external_id) unique — for the
-- canonical row side of that tuple, rex_table = canonical_table, and
-- the external_id + connector pair maps to (source_table, source_id)
-- where source_table is set. Legacy rows where source_table is NULL
-- fall back to rex_table.
CREATE OR REPLACE VIEW rex.source_links AS
SELECT
    cm.id                                       AS id,
    cm.connector                                AS connector_key,
    COALESCE(cm.source_table, cm.rex_table)     AS source_table,
    cm.external_id                              AS source_id,
    cm.rex_table                                AS canonical_table,
    cm.rex_id                                   AS canonical_id,
    cm.project_id                               AS project_id,
    cm.metadata                                 AS metadata,
    cm.external_url                             AS external_url,
    cm.synced_at                                AS synced_at,
    cm.created_at                               AS created_at
FROM rex.connector_mappings cm;


-- 6. rex.v_project_sources -- bridge view over source_links -----------
-- Charter name for the project-row slice of rex.connector_mappings /
-- rex.source_links. Answers "which connector account sourced this
-- project, and what is its native id there?"
-- Moved here from 010 because it depends on rex.source_links, which
-- is created above. Keeping it in 010 caused a forward-reference
-- failure on fresh databases.
CREATE OR REPLACE VIEW rex.v_project_sources AS
SELECT
    sl.id                          AS source_link_id,
    sl.connector_key               AS connector_key,
    sl.source_id                   AS external_project_id,
    sl.canonical_id                AS project_id,
    sl.external_url                AS external_url,
    sl.synced_at                   AS last_synced_at,
    sl.metadata                    AS metadata
FROM rex.source_links sl
WHERE sl.canonical_table = 'projects';

-- ============================================================
-- Migration 013 -- connector_procore schema + starter staging tables
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 006_connector_procore_stage.sql
-- Real-repo slot: 013 (charter 006 + 7)
--
-- Creates the connector_procore schema and the minimum staging tables
-- the Procore adapter needs to land raw API data before it is normalized
-- into canonical rex.* tables.
--
-- Non-negotiable rule: NO canonical product data lives in this schema.
-- Rows here are source-native, identified by source_id, with the full
-- API payload kept intact as jsonb. Normalization happens in the
-- canonical layer (rex.*) and the mapping is recorded in rex.source_links.
--
-- Every staging table has the same shape:
--   - id               uuid PK (rex-side id; not the source id)
--   - source_id        text  (Procore's native id, always as text to
--                              preserve sign/format/leading zeros)
--   - account_id       uuid  (rex.connector_accounts.id that fetched it)
--   - project_source_id text (Procore project id for scoping; null for
--                              cross-project objects like users)
--   - payload          jsonb (raw API response)
--   - fetched_at       timestamptz (when we fetched it)
--   - source_updated_at timestamptz (Procore's own updated_at if present)
--   - checksum         text (stable hash of payload for change detection)
--
-- The adapter layer deduplicates by (account_id, source_id) on upsert.
--
-- Idempotent: CREATE SCHEMA / TABLE IF NOT EXISTS.
-- Depends on: 012 (rex.connector_accounts).
-- ============================================================

CREATE SCHEMA IF NOT EXISTS connector_procore;

-- Helper: the "raw object" shape every staging table gets. Defined as a
-- macro via repeated DDL rather than inheritance so each table is
-- independently indexable and the platform stays portable.


-- 1. connector_procore.projects_raw ------------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.projects_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_cp_projects_raw_source_id ON connector_procore.projects_raw (source_id);
CREATE INDEX IF NOT EXISTS idx_cp_projects_raw_fetched ON connector_procore.projects_raw (fetched_at DESC);


-- 2. connector_procore.users_raw (global directory) --------------------
CREATE TABLE IF NOT EXISTS connector_procore.users_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_cp_users_raw_source_id ON connector_procore.users_raw (source_id);


-- 3. connector_procore.rfis_raw ----------------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.rfis_raw (
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
CREATE INDEX IF NOT EXISTS idx_cp_rfis_raw_project ON connector_procore.rfis_raw (project_source_id);
CREATE INDEX IF NOT EXISTS idx_cp_rfis_raw_updated ON connector_procore.rfis_raw (source_updated_at DESC);


-- 4. connector_procore.submittals_raw ----------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.submittals_raw (
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
CREATE INDEX IF NOT EXISTS idx_cp_submittals_raw_project ON connector_procore.submittals_raw (project_source_id);


-- 5. connector_procore.daily_logs_raw ----------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.daily_logs_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    project_source_id   text NOT NULL,
    log_date            date,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_cp_daily_logs_raw_project ON connector_procore.daily_logs_raw (project_source_id);
CREATE INDEX IF NOT EXISTS idx_cp_daily_logs_raw_date ON connector_procore.daily_logs_raw (log_date DESC);


-- 6. connector_procore.budget_line_items_raw ---------------------------
CREATE TABLE IF NOT EXISTS connector_procore.budget_line_items_raw (
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
CREATE INDEX IF NOT EXISTS idx_cp_budget_raw_project ON connector_procore.budget_line_items_raw (project_source_id);


-- 7. connector_procore.commitments_raw ---------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.commitments_raw (
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
CREATE INDEX IF NOT EXISTS idx_cp_commitments_raw_project ON connector_procore.commitments_raw (project_source_id);


-- 8. connector_procore.change_events_raw -------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.change_events_raw (
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
CREATE INDEX IF NOT EXISTS idx_cp_change_events_raw_project ON connector_procore.change_events_raw (project_source_id);


-- 9. connector_procore.schedule_tasks_raw ------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.schedule_tasks_raw (
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
CREATE INDEX IF NOT EXISTS idx_cp_schedule_tasks_raw_project ON connector_procore.schedule_tasks_raw (project_source_id);


-- 10. connector_procore.documents_raw ----------------------------------
CREATE TABLE IF NOT EXISTS connector_procore.documents_raw (
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
CREATE INDEX IF NOT EXISTS idx_cp_documents_raw_project ON connector_procore.documents_raw (project_source_id);

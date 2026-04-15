-- ============================================================
-- Migration 013 -- connector_exxir schema + starter staging tables
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 007_connector_exxir_stage.sql
-- Real-repo slot: 013
--
-- Creates the connector_exxir schema and the minimum staging tables
-- the Exxir adapter needs. Intentionally narrower than the Procore
-- staging schema because Exxir is not forced to mirror Procore
-- field-for-field at the connector layer. Normalization into the
-- canonical rex.* tables happens in the mapper, not here.
--
-- Same source-native-row shape as connector_procore:
--   id / source_id / account_id / payload jsonb / fetched_at /
--   source_updated_at / checksum, unique (account_id, source_id).
--
-- Idempotent: CREATE SCHEMA / TABLE IF NOT EXISTS.
-- Depends on: 011 (rex.connector_accounts).
-- ============================================================

CREATE SCHEMA IF NOT EXISTS connector_exxir;


CREATE TABLE IF NOT EXISTS connector_exxir.projects_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_ce_projects_raw_source_id ON connector_exxir.projects_raw (source_id);


CREATE TABLE IF NOT EXISTS connector_exxir.users_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_ce_users_raw_source_id ON connector_exxir.users_raw (source_id);


-- Exxir is an owner/operator platform. Its primary signal is financial:
-- budget roll-ups, pay-app state, capital plans. We stage those first.
CREATE TABLE IF NOT EXISTS connector_exxir.budget_line_items_raw (
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
CREATE INDEX IF NOT EXISTS idx_ce_budget_raw_project ON connector_exxir.budget_line_items_raw (project_source_id);


CREATE TABLE IF NOT EXISTS connector_exxir.commitments_raw (
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
CREATE INDEX IF NOT EXISTS idx_ce_commitments_raw_project ON connector_exxir.commitments_raw (project_source_id);


CREATE TABLE IF NOT EXISTS connector_exxir.change_events_raw (
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
CREATE INDEX IF NOT EXISTS idx_ce_change_events_raw_project ON connector_exxir.change_events_raw (project_source_id);


-- Owner-side documents: approvals, budgets, board packets.
CREATE TABLE IF NOT EXISTS connector_exxir.documents_raw (
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
CREATE INDEX IF NOT EXISTS idx_ce_documents_raw_project ON connector_exxir.documents_raw (project_source_id);


-- Owners care about milestones, not individual schedule tasks.
CREATE TABLE IF NOT EXISTS connector_exxir.schedule_milestones_raw (
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
CREATE INDEX IF NOT EXISTS idx_ce_milestones_raw_project ON connector_exxir.schedule_milestones_raw (project_source_id);

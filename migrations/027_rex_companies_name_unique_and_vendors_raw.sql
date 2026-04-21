-- ============================================================
-- Migration 027 -- Unique (name) on rex.companies + connector_procore.vendors_raw
-- ============================================================
-- Phase 4a (feat/phase4a-resource-rollout) lane, Task 4.
--
-- Two small, related DDL changes the ``vendors`` resource sync needs:
--
-- 1) Add UNIQUE (name) to rex.companies so the orchestrator's
--    INSERT ... ON CONFLICT (name) DO UPDATE in _write_vendors has a
--    matching constraint. rex2_canonical_ddl.sql declares name as
--    ``text NOT NULL`` only, no UNIQUE, so Postgres would otherwise
--    fail at plan time with "there is no unique or exclusion
--    constraint matching the ON CONFLICT specification".
--
--    Defensive behavior: if the live DB already contains multiple
--    rex.companies rows with the same ``name`` (e.g. two subs with
--    the same legal name but different locations), the ADD
--    CONSTRAINT fires unique_violation and the swallow keeps
--    migrations moving — an operator then has to resolve the
--    duplicates manually before the vendors sync can succeed on
--    that subset. The orchestrator's ON CONFLICT will still fail
--    with a clear error at sync time if the constraint never
--    landed, so we don't silently mis-stage rows.
--
-- 2) Create connector_procore.vendors_raw. Migration 013 created
--    the ten starter staging tables (projects_raw, users_raw, rfis_raw,
--    submittals_raw, daily_logs_raw, budget_line_items_raw,
--    commitments_raw, change_events_raw, schedule_tasks_raw,
--    documents_raw) but NOT vendors_raw — vendors was added to scope
--    after 013 shipped. Matches the company-level (no project_source_id)
--    shape used by projects_raw and users_raw.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS + DO $$ EXCEPTION guard on
-- the constraint add. Matches the pattern used by migrations 024/025/026.
--
-- Depends on:
--   * rex2_canonical_ddl (creates rex.companies)
--   * 013_connector_procore_stage.sql (creates connector_procore schema)
-- ============================================================

-- 1. UNIQUE (name) on rex.companies ---------------------------------------
DO $$
BEGIN
    ALTER TABLE rex.companies
        ADD CONSTRAINT rex_companies_name_uniq
        UNIQUE (name);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    -- Already present, or duplicate rows prevent the add. Both branches
    -- are defensive: duplicate_table fires if the constraint name is
    -- already taken by an index; unique_violation fires if existing
    -- rows violate uniqueness and we can't add it. Operator remediation
    -- (inspect + dedupe) is manual in either case — swallow here so
    -- migrations keep moving.
    NULL;
END $$;


-- 2. connector_procore.vendors_raw (company-level directory) --------------
CREATE TABLE IF NOT EXISTS connector_procore.vendors_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_cp_vendors_raw_source_id ON connector_procore.vendors_raw (source_id);

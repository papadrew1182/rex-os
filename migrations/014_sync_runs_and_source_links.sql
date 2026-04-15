-- ============================================================
-- Migration 014 — Sync runs, cursors, event log, source_links
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 008_source_links_sync_runs.sql
-- Real-repo slot: 014 (charter 008 + 6)
-- Scope:
--   - create rex.sync_runs, rex.sync_cursors, rex.connector_event_log
--   - evolve rex.connector_mappings by adding source_table/project_id/
--     metadata columns (all nullable, all ADD COLUMN IF NOT EXISTS)
--   - create rex.source_links view that aliases connector_mappings into
--     the charter-shaped (connector_key, source_table, source_id,
--     canonical_table, canonical_id, project_id, metadata) contract
-- Depends on: 011 (rex.connector_accounts).
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

-- ============================================================
-- Migration 012 — connector_procore schema + starter staging tables
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 006_connector_procore_stage.sql
-- Real-repo slot: 012 (charter 006 + 6)
-- Scope: CREATE SCHEMA IF NOT EXISTS connector_procore, plus the
--   minimum set of staging tables the Procore adapter needs.
--   No canonical product data lives in this schema — it holds
--   source-native identifiers and raw API snapshots.
-- Depends on: none (new schema + new tables).
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

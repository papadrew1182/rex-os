-- ============================================================
-- Migration 011 — Connector registry
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 005_connector_registry.sql
-- Real-repo slot: 011 (charter 005 + 6)
-- Scope: create rex.connectors (available connector kinds) and
--   rex.connector_accounts (configured credentials + connection state).
-- Seeds two rows in rex.connectors: 'procore' and 'exxir'.
-- Depends on: rex schema exists.
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

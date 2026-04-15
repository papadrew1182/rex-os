-- ============================================================
-- Migration 015 — Canonical core additions + view bridges
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 009_canonical_core_entities.sql
-- Real-repo slot: 015 (charter 009 + 6)
-- Scope:
--   - create rex.v_organizations, rex.v_vendors, rex.v_trade_partners
--     as companies-filtered views
--   - create rex.v_project_sources as a connector_mappings-filtered view
--   - project_locations + project_calendars creation moved to 010 so
--     this file focuses on view bridges only
-- Depends on: rex.companies, rex.connector_mappings, (10: locations).
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

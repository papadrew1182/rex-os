-- ============================================================
-- Migration 010 — Project, organization, and assignment bridges
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 004_projects_assignments_orgs.sql
-- Real-repo slot: 010 (charter 004 + 6)
-- Scope: create bridging views for the charter's canonical
--   organizations / vendors / trade_partners / project_sources names
--   that map onto the existing rex.companies + rex.project_members +
--   rex.connector_mappings tables. Also creates the net-new
--   rex.project_locations and rex.project_calendars tables.
-- Depends on: existing rex.companies, rex.project_members, rex.projects,
--   rex.connector_mappings (all from rex2_canonical_ddl).
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

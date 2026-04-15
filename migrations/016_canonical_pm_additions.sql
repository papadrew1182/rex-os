-- ============================================================
-- Migration 016 — Canonical PM additions: decisions registry
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 010_canonical_project_mgmt.sql
-- Real-repo slot: 016 (charter 010 + 6)
-- Scope: create rex.meeting_decisions and rex.pending_decisions.
--   The charter's other PM entities (rfis, submittals, tasks, meetings,
--   daily_logs, inspections, observations, punch_items) already exist
--   in rex2_canonical_ddl and do not need to be created or reshaped.
-- Depends on: rex.meetings, rex.projects, rex.people.
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

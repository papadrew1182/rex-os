-- ============================================================
-- Migration 009 — User roles, preferences, and user view bridge
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 003_users_sessions_preferences.sql
-- Real-repo slot: 009 (charter 003 + 6)
-- Scope: create rex.user_roles, rex.user_preferences, and a rex.v_users
--   view that exposes the existing rex.user_accounts in the charter-shaped
--   identity contract. Sessions and auth tables already exist in the
--   rex schema from phase 1–53; this migration does not touch them.
-- Depends on: 008 (needs rex.roles to reference).
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

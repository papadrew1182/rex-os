-- ============================================================
-- Migration 020 — Seed canonical roles, permissions, and aliases
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 023_seed_roles_actions_automations_aliases.sql
--   (Session 2 co-owns the role + alias parts only; action + automation
--    seeds belong to Session 1's lane.)
-- Real-repo slot: 020
-- Scope: INSERT the six canonical roles, the core permission strings,
--   the canonical role → permission grants, and the legacy role aliases
--   including the VP_PM → PM resolution documented in
--   baseline-reconciliation.md §6.
-- Idempotent: every INSERT uses ON CONFLICT DO NOTHING.
-- Depends on: 008 (roles, permissions, role_permissions, role_aliases).
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

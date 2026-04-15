-- ============================================================
-- Migration 008 — RBAC: roles, permissions, role_permissions, role_aliases
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 002_rbac_roles_permissions.sql
-- Real-repo slot: 008 (charter 002 + 6)
-- Scope: create the data-driven RBAC tables. See baseline-reconciliation §3.
-- Idempotent: every CREATE uses IF NOT EXISTS.
-- Depends on: 001_create_schema.sql (the rex schema must exist).
-- Content: stub in this commit; real content lands in the next commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

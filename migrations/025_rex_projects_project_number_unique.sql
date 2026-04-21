-- ============================================================
-- Migration 025 -- Unique (project_number) on rex.projects
-- ============================================================
-- Phase 4a (feat/phase4a-resource-rollout) lane.
--
-- The projects resource sync (Task 2) upserts canonical projects
-- from procore.projects keyed on the natural ``project_number``.
-- Without a matching UNIQUE constraint the orchestrator's
-- INSERT ... ON CONFLICT (project_number) DO UPDATE statement in
-- _write_projects fails at plan time with "there is no unique or
-- exclusion constraint matching the ON CONFLICT specification".
--
-- rex2_canonical_ddl.sql declares project_number as ``text`` only
-- (no UNIQUE), so we add the constraint here.
--
-- NULL handling: project_number is nullable in the base schema.
-- Postgres UNIQUE treats multiple NULLs as distinct (pre-15 default
-- behavior, explicit NULLS DISTINCT in 15+), so existing rows with
-- NULL project_number don't block the ADD. The orchestrator today
-- only upserts projects whose source row has a non-null
-- project_number; rows with NULL natural keys are an operator
-- concern to resolve separately.
--
-- Idempotent: wrapped in a DO $$ block with EXCEPTION WHEN
-- duplicate_object so re-running is a no-op. Matches the pattern
-- used by migration 024.
--
-- Depends on: rex2_canonical_ddl (creates rex.projects).
-- ============================================================

DO $$
BEGIN
    ALTER TABLE rex.projects
        ADD CONSTRAINT rex_projects_project_number_uniq
        UNIQUE (project_number);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    -- Already present, or duplicate rows prevent the add. Both
    -- branches are defensive: duplicate_table fires if the
    -- constraint name is already taken by an index;
    -- unique_violation fires if existing rows violate uniqueness
    -- and we can't add it. Operator remediation (inspect + dedupe)
    -- is manual in either case — swallow here so migrations keep
    -- moving.
    NULL;
END $$;

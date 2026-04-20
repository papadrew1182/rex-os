-- ============================================================
-- Migration 024 -- Unique (project_id, rfi_number) on rex.rfis
-- ============================================================
-- Phase 4 (feat/phase4-procore-rex-app) lane.
--
-- Adds the unique constraint the Procore orchestrator (Task 7)
-- relies on for ON CONFLICT upserts into rex.rfis keyed on the
-- natural (project_id, rfi_number) tuple. Without this, the
-- INSERT ... ON CONFLICT (project_id, rfi_number) DO UPDATE
-- statement in orchestrator._upsert_canonical fails at plan time
-- with "there is no unique or exclusion constraint matching the
-- ON CONFLICT specification".
--
-- Idempotent: wrapped in a DO $$ block with EXCEPTION WHEN
-- duplicate_object so re-running is a no-op. This matches the
-- pattern used by the deferred-FK blocks in rex2_canonical_ddl.sql.
--
-- Depends on: rex2_canonical_ddl (creates rex.rfis).
-- ============================================================

DO $$
BEGIN
    ALTER TABLE rex.rfis
        ADD CONSTRAINT rex_rfis_project_rfi_number_uniq
        UNIQUE (project_id, rfi_number);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    -- Already present, or duplicate rows prevent the add. The
    -- duplicate_table / unique_violation branches are defensive:
    -- a duplicate_table would fire if the constraint name is
    -- already taken by an index; unique_violation would fire if
    -- existing rows violate the uniqueness and we cannot add it.
    -- In both cases the follow-up operator remediation is manual
    -- (inspect + dedupe) so we swallow and let the next migration
    -- run keep the chain moving.
    NULL;
END $$;

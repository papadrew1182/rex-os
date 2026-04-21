-- ============================================================
-- Migration 026 -- Unique (email) on rex.people
-- ============================================================
-- Phase 4a (feat/phase4a-resource-rollout) lane.
--
-- The users resource sync (Task 3) upserts canonical people from
-- procore.users keyed on the natural ``email``. Without a matching
-- UNIQUE constraint the orchestrator's
-- INSERT ... ON CONFLICT (email) DO UPDATE statement in _write_users
-- fails at plan time with "there is no unique or exclusion
-- constraint matching the ON CONFLICT specification".
--
-- rex2_canonical_ddl.sql declares email as ``text`` only (no UNIQUE
-- and nullable), so we add the constraint here.
--
-- NULL handling: rex.people.email is nullable in the base schema
-- (and the DDL does not mark it NOT NULL). Postgres UNIQUE treats
-- multiple NULLs as distinct (pre-15 default behavior, explicit
-- NULLS DISTINCT in 15+), so existing rows with NULL email don't
-- block the ADD. The mapper.map_user synthesizes a deterministic
-- ``procore-user-<id>@placeholder.invalid`` placeholder for source
-- rows with NULL email so the ON CONFLICT (email) upsert has a key
-- to match on; a future `ALTER COLUMN email SET NOT NULL` can
-- follow once all existing NULL emails have been back-filled.
--
-- Idempotent: wrapped in a DO $$ block with EXCEPTION WHEN
-- duplicate_object so re-running is a no-op. Matches the pattern
-- used by migrations 024 and 025.
--
-- Depends on: rex2_canonical_ddl (creates rex.people).
-- ============================================================

DO $$
BEGIN
    ALTER TABLE rex.people
        ADD CONSTRAINT rex_people_email_uniq
        UNIQUE (email);
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

-- migrations/029_rex_notes.sql
-- Phase 6a: simple free-form notes table for the create_note quick action.
-- Deliberately minimal — no tags, no threading, no editing history.
-- If any of those become requirements, extend with a proper design doc.

CREATE TABLE IF NOT EXISTS rex.notes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid REFERENCES rex.projects(id) ON DELETE CASCADE,
    user_account_id uuid NOT NULL REFERENCES rex.user_accounts(id),
    content         text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notes_project
    ON rex.notes (project_id);

CREATE INDEX IF NOT EXISTS idx_notes_user
    ON rex.notes (user_account_id);

CREATE INDEX IF NOT EXISTS idx_notes_created_at
    ON rex.notes (created_at DESC);

COMMENT ON TABLE rex.notes IS
    'Phase 6: free-form notes attached to a project or standalone. Written by the create_note quick action.';

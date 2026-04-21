-- ============================================================
-- Migration 028 -- rex.action_queue
-- ============================================================
-- Phase 6a (feat/phase6a-commands-approvals-core) Task 1.
--
-- Every LLM tool_use invocation + classification + approval
-- lifecycle gets a row in rex.action_queue.
--
--   * Auto-pass actions land as status='auto_committed' immediately
--     (still undoable for 60s via the dismiss/undo path).
--   * Approval-required actions land as status='pending_approval'
--     and block until a valid approver resolves them
--     ('committed', 'dismissed', 'failed', or 'pending_retry').
--
-- Chat tables (rex.chat_conversations, rex.chat_messages) already
-- exist from migration 006. FK constraints are added via idempotent
-- DO blocks (same pattern as migrations 024-027) so the migration
-- does not explode if either target table is ever renamed.
--
-- Depends on:
--   * rex2_canonical_ddl (creates rex.user_accounts)
--   * 006_ai_chat_and_prompts.sql (creates rex.chat_conversations
--     and rex.chat_messages)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS rex.action_queue (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id       uuid,
    message_id            uuid,
    user_account_id       uuid NOT NULL REFERENCES rex.user_accounts(id),
    requested_by_user_id  uuid REFERENCES rex.user_accounts(id),
    tool_slug             text NOT NULL,
    tool_args             jsonb NOT NULL,
    blast_radius          jsonb NOT NULL,
    requires_approval     boolean NOT NULL,
    status                text NOT NULL CHECK (status IN (
        'auto_committed',
        'pending_approval',
        'committed',
        'dismissed',
        'undone',
        'failed',
        'pending_retry'
    )),
    approver_role         text,
    committed_at          timestamptz,
    undone_at             timestamptz,
    error_excerpt         text,
    result_payload        jsonb,
    correction_of_id      uuid REFERENCES rex.action_queue(id),
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_action_queue_status
    ON rex.action_queue (status);

CREATE INDEX IF NOT EXISTS idx_action_queue_user_pending
    ON rex.action_queue (user_account_id, status)
    WHERE status = 'pending_approval';

CREATE INDEX IF NOT EXISTS idx_action_queue_conversation
    ON rex.action_queue (conversation_id);

CREATE INDEX IF NOT EXISTS idx_action_queue_created_at
    ON rex.action_queue (created_at DESC);

COMMENT ON TABLE rex.action_queue IS
    'Phase 6: every LLM tool_use gets a row here. Auto-pass actions start as auto_committed (undoable for 60s); approval-required start as pending_approval (wait for user).';

-- ── FK constraints to chat tables (idempotent) ───────────────────────────
-- Added via DO blocks so a future rename/removal of either chat table
-- won't wedge the whole migration. Pattern matches 024-027.

DO $$
BEGIN
    ALTER TABLE rex.action_queue
        ADD CONSTRAINT action_queue_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES rex.chat_conversations(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object OR undefined_table THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE rex.action_queue
        ADD CONSTRAINT action_queue_message_fk
        FOREIGN KEY (message_id)
        REFERENCES rex.chat_messages(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object OR undefined_table THEN NULL;
END $$;

-- ── updated_at trigger ───────────────────────────────────────────────────

DROP TRIGGER IF EXISTS trg_action_queue_updated_at ON rex.action_queue;
CREATE TRIGGER trg_action_queue_updated_at
    BEFORE UPDATE ON rex.action_queue
    FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();

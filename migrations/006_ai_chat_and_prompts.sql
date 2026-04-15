-- Migration 006: AI spine — chat persistence + prompt registry
--
-- Session 1 (feat/ai-spine) lane.
--
-- Creates the tables the assistant backbone needs to persist conversations,
-- messages, and versioned prompt templates. All tables live in the `rex`
-- schema. There is deliberately only ONE conversation system here; do not
-- reintroduce the legacy `assistant_conversations` vs `chat_conversations`
-- split from rex-procore.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── chat_conversations ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rex.chat_conversations (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                uuid NOT NULL,
    title                  text NOT NULL DEFAULT 'New conversation',
    project_id             uuid NULL,
    active_action_slug     text NULL,
    page_context           jsonb NOT NULL DEFAULT '{}'::jsonb,
    conversation_metadata  jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    last_message_at        timestamptz NOT NULL DEFAULT now(),
    archived_at            timestamptz NULL
);

CREATE INDEX IF NOT EXISTS ix_chat_conversations_user_last
    ON rex.chat_conversations (user_id, last_message_at DESC)
    WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_chat_conversations_project
    ON rex.chat_conversations (project_id)
    WHERE project_id IS NOT NULL;

DROP TRIGGER IF EXISTS trg_chat_conversations_updated_at ON rex.chat_conversations;
CREATE TRIGGER trg_chat_conversations_updated_at
    BEFORE UPDATE ON rex.chat_conversations
    FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();

-- ── chat_messages ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rex.chat_messages (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     uuid NOT NULL REFERENCES rex.chat_conversations(id) ON DELETE CASCADE,
    sender_type         text NOT NULL,
    content             text NOT NULL,
    content_format      text NOT NULL DEFAULT 'markdown',
    structured_payload  jsonb NOT NULL DEFAULT '{}'::jsonb,
    citations           jsonb NOT NULL DEFAULT '[]'::jsonb,
    model_key           text NULL,
    prompt_key          text NULL,
    token_usage         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_sender_type_chk
        CHECK (sender_type IN ('user', 'assistant', 'system', 'tool'))
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_created
    ON rex.chat_messages (conversation_id, created_at);

-- ── ai_prompt_registry ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rex.ai_prompt_registry (
    prompt_key   text NOT NULL,
    version      integer NOT NULL,
    prompt_type  text NOT NULL,
    content      text NOT NULL,
    is_active    boolean NOT NULL DEFAULT false,
    metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (prompt_key, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_prompt_registry_active
    ON rex.ai_prompt_registry (prompt_key)
    WHERE is_active = true;

INSERT INTO rex.ai_prompt_registry (prompt_key, version, prompt_type, content, is_active, metadata)
VALUES
    (
        'assistant.system.base',
        1,
        'system',
        'You are Rex, a multi-connector construction operations assistant. '
        || 'You answer questions using only curated rex.v_* views. '
        || 'You respect the current user role and active project context. '
        || 'You never invent data. If you do not have a view that answers the '
        || 'question, you say so and suggest the closest supported action.',
        true,
        '{"owner": "session_1_ai_spine"}'::jsonb
    )
ON CONFLICT (prompt_key, version) DO NOTHING;

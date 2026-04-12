-- Phase 31-32: Job runner + notifications

CREATE TABLE IF NOT EXISTS rex.job_runs (
    id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    job_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','skipped')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    triggered_by TEXT NOT NULL DEFAULT 'system',  -- system|manual
    triggered_by_user_id UUID REFERENCES rex.user_accounts(id),
    summary TEXT,
    error_excerpt TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_job_runs_key_started ON rex.job_runs(job_key, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_runs_status ON rex.job_runs(status);

CREATE TABLE IF NOT EXISTS rex.notifications (
    id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    user_account_id UUID NOT NULL REFERENCES rex.user_accounts(id),
    project_id UUID REFERENCES rex.projects(id),
    domain TEXT NOT NULL CHECK (domain IN ('foundation','schedule','field_ops','financials','document_management','closeout','system')),
    notification_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','warning','critical','success')),
    title TEXT NOT NULL,
    body TEXT,
    source_type TEXT,
    source_id UUID,
    action_path TEXT,
    dedupe_key TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    email_sent_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_notif_unread ON rex.notifications(user_account_id, created_at DESC)
    WHERE read_at IS NULL AND dismissed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_notif_user ON rex.notifications(user_account_id, created_at DESC);
-- Partial unique index for dedupe: only one unresolved/non-dismissed notification per (user, dedupe_key)
CREATE UNIQUE INDEX IF NOT EXISTS uq_notif_dedupe ON rex.notifications(user_account_id, dedupe_key)
    WHERE dedupe_key IS NOT NULL AND dismissed_at IS NULL AND resolved_at IS NULL;

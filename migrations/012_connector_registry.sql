-- ============================================================
-- Migration 012 -- Connector registry
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 005_connector_registry.sql
-- Real-repo slot: 012
--
-- Data-driven connector registry + per-environment account tracking.
-- Two tables:
--
--   rex.connectors          -- registry of CONNECTOR KINDS (procore, exxir).
--   rex.connector_accounts  -- per-environment configured instances of a
--                              connector kind; holds rolling health state
--                              consumed by /api/connectors + health.
--
-- Secrets are NOT stored here. credentials_ref is an opaque pointer
-- (e.g. 'env:PROCORE_CLIENT_ID', 'vault:rex/procore/demo') resolved by
-- the adapter layer at runtime.
--
-- Idempotent: CREATE IF NOT EXISTS + ON CONFLICT DO NOTHING.
-- Depends on: 001_create_schema.sql (rex schema + set_updated_at trigger).
-- ============================================================

CREATE TABLE IF NOT EXISTS rex.connectors (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_key       text NOT NULL UNIQUE,
    label               text NOT NULL,
    description         text,
    is_enabled          boolean NOT NULL DEFAULT true,
    config_schema       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rex_connectors_is_enabled ON rex.connectors (is_enabled);


CREATE TABLE IF NOT EXISTS rex.connector_accounts (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id        uuid NOT NULL REFERENCES rex.connectors(id) ON DELETE CASCADE,
    label               text NOT NULL,
    environment         text NOT NULL DEFAULT 'production',
    status              text NOT NULL DEFAULT 'configured'
                          CHECK (status IN ('configured', 'connected', 'disconnected', 'error', 'disabled')),
    credentials_ref     text,
    config              jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_sync_at        timestamptz,
    last_success_at     timestamptz,
    last_error_at       timestamptz,
    last_error_message  text,
    is_primary          boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (connector_id, label, environment)
);

CREATE INDEX IF NOT EXISTS idx_rex_connector_accounts_connector ON rex.connector_accounts (connector_id);
CREATE INDEX IF NOT EXISTS idx_rex_connector_accounts_status ON rex.connector_accounts (status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rex_connector_accounts_primary
    ON rex.connector_accounts (connector_id, environment)
    WHERE is_primary = true;


DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_connectors_updated_at') THEN
        CREATE TRIGGER trg_rex_connectors_updated_at
            BEFORE UPDATE ON rex.connectors
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_connector_accounts_updated_at') THEN
        CREATE TRIGGER trg_rex_connector_accounts_updated_at
            BEFORE UPDATE ON rex.connector_accounts
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;


-- Seed the two canonical connector kinds.
INSERT INTO rex.connectors (id, connector_key, label, description, is_enabled)
VALUES
    ('b1000000-0000-4000-c000-000000000001', 'procore', 'Procore',
     'Procore construction management platform. Primary connector for RFIs, submittals, commitments, schedules, documents.', true),
    ('b1000000-0000-4000-c000-000000000002', 'exxir',   'Exxir',
     'Exxir owner/operator platform. First-class adapter contract but may not be connected in every environment.', true)
ON CONFLICT (connector_key) DO NOTHING;

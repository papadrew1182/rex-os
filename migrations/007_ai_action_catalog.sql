-- Migration 007: AI spine — quick action catalog table
--
-- Session 1 (feat/ai-spine) lane.
--
-- Creates the ``rex.ai_action_catalog`` table ONLY. The full 77-entry
-- seed lands in migration 008 from the canonical Python source of truth
-- at ``backend/data/quick_actions_catalog.py``.
--
-- Readiness vocabulary: live | alpha | adapter_pending | writeback_pending | blocked | disabled
-- Risk vocabulary: read_only | internal_write_low | connector_write_medium | connector_write_high
-- Canonical roles: VP | PM | GENERAL_SUPER | LEAD_SUPER | ASSISTANT_SUPER | ACCOUNTANT

CREATE TABLE IF NOT EXISTS rex.ai_action_catalog (
    slug                  text PRIMARY KEY,
    legacy_aliases        text[] NOT NULL DEFAULT '{}',
    label                 text NOT NULL,
    category              text NOT NULL,
    description           text NOT NULL,
    params_schema         jsonb NOT NULL DEFAULT '[]'::jsonb,
    risk_tier             text NOT NULL,
    readiness_state       text NOT NULL,
    required_connectors   text[] NOT NULL DEFAULT '{}',
    role_visibility       text[] NOT NULL DEFAULT '{}',
    handler_key           text NULL,
    enabled               boolean NOT NULL DEFAULT true,
    metadata              jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_action_catalog_risk_tier_chk
        CHECK (risk_tier IN (
            'read_only',
            'internal_write_low',
            'connector_write_medium',
            'connector_write_high'
        )),
    CONSTRAINT ai_action_catalog_readiness_state_chk
        CHECK (readiness_state IN (
            'live',
            'alpha',
            'adapter_pending',
            'writeback_pending',
            'blocked',
            'disabled'
        ))
);

CREATE INDEX IF NOT EXISTS ix_ai_action_catalog_legacy_aliases
    ON rex.ai_action_catalog USING gin (legacy_aliases);
CREATE INDEX IF NOT EXISTS ix_ai_action_catalog_required_connectors
    ON rex.ai_action_catalog USING gin (required_connectors);
CREATE INDEX IF NOT EXISTS ix_ai_action_catalog_role_visibility
    ON rex.ai_action_catalog USING gin (role_visibility);
CREATE INDEX IF NOT EXISTS ix_ai_action_catalog_category
    ON rex.ai_action_catalog (category);

DROP TRIGGER IF EXISTS trg_ai_action_catalog_updated_at ON rex.ai_action_catalog;
CREATE TRIGGER trg_ai_action_catalog_updated_at
    BEFORE UPDATE ON rex.ai_action_catalog
    FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();

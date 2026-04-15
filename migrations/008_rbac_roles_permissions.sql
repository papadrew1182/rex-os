-- ============================================================
-- Migration 008 — RBAC: roles, permissions, role_permissions, role_aliases
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 002_rbac_roles_permissions.sql
-- Real-repo slot: 008 (charter 002 + 6)
--
-- Creates the data-driven RBAC core. See baseline-reconciliation.md §3
-- for why the existing rex.role_templates is kept in place as a UI
-- provisioning template and not conflated with the new canonical role
-- registry.
--
-- The four tables created here are the single source of truth for
-- role identity, capability definition, role→capability grants, and
-- legacy alias mapping. Every downstream permission check must resolve
-- through this chain:
--
--   user_accounts -> user_roles (mig 009) -> role_permissions -> permissions
--
-- Idempotent: all CREATEs use IF NOT EXISTS.
-- Depends on: 001_create_schema.sql (rex schema + set_updated_at trigger).
-- ============================================================

-- ── 1. rex.roles ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rex.roles (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            text NOT NULL UNIQUE,
    display_name    text NOT NULL,
    description     text,
    is_system       boolean NOT NULL DEFAULT false,
    sort_order      int NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rex_roles_is_system ON rex.roles (is_system);


-- ── 2. rex.permissions ──────────────────────────────────────────────────
-- Capability strings, dotted namespace. Examples live in migration 020.

CREATE TABLE IF NOT EXISTS rex.permissions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            text NOT NULL UNIQUE,
    description     text,
    domain          text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rex_permissions_domain ON rex.permissions (domain);


-- ── 3. rex.role_permissions ─────────────────────────────────────────────
-- Many-to-many role -> permission grants. Composite PK prevents
-- accidental duplicate grants; re-grants are idempotent via ON CONFLICT.

CREATE TABLE IF NOT EXISTS rex.role_permissions (
    role_id         uuid NOT NULL REFERENCES rex.roles(id)        ON DELETE CASCADE,
    permission_id   uuid NOT NULL REFERENCES rex.permissions(id)  ON DELETE CASCADE,
    granted_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_id)
);


-- ── 4. rex.role_aliases ─────────────────────────────────────────────────
-- Legacy role names (from rex-procore, from user_accounts.global_role,
-- from imported config files) that must resolve to a canonical role.
-- Ambiguous aliases like VP_PM must still pick one canonical target —
-- `notes` documents the decision so it's reviewable later.

CREATE TABLE IF NOT EXISTS rex.role_aliases (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    alias               text NOT NULL,
    canonical_role_slug text NOT NULL REFERENCES rex.roles(slug) ON UPDATE CASCADE,
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (alias)
);

CREATE INDEX IF NOT EXISTS idx_rex_role_aliases_canonical ON rex.role_aliases (canonical_role_slug);


-- ── updated_at triggers ─────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_rex_roles_updated_at'
    ) THEN
        CREATE TRIGGER trg_rex_roles_updated_at
            BEFORE UPDATE ON rex.roles
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;

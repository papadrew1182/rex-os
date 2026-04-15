-- ============================================================
-- Migration 010 — User roles, preferences, and user view bridge
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 003_users_sessions_preferences.sql
-- Real-repo slot: 010 (charter 003 + 7)
--
-- Bridges the existing rex.user_accounts identity into the charter's
-- data-driven RBAC contract without renaming or reshaping user_accounts
-- itself. Creates three new objects:
--
--   rex.user_roles           — many-to-many user <-> role assignments
--   rex.user_preferences     — per-user JSONB preferences consumed by /api/me
--   rex.v_users (view)       — projects user_accounts + primary role into
--                              the charter's user shape
--
-- rex.sessions (auth tokens) already exists from phase 1-53; untouched.
--
-- Idempotent: CREATE IF NOT EXISTS + CREATE OR REPLACE VIEW.
-- Depends on: 009 (rex.roles), rex2_canonical_ddl.sql (user_accounts, people,
--   project_members), rex2_foundation_bootstrap.sql (seeded users).
-- ============================================================

-- ── 1. rex.user_roles ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rex.user_roles (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_account_id     uuid NOT NULL REFERENCES rex.user_accounts(id) ON DELETE CASCADE,
    role_id             uuid NOT NULL REFERENCES rex.roles(id)         ON DELETE CASCADE,
    is_primary          boolean NOT NULL DEFAULT false,
    granted_at          timestamptz NOT NULL DEFAULT now(),
    granted_by          uuid REFERENCES rex.people(id),
    UNIQUE (user_account_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_rex_user_roles_user ON rex.user_roles (user_account_id);
CREATE INDEX IF NOT EXISTS idx_rex_user_roles_role ON rex.user_roles (role_id);

-- Guarantee a user has at most one primary role.
CREATE UNIQUE INDEX IF NOT EXISTS uq_rex_user_roles_primary_per_user
    ON rex.user_roles (user_account_id)
    WHERE is_primary = true;


-- ── 2. rex.user_preferences ─────────────────────────────────────────────
-- Per-user JSONB bag. /api/me reads feature_flags out of this row.
CREATE TABLE IF NOT EXISTS rex.user_preferences (
    user_account_id     uuid PRIMARY KEY REFERENCES rex.user_accounts(id) ON DELETE CASCADE,
    preferences         jsonb NOT NULL DEFAULT '{}'::jsonb,
    feature_flags       jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at          timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_rex_user_preferences_updated_at'
    ) THEN
        CREATE TRIGGER trg_rex_user_preferences_updated_at
            BEFORE UPDATE ON rex.user_preferences
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;


-- ── 3. rex.v_users — charter-shaped user view ───────────────────────────
-- Read-only projection. Writes still go to the underlying tables.

CREATE OR REPLACE VIEW rex.v_users AS
SELECT
    ua.id                                                          AS id,
    ua.email                                                       AS email,
    TRIM(CONCAT_WS(' ', p.first_name, p.last_name))                AS full_name,
    p.id                                                           AS person_id,
    p.first_name                                                   AS first_name,
    p.last_name                                                    AS last_name,
    ua.is_admin                                                    AS is_admin,
    ua.is_active                                                   AS is_active,
    ua.last_login                                                  AS last_login,
    ua.global_role                                                 AS legacy_global_role,
    (
        SELECT r.slug
        FROM rex.user_roles ur
        JOIN rex.roles r ON r.id = ur.role_id
        WHERE ur.user_account_id = ua.id
          AND ur.is_primary = true
        LIMIT 1
    )                                                              AS primary_role_slug,
    COALESCE(
        (
            SELECT jsonb_agg(r.slug ORDER BY r.sort_order, r.slug)
            FROM rex.user_roles ur
            JOIN rex.roles r ON r.id = ur.role_id
            WHERE ur.user_account_id = ua.id
        ),
        '[]'::jsonb
    )                                                              AS role_slugs,
    COALESCE(up.feature_flags, '{}'::jsonb)                        AS feature_flags,
    ua.created_at                                                  AS created_at,
    ua.updated_at                                                  AS updated_at
FROM rex.user_accounts ua
LEFT JOIN rex.people          p  ON p.id = ua.person_id
LEFT JOIN rex.user_preferences up ON up.user_account_id = ua.id;


-- ── 4. rex.v_user_project_assignments — charter-shaped assignments ──────
-- Projects rex.project_members into the charter's
-- user_project_assignments contract. Read-only view.

CREATE OR REPLACE VIEW rex.v_user_project_assignments AS
SELECT
    pm.id                               AS id,
    ua.id                               AS user_account_id,
    pm.project_id                       AS project_id,
    pr.name                             AS project_name,
    pr.project_number                   AS project_number,
    pr.status                           AS project_status,
    pm.role_template_id                 AS role_template_id,
    pm.access_level                     AS access_level,
    pm.is_primary                       AS is_primary_on_project,
    pm.is_active                        AS is_active,
    pm.start_date                       AS start_date,
    pm.end_date                         AS end_date,
    pm.created_at                       AS created_at
FROM rex.project_members pm
JOIN rex.projects      pr ON pr.id = pm.project_id
JOIN rex.people        p  ON p.id = pm.person_id
LEFT JOIN rex.user_accounts ua ON ua.person_id = p.id;

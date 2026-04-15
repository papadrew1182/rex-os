-- ============================================================
-- Migration 010 -- Project, location, calendar + assignment bridges
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 004_projects_assignments_orgs.sql
-- Real-repo slot: 010
--
-- Creates two genuinely missing canonical tables
-- (rex.project_locations, rex.project_calendars) and the bridge views
-- that give the charter's canonical names (organizations, vendors,
-- trade_partners, project_sources) over existing rex tables. No new
-- storage for the bridged names — just views.
--
-- rex.projects, rex.project_members, rex.companies, rex.people,
-- rex.user_accounts all already exist from phase 1-53.
--
-- Idempotent: CREATE IF NOT EXISTS / CREATE OR REPLACE VIEW.
-- Depends on: rex2_canonical_ddl (projects, companies, project_members,
--   connector_mappings), 008 (rex.roles for the user role view).
-- ============================================================


-- 1. rex.project_locations ---------------------------------------------
-- Hierarchical location registry per project. Site -> Area -> Room.
-- Nothing in phase 1-53 provides this; punch_items.location is a free
-- text field, not a structured location.
CREATE TABLE IF NOT EXISTS rex.project_locations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    parent_id           uuid REFERENCES rex.project_locations(id) ON DELETE CASCADE,
    name                text NOT NULL,
    location_type       text NOT NULL DEFAULT 'area'
                          CHECK (location_type IN ('site','building','floor','area','room','zone','other')),
    sort_order          int NOT NULL DEFAULT 0,
    description         text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, parent_id, name)
);

CREATE INDEX IF NOT EXISTS idx_rex_project_locations_project ON rex.project_locations (project_id);
CREATE INDEX IF NOT EXISTS idx_rex_project_locations_parent ON rex.project_locations (parent_id);


-- 2. rex.project_calendars ---------------------------------------------
-- Working-days / holidays per project. Used by schedule variance views
-- to determine "two business days overdue" vs "two calendar days
-- overdue". Each project has zero or one calendar; if absent, views
-- fall back to a default 5-day work week.
CREATE TABLE IF NOT EXISTS rex.project_calendars (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    name                text NOT NULL DEFAULT 'default',
    working_days        int[] NOT NULL DEFAULT ARRAY[1,2,3,4,5],
    holidays            date[] NOT NULL DEFAULT ARRAY[]::date[],
    timezone            text NOT NULL DEFAULT 'America/Chicago',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_rex_project_calendars_project ON rex.project_calendars (project_id);


-- updated_at triggers
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_project_locations_updated_at') THEN
        CREATE TRIGGER trg_rex_project_locations_updated_at
            BEFORE UPDATE ON rex.project_locations
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_project_calendars_updated_at') THEN
        CREATE TRIGGER trg_rex_project_calendars_updated_at
            BEFORE UPDATE ON rex.project_calendars
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;


-- 3. rex.v_organizations (bridge view) ---------------------------------
-- Charter name for the subset of rex.companies that are owners or GCs.
CREATE OR REPLACE VIEW rex.v_organizations AS
SELECT
    c.id,
    c.name,
    c.company_type                AS organization_type,
    c.trade,
    c.phone,
    c.email,
    c.website,
    c.address_line1,
    c.city,
    c.state,
    c.zip,
    c.status,
    c.created_at,
    c.updated_at
FROM rex.companies c
WHERE c.company_type IN ('owner','gc','architect','engineer','consultant');


-- 4. rex.v_vendors (bridge view) ---------------------------------------
-- Charter name for subcontractors + suppliers.
CREATE OR REPLACE VIEW rex.v_vendors AS
SELECT
    c.id,
    c.name,
    c.company_type                AS vendor_type,
    c.trade,
    c.phone,
    c.email,
    c.website,
    c.license_number,
    c.insurance_expiry,
    c.insurance_carrier,
    c.bonding_capacity,
    c.status,
    c.created_at,
    c.updated_at
FROM rex.companies c
WHERE c.company_type IN ('subcontractor','supplier');


-- 5. rex.v_trade_partners (bridge view) --------------------------------
-- Charter name for subcontractors only.
CREATE OR REPLACE VIEW rex.v_trade_partners AS
SELECT
    c.id,
    c.name,
    c.trade,
    c.phone,
    c.email,
    c.license_number,
    c.insurance_expiry,
    c.insurance_carrier,
    c.bonding_capacity,
    c.status,
    c.created_at,
    c.updated_at
FROM rex.companies c
WHERE c.company_type = 'subcontractor';


-- 6. rex.v_project_sources moved to 014 (depends on rex.source_links
-- which is created there; leaving it here caused a forward-reference
-- failure on fresh databases where 010 runs before 014).


-- 7. rex.v_company_contacts (bridge view) ------------------------------
-- Charter name for people-attached-to-a-company directory surface.
CREATE OR REPLACE VIEW rex.v_company_contacts AS
SELECT
    p.id                           AS person_id,
    p.company_id                   AS company_id,
    c.name                         AS company_name,
    c.company_type                 AS company_type,
    p.first_name                   AS first_name,
    p.last_name                    AS last_name,
    TRIM(CONCAT_WS(' ', p.first_name, p.last_name)) AS full_name,
    p.title                        AS title,
    p.email                        AS email,
    p.phone                        AS phone,
    p.role_type                    AS role_type,
    p.is_active                    AS is_active
FROM rex.people p
LEFT JOIN rex.companies c ON c.id = p.company_id;

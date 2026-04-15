-- ============================================================
-- Migration 017 -- Canonical financial additions + bridge views
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 011_canonical_financials.sql
-- Real-repo slot: 017
--
-- Creates rex.procurement_items (genuinely missing) plus bridge views
-- for the charter's names that map onto existing rex tables:
--   rex.v_budgets   -- project-level rollup over rex.budget_line_items
--   rex.v_pcos      -- alias for rex.potential_change_orders
--   rex.v_pay_apps  -- alias for rex.payment_applications
--
-- Charter objects already in rex: commitments, change_events,
-- lien_waivers, billing_periods, budget_line_items.
--
-- Idempotent: CREATE IF NOT EXISTS + CREATE OR REPLACE VIEW.
-- Depends on: rex.budget_line_items, rex.potential_change_orders,
--   rex.payment_applications, rex.commitments, rex.companies,
--   rex.cost_codes, rex.projects.
-- ============================================================


-- 1. rex.procurement_items ---------------------------------------------
-- Items being procured for the project with their readiness state.
-- Used for procurement-readiness automation (charter wave 2) and for
-- the submittal-to-procurement crosswalk.
CREATE TABLE IF NOT EXISTS rex.procurement_items (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    item_number             text NOT NULL,
    description             text NOT NULL,
    spec_section            text,
    commitment_id           uuid REFERENCES rex.commitments(id),
    vendor_id               uuid REFERENCES rex.companies(id),
    cost_code_id            uuid REFERENCES rex.cost_codes(id),
    quantity                numeric,
    unit                    text,
    unit_price              numeric,
    total_amount            numeric,
    status                  text NOT NULL DEFAULT 'identified'
                              CHECK (status IN ('identified','submitted','approved',
                                                'ordered','shipped','delivered','installed','cancelled')),
    lead_time_days          int,
    required_on_site        date,
    expected_delivery       date,
    actual_delivery         date,
    submittal_id            uuid REFERENCES rex.submittals(id),
    notes                   text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, item_number)
);

CREATE INDEX IF NOT EXISTS idx_rex_procurement_items_project ON rex.procurement_items (project_id);
CREATE INDEX IF NOT EXISTS idx_rex_procurement_items_status ON rex.procurement_items (status);
CREATE INDEX IF NOT EXISTS idx_rex_procurement_items_commitment ON rex.procurement_items (commitment_id);
CREATE INDEX IF NOT EXISTS idx_rex_procurement_items_vendor ON rex.procurement_items (vendor_id);
CREATE INDEX IF NOT EXISTS idx_rex_procurement_items_delivery ON rex.procurement_items (expected_delivery);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_procurement_items_updated_at') THEN
        CREATE TRIGGER trg_rex_procurement_items_updated_at
            BEFORE UPDATE ON rex.procurement_items
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;


-- 2. rex.v_budgets (bridge view) ---------------------------------------
-- Project-level budget rollup. The storage model is
-- rex.budget_line_items per cost_code; this view aggregates back to one
-- row per project so consumers can ask "what is Tower 3's budget
-- position" without joining line items manually.
CREATE OR REPLACE VIEW rex.v_budgets AS
SELECT
    bli.project_id                        AS project_id,
    COUNT(*)                              AS line_item_count,
    SUM(bli.original_budget)              AS original_budget,
    SUM(bli.approved_changes)             AS approved_changes,
    SUM(bli.revised_budget)               AS revised_budget,
    SUM(bli.committed_costs)              AS committed_costs,
    SUM(bli.direct_costs)                 AS direct_costs,
    SUM(bli.pending_changes)              AS pending_changes,
    SUM(bli.projected_cost)               AS projected_cost,
    SUM(bli.over_under)                   AS over_under,
    MIN(bli.created_at)                   AS created_at,
    MAX(bli.updated_at)                   AS updated_at
FROM rex.budget_line_items bli
GROUP BY bli.project_id;


-- 3. rex.v_pcos (bridge view) ------------------------------------------
-- Charter name for potential_change_orders.
CREATE OR REPLACE VIEW rex.v_pcos AS
SELECT
    pco.id,
    pco.change_event_id,
    pco.commitment_id,
    pco.pco_number,
    pco.title,
    pco.status,
    pco.amount,
    pco.cost_code_id,
    pco.description,
    pco.created_by,
    pco.created_at,
    pco.updated_at
FROM rex.potential_change_orders pco;


-- 4. rex.v_pay_apps (bridge view) --------------------------------------
-- Charter name for payment_applications.
CREATE OR REPLACE VIEW rex.v_pay_apps AS
SELECT
    pa.id,
    pa.commitment_id,
    pa.billing_period_id,
    pa.pay_app_number,
    pa.status,
    pa.period_start,
    pa.period_end,
    pa.this_period_amount,
    pa.total_completed,
    pa.retention_held,
    pa.retention_released,
    pa.net_payment_due,
    pa.submitted_date,
    pa.approved_date,
    pa.paid_date,
    pa.created_by,
    pa.created_at,
    pa.updated_at
FROM rex.payment_applications pa;

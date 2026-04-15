-- ============================================================
-- Migration 017 — Canonical financial additions + view bridges
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 011_canonical_financials.sql
-- Real-repo slot: 017 (charter 011 + 6)
-- Scope:
--   - create rex.procurement_items (genuinely missing)
--   - create rex.v_budgets (rollup view over rex.budget_line_items)
--   - create rex.v_pcos alias view over rex.potential_change_orders
--   - create rex.v_pay_apps alias view over rex.payment_applications
-- The charter's other financial entities (commitments, change_events,
-- lien_waivers, billing_periods) already exist in rex2_canonical_ddl.
-- Depends on: rex.budget_line_items, rex.potential_change_orders,
--   rex.payment_applications, rex.cost_codes, rex.projects.
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;

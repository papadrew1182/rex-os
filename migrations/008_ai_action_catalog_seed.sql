-- Migration 008: AI spine — full quick-action catalog seed
--
-- Session 1 (feat/ai-spine) Work Packet C.
--
-- Forward-only idempotent bootstrap of the canonical 77-slug /
-- 80-alias quick-action catalog. The source of truth is the
-- Python list at ``backend/app/data/quick_actions_catalog.py``. Both files
-- must stay in sync. This file is REGENERATED from the Python source via
-- ``py -3 scripts/_build_catalog_migration.py`` (run from backend/).
-- Do not hand-edit the JSONB blob below.
--
-- Dedupes encoded:
--   C-5  + C-29 -> rfi_aging              (Session 3 mockCatalog parity)
--   C-8  + C-28 -> submittal_sla          (charter-required)
--   C-15 + C-60 -> monthly_owner_report   (charter-required)
--
-- Harmonization vs migration 007:
--   * daily_log_summary   category: FIELD_OPS  -> PROJECT_MGMT
--   * monthly_owner_report category: REPORTING -> EXECUTIVE
--   * morning_briefing    category: MYDAY      -> OPERATIONS
--   * scorecard_preview   category: PORTFOLIO  -> PERFORMANCE
--   * slug rename: lookahead_2week -> two_week_lookahead
--
-- Row-level idempotency: ON CONFLICT (slug) DO UPDATE SET <all fields>.
-- Running this migration on a DB that already has the full catalog is a
-- safe no-op because every field is set from EXCLUDED.

-- Step 1: rename the one pre-existing slug that was harmonized against
-- the mockCatalog and the rex-procore panels.
UPDATE rex.ai_action_catalog
   SET slug = 'two_week_lookahead'
 WHERE slug = 'lookahead_2week';

-- Step 2: bulk upsert from an inline JSONB payload. jsonb_to_recordset
-- unpacks the array into typed columns; text[] fields are materialized
-- via jsonb_array_elements_text inside the SELECT.
WITH seed AS (
    SELECT *
    FROM jsonb_to_recordset($CATALOG_SEED$
[
  {
    "slug": "budget_variance",
    "legacy_aliases": [
      "C-1"
    ],
    "label": "Budget Variance",
    "category": "FINANCIALS",
    "description": "Budget vs projected cost by cost code",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.budget_variance",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "change_event_sweep",
    "legacy_aliases": [
      "C-2"
    ],
    "label": "Change Event Sweep",
    "category": "FINANCIALS",
    "description": "Open and unpriced change events across all projects",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.change_event_sweep",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "invoice_lien_compliance",
    "legacy_aliases": [
      "C-3"
    ],
    "label": "Invoice and Lien Compliance",
    "category": "FINANCIALS",
    "description": "G703 and lien waiver compliance at a billing date",
    "params_schema": [
      {
        "name": "BILLING_DATE",
        "type": "date",
        "label": "Billing Date",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.invoice_lien_compliance",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "pco_summary_30d",
    "legacy_aliases": [
      "C-4"
    ],
    "label": "PCO Summary (30 Days)",
    "category": "FINANCIALS",
    "description": "Potential change orders created in the last 30 days",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.pco_summary_30d",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "cash_flow_forecast",
    "legacy_aliases": [
      "C-26"
    ],
    "label": "Cash Flow Forecast",
    "category": "FINANCIALS",
    "description": "90-day billing and receivables forecast",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.cash_flow_forecast",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "commitment_reconciliation",
    "legacy_aliases": [
      "C-27"
    ],
    "label": "Commitment Reconciliation",
    "category": "FINANCIALS",
    "description": "Subcontract vs billed discrepancies",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project_opt",
        "label": "Project (optional)",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.commitment_reconciliation",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "pco_pipeline_status",
    "legacy_aliases": [
      "C-30"
    ],
    "label": "PCO Pipeline Status",
    "category": "FINANCIALS",
    "description": "Open PCOs - flags 14+ days without linked CO package",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.pco_pipeline_status",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "subcontract_po_execution",
    "legacy_aliases": [
      "C-31"
    ],
    "label": "Subcontract and PO Execution",
    "category": "FINANCIALS",
    "description": "Commitment execution status - flags 30+ day delays",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.subcontract_po_execution",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "direct_cost_vs_budget",
    "legacy_aliases": [
      "C-32"
    ],
    "label": "Direct Cost vs Budget",
    "category": "FINANCIALS",
    "description": "Direct cost actuals vs budget by cost code this month",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.direct_cost_vs_budget",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "requisition_invoice_status",
    "legacy_aliases": [
      "C-33"
    ],
    "label": "Requisition / Invoice Status",
    "category": "FINANCIALS",
    "description": "Subcontract pay app status - flags past-due requisitions",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.requisition_invoice_status",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "payment_app_pipeline",
    "legacy_aliases": [
      "C-34"
    ],
    "label": "Payment App Pipeline",
    "category": "FINANCIALS",
    "description": "Prime contract owner billing pipeline",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.payment_app_pipeline",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "lien_waiver_compliance",
    "legacy_aliases": [
      "C-35"
    ],
    "label": "Lien Waiver Compliance",
    "category": "FINANCIALS",
    "description": "Lien waiver status - flags unsigned past payment date",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.lien_waiver_compliance",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "budget_variance_by_cost_code",
    "legacy_aliases": [
      "C-49"
    ],
    "label": "Budget Variance by Cost Code",
    "category": "FINANCIALS",
    "description": "Cost codes where projected exceeds revised by 10%+",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.budget_variance_by_cost_code",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "change_exposure_map",
    "legacy_aliases": [
      "C-55"
    ],
    "label": "Change Exposure Map",
    "category": "FINANCIALS",
    "description": "Change event exposure mapped to schedule phases",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.change_exposure_map",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "portfolio_cash_flow",
    "legacy_aliases": [
      "C-70"
    ],
    "label": "Portfolio Cash Flow",
    "category": "FINANCIALS",
    "description": "90-day cash flow projection across all active projects",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.portfolio_cash_flow",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "portfolio_budget_rollup",
    "legacy_aliases": [
      "C-71"
    ],
    "label": "Portfolio Budget Roll-Up",
    "category": "FINANCIALS",
    "description": "Consolidated budget vs projected vs committed across projects",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.financials.portfolio_budget_rollup",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "rfi_aging",
    "legacy_aliases": [
      "C-5",
      "C-29"
    ],
    "label": "RFI Aging",
    "category": "PROJECT_MGMT",
    "description": "Overdue RFIs across active projects with ball-in-court and cost/schedule impact",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.rfi_aging",
    "enabled": true,
    "metadata": {
      "deduped_from": [
        "C-5",
        "C-29"
      ]
    }
  },
  {
    "slug": "daily_log_summary",
    "legacy_aliases": [
      "C-6"
    ],
    "label": "Daily Log Summary",
    "category": "PROJECT_MGMT",
    "description": "Morning field briefing from yesterday's daily logs",
    "params_schema": [
      {
        "name": "YESTERDAY_DATE",
        "type": "date",
        "label": "Date",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.daily_log_summary",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "punch_list_analysis",
    "legacy_aliases": [
      "C-7"
    ],
    "label": "Punch List Analysis",
    "category": "PROJECT_MGMT",
    "description": "Top deficiency types by trade and location",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.punch_list_analysis",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "submittal_sla",
    "legacy_aliases": [
      "C-8",
      "C-28"
    ],
    "label": "Submittal SLA Check",
    "category": "PROJECT_MGMT",
    "description": "Submittals exceeding internal / A&E review SLA",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      },
      {
        "name": "MODE",
        "type": "select",
        "label": "Scope",
        "required": false,
        "options": [
          {
            "value": "internal",
            "label": "Internal review"
          },
          {
            "value": "ae",
            "label": "A&E review"
          },
          {
            "value": "both",
            "label": "Both"
          }
        ]
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.submittal_sla",
    "enabled": true,
    "metadata": {
      "deduped_from": [
        "C-8",
        "C-28"
      ]
    }
  },
  {
    "slug": "draft_rfi_response",
    "legacy_aliases": [
      "C-9"
    ],
    "label": "Draft RFI Response",
    "category": "PROJECT_MGMT",
    "description": "AI-drafted RFI response with drawing and spec references",
    "params_schema": [
      {
        "name": "RFI_NUMBER",
        "type": "text",
        "label": "RFI Number",
        "required": true
      },
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.draft_rfi_response",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "meeting_activity",
    "legacy_aliases": [
      "C-36"
    ],
    "label": "Meeting Activity",
    "category": "PROJECT_MGMT",
    "description": "Meeting frequency - flags projects with no meetings in 30 days",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.meeting_activity",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "drawing_log_status",
    "legacy_aliases": [
      "C-37"
    ],
    "label": "Drawing Log Status",
    "category": "PROJECT_MGMT",
    "description": "Drawing log by discipline - flags stale revisions",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.drawing_log_status",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "inspection_pass_fail",
    "legacy_aliases": [
      "C-38"
    ],
    "label": "Inspection Pass/Fail",
    "category": "PROJECT_MGMT",
    "description": "Inspection results - flags failures and overdue items",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.inspection_pass_fail",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "meeting_minutes_action_items",
    "legacy_aliases": [
      "C-39"
    ],
    "label": "Meeting Minutes and Action Items",
    "category": "PROJECT_MGMT",
    "description": "Open action items by project - flags meetings with unresolved items",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.meeting_minutes_action_items",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "drawing_revision_tracker",
    "legacy_aliases": [
      "C-40"
    ],
    "label": "Drawing Revision Tracker",
    "category": "PROJECT_MGMT",
    "description": "Revision activity by discipline - flags obsolete drawings",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.drawing_revision_tracker",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "form_completion_status",
    "legacy_aliases": [
      "C-41"
    ],
    "label": "Form Completion Status",
    "category": "PROJECT_MGMT",
    "description": "Open forms by project and template - flags overdue items",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.form_completion_status",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "photo_documentation_gaps",
    "legacy_aliases": [
      "C-45"
    ],
    "label": "Photo Documentation Gaps",
    "category": "PROJECT_MGMT",
    "description": "Photo counts by project - flags locations with no recent coverage",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.photo_documentation_gaps",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "specification_lookup",
    "legacy_aliases": [
      "C-46"
    ],
    "label": "Specification Lookup",
    "category": "PROJECT_MGMT",
    "description": "Spec sections by division - flags missing or incomplete coverage",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.specification_lookup",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "observation_trends",
    "legacy_aliases": [
      "C-47"
    ],
    "label": "Observation Trends",
    "category": "PROJECT_MGMT",
    "description": "Open observations by type and trade - flags overdue and repeat items",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.observation_trends",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "inspection_summary",
    "legacy_aliases": [
      "C-48"
    ],
    "label": "Inspection Summary",
    "category": "PROJECT_MGMT",
    "description": "Pass/fail rates by project and inspection type",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.inspection_summary",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "photo_intelligence_scan",
    "legacy_aliases": [
      "C-78"
    ],
    "label": "Photo Intelligence Scan",
    "category": "PROJECT_MGMT",
    "description": "AI analysis of recent job-site photos - flags safety, quality, progress",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.project_mgmt.photo_intelligence_scan",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "critical_path_delays",
    "legacy_aliases": [
      "C-10"
    ],
    "label": "Critical Path Delays",
    "category": "SCHEDULING",
    "description": "Critical path tasks behind schedule",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.scheduling.critical_path_delays",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "two_week_lookahead",
    "legacy_aliases": [
      "C-11"
    ],
    "label": "2-Week Look-Ahead",
    "category": "SCHEDULING",
    "description": "Superintendent-ready look-ahead narrative",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      },
      {
        "name": "START_DATE",
        "type": "date",
        "label": "Start",
        "required": false
      },
      {
        "name": "END_DATE",
        "type": "date",
        "label": "End",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.scheduling.two_week_lookahead",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "resource_conflicts",
    "legacy_aliases": [
      "C-12"
    ],
    "label": "Resource Conflicts",
    "category": "SCHEDULING",
    "description": "Cross-project resource overlaps, next 14 days",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.scheduling.resource_conflicts",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "schedule_variance",
    "legacy_aliases": [
      "C-42"
    ],
    "label": "Schedule Variance Report",
    "category": "SCHEDULING",
    "description": "Tasks behind schedule - flags critical path with negative float",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.scheduling.schedule_variance",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "lookahead_status",
    "legacy_aliases": [
      "C-43"
    ],
    "label": "Lookahead Status",
    "category": "SCHEDULING",
    "description": "Active lookaheads by project - flags gaps in weekly planning",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.scheduling.lookahead_status",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "field_productivity_trends",
    "legacy_aliases": [
      "C-44"
    ],
    "label": "Field Productivity Trends",
    "category": "SCHEDULING",
    "description": "Actual production quantities by crew and task code",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.scheduling.field_productivity_trends",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "enriched_lookahead",
    "legacy_aliases": [
      "C-50"
    ],
    "label": "Enriched Lookahead",
    "category": "SCHEDULING",
    "description": "Constraint-aware lookahead - flags tasks with open RFIs and pending submittals",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      },
      {
        "name": "WEEKS",
        "type": "text",
        "label": "Weeks (2/3/4/6)",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.scheduling.enriched_lookahead",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "schedule_vs_billing_check",
    "legacy_aliases": [
      "C-51"
    ],
    "label": "Schedule vs Billing Check",
    "category": "SCHEDULING",
    "description": "Compares schedule progress against billing percent",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.scheduling.schedule_vs_billing_check",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "daily_log_vs_schedule_check",
    "legacy_aliases": [
      "C-54"
    ],
    "label": "Daily Log vs Schedule Check",
    "category": "SCHEDULING",
    "description": "Trades that should be active per schedule but show no/low daily log activity",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      },
      {
        "name": "DAYS",
        "type": "text",
        "label": "Lookback days",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.scheduling.daily_log_vs_schedule_check",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "punch_milestone_risk_check",
    "legacy_aliases": [
      "C-56"
    ],
    "label": "Punch-Milestone Risk Check",
    "category": "SCHEDULING",
    "description": "Punch list closeout risk for upcoming milestones",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.scheduling.punch_milestone_risk_check",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "project_team_roster",
    "legacy_aliases": [
      "C-13"
    ],
    "label": "Project Team Roster",
    "category": "DIRECTORY",
    "description": "Active users with permission flags",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.directory.project_team_roster",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "vendor_compliance",
    "legacy_aliases": [
      "C-14"
    ],
    "label": "Vendor Compliance",
    "category": "DIRECTORY",
    "description": "Insurance status RED/YELLOW/GREEN",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.directory.vendor_compliance",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "monthly_owner_report",
    "legacy_aliases": [
      "C-15",
      "C-60"
    ],
    "label": "Monthly Owner Report",
    "category": "EXECUTIVE",
    "description": "Formal monthly owner/lender report - budget, schedule, issues, photos",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      },
      {
        "name": "REPORT_MONTH",
        "type": "month",
        "label": "Report Month",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.executive.monthly_owner_report",
    "enabled": true,
    "metadata": {
      "deduped_from": [
        "C-15",
        "C-60"
      ]
    }
  },
  {
    "slug": "portfolio_snapshot",
    "legacy_aliases": [
      "C-69"
    ],
    "label": "Portfolio Snapshot",
    "category": "EXECUTIVE",
    "description": "Cross-project portfolio view: budget health, schedule, open items, risk ratings",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP"
    ],
    "handler_key": "rex.view.executive.portfolio_snapshot",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "portfolio_vendor_rankings",
    "legacy_aliases": [
      "C-72"
    ],
    "label": "Portfolio Vendor Rankings",
    "category": "EXECUTIVE",
    "description": "Top and bottom performing vendors ranked by punch, schedule, billing compliance",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP"
    ],
    "handler_key": "rex.view.executive.portfolio_vendor_rankings",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "portfolio_trend_analysis",
    "legacy_aliases": [
      "C-73"
    ],
    "label": "Portfolio Trend Analysis",
    "category": "EXECUTIVE",
    "description": "30/60/90-day trend for key metrics: RFIs, punch, budget variance, schedule",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP"
    ],
    "handler_key": "rex.view.executive.portfolio_trend_analysis",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "risk_prediction_report",
    "legacy_aliases": [
      "C-74"
    ],
    "label": "Risk Prediction Report",
    "category": "EXECUTIVE",
    "description": "2-4 week forward-looking risk predictions",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project_opt",
        "label": "Project (optional)",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP"
    ],
    "handler_key": "rex.view.executive.risk_prediction_report",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "active_risk_dashboard",
    "legacy_aliases": [
      "C-75"
    ],
    "label": "Active Risk Dashboard",
    "category": "EXECUTIVE",
    "description": "All active risk predictions ranked by severity - CRITICAL/HIGH/MEDIUM/LOW",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project_opt",
        "label": "Project (optional)",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP"
    ],
    "handler_key": "rex.view.executive.active_risk_dashboard",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "scorecard_preview",
    "legacy_aliases": [
      "C-16"
    ],
    "label": "Scorecard Preview",
    "category": "PERFORMANCE",
    "description": "Pre-commit scores and payout projections for a quarter",
    "params_schema": [
      {
        "name": "QUARTER",
        "type": "quarter",
        "label": "Quarter",
        "required": true
      },
      {
        "name": "YEAR",
        "type": "year",
        "label": "Year",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.performance.scorecard_preview",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "milestone_bonus_status",
    "legacy_aliases": [
      "C-17"
    ],
    "label": "Milestone Bonus Status",
    "category": "PERFORMANCE",
    "description": "Bonus pipeline: earned, pending, holdback",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.performance.milestone_bonus_status",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "quarterly_review_prep",
    "legacy_aliases": [
      "C-18"
    ],
    "label": "Quarterly Review Prep",
    "category": "PERFORMANCE",
    "description": "Full evidence pack for quarterly review",
    "params_schema": [
      {
        "name": "QUARTER",
        "type": "quarter",
        "label": "Quarter",
        "required": true
      },
      {
        "name": "YEAR",
        "type": "year",
        "label": "Year",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.performance.quarterly_review_prep",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "buyout_procurement",
    "legacy_aliases": [
      "C-19"
    ],
    "label": "Buyout and Procurement",
    "category": "PROCUREMENT",
    "description": "Uncommitted scope and long-lead items",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project_opt",
        "label": "Project (optional)",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.procurement.buyout_procurement",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "schedule_health_dashboard",
    "legacy_aliases": [
      "C-20"
    ],
    "label": "Schedule Health Dashboard",
    "category": "PROCUREMENT",
    "description": "Portfolio-wide schedule health",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.procurement.schedule_health_dashboard",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "inspection_readiness",
    "legacy_aliases": [
      "C-21"
    ],
    "label": "Inspection Readiness",
    "category": "PROCUREMENT",
    "description": "Upcoming inspections and prerequisite status",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.procurement.inspection_readiness",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "procurement_readiness",
    "legacy_aliases": [
      "C-52"
    ],
    "label": "Procurement Readiness",
    "category": "PROCUREMENT",
    "description": "Upcoming task procurement status - GREEN/YELLOW/RED",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      },
      {
        "name": "WEEKS",
        "type": "text",
        "label": "Weeks ahead",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "blocked",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.procurement.procurement_readiness",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "vendor_performance_scorecard",
    "legacy_aliases": [
      "C-53"
    ],
    "label": "Vendor Performance Scorecard",
    "category": "PROCUREMENT",
    "description": "Cross-wired vendor scorecard: punch, schedule, billing, insurance",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.procurement.vendor_performance_scorecard",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "morning_briefing",
    "legacy_aliases": [
      "C-22"
    ],
    "label": "Morning Briefing",
    "category": "OPERATIONS",
    "description": "On-demand briefing with all alerts",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.operations.morning_briefing",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "weekly_agenda_generator",
    "legacy_aliases": [
      "C-23"
    ],
    "label": "Weekly Agenda Generator",
    "category": "OPERATIONS",
    "description": "Role-specific weekly meeting agenda",
    "params_schema": [
      {
        "name": "ROLE",
        "type": "role",
        "label": "Role",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.operations.weekly_agenda_generator",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "closeout_readiness",
    "legacy_aliases": [
      "C-24"
    ],
    "label": "Closeout Readiness",
    "category": "OPERATIONS",
    "description": "Closeout completeness and blocking items",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER"
    ],
    "handler_key": "rex.view.operations.closeout_readiness",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "documentation_compliance",
    "legacy_aliases": [
      "C-25"
    ],
    "label": "Documentation Compliance",
    "category": "OPERATIONS",
    "description": "Process hygiene gaps and scorecard deductions",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.operations.documentation_compliance",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "oac_briefing_packet",
    "legacy_aliases": [
      "C-57"
    ],
    "label": "OAC Briefing Packet",
    "category": "OPERATIONS",
    "description": "Pre-meeting briefing for OAC: budget, RFIs, schedule, open items",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.operations.oac_briefing_packet",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "sub_coordination_briefing",
    "legacy_aliases": [
      "C-58"
    ],
    "label": "Sub Coordination Briefing",
    "category": "OPERATIONS",
    "description": "Subcontractor coordination meeting prep",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.operations.sub_coordination_briefing",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "post_meeting_minutes",
    "legacy_aliases": [
      "C-59"
    ],
    "label": "Post-Meeting Minutes",
    "category": "OPERATIONS",
    "description": "Generate meeting minutes from an agenda - extracts decisions, action items, owners",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      },
      {
        "name": "MEETING_TYPE",
        "type": "text",
        "label": "Meeting Type",
        "required": false
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.operations.post_meeting_minutes",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "pending_decisions_log",
    "legacy_aliases": [
      "C-61"
    ],
    "label": "Pending Decisions Log",
    "category": "OPERATIONS",
    "description": "Open decisions by owner - flags items with no resolution in 7+ days",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.operations.pending_decisions_log",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "decision_escalation_report",
    "legacy_aliases": [
      "C-62"
    ],
    "label": "Decision Escalation Report",
    "category": "OPERATIONS",
    "description": "Decisions past due or approaching critical milestones",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.operations.decision_escalation_report",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "lookahead_sync_briefing",
    "legacy_aliases": [
      "C-63"
    ],
    "label": "Lookahead Sync Briefing",
    "category": "OPERATIONS",
    "description": "3-week lookahead constraint sync: vendors, RFIs, submittals, change events",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "adapter_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.operations.lookahead_sync_briefing",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "meeting_packet_history",
    "legacy_aliases": [
      "C-64"
    ],
    "label": "Meeting Packet History",
    "category": "OPERATIONS",
    "description": "All generated meeting packets for a project with attachment status",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.operations.meeting_packet_history",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "action_queue_review",
    "legacy_aliases": [
      "C-65"
    ],
    "label": "Action Queue Review",
    "category": "OPERATIONS",
    "description": "Pending write-back actions awaiting approval",
    "params_schema": [],
    "risk_tier": "connector_write_medium",
    "readiness_state": "writeback_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.operations.action_queue_review",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "writeback_log",
    "legacy_aliases": [
      "C-66"
    ],
    "label": "Write-Back Log",
    "category": "OPERATIONS",
    "description": "Recent write-back actions executed - success/failure status",
    "params_schema": [],
    "risk_tier": "connector_write_medium",
    "readiness_state": "writeback_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.operations.writeback_log",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "auto_queue_review",
    "legacy_aliases": [
      "C-67"
    ],
    "label": "Auto-Queue Review",
    "category": "OPERATIONS",
    "description": "AI-proposed actions from pattern detection - review and approve for execution",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project_opt",
        "label": "Project (optional)",
        "required": false
      }
    ],
    "risk_tier": "connector_write_medium",
    "readiness_state": "writeback_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.operations.auto_queue_review",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "command_mode",
    "legacy_aliases": [
      "C-68"
    ],
    "label": "Command Mode",
    "category": "OPERATIONS",
    "description": "Type what you want done in plain English - Rex parses it into actions",
    "params_schema": [],
    "risk_tier": "connector_write_medium",
    "readiness_state": "writeback_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.operations.command_mode",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "my_day_briefing",
    "legacy_aliases": [
      "C-76"
    ],
    "label": "My Day Briefing",
    "category": "OPERATIONS",
    "description": "Personalized daily briefing: alerts, tasks, meetings, weather, top priorities",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "live",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.operations.my_day_briefing",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "weather_impact_forecast",
    "legacy_aliases": [
      "C-77"
    ],
    "label": "Weather Impact Forecast",
    "category": "OPERATIONS",
    "description": "7-day weather forecast with work impact",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER"
    ],
    "handler_key": "rex.view.operations.weather_impact_forecast",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "sub_communication_hub",
    "legacy_aliases": [
      "C-79"
    ],
    "label": "Sub Communication Hub",
    "category": "OPERATIONS",
    "description": "Weekly status updates to active subcontractors with their project data",
    "params_schema": [
      {
        "name": "PROJECT_ID",
        "type": "project",
        "label": "Project",
        "required": true
      }
    ],
    "risk_tier": "connector_write_medium",
    "readiness_state": "writeback_pending",
    "required_connectors": [
      "procore"
    ],
    "role_visibility": [
      "VP",
      "PM"
    ],
    "handler_key": "rex.view.operations.sub_communication_hub",
    "enabled": true,
    "metadata": {}
  },
  {
    "slug": "training_status",
    "legacy_aliases": [
      "C-104"
    ],
    "label": "Training Status",
    "category": "TRAINING",
    "description": "Rex University progress and next recommended lesson",
    "params_schema": [],
    "risk_tier": "read_only",
    "readiness_state": "alpha",
    "required_connectors": [],
    "role_visibility": [
      "VP",
      "PM",
      "GENERAL_SUPER",
      "LEAD_SUPER",
      "ASSISTANT_SUPER",
      "ACCOUNTANT"
    ],
    "handler_key": "rex.view.training.training_status",
    "enabled": true,
    "metadata": {}
  }
]
$CATALOG_SEED$::jsonb) AS t(
        slug text,
        legacy_aliases jsonb,
        label text,
        category text,
        description text,
        params_schema jsonb,
        risk_tier text,
        readiness_state text,
        required_connectors jsonb,
        role_visibility jsonb,
        handler_key text,
        enabled boolean,
        metadata jsonb
    )
)
INSERT INTO rex.ai_action_catalog
    (slug, legacy_aliases, label, category, description,
     params_schema, risk_tier, readiness_state,
     required_connectors, role_visibility, handler_key,
     enabled, metadata)
SELECT
    slug,
    ARRAY(SELECT jsonb_array_elements_text(legacy_aliases)),
    label,
    category,
    description,
    params_schema,
    risk_tier,
    readiness_state,
    ARRAY(SELECT jsonb_array_elements_text(required_connectors)),
    ARRAY(SELECT jsonb_array_elements_text(role_visibility)),
    handler_key,
    enabled,
    metadata
FROM seed
ON CONFLICT (slug) DO UPDATE SET
    legacy_aliases      = EXCLUDED.legacy_aliases,
    label               = EXCLUDED.label,
    category            = EXCLUDED.category,
    description         = EXCLUDED.description,
    params_schema       = EXCLUDED.params_schema,
    risk_tier           = EXCLUDED.risk_tier,
    readiness_state     = EXCLUDED.readiness_state,
    required_connectors = EXCLUDED.required_connectors,
    role_visibility     = EXCLUDED.role_visibility,
    handler_key         = EXCLUDED.handler_key,
    enabled             = EXCLUDED.enabled,
    metadata            = EXCLUDED.metadata;

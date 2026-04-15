"""Canonical quick-action catalog — Session 1 source of truth.

Derived from ``docs/roadmaps/rex_os_quick_actions_inventory.csv`` (80
legacy ``C-*`` actions) with three dedupes applied so legacy aliases
collapse onto 77 canonical slugs:

    C-8  + C-28 -> submittal_sla          (charter-required)
    C-15 + C-60 -> monthly_owner_report   (charter-required)
    C-5  + C-29 -> rfi_aging              (Session 3 mockCatalog parity)

**This module is the machine-readable source of truth.** The SQL
bootstrap in ``migrations/008_ai_action_catalog_seed.sql`` is regenerated
from this list via ``py -3 scripts/_build_catalog_migration.py`` — if you
edit one, regenerate the other and run the tests in
``tests/test_quick_actions_catalog.py``.

Invariants enforced by tests:
* exactly 77 canonical slugs
* exactly 80 legacy aliases across all slugs
* every slug is unique
* every legacy alias is unique across the whole catalog
* every legacy alias matches ``C-[0-9]+``
* every ``role_visibility`` entry is a canonical role key
* every ``readiness_state`` is in the readiness vocabulary
* every ``risk_tier`` is in the risk vocabulary
* required dedupes are present (``C-8``/``C-28``/``C-15``/``C-60``)
"""

from __future__ import annotations

from typing import Any

# ── canonical role presets ────────────────────────────────────────────────
_R_ALL: list[str] = [
    "VP",
    "PM",
    "GENERAL_SUPER",
    "LEAD_SUPER",
    "ASSISTANT_SUPER",
    "ACCOUNTANT",
]
_R_FIELD: list[str] = ["VP", "PM", "GENERAL_SUPER", "LEAD_SUPER", "ASSISTANT_SUPER"]
_R_FIN: list[str] = ["VP", "PM", "ACCOUNTANT"]
_R_PM_LEAD: list[str] = ["VP", "PM", "GENERAL_SUPER", "LEAD_SUPER"]
_R_VP_PM: list[str] = ["VP", "PM"]
_R_VP_ONLY: list[str] = ["VP"]

# ── param presets ─────────────────────────────────────────────────────────
_P_PROJECT_REQ: list[dict[str, Any]] = [
    {"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True}
]
_P_PROJECT_OPT: list[dict[str, Any]] = [
    {"name": "PROJECT_ID", "type": "project_opt", "label": "Project (optional)", "required": False}
]
_P_NONE: list[dict[str, Any]] = []

# ── category labels used by the catalog_service category projection ──────
CATEGORY_LABELS: dict[str, str] = {
    "FINANCIALS": "Financials",
    "SCHEDULING": "Scheduling",
    "PROJECT_MGMT": "Project Management",
    "PROCUREMENT": "Procurement",
    "OPERATIONS": "Operations",
    "EXECUTIVE": "Executive",
    "DIRECTORY": "Directory",
    "PERFORMANCE": "Performance",
    "TRAINING": "Training",
}


def _entry(
    slug: str,
    aliases: list[str],
    label: str,
    category: str,
    description: str,
    params: list[dict[str, Any]],
    readiness: str,
    connectors: list[str],
    roles: list[str],
    *,
    risk: str = "read_only",
    handler: str | None = None,
    enabled: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "slug": slug,
        "legacy_aliases": list(aliases),
        "label": label,
        "category": category,
        "description": description,
        "params_schema": list(params),
        "risk_tier": risk,
        "readiness_state": readiness,
        "required_connectors": list(connectors),
        "role_visibility": list(roles),
        "handler_key": handler or f"rex.view.{category.lower()}.{slug}",
        "enabled": enabled,
        "metadata": dict(metadata or {}),
    }


QUICK_ACTIONS_CATALOG: list[dict[str, Any]] = [
    # ── FINANCIALS (16) ──────────────────────────────────────────────────
    _entry("budget_variance", ["C-1"], "Budget Variance", "FINANCIALS",
        "Budget vs projected cost by cost code",
        _P_PROJECT_REQ, "alpha", ["procore"], _R_FIN),
    _entry("change_event_sweep", ["C-2"], "Change Event Sweep", "FINANCIALS",
        "Open and unpriced change events across all projects",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("invoice_lien_compliance", ["C-3"], "Invoice and Lien Compliance", "FINANCIALS",
        "G703 and lien waiver compliance at a billing date",
        [{"name": "BILLING_DATE", "type": "date", "label": "Billing Date", "required": True}],
        "adapter_pending", ["procore"], _R_FIN),
    _entry("pco_summary_30d", ["C-4"], "PCO Summary (30 Days)", "FINANCIALS",
        "Potential change orders created in the last 30 days",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("cash_flow_forecast", ["C-26"], "Cash Flow Forecast", "FINANCIALS",
        "90-day billing and receivables forecast",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("commitment_reconciliation", ["C-27"], "Commitment Reconciliation", "FINANCIALS",
        "Subcontract vs billed discrepancies",
        _P_PROJECT_OPT, "adapter_pending", ["procore"], _R_FIN),
    _entry("pco_pipeline_status", ["C-30"], "PCO Pipeline Status", "FINANCIALS",
        "Open PCOs - flags 14+ days without linked CO package",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("subcontract_po_execution", ["C-31"], "Subcontract and PO Execution", "FINANCIALS",
        "Commitment execution status - flags 30+ day delays",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("direct_cost_vs_budget", ["C-32"], "Direct Cost vs Budget", "FINANCIALS",
        "Direct cost actuals vs budget by cost code this month",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("requisition_invoice_status", ["C-33"], "Requisition / Invoice Status", "FINANCIALS",
        "Subcontract pay app status - flags past-due requisitions",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("payment_app_pipeline", ["C-34"], "Payment App Pipeline", "FINANCIALS",
        "Prime contract owner billing pipeline",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("lien_waiver_compliance", ["C-35"], "Lien Waiver Compliance", "FINANCIALS",
        "Lien waiver status - flags unsigned past payment date",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("budget_variance_by_cost_code", ["C-49"], "Budget Variance by Cost Code", "FINANCIALS",
        "Cost codes where projected exceeds revised by 10%+",
        _P_NONE, "adapter_pending", ["procore"], _R_FIN),
    _entry("change_exposure_map", ["C-55"], "Change Exposure Map", "FINANCIALS",
        "Change event exposure mapped to schedule phases",
        _P_PROJECT_REQ, "adapter_pending", ["procore"], _R_FIN),
    _entry("portfolio_cash_flow", ["C-70"], "Portfolio Cash Flow", "FINANCIALS",
        "90-day cash flow projection across all active projects",
        _P_NONE, "alpha", ["procore"], _R_FIN),
    _entry("portfolio_budget_rollup", ["C-71"], "Portfolio Budget Roll-Up", "FINANCIALS",
        "Consolidated budget vs projected vs committed across projects",
        _P_NONE, "alpha", ["procore"], _R_FIN),

    # ── PROJECT_MGMT (16 canonical, 18 aliases) ─────────────────────────
    _entry("rfi_aging", ["C-5", "C-29"], "RFI Aging", "PROJECT_MGMT",
        "Overdue RFIs across active projects with ball-in-court and cost/schedule impact",
        _P_NONE, "alpha", ["procore"], _R_FIELD,
        metadata={"deduped_from": ["C-5", "C-29"]}),
    _entry("daily_log_summary", ["C-6"], "Daily Log Summary", "PROJECT_MGMT",
        "Morning field briefing from yesterday's daily logs",
        [{"name": "YESTERDAY_DATE", "type": "date", "label": "Date", "required": False}],
        "alpha", ["procore"], _R_FIELD),
    _entry("punch_list_analysis", ["C-7"], "Punch List Analysis", "PROJECT_MGMT",
        "Top deficiency types by trade and location",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("submittal_sla", ["C-8", "C-28"], "Submittal SLA Check", "PROJECT_MGMT",
        "Submittals exceeding internal / A&E review SLA",
        [{"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True},
         {"name": "MODE", "type": "select", "label": "Scope", "required": False,
          "options": [
              {"value": "internal", "label": "Internal review"},
              {"value": "ae", "label": "A&E review"},
              {"value": "both", "label": "Both"}]}],
        "alpha", ["procore"], _R_FIELD,
        metadata={"deduped_from": ["C-8", "C-28"]}),
    _entry("draft_rfi_response", ["C-9"], "Draft RFI Response", "PROJECT_MGMT",
        "AI-drafted RFI response with drawing and spec references",
        [{"name": "RFI_NUMBER", "type": "text", "label": "RFI Number", "required": True},
         {"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True}],
        "alpha", ["procore"], _R_FIELD),
    _entry("meeting_activity", ["C-36"], "Meeting Activity", "PROJECT_MGMT",
        "Meeting frequency - flags projects with no meetings in 30 days",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("drawing_log_status", ["C-37"], "Drawing Log Status", "PROJECT_MGMT",
        "Drawing log by discipline - flags stale revisions",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("inspection_pass_fail", ["C-38"], "Inspection Pass/Fail", "PROJECT_MGMT",
        "Inspection results - flags failures and overdue items",
        _P_NONE, "adapter_pending", ["procore"], _R_PM_LEAD),
    _entry("meeting_minutes_action_items", ["C-39"], "Meeting Minutes and Action Items", "PROJECT_MGMT",
        "Open action items by project - flags meetings with unresolved items",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("drawing_revision_tracker", ["C-40"], "Drawing Revision Tracker", "PROJECT_MGMT",
        "Revision activity by discipline - flags obsolete drawings",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("form_completion_status", ["C-41"], "Form Completion Status", "PROJECT_MGMT",
        "Open forms by project and template - flags overdue items",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("photo_documentation_gaps", ["C-45"], "Photo Documentation Gaps", "PROJECT_MGMT",
        "Photo counts by project - flags locations with no recent coverage",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("specification_lookup", ["C-46"], "Specification Lookup", "PROJECT_MGMT",
        "Spec sections by division - flags missing or incomplete coverage",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("observation_trends", ["C-47"], "Observation Trends", "PROJECT_MGMT",
        "Open observations by type and trade - flags overdue and repeat items",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("inspection_summary", ["C-48"], "Inspection Summary", "PROJECT_MGMT",
        "Pass/fail rates by project and inspection type",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("photo_intelligence_scan", ["C-78"], "Photo Intelligence Scan", "PROJECT_MGMT",
        "AI analysis of recent job-site photos - flags safety, quality, progress",
        _P_PROJECT_REQ, "adapter_pending", ["procore"], _R_FIELD),

    # ── SCHEDULING (10) ─────────────────────────────────────────────────
    _entry("critical_path_delays", ["C-10"], "Critical Path Delays", "SCHEDULING",
        "Critical path tasks behind schedule",
        _P_PROJECT_REQ, "alpha", ["procore"], _R_FIELD),
    _entry("two_week_lookahead", ["C-11"], "2-Week Look-Ahead", "SCHEDULING",
        "Superintendent-ready look-ahead narrative",
        [{"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True},
         {"name": "START_DATE", "type": "date", "label": "Start", "required": False},
         {"name": "END_DATE", "type": "date", "label": "End", "required": False}],
        "alpha", ["procore"], _R_FIELD),
    _entry("resource_conflicts", ["C-12"], "Resource Conflicts", "SCHEDULING",
        "Cross-project resource overlaps, next 14 days",
        _P_NONE, "adapter_pending", ["procore"], _R_PM_LEAD),
    _entry("schedule_variance", ["C-42"], "Schedule Variance Report", "SCHEDULING",
        "Tasks behind schedule - flags critical path with negative float",
        _P_NONE, "adapter_pending", ["procore"], _R_PM_LEAD),
    _entry("lookahead_status", ["C-43"], "Lookahead Status", "SCHEDULING",
        "Active lookaheads by project - flags gaps in weekly planning",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("field_productivity_trends", ["C-44"], "Field Productivity Trends", "SCHEDULING",
        "Actual production quantities by crew and task code",
        _P_NONE, "adapter_pending", ["procore"], _R_FIELD),
    _entry("enriched_lookahead", ["C-50"], "Enriched Lookahead", "SCHEDULING",
        "Constraint-aware lookahead - flags tasks with open RFIs and pending submittals",
        [{"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True},
         {"name": "WEEKS", "type": "text", "label": "Weeks (2/3/4/6)", "required": False}],
        "adapter_pending", ["procore"], _R_FIELD),
    _entry("schedule_vs_billing_check", ["C-51"], "Schedule vs Billing Check", "SCHEDULING",
        "Compares schedule progress against billing percent",
        _P_PROJECT_REQ, "adapter_pending", ["procore"], _R_FIN),
    _entry("daily_log_vs_schedule_check", ["C-54"], "Daily Log vs Schedule Check", "SCHEDULING",
        "Trades that should be active per schedule but show no/low daily log activity",
        [{"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True},
         {"name": "DAYS", "type": "text", "label": "Lookback days", "required": False}],
        "adapter_pending", ["procore"], _R_FIELD),
    _entry("punch_milestone_risk_check", ["C-56"], "Punch-Milestone Risk Check", "SCHEDULING",
        "Punch list closeout risk for upcoming milestones",
        _P_PROJECT_REQ, "adapter_pending", ["procore"], _R_PM_LEAD),

    # ── DIRECTORY (2) ───────────────────────────────────────────────────
    _entry("project_team_roster", ["C-13"], "Project Team Roster", "DIRECTORY",
        "Active users with permission flags",
        _P_PROJECT_REQ, "live", [], _R_ALL),
    _entry("vendor_compliance", ["C-14"], "Vendor Compliance", "DIRECTORY",
        "Insurance status RED/YELLOW/GREEN",
        _P_NONE, "live", [], _R_FIN),

    # ── EXECUTIVE (6 canonical, 7 aliases) ──────────────────────────────
    _entry("monthly_owner_report", ["C-15", "C-60"], "Monthly Owner Report", "EXECUTIVE",
        "Formal monthly owner/lender report - budget, schedule, issues, photos",
        [{"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True},
         {"name": "REPORT_MONTH", "type": "month", "label": "Report Month", "required": True}],
        "adapter_pending", ["procore"], _R_VP_PM,
        metadata={"deduped_from": ["C-15", "C-60"]}),
    _entry("portfolio_snapshot", ["C-69"], "Portfolio Snapshot", "EXECUTIVE",
        "Cross-project portfolio view: budget health, schedule, open items, risk ratings",
        _P_NONE, "alpha", [], _R_VP_ONLY),
    _entry("portfolio_vendor_rankings", ["C-72"], "Portfolio Vendor Rankings", "EXECUTIVE",
        "Top and bottom performing vendors ranked by punch, schedule, billing compliance",
        _P_NONE, "adapter_pending", ["procore"], _R_VP_ONLY),
    _entry("portfolio_trend_analysis", ["C-73"], "Portfolio Trend Analysis", "EXECUTIVE",
        "30/60/90-day trend for key metrics: RFIs, punch, budget variance, schedule",
        _P_NONE, "adapter_pending", ["procore"], _R_VP_ONLY),
    _entry("risk_prediction_report", ["C-74"], "Risk Prediction Report", "EXECUTIVE",
        "2-4 week forward-looking risk predictions",
        _P_PROJECT_OPT, "alpha", [], _R_VP_ONLY),
    _entry("active_risk_dashboard", ["C-75"], "Active Risk Dashboard", "EXECUTIVE",
        "All active risk predictions ranked by severity - CRITICAL/HIGH/MEDIUM/LOW",
        _P_PROJECT_OPT, "alpha", [], _R_VP_ONLY),

    # ── PERFORMANCE (3) ─────────────────────────────────────────────────
    _entry("scorecard_preview", ["C-16"], "Scorecard Preview", "PERFORMANCE",
        "Pre-commit scores and payout projections for a quarter",
        [{"name": "QUARTER", "type": "quarter", "label": "Quarter", "required": True},
         {"name": "YEAR", "type": "year", "label": "Year", "required": True}],
        "alpha", [], _R_VP_PM),
    _entry("milestone_bonus_status", ["C-17"], "Milestone Bonus Status", "PERFORMANCE",
        "Bonus pipeline: earned, pending, holdback",
        _P_NONE, "adapter_pending", ["procore"], _R_VP_PM),
    _entry("quarterly_review_prep", ["C-18"], "Quarterly Review Prep", "PERFORMANCE",
        "Full evidence pack for quarterly review",
        [{"name": "QUARTER", "type": "quarter", "label": "Quarter", "required": True},
         {"name": "YEAR", "type": "year", "label": "Year", "required": True}],
        "adapter_pending", ["procore"], _R_VP_PM),

    # ── PROCUREMENT (5) ─────────────────────────────────────────────────
    _entry("buyout_procurement", ["C-19"], "Buyout and Procurement", "PROCUREMENT",
        "Uncommitted scope and long-lead items",
        _P_PROJECT_OPT, "adapter_pending", ["procore"], _R_PM_LEAD),
    _entry("schedule_health_dashboard", ["C-20"], "Schedule Health Dashboard", "PROCUREMENT",
        "Portfolio-wide schedule health",
        _P_NONE, "alpha", ["procore"], _R_PM_LEAD),
    _entry("inspection_readiness", ["C-21"], "Inspection Readiness", "PROCUREMENT",
        "Upcoming inspections and prerequisite status",
        _P_PROJECT_REQ, "adapter_pending", ["procore"], _R_FIELD),
    _entry("procurement_readiness", ["C-52"], "Procurement Readiness", "PROCUREMENT",
        "Upcoming task procurement status - GREEN/YELLOW/RED",
        [{"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True},
         {"name": "WEEKS", "type": "text", "label": "Weeks ahead", "required": False}],
        "blocked", ["procore"], _R_PM_LEAD),
    _entry("vendor_performance_scorecard", ["C-53"], "Vendor Performance Scorecard", "PROCUREMENT",
        "Cross-wired vendor scorecard: punch, schedule, billing, insurance",
        _P_PROJECT_REQ, "adapter_pending", ["procore"], _R_PM_LEAD),

    # ── OPERATIONS (18) ─────────────────────────────────────────────────
    _entry("morning_briefing", ["C-22"], "Morning Briefing", "OPERATIONS",
        "On-demand briefing with all alerts",
        _P_NONE, "live", [], _R_ALL),
    _entry("weekly_agenda_generator", ["C-23"], "Weekly Agenda Generator", "OPERATIONS",
        "Role-specific weekly meeting agenda",
        [{"name": "ROLE", "type": "role", "label": "Role", "required": False}],
        "alpha", [], _R_ALL),
    _entry("closeout_readiness", ["C-24"], "Closeout Readiness", "OPERATIONS",
        "Closeout completeness and blocking items",
        _P_PROJECT_REQ, "live", [], _R_PM_LEAD),
    _entry("documentation_compliance", ["C-25"], "Documentation Compliance", "OPERATIONS",
        "Process hygiene gaps and scorecard deductions",
        _P_NONE, "alpha", ["procore"], _R_FIELD),
    _entry("oac_briefing_packet", ["C-57"], "OAC Briefing Packet", "OPERATIONS",
        "Pre-meeting briefing for OAC: budget, RFIs, schedule, open items",
        _P_PROJECT_REQ, "alpha", ["procore"], _R_VP_PM),
    _entry("sub_coordination_briefing", ["C-58"], "Sub Coordination Briefing", "OPERATIONS",
        "Subcontractor coordination meeting prep",
        _P_PROJECT_REQ, "alpha", ["procore"], _R_FIELD),
    _entry("post_meeting_minutes", ["C-59"], "Post-Meeting Minutes", "OPERATIONS",
        "Generate meeting minutes from an agenda - extracts decisions, action items, owners",
        [{"name": "PROJECT_ID", "type": "project", "label": "Project", "required": True},
         {"name": "MEETING_TYPE", "type": "text", "label": "Meeting Type", "required": False}],
        "alpha", [], _R_FIELD),
    _entry("pending_decisions_log", ["C-61"], "Pending Decisions Log", "OPERATIONS",
        "Open decisions by owner - flags items with no resolution in 7+ days",
        _P_PROJECT_REQ, "alpha", [], _R_FIELD),
    _entry("decision_escalation_report", ["C-62"], "Decision Escalation Report", "OPERATIONS",
        "Decisions past due or approaching critical milestones",
        _P_PROJECT_REQ, "alpha", [], _R_VP_PM),
    _entry("lookahead_sync_briefing", ["C-63"], "Lookahead Sync Briefing", "OPERATIONS",
        "3-week lookahead constraint sync: vendors, RFIs, submittals, change events",
        _P_PROJECT_REQ, "adapter_pending", ["procore"], _R_FIELD),
    _entry("meeting_packet_history", ["C-64"], "Meeting Packet History", "OPERATIONS",
        "All generated meeting packets for a project with attachment status",
        _P_PROJECT_REQ, "alpha", [], _R_FIELD),
    _entry("action_queue_review", ["C-65"], "Action Queue Review", "OPERATIONS",
        "Pending write-back actions awaiting approval",
        _P_NONE, "writeback_pending", ["procore"], _R_VP_PM,
        risk="connector_write_medium"),
    _entry("writeback_log", ["C-66"], "Write-Back Log", "OPERATIONS",
        "Recent write-back actions executed - success/failure status",
        _P_NONE, "writeback_pending", ["procore"], _R_VP_PM,
        risk="connector_write_medium"),
    _entry("auto_queue_review", ["C-67"], "Auto-Queue Review", "OPERATIONS",
        "AI-proposed actions from pattern detection - review and approve for execution",
        _P_PROJECT_OPT, "writeback_pending", ["procore"], _R_VP_PM,
        risk="connector_write_medium"),
    _entry("command_mode", ["C-68"], "Command Mode", "OPERATIONS",
        "Type what you want done in plain English - Rex parses it into actions",
        _P_NONE, "writeback_pending", ["procore"], _R_ALL,
        risk="connector_write_medium"),
    _entry("my_day_briefing", ["C-76"], "My Day Briefing", "OPERATIONS",
        "Personalized daily briefing: alerts, tasks, meetings, weather, top priorities",
        _P_NONE, "alpha", [], _R_ALL),
    _entry("weather_impact_forecast", ["C-77"], "Weather Impact Forecast", "OPERATIONS",
        "7-day weather forecast with work impact",
        _P_PROJECT_REQ, "alpha", [], _R_FIELD),
    _entry("sub_communication_hub", ["C-79"], "Sub Communication Hub", "OPERATIONS",
        "Weekly status updates to active subcontractors with their project data",
        _P_PROJECT_REQ, "writeback_pending", ["procore"], _R_VP_PM,
        risk="connector_write_medium"),

    # ── TRAINING (1) ────────────────────────────────────────────────────
    _entry("training_status", ["C-104"], "Training Status", "TRAINING",
        "Rex University progress and next recommended lesson",
        _P_NONE, "alpha", [], _R_ALL),
]


CANONICAL_SLUG_COUNT: int = len(QUICK_ACTIONS_CATALOG)
LEGACY_ALIAS_COUNT: int = sum(len(a["legacy_aliases"]) for a in QUICK_ACTIONS_CATALOG)

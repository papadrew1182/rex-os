// Mock automation registry for the ControlPlane automation panel.
// Derived shape from `docs/roadmaps/rex_os_automation_inventory.csv`;
// swapped to live data once Session 1 ships the automation registry
// endpoint. Readiness vocabulary must match the catalog contract:
//   live | alpha | adapter_pending | writeback_pending | blocked | disabled
//
// execution_type vocabulary (frontend-display-only until Session 1
// freezes it):
//   scheduled  — fires on cron
//   manual     — admin-triggered only
//   event      — fires on backend event / webhook
//   hybrid     — scheduled + can be manually triggered too

export const mockAutomations = [
  {
    slug: "daily_procore_sync",
    label: "Procore daily sync",
    category: "SYNC",
    schedule_cron: "0 6 * * *",
    execution_type: "scheduled",
    enabled: true,
    readiness_state: "adapter_pending",
    last_run_at: null,
    last_success_at: null,
    last_failure_at: null,
  },
  {
    slug: "rfi_aging_refresh",
    label: "RFI aging refresh",
    category: "ALERTS",
    schedule_cron: "*/30 * * * *",
    execution_type: "hybrid",
    enabled: true,
    readiness_state: "live",
    last_run_at: "2026-04-14T17:00:00Z",
    last_success_at: "2026-04-14T17:00:00Z",
    last_failure_at: null,
  },
  {
    slug: "warranty_status_refresh",
    label: "Warranty status refresh",
    category: "ALERTS",
    schedule_cron: "0 6 * * *",
    execution_type: "scheduled",
    enabled: true,
    readiness_state: "live",
    last_run_at: "2026-04-14T06:00:00Z",
    last_success_at: "2026-04-14T06:00:00Z",
    last_failure_at: null,
  },
  {
    slug: "insurance_status_refresh",
    label: "Insurance status refresh",
    category: "ALERTS",
    schedule_cron: "15 6 * * *",
    execution_type: "scheduled",
    enabled: true,
    readiness_state: "live",
    last_run_at: "2026-04-14T06:15:00Z",
    last_success_at: "2026-04-14T06:15:00Z",
    last_failure_at: null,
  },
  {
    slug: "schedule_snapshot_daily",
    label: "Schedule snapshot",
    category: "SCHEDULE",
    schedule_cron: "30 6 * * *",
    execution_type: "scheduled",
    enabled: true,
    readiness_state: "live",
    last_run_at: "2026-04-14T06:30:00Z",
    last_success_at: "2026-04-14T06:30:00Z",
    last_failure_at: null,
  },
  {
    slug: "aging_alerts",
    label: "Aging alerts (RFI / submittal / punch)",
    category: "ALERTS",
    schedule_cron: "45 6 * * *",
    execution_type: "scheduled",
    enabled: true,
    readiness_state: "live",
    last_run_at: "2026-04-14T06:45:00Z",
    last_success_at: "2026-04-14T06:45:00Z",
    last_failure_at: null,
  },
  {
    slug: "morning_briefing_digest",
    label: "Morning briefing digest email",
    category: "DIGESTS",
    schedule_cron: "0 7 * * 1-5",
    execution_type: "scheduled",
    enabled: false,
    readiness_state: "blocked",
    last_run_at: null,
    last_success_at: null,
    last_failure_at: null,
  },
  {
    slug: "weather_impact_forecast",
    label: "Weather impact forecast",
    category: "INTELLIGENCE",
    schedule_cron: "0 5 * * *",
    execution_type: "scheduled",
    enabled: false,
    readiness_state: "blocked",
    last_run_at: null,
    last_success_at: null,
    last_failure_at: null,
  },
  {
    slug: "photo_intelligence_scan",
    label: "Photo intelligence scan",
    category: "INTELLIGENCE",
    schedule_cron: "0 4 * * *",
    execution_type: "scheduled",
    enabled: false,
    readiness_state: "disabled",
    last_run_at: null,
    last_success_at: null,
    last_failure_at: null,
  },
];

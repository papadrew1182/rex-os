# ACTIVE_PR_QUEUE

Last Updated (UTC): 2026-05-17 16:51:03Z

## In Flight
1. **UI Overhaul + Dashboard Seed (current)**
   - Branch: `feat/ui-overhaul-dashboard`
   - Base: `main`
   - Scope:
     - New role-based dashboard route/page
     - AI quick actions panel + FAB + mobile nav
     - Collapsible sidebar groups + content max-width
     - Demo-only `migrations/seed_dashboard_demo.sql`
   - Validation completed:
     - `bash backend/scripts/fresh_db_replay.sh` PASS
     - `npm run build` PASS
     - seed SQL idempotency verified against local replay DB

## Next (Queued)
1. Connector + AI spine stabilization checks (tool/queue/SSE/procore scheduler posture)
2. Operational hardening pass (stale docs, CI parity edges, duplicate-key audit planning)

# Session Handoff — 2026-04-21

Pick this up immediately in the next session.

## Where we are

**Phase 4 (Procore connector):** SHIPPED. RFI reference pipeline (Rex App → `connector_procore.rfis_raw` → `rex.rfis`) live on prod and demo. 10 other resources remain in the follow-up `2026-04-XX-phase4-procore-remaining-resources` plan.

**Phase 5 Wave 1 alpha actions:** SHIPPED as of this session. All 8 alpha slugs now return data-grounded assistant responses via chat-enrichment pattern.

| slug | state | reads from |
|---|---|---|
| `rfi_aging` | live | `rex.v_project_mgmt` |
| `submittal_sla` | live | `rex.v_project_mgmt` |
| `budget_variance` | live | `rex.v_financials` |
| `daily_log_summary` | live | `rex.daily_logs` + `rex.manpower_entries` |
| `critical_path_delays` | live | `rex.schedule_activities` + `rex.schedules` |
| `two_week_lookahead` | live | `rex.schedule_activities` + `rex.schedules` |
| `documentation_compliance` | live | `rex.v_closeout_items` |
| `my_day_briefing` | live | `rex.v_myday` |

## Wave 1 actions still pending (`adapter_pending`)

Blocked on Phase 4 resource rollout (submittals/daily_logs/tasks/change_events connector syncs):

- `change_event_sweep`
- `inspection_pass_fail`
- `schedule_variance`
- `lookahead_status`

## Deploy state

- **Prod (`rex-os-api-production.up.railway.app`):** commit `de4a2e3017ef`, migration 024 applied, REX_APP_DATABASE_URL set, scheduler running 5 jobs. `/api/ready` green.
- **Demo (`rex-os-demo.up.railway.app`):** commit `de4a2e3017ef`, demo seed loaded, REX_APP_DATABASE_URL set, scheduler disabled (demo convention). `/api/ready` green.
- **Frontend (Vercel):** both prod and demo deployed, 200s.

## Phase 5 Live smoke results (this session)

Invoked each of the 8 handlers against demo's Postgres with `aroberts@exxircapital.com`:

- `rfi_aging`: 6 open, buckets 1/0/1/0, oldest 18 days (Bishop Modern)
- `submittal_sla`: 6 open, buckets 3/3/0/0, oldest 6 days
- `budget_variance`: 4 projects, 0 over 5%, portfolio +$70k, worst +0.7% (Bishop Modern)
- `daily_log_summary`: 7 logs in 7 days, 0 today, 4 projects without today's log
- `critical_path_delays`: 6 delayed (>2d), worst 17 days
- `two_week_lookahead`: 0 tasks starting (empty-state rendering correct)
- `documentation_compliance`: 4 overdue closeout items
- `my_day_briefing`: 1 item on aroberts's plate (overdue RFI)

## Known follow-ups for Phase 5 polish (not urgent)

1. `budget_variance.total_projects` derives from LIMIT 10 — swap to a separate `COUNT(*)` before projects scale past 10 with budgets.
2. `submittal_sla` uses `EXTRACT(DAY FROM interval)` — fine in practice but `EPOCH/86400` is more robust for long intervals.
3. `my_day_briefing` doesn't validate `project_id` against user's access — safe because `v_myday` is user-keyed, but scope label could lie.
4. No end-to-end test for "view-missing" path (dispatcher sentinel is covered at the dispatcher level).
5. `_render_fragment` is underscored but imported across 8 modules — drop the underscore.

## What's next (per full roadmap in `docs/roadmaps/rex_os_full_roadmap.md`)

Phase 5 exit criterion ("the assistant sidebar is useful for daily operational work") is partially hit: 12 of 16 Wave 1 actions are now live (the 4 previously-live ones + our 8). The remaining 4 `adapter_pending` actions unblock only when Phase 4 resource rollout lands connector data for submittals/daily_logs/tasks/change_events.

**Two natural next steps:**

1. **Phase 4 resource rollout plan** — extend the connector to the 10 remaining resources. Unblocks the 4 adapter_pending Wave 1 actions. Plan file: not yet written.
2. **Phase 6 (Action execution, command mode, approvals)** — once Wave 1 is enough for Andrew to use daily, the next leverage is turning natural language into safe actions with an approval queue.

Andrew previously preferred "ship what's wired, investigate followups in parallel." On that pattern, Phase 4 resource rollout is the obvious next plan.

## PRs merged this session

- **#13** — feat: Phase 5 Wave 1 — wire 8 alpha quick actions to real SQL (merged, de4a2e3)

## Plan + spec documents

- Spec: `docs/superpowers/specs/2026-04-21-phase5-wave1-alpha-actions-design.md`
- Plan: `docs/superpowers/plans/2026-04-21-phase5-wave1-alpha-actions.md`

## Test suite

Full backend: **794 passed, 1 skipped** (767 baseline + 27 new Phase 5 tests, zero regressions).

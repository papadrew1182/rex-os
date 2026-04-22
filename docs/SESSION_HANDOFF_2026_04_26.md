# Session Handoff — 2026-04-26

Pick this up immediately in the next session.

## Where we are

**Phase 6a + 6b Wave 1 + Frontend Wave 1 + 6b Wave 2** — all shipped earlier this week (PRs #16, #17, #18, #19). 14 LLM tools registered; approval cards, undo, and failure UI live.

**Phase 4 Wave 2 (direct Procore API):** SHIPPED 2026-04-22 — PR #20, merge commit `ca65c9d`. 5 Procore resources now sync directly from Procore's REST API into Rex OS canonical tables via the existing Phase 4a scaffolding. Old rex-procore app is no longer on the critical data path (still running, not actively used for the Wave 2 resources).

## What's live as of Phase 4 Wave 2

**5 resources syncing directly from Procore API** (every 30 min on prod via apscheduler):

| Procore endpoint | Staging | Canonical | Quick actions unblocked |
|---|---|---|---|
| `/projects/{id}/submittals` | `connector_procore.submittals_raw` | `rex.submittals` | submittal_sla (fuller data) |
| `/projects/{id}/daily_logs/construction_report_logs` | `connector_procore.daily_logs_raw` | `rex.daily_logs` | daily_log_summary (real data) |
| `/projects/{id}/schedule/standard_tasks` | `connector_procore.schedule_tasks_raw` | `rex.schedule_activities` | schedule_variance, lookahead_status |
| `/projects/{id}/change_events` | `connector_procore.change_events_raw` | `rex.change_events` | change_event_sweep |
| `/projects/{id}/inspection_lists` | `connector_procore.inspections_raw` | `rex.inspections` | inspection_pass_fail |

**4 quick actions flipped from `adapter_pending` → `live`:** `change_event_sweep`, `inspection_pass_fail`, `schedule_variance`, `lookahead_status`.

## Architecture summary

- `ProcoreClient` in `backend/app/services/ai/tools/procore_api.py` (originally Phase 6a for `answer_rfi` writeback) gained 5 new read-only `list_<resource>()` methods + a `_paginate` helper + `_auth_headers` helper.
- `ProcoreAdapter` went from pure rex-procore-DB-read to hybrid: projects/users/vendors still read from rex-procore DB via `RexAppDbClient`; the 5 Wave 2 resources call Procore API via `ProcoreClient`.
- Mapper normalizes Procore's free-text enum values into the Rex canonical CHECK enums (e.g. "Shop Drawings" → `shop_drawing`), falling back to safe defaults on unknown values. FK fields (assigned_to, created_by, etc.) are None pending a later enrichment pass.
- Orchestrator's `_CANONICAL_WRITERS` dict gained 5 new entries. Each upserts on a project-scoped natural key (e.g. `(project_id, submittal_number)`). Schedule activities bootstrap a `rex.schedules` row ("Procore default schedule") on first sync for a project.
- Scheduler job `procore_api_sync` registered via the existing `@register_job` decorator pattern (not a manual `scheduler.add_job` call). Every 30 min. Demo scheduler stays disabled via `REX_ENABLE_SCHEDULER` gate.

## Migrations added (5)

- 030 — `connector_procore.inspections_raw` staging table + `rex.sync_runs.cursor_watermark` column
- 031 — `UNIQUE(project_id, submittal_number)` on `rex.submittals`
- 032 — `UNIQUE(project_id, name)` on `rex.schedules` + `UNIQUE(schedule_id, activity_number)` on `rex.schedule_activities`
- 033 — `UNIQUE(project_id, event_number)` on `rex.change_events`
- 034 — `UNIQUE(project_id, inspection_number)` on `rex.inspections`

All registered in `backend/app/migrate.py::MIGRATION_ORDER`.

## Deploy state (verify post-op-step)

- **Prod backend (`rex-os-api-production.up.railway.app`):** Railway auto-deployed from main. 5 migrations apply on boot. `procore_api_sync` job registers. **Won't actually sync until operator adds `PROCORE_REFRESH_TOKEN`.**
- **Demo backend (`rex-os-demo.up.railway.app`):** Same. **Won't sync until operator adds all 6 Procore env vars.**
- **Vercel prod (`rex-os.vercel.app`):** no frontend changes this wave; should deploy identical to before.

## Operator prerequisites (CRITICAL — blocks actual sync)

1. **Prod Railway** — add environment variable:
   - `PROCORE_REFRESH_TOKEN` (copy from rex-procore's Railway env)
2. **Demo Railway** — add environment variables (copy all from rex-procore and/or prod):
   - `PROCORE_CLIENT_ID`
   - `PROCORE_CLIENT_SECRET`
   - `PROCORE_COMPANY_ID`
   - `PROCORE_BASE_URL`
   - `PROCORE_TOKEN_URL`
   - `PROCORE_REFRESH_TOKEN`
3. Restart both services after setting.
4. Verify first prod scheduler tick within 30 min — check `rex.sync_runs` for 5+ rows per connector_account with `status='success'`.

Until operator step is done, the scheduler fires every 30 min but `ProcoreClient.from_env()` raises `ProcoreNotConfigured`, the adapter returns empty pages, and `rex.sync_runs` rows land with `record_count=0`. Harmless no-op until creds are set.

## Known follow-ups (not blocking, but worth tracking)

1. **Procore endpoint path verification.** The 5 `list_<resource>()` methods use best-guess paths. When the operator sets the refresh token, watch `rex.sync_runs` for `status='failed'` rows and inspect `error_excerpt` — HTTP 404 means wrong path, adjust in `procore_api.py`. Most likely suspects: `inspection_lists` (might be `checklist/list_item_inspections` in Procore v1.0) and `schedule/standard_tasks`.
2. **Field-enum normalization coverage.** The mapper uses title-case → lowercase-underscore conversion for CHECK enums with fallbacks to safe defaults (e.g. unknown submittal_type → `other`). If Procore returns a value we haven't seen, it silently lands as the fallback. Spot-check rex.submittals.submittal_type and similar distributions after a week of syncs.
3. **FK resolution is deferred.** All mappers emit None for assigned_to / created_by / etc. Real person/company linkage requires a follow-up enrichment pass. Quick actions that read assignee names (e.g. `submittal_sla`) won't show them until that ships.
4. **Schedule predecessors/successors** — Procore `standard_tasks` includes arrays of predecessor/successor task ids. Skipped in Wave 2; separate plan.
5. **Deep historical backfill** — first scheduler tick pulls all rows Procore returns for `updated_since=NULL`. For active Bishop projects with years of history, this might hit rate limits. Watch for 429s in logs.
6. **Manpower entries** (child of daily_logs) — not synced. `daily_log_summary` reads `rex.manpower_entries` which still comes from demo seed.
7. **Rex-procore cron shutdown** — old app still running (producing nothing new for these 5 resources, but keep it for the projects/users/vendors sync). Shut off later after a week of stable direct sync.

## Unblocked by Wave 2 (things you can do now that you couldn't before)

- Run `submittal_sla`, `daily_log_summary`, `schedule_variance`, `lookahead_status`, `change_event_sweep`, `inspection_pass_fail` quick actions and see real data.
- Use `pay_application` + `lien_waiver` LLM tools on prod **once commitments sync** (future wave — see below).
- Procore writeback wave per spec §5 (submittals first) becomes viable.

## Still-blocked items

- `pay_application` + `lien_waiver` on prod — these tools need `rex.commitments` populated. Wave 2 didn't include commitments (out of scope per `project_phase4_wave2_blocked` memory). Next wave should target commitments + billing_periods + prime_contracts to fully unblock financial tools on prod.
- `punch_close` / `punch_reopen` — need `rex.punch_items` populated. Procore has `punch_items` as a resource; add in a Wave 2.5 plan.

## What's next

Candidates in rough priority order:

1. **Operator env-var work** (you) — unblocks the entire Wave 2 from being a no-op on Railway. Without this step, the scheduler runs but syncs nothing.
2. **Wait-and-learn (1 week)** — let the scheduler run, watch `rex.sync_runs` for failures, iterate on mapper enum coverage + endpoint paths based on real Procore responses.
3. **Phase 4 Wave 2.5: commitments + billing_periods + prime_contracts** — unblocks `pay_application` + `lien_waiver` on prod. Smaller than Wave 2 (3 resources, same pattern).
4. **Phase 4 Wave 2.6: punch_items + manpower_entries** — unblocks `punch_close`/`punch_reopen` tools + lights up `daily_log_summary` fully.
5. **Procore writeback wave (submittals)** — per spec §5. Second external writeback after `answer_rfi`.
6. **Frontend polish** — `answer_rfi` still doesn't work on prod without refresh_token. If operator step lands, verify real end-to-end on mobile.

Recommendation: candidate 1 immediately; candidate 2 (let it bake for a week); then candidate 3 as the next planned wave.

## PRs merged this session

- **#20** — feat: Phase 4 Wave 2 — direct Procore API read sync (merge commit `ca65c9d`)

## Plan + spec

- Spec: `docs/superpowers/specs/2026-04-22-phase4-wave2-direct-procore-design.md`
- Plan: `docs/superpowers/plans/2026-04-22-phase4-wave2-direct-procore.md`

## Test suite

- **Backend:** 1091 passed, 1 skipped, 0 failed (baseline 977 + 114 new).
- **Frontend:** unchanged vs prior session (51 pure-Node tests passing).

## Learnings banked this session

1. **Plan assumption validation always yields findings.** 4 of 5 resources needed supplementary unique-constraint migrations not anticipated in the spec. Also caught: `ConnectorPage` uses `items=` not `records=`; payload natural key is `"id"` not `"source_id"`; `staging.ALLOWED_TABLES` allow-list needed extension; `rex.submittals.submittal_type` enum differs from my spec's guess; `_RESOURCE_CONFIG` dict needs per-resource registration; apscheduler uses `@register_job` decorator not manual `add_job()`. Pattern: subagent's first step should always be "read the existing file you're extending" before coding.
2. **Silent migration gaps compound.** T3 created migration 031 but forgot to register it in `MIGRATION_ORDER`. T5 caught that + added the registration alongside its own. If T5 hadn't noticed, the unique constraint would have been missing in prod + the `ON CONFLICT` would have failed silently or raised.
3. **Phase 6a's `ProcoreClient` was the right investment.** Adding 5 read methods + pagination helper + auth headers to an existing OAuth-working client took ~1 subagent iteration. Building from scratch would've been a multi-day OAuth shakedown.
4. **Hybrid adapter is fine.** Leaving projects/users/vendors on the rex-procore DB read path + routing the 5 new resources through Procore API direct is not architecturally clean, but it minimizes regression risk. Migrate the older 3 to API reads in a future cleanup wave.

## Operator checklist (you, the next day)

- [ ] Add `PROCORE_REFRESH_TOKEN` to prod Railway (copy from rex-procore env)
- [ ] Add all 6 Procore env vars to demo Railway (copy from prod)
- [ ] Restart both services
- [ ] Wait 30 min, then check prod `rex.sync_runs` — expect 5 success rows per connector_account
- [ ] Spot-check one project in the Procore UI vs Rex OS canonical (submittal_number/count should agree approximately)
- [ ] Railway logs second pass ~1 min after first — look for `procore_api_sync FAIL` entries; flag any repeated endpoint 404s

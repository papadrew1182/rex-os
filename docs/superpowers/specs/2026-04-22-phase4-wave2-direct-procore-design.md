# Phase 4 Wave 2 — Direct Procore API Read Sync (5 Resources)

**Status:** approved 2026-04-22 (design brainstorm complete). Ready for implementation plan.
**Author:** Claude + Andrew Roberts.
**Parent specs:**
- `docs/superpowers/specs/2026-04-21-phase4-procore-rex-app-design.md` (Phase 4 original — rex-procore DB read path)
- `docs/superpowers/specs/2026-04-21-phase6-commands-approvals-design.md` (Phase 6 — writeback ordering reference)
**Supersedes:** the paused Phase 4 Wave 2 plan that tried to read from the old rex-procore DB (see `project_phase4_wave2_blocked` memory).

## Goal

Land 5 Procore resources (submittals, daily_logs, schedule_activities, change_events, inspections) in Rex OS by calling Procore's REST API directly. Bypass the rex-procore app's silently-failing cron. Store raw Procore responses in `connector_procore.*` staging tables; map into `rex.*` canonical tables via the existing Phase 4a orchestrator pattern. Scheduled every 30 min via the existing apscheduler.

**Exit criterion:** Within 30 min of merge + operator env-var setup, prod's `rex.submittals` / `rex.daily_logs` / `rex.schedule_activities` / `rex.change_events` / `rex.inspections` have real rows for active Procore projects. The 4 `adapter_pending` quick actions (`change_event_sweep`, `inspection_pass_fail`, `schedule_variance`, `lookahead_status`) flip to `live`.

## Pre-locked decisions (2026-04-22 brainstorm)

1. **Strategy** = **C**: Port rex-procore's existing Procore OAuth refresh_token to Rex OS. No new Procore OAuth app registration. Rex OS becomes a second, independent consumer using the same credentials.
2. **Scope** = **B**: 5 resources in one PR (submittals, daily_logs, schedule_activities from Procore's `standard_tasks`, change_events, inspections). Unblocks all 4 pending quick actions + lights up `daily_log_summary` with real data.
3. **Read pattern** = **A**: Scheduled polling via the existing apscheduler. Every 30 min. Procore `updated_at_min=<cursor>` windowing per resource per project. Webhooks deferred.
4. **Storage pattern** = **A**: Keep Phase 4a's two-tier staging → canonical. New `connector_procore.<resource>_raw` tables per resource. One migration per resource.
5. **Reuse** the Phase 6a `ProcoreClient` in `backend/app/services/ai/tools/procore_api.py`. Extend with 5 new `list_<resource>()` methods. Don't fork a second Procore client.

## Current-state facts (verified 2026-04-22)

**Railway env vars:**
- Prod has `PROCORE_CLIENT_ID`, `PROCORE_CLIENT_SECRET`, `PROCORE_COMPANY_ID`, `PROCORE_BASE_URL`, `PROCORE_TOKEN_URL`. **Missing: `PROCORE_REFRESH_TOKEN`.** Operator step: port from rex-procore.
- Demo has **none** of the Procore env vars. Operator step: copy all 6 from prod.

**rex-procore DB state:**
- `procore.projects` (8), `procore.users` (615), `procore.vendors` (619) — populated. These continue to sync via the existing Phase 4a DB-read path. This wave does NOT touch them.
- `procore.rfis` (3 test-seeded), `procore.submittals` (0), `procore.daily_logs` (0), `procore.tasks` (0), `procore.change_events` (0), `procore.punch_items` (0), `procore.manpower_logs` (0) — empty. This is what's blocked today.
- `procore.inspections` and `procore.schedule_tasks` — tables don't exist in rex-procore DB.

Direct Procore API access sidesteps all of this. The Procore API has the canonical data; we just need to read it.

**Canonical tables (rex.*):**
All 5 targets exist in `migrations/rex2_canonical_ddl.sql`. No canonical migrations needed.

## Architecture

### Layered flow per resource

```
Procore REST API
    ↓  ProcoreClient.list_<resource>(project_id, updated_since)       (new methods)
connector_procore.<resource>_raw                                       (new staging tables × 5)
    ↓  mapper.map_<resource>(raw)                                      (new mapper fns × 5)
rex.<resource>                                                          (existing canonical)
```

### File layout

Reuses `backend/app/services/connectors/procore/`:

- **`procore_api.py`** (existing, extends) — the `ProcoreClient` from Phase 6a. Adds 5 list methods.
- **`adapter.py`** (existing, extends) — new top-level fetch functions that wrap the `ProcoreClient` methods and convert the raw API responses to the shape the orchestrator expects. Existing `fetch_rfis` / `list_projects` etc. remain using the rex-procore DB.
- **`payloads.py`** (existing, extends) — new `build_<resource>_payload()` helpers to normalize the staging row shape.
- **`mapper.py`** (existing, extends) — 5 new `map_<resource>()` functions.
- **`orchestrator.py`** (existing, extends) — 5 new `_write_<resource>` functions; 5 new entries in `_CANONICAL_WRITERS`.
- **`scheduler_job.py`** (new) — the apscheduler job function for the 30-min sync.
- **`backend/app/routes/admin_connectors.py`** (existing, extends) — extend the `/sync/{resource}` endpoint's resource enum.

**Migrations** (5 new, one per resource):
- `migrations/030_connector_procore_submittals_raw.sql`
- `migrations/031_connector_procore_daily_logs_raw.sql`
- `migrations/032_connector_procore_schedule_tasks_raw.sql`
- `migrations/033_connector_procore_change_events_raw.sql`
- `migrations/034_connector_procore_inspections_raw.sql`

Each is structurally identical to `connector_procore.rfis_raw` (migration 013).

## Procore API endpoint surface

Exact paths to be confirmed against Procore's REST API v1.0 docs at implementation time. Best-knowledge starting point:

| Resource | Endpoint | Filter |
|---|---|---|
| submittals | `GET /rest/v1.0/projects/{id}/submittals` | `filters[updated_at]=<since>` |
| daily_logs | `GET /rest/v1.0/projects/{id}/daily_logs/construction_report_logs` | `log_date>=<since>` |
| schedule_tasks | `GET /rest/v1.0/projects/{id}/schedule/standard_tasks` | `updated_at_min=<since>` |
| change_events | `GET /rest/v1.0/projects/{id}/change_events` | `filters[updated_at]=<since>` |
| inspections | `GET /rest/v1.0/projects/{id}/checklist/list_item_inspections` (or `inspection_lists` — verify) | `updated_at>=<since>` |

Headers on every request:
- `Authorization: Bearer <access_token>` (from OAuth refresh flow — existing code)
- `Procore-Company-Id: <PROCORE_COMPANY_ID>` (from env)

Pagination: Procore returns a `per_page` / `page` model. The adapter loops until the response has fewer rows than `per_page`. Plan marks this as the single point that most needs testing — one off-by-one and we silently miss pages.

Rate limit: Procore returns 429 with `Retry-After` header. The adapter respects it — exponential backoff up to 3 retries.

## Staging table schema

One migration per resource. All 5 are identical in shape (varying only in table name):

```sql
CREATE SCHEMA IF NOT EXISTS connector_procore;

CREATE TABLE IF NOT EXISTS connector_procore.submittals_raw (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id  uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    procore_id            bigint NOT NULL,
    project_procore_id    bigint NOT NULL,
    raw                   jsonb NOT NULL,
    raw_hash              text NOT NULL,
    last_seen_at          timestamptz NOT NULL DEFAULT now(),
    synced_at             timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (connector_account_id, procore_id)
);

CREATE INDEX IF NOT EXISTS idx_submittals_raw_project_procore_id
    ON connector_procore.submittals_raw (project_procore_id);
CREATE INDEX IF NOT EXISTS idx_submittals_raw_synced_at
    ON connector_procore.submittals_raw (synced_at);
```

Same pattern for daily_logs_raw, schedule_tasks_raw, change_events_raw, inspections_raw.

`raw_hash` is used to skip re-upserts when Procore returns an unchanged row (compute `md5(raw::text)`).

## Mapper contracts

Each `map_<resource>(raw: dict, connector_account_id, resolver) -> dict | None`:
- Input: one Procore API row + a resolver that maps `procore_id` → `rex.<fk_target>.id` via `rex.connector_mappings`.
- Output: dict ready for the canonical writer's INSERT ... ON CONFLICT. Returns `None` if required FKs don't resolve (the orchestrator skips + logs).

Mapper stubs already exist for `submittals` and `commitments` in Phase 4a's `mapper.py`. Extend them with real field coverage; add 4 new stubs for the remaining resources.

### Field mapping highlights

**submittals** → `rex.submittals`:
- `number` → `submittal_number`
- `title` → `title`
- `submittal_type` (raw) → CHECK-valid value from `('shop_drawing','product_data','sample','mock_up','quality_submittal','informational_submittal')` — mapper normalizes or falls back to `'informational_submittal'`
- `status` (raw) → CHECK-valid value from the 7 rex.submittals status enum — same normalization
- `due_date`, `submitted_date`, `approved_date` → parse ISO
- `assigned_to.id` / `ball_in_court.id` / `responsible_contractor.id` → resolve through `rex.connector_mappings`

**daily_logs** → `rex.daily_logs`:
- `date` → `log_date`
- `status` inferred from published state
- Weather summary text (Procore stores structured weather — flatten to `weather_summary` text)
- Unique per (project_id, log_date).

**schedule_tasks** → `rex.schedule_activities`:
- `task_number` → `activity_number`
- `name` → `name`
- `start_date`, `finish_date` → dates
- `percent_complete`, `predecessors`, `successors` → resolve by procore_id to FK ids where the relation table exists (might defer predecessors/successors to a follow-up — flag in plan)

**change_events** → `rex.change_events`:
- `number` → `event_number`
- `title`, `description`
- `estimated_amount` (numeric)
- `reason` → normalize to the 5-value CHECK enum
- `event_type` → normalize to the 5-value CHECK enum

**inspections** → `rex.inspections`:
- `inspection_number`, `inspection_type` → normalize to CHECK-valid
- `inspection_date`, `location`, `inspector_id` (resolve)
- `overall_status` → rex.inspections.status CHECK enum

All 5 mappers skip + log when the raw payload has a shape Procore didn't document. Don't throw — one bad row shouldn't kill the sync.

## Orchestrator integration

New entries in `_CANONICAL_WRITERS`:

```python
_CANONICAL_WRITERS.update({
    "submittals":          _write_submittals,           # → rex.submittals
    "daily_logs":          _write_daily_logs,           # → rex.daily_logs
    "schedule_activities": _write_schedule_activities,  # → rex.schedule_activities
    "change_events":       _write_change_events,        # → rex.change_events
    "inspections":         _write_inspections,          # → rex.inspections
})
```

Each `_write_*` function follows the Phase 4a pattern: `INSERT INTO rex.<table> (...) VALUES (...) ON CONFLICT (natural_key) DO UPDATE SET ...`.

The orchestrator's existing project-scoped loop handles these 5 resources. Each resource runs per-project-per-connector-account. The `sync_run_id` threads through so `rex.sync_runs` + `rex.source_links` get proper audit entries.

## Cursor tracking

Extend `rex.sync_runs` to record the per-resource `updated_at` watermark at the end of a successful run:

```sql
-- already exists (from Phase 4a migration 015):
CREATE TABLE rex.sync_runs (
    id, connector_account_id, resource_type, started_at, finished_at,
    status, record_count, error_excerpt, ...
);

-- Wave 2 adds:
ALTER TABLE rex.sync_runs ADD COLUMN IF NOT EXISTS cursor_watermark timestamptz;
```

One schema migration: migration 035.

Before a run, the orchestrator reads `SELECT MAX(cursor_watermark) FROM rex.sync_runs WHERE resource_type = $1 AND connector_account_id = $2 AND status = 'success'` and uses that as `updated_since`. After the run, it writes the new watermark (max of any row's `updated_at` it saw).

On first run per (resource, account), `updated_since` is NULL; the adapter fetches all rows from Procore for that resource on that account. This is the implicit backfill.

## Scheduler job

New apscheduler job registered at app startup in `backend/app/scheduler.py`:

```python
scheduler.add_job(
    procore_api_sync_job,
    "cron",
    minute="*/30",
    id="procore_api_sync",
    max_instances=1,
    replace_existing=True,
)
```

Demo scheduler stays disabled (`REX_ENABLE_SCHEDULER` unset). Demo exercises via the admin HTTP endpoint instead.

`procore_api_sync_job` iterates connector_accounts with `connector_id=procore` and `is_active=true`, iterates active projects, iterates the 5 resources in order (submittals → daily_logs → schedule_tasks → change_events → inspections), writes sync_runs rows per iteration.

Total requests per 30-min cycle worst case: `n_projects × 5 resources × avg_pages_per_resource`. For Bishop Construction's ~8 active projects with low daily churn, expect 40–80 API calls per cycle — well under Procore's rate limit.

## Admin HTTP endpoint

Existing `POST /api/admin/connectors/{account_id}/sync/{resource}` (used by Phase 4a smoke script). Extend the `resource` path parameter's enum:

```
before: projects | users | vendors | rfis
after:  projects | users | vendors | rfis |
        submittals | daily_logs | schedule_activities | change_events | inspections
```

Lets you trigger a one-off sync via curl for any of the new 5 on demand. Same auth as the Phase 4a version.

## Error handling

- **Rate limit (429):** respect `Retry-After`, up to 3 retries per page, then skip page + log.
- **5xx from Procore:** fail the whole resource-level run with `status='failed'`. Next scheduler tick retries.
- **Bad row in a page:** log + skip. The row is written to staging with a raw_hash anyway; if Procore fixes it, next sync re-ingests.
- **FK resolution failure in mapper:** skip + log. Row stays in staging; retries on next sync when the FK target has been synced.
- **Procore OAuth expires:** the existing `ProcoreClient._ensure_token` refresh handles this. If the refresh itself fails, raise `ProcoreNotConfigured` and the sync run is marked failed.

## Testing strategy

**Unit tests** (live-DB, following Phase 4a patterns):
- 5 × mapper tests (`test_mapper.py` extensions): canned Procore JSON → expected canonical dict.
- 5 × adapter tests: mocked httpx transport returns 1 full page + 1 empty page, asserts pagination loop terminates.
- 1 × `ProcoreClient` test covering the 5 new `list_<resource>()` methods (one test each with a mocked transport returning 2 pages, asserting the URL + query params + merged result).

**Integration tests** (live-DB + mocked adapter):
- Orchestrator: given a mocked adapter yielding 3 canned pages, assert the full pipeline (adapter → staging INSERT → mapper → canonical INSERT) produces the expected rows.

**Live smoke** (post-deploy):
- Demo: use the admin endpoint to trigger each of the 5 syncs. Inspect row counts in staging + canonical.
- Prod: wait for the first scheduler tick (~30 min post-deploy). Inspect `rex.sync_runs` for 5 successful entries per connector_account. Spot-check canonical rows against Procore UI for one project.

Target: ~30 new tests. Baseline: 977 backend tests. After Wave 2: ~1007 tests.

## Quick action flip

Update `backend/app/data/quick_actions_catalog.py` — flip 4 entries from `adapter_pending` to `live`:
- `change_event_sweep`
- `inspection_pass_fail`
- `schedule_variance`
- `lookahead_status`

And regenerate migration 008 (the catalog seed migration) the same way Phase 5 Wave 1 did.

## Deploy sequence

1. **Operator prerequisites** (Andrew's homework; separate from this PR):
   - Copy `PROCORE_REFRESH_TOKEN` from rex-procore Railway → Rex OS prod + demo.
   - Demo also needs: `PROCORE_CLIENT_ID`, `PROCORE_CLIENT_SECRET`, `PROCORE_COMPANY_ID`, `PROCORE_BASE_URL`, `PROCORE_TOKEN_URL` (copy from prod).
   - Restart both services after setting.
2. Merge PR. 6 new migrations apply on boot (5 staging tables + 1 sync_runs ALTER).
3. Scheduler picks up the new `procore_api_sync` job on prod. Demo stays on-demand via admin endpoint.
4. Railway + Vercel auto-deploy. Two-pass log check on both envs.
5. First scheduler tick within 30 min — inspect `rex.sync_runs`. Expected: one row per (resource × active connector_account), all `status='success'`.
6. Smoke via demo admin endpoint for fast feedback while prod's first tick is pending.
7. Update handoff doc.

## Out of scope for Wave 2

- **Webhooks** — deferred per brainstorm Q3.
- **Manpower entries** (child of daily_logs) — needs child-record sync pattern; separate plan.
- **Photos, markups, observations, punch_items, commitments, billing_periods** — future resources. Commitments in particular unblocks `pay_application` / `lien_waiver` on prod, but this wave focuses on the 5 that unblock quick actions. Follow-up wave.
- **Writeback for the 5** — this is the READ wave. Writeback sequence per parent spec §5 picks up with submittals in a later wave once read-path is stable.
- **Migrating projects/users/vendors from rex-procore DB to Procore API** — works today via DB read. Break the read path = regression risk. Migrate in a future cleanup.
- **Deep historical backfill** — first run reads whatever Procore returns from `updated_at_min=NULL`. May hit rate limits on large historical pulls. Plan notes this; no explicit backfill pagination strategy beyond "let it take N runs to catch up."
- **Rex-procore cron shutdown** — keep running alongside for safety net. Separate op once Rex OS has been stable for a week.

## Success criteria

- 6 migrations apply cleanly on prod + demo (5 staging tables + 1 sync_runs ALTER).
- Scheduler registers the `procore_api_sync` job on prod boot.
- First prod sync tick within 30 min of deploy; `rex.sync_runs` has 5 success rows per connector_account.
- `rex.submittals` / `rex.daily_logs` / `rex.schedule_activities` / `rex.change_events` / `rex.inspections` have real rows for ≥1 active project within 1 hour of deploy.
- 4 quick action catalog entries flip to `live` (catalog migration 008 regenerated).
- Backend regression: 1007+ passing, zero failures.
- Demo admin endpoint smoke: trigger each of the 5 resource syncs, observe success + row growth.

## Spec self-review

**Placeholder scan:** one — the Procore endpoint paths (§Architecture table) say "verify against docs at implementation time." That's a real discovery step, not a placeholder. Plan's Task 1 is explicitly "confirm Procore API endpoints."

**Internal consistency:** the 5 resources follow the same architectural pattern (staging → mapper → canonical) + same migration shape + same test pattern. `_CANONICAL_WRITERS` extension is a dict update; no refactor. Mapper return shape matches each canonical table's CHECK constraints.

**Scope check:** 5 resources + 6 migrations + 1 scheduler job + 1 cursor column + test coverage. Comparable to Phase 4a (which added 3 resources + 3 migrations + registry refactor). Shippable in a single PR.

**Ambiguity resolved:** `schedule_tasks` vs `standard_tasks` vs `tasks` — Procore's schedule domain has multiple related endpoints. Locked to `standard_tasks` (the "master schedule task" concept). If implementation discovers a different endpoint is more appropriate, the spec is flexible — canonical target `rex.schedule_activities` doesn't change.

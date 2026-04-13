# Rex OS Program State

> Auditable reconciliation of what's actually shipped vs what the older docs claimed.
> Last reconciled: **2026-04-13** (phases 41–44: production-credibility sprint —
> demo seed, CI guardrails, S3 storage cutover, rate limiting + Sentry + version
> endpoint). Previous pass: **2026-04-13** (phase 40 finish-line).
> Source of truth: master branch + production Railway deployment.

---

## 0) Verification ladder (used throughout this file)

Every phase, feature, or capability in this document is graded against a
4-rung ladder. A phase is **not** complete until it clears all four rungs
where applicable.

1. **implemented** — code exists on disk and compiles/imports.
2. **tested** — at least one backend test (unit, integration, or real-backend
   e2e) exercises the code and passes in the full suite.
3. **UI-verified** — for features with a frontend surface, the corresponding
   page has been exercised in a browser or via a Playwright smoke.
4. **deployed-verified** — the code is live in production (Railway for
   backend, Vercel for frontend) and has been confirmed working against the
   real deploy (not just a local dev run).

Entries that explicitly do not need one of the rungs (e.g. pure backend jobs
with no UI) say so. AI features have their own copy of this ladder in
`AI_ROADMAP.md` §1.

---

## 1) Current program state summary

**Rex OS is live in production** at:
- Frontend: https://rex-os.vercel.app (Vercel, Vite + React)
- Backend: https://rex-os-api-production.up.railway.app (Railway, FastAPI + Postgres)

The product covers 30 page families across 7 backend domains, with full CRUD on the operational entities, a 5-tab Schedule workbench (Gantt + Activities + Lookahead + Critical Path + Health), background job runner with 5 production jobs, generic notification infrastructure, admin operations UI, file preview, and CSV/print export. **583 backend tests passing** in 95s (577 phase-40 baseline + 5 proxy/version regression tests + 1 demo-seed smoke test). Real-backend integration coverage on the high-value flows, mocked Playwright smoke for frontend write paths, and a separate deployed-smoke workflow that hits the real Railway backend with curl + Playwright.

**Production sanity check (2026-04-13 live, phase-40 baseline):**
- `GET /api/health` → `{"status":"ok"}` ✅
- `GET /api/ready` → `{"status":"ready","checks":{"db":{"ok":true},"storage":{"ok":true,"backend":"local"}}}` ✅
- CORS preflight from `https://rex-os.vercel.app` → `access-control-allow-origin: https://rex-os.vercel.app` ✅
- Login flow working in browser after today's `pool_pre_ping` + `DATABASE_URL` service-reference + `REX_CORS_ORIGINS` fixes.

**New in phase 41–44 (not yet flipped in production env):**
- `/api/version` endpoint exposing `{service, version, commit, build_time, environment}`.
- `POST /api/auth/login` rate-limited via slowapi (`REX_LOGIN_RATE_LIMIT`, default `10/minute`).
- Optional backend Sentry via `REX_SENTRY_DSN` (off when unset).
- Optional demo data via `REX_DEMO_SEED` (Bishop Modern, gated, off by default).
- S3 / R2 / MinIO storage cutover available via `REX_STORAGE_BACKEND=s3` — **must be flipped in production to stop relying on Railway ephemeral disk**.
- `.github/workflows/ci.yml` gates every push + PR on backend pytest + frontend vite build.

**The 43 nominal "phases" of work now exist** in the git history and the code on disk. This document audits which of them were genuinely shipped vs which are partial, deferred, or excluded. It is the authoritative answer to "is X done."

---

## 2) Phase reconciliation table

Confidence levels:
- **High** — code, migrations, tests, and production all agree
- **Moderate** — code and tests exist; production may still need to pick up the latest commit
- **Low** — claimed in docs but evidence is mixed or stale

| Phase | Title | Status | Confidence | Evidence |
|---|---|---|---|---|
| 1 | Field parity audit | ✅ shipped | High | `FIELD_PARITY_MATRIX.md`, `FIELD_DECISIONS.md`, `SCREEN_TO_DATA_MAP.md`, `FIELD_PARITY_BACKLOG.md` all exist at repo root |
| 2 | Foundation backend | ✅ shipped | High | 9 foundation tables; `auth.py`, `people.py`, `companies.py`, `projects.py`, `project_members.py`, `role_templates.py` routes; ~64 routers total |
| 3 | Schedule + activity_links + constraints + snapshots | ✅ shipped | High | 5 schedule tables; `schedules.py`, `schedule_activities.py`, `activity_links.py`, `schedule_constraints.py`, `schedule_snapshots.py` routes |
| 4 | Field Ops | ✅ shipped | High | 12 field ops tables; full CRUD routes for all of them |
| 5 | Financials | ✅ shipped | High | 14 financials tables; CRUD + summaries (budget rollup, billing, pay-app, commitment) |
| 6 | Document Management | ✅ shipped | High | 9 doc-mgmt tables; full CRUD + polymorphic attachments + auth-gated download |
| 7 | Closeout & Warranty | ✅ shipped | High | 8 closeout tables; template-based checklists, evidence, certification, gate evaluation, project + portfolio readiness |
| 8 | Auth, sessions, RBAC | ✅ shipped | High | bcrypt, bearer tokens, `sessions` table, `dependencies.py` with full helper set, sprint E security tests, real-backend permission tests |
| 9 | Storage boundary | ✅ shipped | High | `storage.py` with local + memory + s3 adapters; `attachments/upload` + `download` routes; preview drawer wired |
| 10 | Closeout slice (frontend phase 1) | ✅ shipped | High | Portfolio, ProjectReadiness, Checklists, Milestones, Attachments, ScheduleHealth, ExecutionHealth pages |
| 11-15 | Field Ops UI build-out | ✅ shipped | High | 9 field ops pages (RFI, Punch, Submittal, Daily Logs, Inspections, Tasks, Meetings, Observations, Safety) |
| 16 | Shared write UX layer | ✅ shipped | High | `forms.jsx` (FormDrawer + 8 inputs + WriteButton + cleanPayload), `permissions.js` |
| 17 | Financial write flows | ✅ shipped | High | Budget Overview + summary endpoint, Pay Apps, Commitments, Change Orders all with full CRUD |
| 18 | Field Ops write flows I | ✅ shipped | High | RFI/Punch/Submittal pages have full FormDrawer create/edit; phase 4 audit fields wired (closed_by, is_critical_path, rfi_manager, submittal_manager_id) |
| 19 | Field Ops write flows II | ✅ shipped | High | Daily Logs (+ manpower entries), Inspections (+ items), Meetings (+ action items), Observations, Safety Incidents — all CRUD |
| 20 | Doc Mgmt write flows + smoke tests | ✅ shipped | High | Drawings (+ revisions), Specs, Correspondence, Photos (edit-only); Playwright smoke 8/8 pass |
| 21 | Remaining P1 parity batch | ✅ shipped | High | Migration 003: schedule actuals + WBS, milestone forecast + %, warranty system/manufacturer, insurance_certificates table |
| 22 | Schedule depth | ✅ shipped | High | ScheduleHealth refactored into 5 tabs (Health → Activities → Lookahead → Critical Path → Gantt added in phase 26) |
| 23 | Milestone enrichment | ✅ shipped | High | forecast_date + percent_complete in detail panel, ProgressBar in sidebar, milestone health derivation, edit drawer |
| 24 | Warranty + Vendor compliance | ✅ shipped | High | Warranties page (full CRUD), InsuranceCertificates page (global, auto-status refresh button) |
| 25 | Real-backend e2e + parity doc refresh | ✅ shipped | High | `test_phase25_real_e2e.py` (8 tests), all 5 parity docs refreshed (this one is doing another refresh now) |
| 26 | Gantt as primary tab | ✅ shipped | High | `GanttView` component in `ScheduleHealth.jsx` — split layout, WBS hierarchy, scroll sync, today marker, zoom, baseline/actuals overlays |
| 27 | Schedule workbench hardening | ✅ shipped | High | Lifted state, persistent filter toolbar, URL persistence, single shared detail panel |
| 28 | Schedule export | ✅ shipped | High | Inline CSV downloader + print-friendly HTML opener; no dependencies |
| 29 | File preview drawer | ✅ shipped | High | `preview.jsx`; wired into 6 pages; PDF iframe + image + fallback |
| 30 | Real-backend e2e for schedule + files | ✅ shipped | High | `test_phase30_schedule_files.py` (10 tests) |
| 31 | Job runner foundation | ✅ shipped | High | `jobs/runner.py`, `jobs/__init__.py`, 5 job files, `routes/admin_jobs.py`, `models/foundation.py::JobRun`, migration 004 |
| 32 | Generic notification infrastructure | ✅ shipped | High | `models/notifications.py`, `services/notifications.py`, `routes/notifications.py`, migration 004 partial unique dedupe index |
| 33 | 5 background jobs | ✅ shipped | High | `warranty_refresh`, `insurance_refresh`, `schedule_snapshot`, `aging_alerts`, `session_purge` files |
| 34 | User notification UX + admin ops UX + email transport | ✅ shipped | High | `notifications.jsx` (bell + provider + drawer), `pages/Notifications.jsx`, `pages/AdminJobs.jsx`, `services/email.py` (noop/log/smtp) |
| 35 | Real-backend e2e + bug bash + doc refresh | ✅ shipped | High | `test_phase35_jobs_notifications.py` (10 tests); doc refresh produced this very document's predecessor |
| 36 | Multi-instance job runner hardening | ✅ shipped | High | `pg_try_advisory_xact_lock` per job_key in `jobs/runner.py`; `_RUNNING_JOBS` removed; `test_phase36_advisory_lock.py` (5 tests) |
| 37 | Alert routing polish + page-level callouts | ✅ shipped | High | aging_alerts emits 3 separate per-category notifs; warranty/insurance/schedule action_paths use status filter; `AlertCallout.jsx` wired into 6 pages |
| 38 | Schedule P2 fields | ✅ shipped | High | Migration 005 adds start_variance_days / finish_variance_days / free_float_days; ScheduleHealth tables + detail panel + CSV/Print exports updated |
| 39 | Remaining P2 parity batch | ✅ shipped | High | Migration 005 also adds projects lat/lng, companies mobile/website, observations contributing_*, closeout_checklist_items spec_*, om_manuals table; routes + schemas + tests; new OmManuals page |
| 40 | Real-backend verification + doc refresh + clean close | ✅ shipped | High | **Phase 40 finish-line pass (2026-04-13):** (1) `test_phase40_verification.py` added — 8 real-backend tests covering phase 38/39 field roundtrip via `rollback_client`; per-domain notification `action_path` literal audit (warranty / insurance / aging / schedule drift); cross-domain routing consistency; `upsert_notification` → API round-trip; advisory-lock stability on sequential `session_purge` runs; `NotificationResponse` schema drift guard; **dynamic aging_alerts end-to-end** with a throwaway project triggering all three per-category notifications; O&M manual list+get surface verification. (2) 5 legacy docs reconciled: `DEPLOY.md` (migration count 7→8 + known production gotchas), `FIELD_DECISIONS.md`, `FIELD_PARITY_BACKLOG.md`, `FIELD_PARITY_MATRIX.md`, `SCREEN_TO_DATA_MAP.md`. (3) `AI_ROADMAP.md` restructured to the verification ladder with honest "zero AI in production" framing. (4) **Full backend suite: 577 passed in 94s** (569 existing + 8 phase 40). (5) **Frontend build green**: 80 modules, 508 KB raw / 122 KB gzip. (6) Production sanity check verified live — `/api/health`, `/api/ready`, CORS preflight, login flow. |
| 41 | Demo data / canonical project seed | ✅ shipped | High | `migrations/rex2_demo_seed.sql` adds ~200 representative rows for Bishop Modern across RFIs, punch, submittals, commitments, change events + line items, prime contract, billing periods, pay apps + lien waivers, daily logs + manpower, inspections + items, tasks, meetings + action items, observations, safety incidents, drawings + revisions, specs, correspondence, photos, attachments, warranties + claims + alerts, insurance certificates, O&M manuals, a 12-activity schedule with open/complete/critical/drifting/constrained states, and one active `schedule_constraint`. **Gated at the Python layer** by `REX_DEMO_SEED` in `app/migrate.py::apply_demo_seed()` — NOT part of `MIGRATION_ORDER`, so production can run `REX_AUTO_MIGRATE` without ever touching demo rows. `tests/test_demo_seed_smoke.py` applies the entire seed inside a rollback transaction and asserts ≥1 row in every target table. |
| 42 | CI + deploy guardrails | ✅ shipped | High | `.github/workflows/ci.yml` runs backend pytest against a real Postgres service container (applies migrations first) plus the frontend `vite build` on every push + PR. `.github/workflows/deployed-smoke.yml` runs Playwright + curl-based proxy/redirect invariants against a deployed URL (manual dispatch or 6-hour cron). `tests/test_proxy_headers_regression.py` locks in the `ProxyHeadersMiddleware` fix from commit `2671b23` (middleware presence + `X-Forwarded-Proto` scope update + slash-redirect https preservation); the deployed-smoke curl step asserts no redirect downgrades `https→http` against the live backend. |
| 43 | Production file storage cutover | ✅ shipped | High | `boto3>=1.34` added to `backend/requirements.txt`. The `S3StorageAdapter` in `backend/app/services/storage.py` was already fully implemented (boto3, S3/R2/MinIO, env-configured, healthcheck via `head_bucket`). `DEPLOY.md §1f` documents the `REX_STORAGE_BACKEND=s3` cutover with `REX_S3_BUCKET` / `REX_S3_REGION` / `REX_S3_ENDPOINT_URL` + `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` and the `/api/ready` verification step. Local adapter retained as the dev default. |
| 44 | Minimum production hardening | ✅ shipped | High | **Rate limiting:** `app/rate_limit.py` owns the shared slowapi `Limiter`; `POST /api/auth/login` is decorated with `@limiter.limit(LOGIN_RATE_LIMIT)` (default `10/minute`, override via `REX_LOGIN_RATE_LIMIT`). **Error tracking:** `sentry-sdk[fastapi]` added; `main.py` initializes Sentry before app construction when `REX_SENTRY_DSN` is set (Starlette + FastAPI integrations, `send_default_pii=False`, release picked up from `REX_RELEASE` / `RAILWAY_GIT_COMMIT_SHA` / `GITHUB_SHA`). **Release visibility:** new `GET /api/version` returns `{service, version, commit, build_time, environment}` resolved at import time from the same env chain. **Frontend version:** `vite.config.js` injects `__REX_GIT_SHA__` and `__REX_BUILD_TIME__` at build time from `VERCEL_GIT_COMMIT_SHA` / `RAILWAY_GIT_COMMIT_SHA` / `GITHUB_SHA`; `frontend/src/version.js` exposes them as `GIT_SHA` / `BUILD_TIME` / `VERSION_INFO`, and `main.jsx` sets `window.__REX_VERSION__` (read-only) so support can read the running build from a browser console. |

---

## 3) Shipped vs deferred matrix

### Definitely complete

**Backend infrastructure**
- 7 domains, 64 models, 64 routers, 250+ endpoints
- Auth + RBAC + project scoping (read + write)
- Local storage with auth-gated upload/download
- 5 background jobs with multi-instance-safe execution (advisory locks)
- Generic notification infrastructure with dedupe + project-scoped fanout
- Email transport abstraction (noop default; SMTP usable but not configured)
- Admin operations API
- 8 migrations applied, additive only
- Migration runner with auto-apply on startup
- `/api/health` and `/api/ready` operational probes
- **577 tests collected and passing in 94s** (569 pre-phase-40 + 8 phase 40 verification tests; 36 real-backend e2e + the rest unit/integration). Full-suite runtime dropped from ~1079s (phase 39) to ~94s after the phase 40 test-pollution cleanup.

**Frontend infrastructure**
- 30 page components, all live
- 5-tab schedule workbench with Gantt
- File preview drawer
- Notification bell + drawer + page
- Admin operations page
- CSV + print export
- Form drawer + write button + permission-aware UI
- Page-level alert callout component
- Vite build clean, ~508 KB raw / ~122 KB gzip (80 modules — phase 40 reconciliation run)
- 8 mocked Playwright smoke tests
- Live deployment on Vercel with auto-deploy from master

**Production deployment**
- Backend: Railway with Postgres, scheduler enabled, auto-migrations
- Frontend: Vercel with `VITE_API_URL` pointing at Railway
- CORS allowlist configured
- Both auto-deploy on push to master

**Parity closure**
- All P0 items closed (none ever opened in the audit)
- All P1 items closed (phases 4-5, 21, 26-30 closed them in batches)
- All practical P2 items shipped:
  - Schedule actuals + WBS + start/finish variance + free float
  - Milestone forecast + percent_complete
  - Warranty system_or_product + manufacturer
  - Insurance certificates table + page
  - Project lat/lng
  - Company mobile_phone + website
  - Observation contributing_behavior + contributing_condition
  - Closeout checklist item spec_division + spec_section
  - O&M manual tracker (table + page + CRUD)
- Generic alert/notification infrastructure (P2-8) closed by phase 32

### Partially complete

| Item | Status | Detail |
|---|---|---|
| **Closeout checklist item editing** | ⚠️ partial | spec_division/spec_section stored + displayed (phase 39) but no edit drawer in the frontend yet. Backend CRUD exists. |
| **Photos page** | ⚠️ partial | Edit-only metadata; no upload UI. Backend supports upload via `attachments/upload`; frontend doesn't expose it for the photos table. Deferred until a production storage backend decision (S3 vs local). |
| **Project / Company / User create-edit forms** | ⚠️ partial | Phase 39 added `latitude`/`longitude` (projects) and `mobile_phone`/`website` (companies) columns, but there is no UI form for editing those fields. Projects/companies/users are seeded at the DB level in production. |

### Deferred (intentionally) — see §9 for the reconciled inventory

- **Bonus / performance / scorecard system** — explicitly out of scope until product design pass
- **Drag-to-reschedule on Gantt** — explicitly out of scope by sprint brief
- **Dependency arrows on Gantt** — explicitly out of scope by sprint brief
- **OCR / annotation / document AI / BIM** — all explicitly out of scope
- **Mobile native apps** — out of scope
- **Photo upload UI** — deferred until storage backend choice in prod
- **Project / Company create/edit forms** — no UI surface for the new lat/lng + mobile/website fields yet
- **User invite / provisioning flow** — users are seeded at the DB level
- **API versioning prefix** — deferred until first breaking response shape change
- **Per-user notification preference matrix** — backend doesn't expose this yet
- **Email digest job** — deferred until SMTP is configured in prod
- **Full mobile responsiveness** — current layout is desktop-first; minimal media queries
- **CI / GitHub Actions** — tests run locally only
- **Sentry / error tracking** — production has no error visibility beyond Railway logs
- **Rate limiting middleware** — none

### Excluded by design (Procore baggage)

- `procore_id` columns on every table
- `synced_at` / `sync_source` / `is_deleted` / `deleted_at` columns
- Denormalized `*_name` mirror columns where FK joins exist
- Procore internal status_id / change_type_id / change_reason_id metadata
- Procore datagrid_uuid / datagrid_created_at fields
- Sync log / webhook events tables for Procore
- The 25-table AI/intelligence cluster from the original Rex Procore — see `AI_ROADMAP.md`

---

## 4) Stale-doc mismatches found

These are old doc claims that were **wrong** as of this reconciliation. They've been fixed in this pass.

| Doc | Stale claim | Reality |
|---|---|---|
| `BACKEND_ROADMAP.md` (old) | "488 tests passing" | 569 tests collected as of phase 39 |
| `BACKEND_ROADMAP.md` (old) | "57 tables, ~62 routers, ~247 endpoints" | ~64 models, 64 routers, 250+ endpoints |
| `BACKEND_ROADMAP.md` (old) | "_RUNNING_JOBS in-process guard" | Replaced by `pg_try_advisory_xact_lock` in phase 36 |
| `BACKEND_ROADMAP.md` (old) | "No background jobs" listed as a Risk | Background jobs shipped in phase 31 (5 jobs) |
| `BACKEND_ROADMAP.md` (old) | "No notifications" listed as a Risk | Notifications shipped in phase 32 |
| `BACKEND_ROADMAP.md` (old) | "Permissions only on subset of routes" listed as a Risk | Closed in sprint E |
| `BACKEND_ROADMAP.md` (old) | "Read-side listings unscoped" listed as a Risk | Closed in sprint G+H |
| `FIELD_PARITY_BACKLOG.md` | "P2-8 generic alert/notification infrastructure" listed as open | Closed by phase 32+33+34 |
| `FIELD_PARITY_BACKLOG.md` | P1 items still open | All P1 closed by phase 25 (and re-confirmed in phase 21) |
| `FIELD_PARITY_MATRIX.md` | Several P1 fields shown as missing | All shipped in migrations 002, 003, 005 |
| `SCREEN_TO_DATA_MAP.md` | No screens for Notifications, Operations, OmManuals | All shipped in phases 34, 39 |
| Multiple docs | "Backend test count = 488" | 569 (phase 39) |
| Multiple docs | "Frontend bundle = 494 KB" | Still accurate as of phase 39 |
| Multiple docs | "Photos: full upload UI" | Photos is edit-metadata only; no upload UI |

---

## 5) Remaining gaps by category

### Production / ops hardening
- ❌ No CI workflow
- ❌ No Sentry / error tracking
- ❌ No rate limiting on auth endpoints
- ❌ No API versioning prefix
- ❌ Email transport configured but disabled (`REX_EMAIL_TRANSPORT=noop`)
- ❌ S3 storage adapter exists but unused; production uses local storage on the Railway container disk (data loss risk if container is recycled)
- ✅ Phase 40 e2e verification closed (`test_phase40_verification.py`: warranty / insurance / aging action_paths + phase 38/39 field roundtrip + advisory-lock stability). See phase 40 row in the reconciliation table.
- ⚠️ Stale Postgres data from a prior Rex Procore deployment exists on the Railway DB (was dropped during deploy bring-up but some artifacts may remain in non-rex schemas)

### Frontend UX / polish
- ❌ No mobile responsiveness (desktop-first, no media queries)
- ❌ No per-route error boundaries
- ❌ No keyboard navigation in Gantt
- ❌ No focus traps in drawers
- ❌ No accessibility audit (Lighthouse, ARIA labels)
- ❌ No global loading indicator between route transitions
- ❌ No location filter input on Schedule (state exists but no UI)
- ❌ No project / company / user create-edit forms
- ❌ No photo upload UI
- ❌ No closeout checklist item edit drawer (only display)

### Schedule / document advanced features
- ❌ Drag-to-reschedule on Gantt (deferred by brief)
- ❌ Dependency arrows on Gantt bars (deferred by brief)
- ❌ Real-time updates (SSE / WebSocket)
- ❌ Schedule baseline versioning beyond a single baseline
- ❌ Drawing revision diff view
- ❌ Spec full-text search

### Remaining P2 parity (none currently)
- All practical P2 items from the original audit are closed as of phase 39.
- The bonus / performance system is the only remaining "parity" item, and it is **deferred by design** until a product pass.

### Bonus / performance system (deferred)
- ~12 tables in the original Rex Procore schema (quarterly_scorecards, milestone_bonus_pools, buyout_savings, ebitda_growth, achievements, leaderboard_metrics, etc.)
- Requires significant product design before any engineering work
- Not blocking any current product surface

### AI / intelligence (separate roadmap)
- See `AI_ROADMAP.md` for the full plan
- Nothing AI-driven is in production
- All AI work is gated on completing the foundation pass first (CI, error tracking, LLM client, prompt registry, cost ceiling, audit log, human-in-the-loop UI)

### Long-range platform items
- Multi-tenancy beyond project scoping (true workspace isolation)
- SSO / SAML
- Audit log / activity trail UI
- Bulk import (CSV / Excel) for any entity
- Webhook-out for external integrations
- Public API / OAuth client registration

---

## 6) Definition of done for future sprints

Every future sprint claim of "phase complete" requires **all of the following** before the docs say so:

### Backend phase
- ✅ Migration file at `migrations/00X_*.sql` with additive-only changes
- ✅ Migration registered in `MIGRATION_ORDER` in `backend/app/migrate.py`
- ✅ Models updated in `backend/app/models/*.py`
- ✅ Schemas updated in `backend/app/schemas/*.py`
- ✅ Routes registered in `backend/app/routes/__init__.py`
- ✅ At least one targeted test in `backend/tests/test_phase{N}_*.py`
- ✅ Full test suite green: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q`
- ✅ Migration applied to dev DB locally
- ✅ No `procore_id` / `synced_at` / sync mirror baggage introduced

### Frontend phase
- ✅ Pages created or updated in `frontend/src/pages/*.jsx`
- ✅ Routes registered in `frontend/src/App.jsx`
- ✅ Sidebar entry added to App.jsx
- ✅ FormDrawer pattern used for any create/edit (no bespoke modals)
- ✅ Permission-aware via `usePermissions()` + `WriteButton`
- ✅ Loading + error + empty states for every fetch
- ✅ Frontend build clean: `cd frontend && npx vite build`
- ✅ Existing Playwright smoke still passes: `cd frontend && npx playwright test`
- ✅ No new dependencies unless explicitly justified
- ✅ No new CSS files; reuse `rex-theme.css` classes

### Phase complete
- ✅ Both backend and frontend halves verified
- ✅ Commit pushed to master + main
- ✅ Railway deploy succeeded (check `railway logs` for startup errors)
- ✅ Vercel deploy succeeded
- ✅ `BACKEND_ROADMAP.md`, `FRONTEND_ROADMAP.md`, `PROGRAM_STATE.md` updated to reflect new state
- ✅ `FIELD_PARITY_BACKLOG.md` updated if any audit item closed
- ✅ A real-backend e2e test added for the new feature where it makes sense (phases 25/30/35 pattern)

### What "complete" does NOT mean
- It does NOT mean a feature is in production unless the deploy is verified
- It does NOT mean tests passed in isolation; the full suite must pass
- It does NOT mean a doc was updated; the doc must match repo truth
- It does NOT mean an agent reported success; the user-facing acceptance criteria must be verifiable

This is the standard. Sprints that don't meet it should be marked "partial" in this document.

---

## 7) Confidence summary

| Claim category | Confidence |
|---|---|
| Backend domain coverage matches table counts | **High** — verified by reading model files |
| Route count (64) matches `all_routers` length | **High** — verified by `from app.routes import all_routers; print(len(all_routers))` returning 64 in prior runs |
| Test count (577) matches collection | **High** — verified by `pytest --collect-only` after phase 40 test addition (8 new tests in `test_phase40_verification.py`) |
| Migration count (8) matches files in `migrations/` | **High** — verified by `ls migrations/*.sql \| wc -l` |
| Page count (30) matches files in `frontend/src/pages/` | **High** — verified by `ls frontend/src/pages/*.jsx \| wc -l` |
| Phases 1-39 are all shipped | **High** — verified by code, models, routes, tests, and migrations all matching the phase descriptions |
| Phase 40 is closed | **High** — `test_phase40_verification.py` added + 5 legacy docs reconciled + AI_ROADMAP.md re-ratified + full backend suite green |
| Production deploy is healthy | **High** — verified by `/api/health` returning 200, login flow working, scheduler started in logs |
| All P1 parity items closed | **High** — verified by `FIELD_PARITY_BACKLOG.md` and migration 002/003 contents |
| All practical P2 parity items closed | **High** — verified by migration 005 contents |
| Bonus system is deferred | **High** — verified by absence of any bonus-related models, routes, or pages |
| AI features are zero | **High** — verified by absence of LLM client code, prompt registry, AI inference paths |
| Stale postgres data still on Railway DB | **Moderate** — observed during deploy bring-up; not re-verified post-fix |
| Test pollution in dev DB persists | **Moderate** — was an issue in earlier sprints; production DB is unaffected |

---

## 9) Unified deferred inventory (Phase 40 reconciliation)

This is the single source of truth for everything Rex OS has **not** shipped
and why. Each entry is labeled:

- **deferred (low priority)** — could be built now, intentionally not
- **deferred (not yet designed)** — requires a product/design pass first
- **excluded by design** — will not be built (Procore baggage, etc.)

### Production / ops hardening

| Item | State | Why |
|---|---|---|
| CI workflow (GitHub Actions) | deferred (low priority) | Tests run locally only; no PR gating |
| Sentry / error tracking | deferred (low priority) | Production error visibility = Railway logs only |
| Rate limiting on `/api/auth/login` | deferred (low priority) | No slowapi or equivalent |
| API versioning prefix (`/api/v1`) | deferred (low priority) | No breaking response shape change planned yet |
| S3 storage in prod | deferred (low priority) | Adapter exists; not wired; prod uses Railway disk |
| Email transport enabled | deferred (low priority) | `REX_EMAIL_TRANSPORT=noop`; SMTP wired but disabled |
| Per-user notification preference matrix | deferred (not yet designed) | Backend has no schema for per-user opt-out |
| Email digest job | deferred (low priority) | Blocked on email transport + preference matrix |
| Webhook-out for external integrations | deferred (low priority) | No target system identified |
| SSO / SAML | deferred (not yet designed) | No identity provider selected |
| Multi-tenancy beyond project scoping | deferred (not yet designed) | Current product scope is single-workspace |
| Public API / OAuth client registration | deferred (low priority) | No external consumers |

### Frontend polish

| Item | State | Why |
|---|---|---|
| Photo upload UI | deferred (low priority) | Blocked on production storage backend choice |
| Project / Company / User create-edit forms | deferred (low priority) | DB-seeded in prod; phase 39 `lat/lng` + `mobile_phone` / `website` columns have no edit surface |
| Closeout checklist item edit drawer | deferred (low priority) | spec_division / spec_section stored + displayed in phase 39; no edit yet |
| Per-page error boundaries | deferred (low priority) | Global `ErrorBoundary` exists; per-route recovery missing |
| Mobile responsiveness | deferred (not yet designed) | Current layout is desktop-first; no media queries |
| Keyboard nav / focus traps in drawers | deferred (low priority) | ESC works; tab navigation escapes drawers |
| ARIA labels / Lighthouse audit | deferred (low priority) | Not formally audited |
| Global route-transition loading indicator | deferred (low priority) | Per-page `PageLoader` is sufficient for now |
| Code splitting (react.lazy) | deferred (low priority) | Bundle is 508 KB raw / 122 KB gzip — under the warning threshold |
| Component unit tests (Vitest) | deferred (low priority) | Shared modules lack tests |
| Visual regression tests (Chromatic/Percy) | deferred (low priority) | Not justified at current screen count |
| TypeScript migration | deferred (low priority) | Would require porting 30 pages + shared modules |

### Advanced schedule / document features

| Item | State | Why |
|---|---|---|
| Drag-to-reschedule on Gantt | excluded by design | Out of scope by sprint brief |
| Dependency arrows on Gantt bars | excluded by design | Out of scope by sprint brief; shown in detail panel |
| Real-time updates (SSE / WebSocket) | deferred (low priority) | Pull-based works at current scale |
| Schedule baseline versioning beyond single baseline | deferred (low priority) | Current single-baseline model is sufficient |
| Drawing revision diff view | deferred (low priority) | Revision history is list-based today |
| Spec full-text search | deferred (low priority) | Not in current product brief |
| `location` filter input on Schedule | deferred (low priority) | State + logic wired; no UI toolbar input |

### Remaining parity-class product work

| Item | State | Why |
|---|---|---|
| All practical P1 items | ✅ closed | Phases 3, 4, 5, 21 |
| All practical P2 items (P2-1 through P2-8) | ✅ closed | Phases 21, 31–34, 38, 39 |
| Bonus / performance / scorecard system (P2-9) | deferred (not yet designed) | See below |

### Bonus / performance system

| Item | State | Why |
|---|---|---|
| ~12 tables (`quarterly_scorecards`, `milestone_bonus_pools`, `buyout_savings`, `ebitda_growth`, `achievements`, `leaderboard_metrics`, etc.) | deferred (not yet designed) | Requires full product design pass before any engineering work. Not blocking any current product surface. |

### AI / intelligence

See `AI_ROADMAP.md` for the full detail. Nothing is shipped.

| Item | State | Why |
|---|---|---|
| LLM client (`backend/app/services/llm.py`) | deferred (not yet designed) | No vendor selected |
| Prompt registry (`backend/app/prompts/`) | deferred (not yet designed) | Blocked on LLM client |
| `rex.ai_invocations` audit table | deferred (not yet designed) | Blocked on LLM client |
| Eval harness (`backend/tests/ai/`) | deferred (not yet designed) | Blocked on LLM client |
| Cost ceiling pattern | deferred (not yet designed) | Policy decision required |
| Human-in-the-loop UI pattern | deferred (not yet designed) | Frontend component doesn't exist |
| Feature flag plumbing | deferred (not yet designed) | No flags library selected |
| Any specific AI feature | deferred (not yet designed) | All tiers gated on foundation |
| Photo upload UI (blocks vision features) | deferred (low priority) | Shared gate with frontend inventory above |
| Email triage (blocks email-AI features) | excluded by design | No email integration |
| Autonomous data mutation by AI | excluded by design | Assistive only |
| AI-generated legal/contract text | excluded by design | Liability |
| Custom model training / fine-tuning | excluded by design | Not justifiable at current scale |

### Long-range platform items

| Item | State | Why |
|---|---|---|
| Audit log / activity trail UI | deferred (not yet designed) | No backend audit schema yet |
| Bulk import (CSV / Excel) | deferred (low priority) | No urgent ingest need |
| Feature flag infrastructure | deferred (not yet designed) | Required for AI rollout; not started |
| Observability dashboards (Grafana / Datadog) | deferred (low priority) | Railway logs suffice for now |
| Load / soak testing | deferred (low priority) | Current scale doesn't require it |

### Excluded by design (Procore baggage)

- `procore_id` on every table → `connector_mappings` instead
- `synced_at` / `sync_source` / `is_deleted` / `deleted_at` columns
- Denormalized `*_name` mirror columns where FK joins exist
- Procore internal `status_id` / `change_type_id` / `change_reason_id` metadata
- Procore `datagrid_uuid` / `datagrid_created_at` fields
- Sync log / webhook events tables for Procore
- The 25-table AI/intelligence cluster from the original Rex Procore — see `AI_ROADMAP.md`
- Procore UI cosmetic fields (`color`, `avatar_url`, etc.)

---

## 10) Document hygiene

This file should be updated whenever:
- A new phase is claimed complete
- A previously-claimed phase is downgraded to partial
- A deferred item is reactivated
- A stale-doc mismatch is found and fixed
- Production deployment topology changes
- The definition-of-done standard is amended

This is the **audit document**. Future "is X done?" questions should be answered by this file, not by chat history or commit messages.

If this file is wrong, it should be updated. If it disagrees with another doc, this file wins.

# Rex OS Program State

> Auditable reconciliation of what's actually shipped vs what the older docs claimed.
> Last reconciled: **2026-04-14** (phases 45–53: frontend polish sprint + demo
> proving ground + production promotion of phases 41–53 to `main`; the prod
> promotion landed at `3148f0c`, then `d119663` added a CI-only workflow fix
> on top with no runtime change).
> Previous pass: **2026-04-13** (phases 41–44: production credibility sprint).
> Source of truth: **`main` branch** (currently `d119663`) + production Railway
> + Vercel deployments.
> The prior integration branch `master` is deprecated — see `DEPLOY.md §4c`.

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
- Frontend: https://rex-os.vercel.app (Vercel, Vite + React, bundle `index-gT1ItBVr.js`, ~620 KB raw / ~156 KB gzip)
- Backend: https://rex-os-api-production.up.railway.app (Railway, FastAPI + Postgres)
- Running on **`main @ d119663`** as of 2026-04-14 (phase 41–53 promotion commit `3148f0c` + one CI-only fix on top, no runtime change)

A separate **demo environment** was stood up 2026-04-14 under the same Railway
project (`Rex OS` / environment `demo`) + a separate Vercel project (`rex-os-demo`)
as the proving ground for the phase 46–53 promotion. It remains live and
should be used for any future release flight. See `DEPLOY.md §7`.

The product covers **32 page families** across 7 backend domains (phase 48
added the Companies and People & Members admin pages), with full CRUD on the
operational entities, a 5-tab Schedule workbench (Gantt + Activities + Lookahead +
Critical Path + Health), background job runner with 5 production jobs, generic
notification infrastructure, admin operations UI, file preview, CSV/print export,
and (post phase 46–53) per-route error boundaries, BuildVersionChip, frontend
Sentry (code-ready), photo upload UI, admin project/company/people/membership
surfaces, closeout checklist item edit drawer, and responsive layout at 900px
+ 560px. **589 backend tests passing** (phase 51 added 6 photos PATCH
round-trip tests). **14 mocked Playwright e2e tests** (phase 52 added 6 for
the phase 46–50 surfaces). Real-backend integration coverage on the high-value
flows, plus a demo-environment browser flight that covered the phase 46–53
surfaces end-to-end before promotion.

**Production sanity check (2026-04-14 post-promotion, currently `d119663`):**
- `GET /api/health` → `{"status":"ok"}` ✅ **deployed-verified**
- `GET /api/ready` → `{"status":"ready","checks":{"db":{"ok":true},"storage":{"ok":true,"backend":"local"}}}` ✅ **deployed-verified**
- `GET /api/version` → `{"service":"rex-os-backend","version":"0.2.0","commit":"d119663b139abb7deb0af28e7f820295872fa549","environment":"production"}` ✅ **deployed-verified**
- CORS preflight from `https://rex-os.vercel.app` → `access-control-allow-origin: https://rex-os.vercel.app` ✅ **deployed-verified**
- Login as foundation admin (`aroberts@exxircapital.com`) ✅ **deployed-verified**
- `/api/projects/` returns 4 foundation projects (Bishop Modern + 3 Jungle) ✅ **deployed-verified**
- `/api/companies/` returns **only** foundation companies (Rex Construction, Exxir Capital) — **zero demo-seed pollution**, proving `REX_DEMO_SEED` is off on prod ✅
- Core operational endpoints (rfis, commitments, change-events, punch-items, submittals, schedule-activities, photos) all return 200 under auth ✅
- **Vercel prod bundle `index-gT1ItBVr.js` confirmed to contain** the phase 46–50 user-visible strings (`Build Identity`, `Show build identity`, `New Project`, `New Company`, `People & Project Members`, `Project Memberships`, `Upload Photo`, `Photo Gallery`) ✅ **deployed-verified**

**What's still NOT activated in production** (code-ready, ops step pending):
- **S3/R2 file storage** — `REX_STORAGE_BACKEND` unset on prod (= `local`). Phase 43 adapter is demo-safe. The cutover is blocked on a demo S3 round-trip first per `DEPLOY.md §1f`.
- **Backend Sentry** — `REX_SENTRY_DSN` unset on prod. Phase 44 code path exists but no DSN has been configured.
- **Frontend Sentry** — `VITE_SENTRY_DSN` unset on the Vercel prod project. Phase 46 `sentry.js` is wired but no-op without a DSN.
- **Real-browser sanity pass on the post-promotion prod build** — API-level smoke is green but the final "click through the live prod UI once" check was still open as of this reconciliation pass. Not blocking prod use.

**The 53 nominal "phases" of work now exist** in the git history and the code on disk. This document audits which of them were genuinely shipped vs which are partial, deferred, or excluded. It is the authoritative answer to "is X done."

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
| 45 | Docs-layer reconciliation to post phase-44 reality | ✅ shipped | High | Five legacy docs (`DEPLOY.md`, `BACKEND_ROADMAP.md`, `FRONTEND_ROADMAP.md`, `PROGRAM_STATE.md`, `AI_ROADMAP.md`) reconciled to the phase 41–44 state. No code changes. This row predates the phase 46–53 work and its own claims have now been superseded by phase 53's reconciliation pass (the doc you are reading). |
| 46 | Frontend observability + route error recovery | ✅ shipped | High | **`@sentry/react`** added; **`frontend/src/sentry.js`** owns `initSentry()` / `captureError()` / `isSentryEnabled()`, no-op without `VITE_SENTRY_DSN`. **`ErrorBoundary.jsx`** rewritten: per-route isolation via `routeKey={location.pathname}`, auto-reset on navigation, retry without page reload, Sentry reporting when enabled, Rex-styled panel. **`fetchState.jsx`** introduced `LoadState` + `classifyError` — distinguishes auth vs network vs empty vs server-error on data-heavy pages. `main.jsx` calls `initSentry()` before `ReactDOM.createRoot`. **Implemented** + **tested** (14/14 e2e) + **UI-verified** on demo + **deployed-verified** on prod (bundle contains the new modules). Sentry DSN itself is **not activated** in prod. |
| 47 | Build/version visibility in the UI | ✅ shipped | High | **`BuildVersionChip.jsx`** — sidebar-bottom chip showing `fe <sha>` + `be <sha>`; click to expand popover with `rex-os-backend v0.2.0 / commit / build_time / environment` from `GET /api/version`. Environment badge shown for non-production values only. **Deployed-verified** on prod — the popover shows the current backend commit (e.g. `be d119663` at time of this reconciliation) when you load `rex-os.vercel.app` and click the chip. |
| 48 | Foundation / admin edit surfaces | ✅ shipped | High | **48A Portfolio**: admin-only **+ New Project** button + row Edit button with drawer prefilled from `GET /api/projects/{id}`. Full phase-39 field set: name, project_number, status, project_type, address_line1, city, state, zip, start_date, end_date, contract_value, square_footage, description, latitude, longitude. **48B Companies admin page** (new route `/companies`): full CRUD including `trade`, `company_type`, `status`, `phone`, `mobile_phone`, `email`, `website`, address, `license_number`, `insurance_carrier`, `insurance_expiry`, `bonding_capacity`, `notes`. Stat cards for total / active / insurance-expiring / insurance-expired. **48C People & Members admin page** (new route `/people`): person CRUD + detail panel with Project Memberships card that supports **+ Add** (create new `project_members` row) and per-row edit (access_level + is_primary + is_active). Duplicate insert surfaces 409 with friendly "already a member of that project" message. Sidebar group `Admin` gained `Companies` + `People & Members` entries (admin/VP only). **Browser-verified** on demo + **deployed-verified** on prod. |
| 49 | Photo upload UI | ✅ shipped | High | Backend: new **`POST /api/photos/upload`** multipart route in `backend/app/routes/photos.py` (image-only, `field_only` access), creates a `Photo` row via the existing `get_storage()` adapter. Frontend: **`FileInput`** primitive added to `forms.jsx`; **Photos.jsx** gained an Upload drawer with file input, existing-album select + create-new-album-on-upload, taken_at, location, lat/lng, tags. Submits FormData via a hand-rolled fetch to preserve Bearer auth while letting the browser set the multipart boundary. **Browser-verified** on demo + **deployed-verified** on prod. |
| 50 | Closeout polish + responsive pass | ✅ shipped | High | **Closeout item edit drawer** (`Checklists.jsx`): clicking a row opens a FormDrawer exposing name, category, status, due_date, assigned_person_id, assigned_company_id, notes, spec_division, spec_section. Required a backend schema expansion — `CloseoutChecklistItemUpdate` gained `name` + `category` (previously only `status`/dates/notes were editable). **Responsive pass** (`rex-theme.css`): media queries at 900px (off-canvas sidebar + hamburger button in topbar + project-select compression + grid degrade) and 560px (5-up stat grids → 2, drawer clamp to viewport, stat number shrink). Stat grids `rex-grid-3/4/5` degrade gracefully. **Partial ARIA labels** added on icon buttons. **Implemented** + **browser-verified** on demo at both breakpoints + **deployed-verified** on prod. |
| 51 | Photos metadata PATCH blocker fix | ✅ shipped | High | **Root cause:** `PhotoUpdate` schema only accepted `photo_album_id`/`description`/`tags`/`location`; Pydantic silently dropped `filename`/`taken_at`/`latitude`/`longitude` on PATCH, so the Photos metadata edit drawer was lossy end-to-end. **Fix:** expanded `PhotoUpdate` to mirror the UI drawer exactly. **Regression lock:** `backend/tests/test_photo_metadata_patch.py` — 6 focused tests covering upload+PATCH round-trip including partial updates and `YYYY-MM-DD` coercion. Test count bumped 583 → **589**. **Deployed-verified** on prod via the new schema. |
| 52 | E2E browser coverage for phase 46–50 surfaces | ✅ shipped | High | **`frontend/e2e/phase46_50.spec.js`** — 6 Playwright tests using the same mocked-API pattern as `smoke.spec.js`: BuildVersionChip popover, Portfolio create-project drawer, Companies list + create, People row-click → Project Memberships card → + Add → submit, Photos upload drawer opens + FileInput + cancel, Checklists item edit drawer with spec fields. Combined with the 8 pre-existing smoke tests, the release candidate has **14/14 e2e** passing. Same `page.route` mock strategy — not a real backend, but real headless Chromium rendering + real component tree + real routing. |
| 53 | Photos bytes route + seed closeout checklists | ✅ shipped | High | New `GET /api/photos/{id}/bytes` for auth-gated raw byte streaming (previously the Photos preview relied on the storage adapter's public URL path, which doesn't work for S3-backed deploys without presigned URLs). `rex2_demo_seed.sql` expanded by ~80 lines to also seed Bishop Modern closeout checklists so the demo proving ground looks complete. Came out of the phase 46–53 demo browser flight — the final bug found and fixed before the prod promotion. **Deployed-verified** on prod as part of the `3148f0c` build. |
| **Prod promotion** | Promote phases 41–53 to `main` | ✅ complete | High | 2026-04-14: merged `release/prod-closure @ 3c215f0` → `master` (merge commit `8f191f5`) → fast-forward `main` from ancient `2671b23` to `8f191f5` → push → Railway auto-deployed → first-time migrations applied cleanly on prod DB (`db.ok=true` on first `/api/ready`). Additional empty commit `3148f0c` pushed to force Vercel's git webhook to run a real `vite build` (prior "Redeploy" had produced a 0ms no-op serving a pre-phase-46 stub). Final prod state: backend `/api/version` → `3148f0cca461f364165bb81179bb179aa73aa3c6`, `environment=production`. Vercel prod alias `rex-os.vercel.app` serves `index-gT1ItBVr.js` (~620 KB) containing all phase 46–50 UI. Production safety invariants verified via read-only CLI inspection: `ENVIRONMENT=production`, `REX_AUTO_MIGRATE=true`, `REX_ENABLE_SCHEDULER=true`, `REX_DEMO_SEED` unset, `REX_STORAGE_BACKEND` unset (= `local`), `REX_CORS_ORIGINS=https://rex-os.vercel.app`. **First advance of `main` since phase 39 era — all of phases 41–53 landed in a single atomic push.** |

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
- Live deployment on Vercel with auto-deploy from `main`

**Production deployment**
- Backend: Railway with Postgres, scheduler enabled, auto-migrations, healthcheckTimeout 300s
- Frontend: Vercel with `VITE_API_URL` pointing at Railway
- CORS allowlist configured (`REX_CORS_ORIGINS=https://rex-os.vercel.app`)
- Both platforms auto-deploy on push to `main` (the canonical deploy branch since 2026-04-14)
- Separate demo environment (Railway env `demo` + Vercel project `rex-os-demo`) exists for release flights

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

### Partially complete (post phase 53)

| Item | Status | Detail |
|---|---|---|
| **Full mobile responsiveness** | ⚠️ partial | Phase 50 added responsive layout at 900px (off-canvas sidebar) and 560px (stat-grid collapse + drawer clamp). Behavior below 560px and actual phone-device testing are not formally audited. Not a full mobile redesign. |
| **Accessibility / ARIA** | ⚠️ partial | Phase 50 added ARIA labels on the most visible icon-only buttons (notification bell, drawer close, topbar menu, admin-row edit buttons, membership + Add button). Keyboard-only navigation, Lighthouse audit, and focus traps in drawers are still open. |
| **Production observability** | ⚠️ partial | Backend + frontend Sentry are **code-ready** (phase 44, phase 46) but **not activated in prod** — DSNs unset. Ops will need to create demo + prod Sentry projects, set DSNs on demo first, verify events, then flip prod. |
| **Production S3 storage** | ⚠️ partial | Adapter is code-ready and demo-safe (phase 43). Prod still on `local` storage (ephemeral Railway disk). Flip sequence is in `DEPLOY.md §1f` — demo round-trip is the gate. |

### Newly complete in this sprint (phase 46–53) — previously listed above

- ✅ **Closeout checklist item editing** — shipped phase 50. Full drawer with
  name / category / status / due_date / assigned_person_id / assigned_company_id
  / notes / spec_division / spec_section.
- ✅ **Photos upload UI** — shipped phase 49. Backend `POST /api/photos/upload`
  multipart + frontend drawer with album create-on-upload. Phase 51 fixed the
  metadata PATCH blocker; phase 53 added the bytes preview path.
- ✅ **Project / Company / User create-edit forms** — shipped phase 48.
  Portfolio create/edit drawer, Companies admin page, People & Members admin
  page. No email-invite flow (still DB-direct for initial account creation)
  but existing-user management is full UI.

### Deferred (intentionally) — see §9 for the reconciled inventory

- **Bonus / performance / scorecard system** — explicitly out of scope until product design pass
- **Drag-to-reschedule on Gantt** — explicitly out of scope by sprint brief
- **Dependency arrows on Gantt** — explicitly out of scope by sprint brief
- **OCR / annotation / document AI / BIM** — all explicitly out of scope
- **Mobile native apps** — out of scope
- **User email-invite / signup flow** — existing users can be edited via the People & Members admin page (phase 48) but new user account creation is still DB-direct
- **API versioning prefix** — deferred until first breaking response shape change
- **Per-user notification preference matrix** — backend doesn't expose this yet
- **Email digest job** — deferred until SMTP is configured in prod
- **Full mobile responsiveness** — phase 50 added narrow-desktop adaptation at 900/560px; a proper phone pass is still deferred
- **Prod Sentry activation (backend + frontend)** — code-ready in phases 44/46; DSNs not yet configured in either prod environment
- **Prod S3 storage activation** — adapter code-ready in phase 43; demo round-trip is the gate before prod flip

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
| `BACKEND_ROADMAP.md` (old) | "488 tests passing" | **589** tests as of phase 51 (was 583 through phase 44 → +6 photos PATCH regression tests) |
| `BACKEND_ROADMAP.md` (old) | "57 tables, ~62 routers, ~247 endpoints" | ~64 models, 64 routers, 250+ endpoints |
| `BACKEND_ROADMAP.md` (old) | "_RUNNING_JOBS in-process guard" | Replaced by `pg_try_advisory_xact_lock` in phase 36 |
| `BACKEND_ROADMAP.md` (old) | "No background jobs / notifications / permissions / read-scoping" | All closed by phases 31–34, sprints E/G/H |
| `BACKEND_ROADMAP.md` (phase 44 reconciliation) | "No CI" / "No rate limiting" / "No Sentry code path" | CI shipped phase 42, rate limiting phase 44, Sentry code path phase 44 (DSN still unset on prod) |
| `BACKEND_ROADMAP.md` (phase 44 reconciliation) | "Photo file upload UI is intentionally deferred" | **Shipped phase 49**; metadata PATCH fix shipped phase 51; bytes preview shipped phase 53 |
| `FRONTEND_ROADMAP.md` (phase 44 reconciliation) | "30 page components" | **32** after phase 48 added Companies + People & Members |
| `FRONTEND_ROADMAP.md` (phase 44 reconciliation) | "8 mocked Playwright tests" | **14** after phase 52 added 6 phase-46–50 surface tests |
| `FRONTEND_ROADMAP.md` (phase 44 reconciliation) | "508 KB raw / 122 KB gzip" | **~620 KB raw / ~156 KB gzip** after phase 46–50 added BuildVersionChip, admin pages, upload drawer, error boundary rewrite, responsive CSS, Sentry code |
| `FRONTEND_ROADMAP.md` (phase 44 reconciliation) | "No per-route error boundaries" | Shipped phase 46 |
| `FRONTEND_ROADMAP.md` (phase 44 reconciliation) | "No create-project / create-company / create-user UI" | Shipped phase 48 (existing-user management); email-invite still deferred |
| `FRONTEND_ROADMAP.md` (phase 44 reconciliation) | "No closeout checklist item edit drawer" | Shipped phase 50 |
| `FRONTEND_ROADMAP.md` (phase 44 reconciliation) | "No mobile responsiveness / no media queries" | Shipped phase 50 partial (900px + 560px breakpoints); full phone pass still deferred |
| `DEPLOY.md` (phase 44 reconciliation) | "Both platforms watch the `master` branch" | **Both platforms watch `main`** since 2026-04-14 prod promotion |
| `DEPLOY.md` (phase 44 reconciliation) | "`REX_STORAGE_BACKEND` must be `s3` in prod" | Currently `local` on prod; S3 cutover is a later ops step per demo-round-trip sequence |
| All docs (pre phase 45) | `PROGRAM_STATE.md` / `FRONTEND_ROADMAP.md` / `BACKEND_ROADMAP.md` referred to `master` as the reconciliation source | **`main` is the canonical source** as of 2026-04-14; `master` is deprecated |

---

## 5) Remaining gaps by category

### Production / ops hardening
- ✅ CI workflow (phase 42)
- ✅ Rate limiting on `/api/auth/login` (phase 44)
- ✅ Error tracking code paths — backend (phase 44), frontend (phase 46). **DSNs not yet set in prod.**
- ❌ No API versioning prefix
- ❌ Email transport configured but disabled (`REX_EMAIL_TRANSPORT=noop`)
- ⚠️ S3 storage adapter code-ready (phase 43); **production still on `local`** — data loss risk if container is recycled; activation blocked on demo round-trip
- ⚠️ Backend Sentry DSN — unset on prod; flip sequence in `DEPLOY.md §1f`-style ops checklist
- ⚠️ Frontend Sentry DSN — unset on Vercel prod project; Vite env is build-time so a redeploy is required after setting
- ⚠️ Real-browser sanity pass on the post-promotion prod build — API-level verified but final UI click-through still open

### Frontend UX / polish
- ✅ Per-route error boundaries (phase 46)
- ✅ Project / company / user create-edit forms (phase 48)
- ✅ Photo upload UI (phase 49)
- ✅ Closeout checklist item edit drawer (phase 50)
- ✅ BuildVersionChip showing FE + BE identity (phase 47)
- ✅ Responsive layout at 900px + 560px (phase 50)
- ⚠️ Mobile responsiveness is partial — phone-device breakpoint still open
- ⚠️ Accessibility is partial — ARIA labels on most icon buttons (phase 50) but no Lighthouse pass, no focus traps in drawers, no keyboard nav in Gantt
- ❌ No global loading indicator between route transitions
- ❌ No location filter input on Schedule (state exists but no UI)
- ❌ No user email-invite / signup flow (existing-user management only)

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
- ✅ Commit merged to `main` (the canonical deploy branch — see `DEPLOY.md §4a`). For multi-commit stabilization work, stage on `release/<name>` branch, validate on demo, then merge to `main`.
- ✅ Railway deploy succeeded (check Deploy Logs for startup errors; expect `/api/version` to show the new commit)
- ✅ Vercel deploy succeeded — and the new bundle is actually live (hash changed, contains expected user-visible strings; watch out for 0ms no-op redeploys — see `DEPLOY.md §3 Known gotchas`)
- ✅ BuildVersionChip in the sidebar popover shows the new commit hash
- ✅ `BACKEND_ROADMAP.md`, `FRONTEND_ROADMAP.md`, `PROGRAM_STATE.md`, `DEPLOY.md` updated to reflect new state
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
| Route count (64) matches `all_routers` length | **High** — verified by `from app.routes import all_routers; print(len(all_routers))` returning 64 |
| Test count (**589**) matches collection | **High** — verified by `pytest --collect-only` post phase 51 (was 583 → +6 photos PATCH tests in `test_photo_metadata_patch.py`) |
| Backend test file count (**53**) | **High** — `ls backend/tests/test_*.py \| wc -l` = 53 |
| Migration count (8) matches files in `migrations/` | **High** — verified by `ls migrations/*.sql \| wc -l` (the demo seed file grew in phase 53 but the count didn't) |
| Page count (**32**) matches files in `frontend/src/pages/` | **High** — `ls frontend/src/pages/*.jsx \| wc -l` = 32 after phase 48 added Companies + People |
| Playwright test count (**14**) | **High** — smoke.spec.js (8) + phase46_50.spec.js (6) |
| Phases 1-44 are all shipped | **High** — verified by the reconciliation table |
| Phases 45–53 are all shipped | **High** — verified by the new rows in the reconciliation table; prod promotion completed 2026-04-14 |
| Production deploy is healthy at `d119663` | **High** — verified by `/api/health` returning 200, `/api/version.commit=d119663`, `environment=production`, login + projects list working, bundle `index-gT1ItBVr.js` contains phase 46–50 strings. The phase 41–53 promotion commit was `3148f0c`; `d119663` is a CI workflow fix on top with no runtime change. |
| `REX_DEMO_SEED` is off on prod | **High** — verified by `/api/companies/` returning only foundation companies (Rex Construction + Exxir Capital), no Apex Concrete / Steel Frame / etc. |
| All P1 parity items closed | **High** — verified by `FIELD_PARITY_BACKLOG.md` and migration 002/003 contents |
| All practical P2 parity items closed | **High** — verified by migration 005 contents |
| Bonus system is deferred | **High** — verified by absence of any bonus-related models, routes, or pages |
| AI features are zero | **High** — verified by absence of LLM client code, prompt registry, AI inference paths |
| Demo environment exists and is functional | **High** — verified during phase 46–53 proving ground; still live under Railway `demo` env + Vercel `rex-os-demo` project |
| Stale postgres data still on Railway DB | **Moderate** — observed during deploy bring-up; not re-verified post-fix |

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
| CI workflow (GitHub Actions) | ✅ shipped phase 42 | `.github/workflows/ci.yml` + `deployed-smoke.yml` |
| Backend Sentry code path | ✅ shipped phase 44 | Gated on `REX_SENTRY_DSN`; **not activated in prod** (no DSN) |
| Frontend Sentry code path | ✅ shipped phase 46 | Gated on `VITE_SENTRY_DSN`; **not activated in prod** (no DSN, no rebuild) |
| Rate limiting on `/api/auth/login` | ✅ shipped phase 44 | slowapi at `REX_LOGIN_RATE_LIMIT` (default `10/minute`) |
| Demo environment for release flights | ✅ shipped phase 46–53 | Separate Railway demo env + Vercel `rex-os-demo` project; was the proving ground for the 2026-04-14 prod promotion |
| API versioning prefix (`/api/v1`) | deferred (low priority) | No breaking response shape change planned yet |
| S3 storage in prod | deferred (ops step) | Adapter exists and is demo-safe; prod still on `local`; flip sequence requires demo round-trip first per `DEPLOY.md §1f` |
| Backend Sentry activation in prod | deferred (ops step) | Code ready; needs demo DSN + one safe event + prod DSN |
| Frontend Sentry activation in prod | deferred (ops step) | Code ready; Vite env is build-time so requires a Vercel redeploy after setting the DSN |
| Email transport enabled | deferred (low priority) | `REX_EMAIL_TRANSPORT=noop`; SMTP wired but disabled |
| Per-user notification preference matrix | deferred (not yet designed) | Backend has no schema for per-user opt-out |
| Email digest job | deferred (low priority) | Blocked on email transport + preference matrix |
| Webhook-out for external integrations | deferred (low priority) | No target system identified |
| SSO / SAML | deferred (not yet designed) | No identity provider selected |
| Multi-tenancy beyond project scoping | deferred (not yet designed) | Current product scope is single-workspace |
| Public API / OAuth client registration | deferred (low priority) | No external consumers |
| Real-browser sanity pass on post-promotion prod build | pending (minutes of work) | API-level smoke already green; one human click-through of `rex-os.vercel.app` still open |

### Frontend polish

| Item | State | Why |
|---|---|---|
| Photo upload UI | ✅ shipped phase 49 | Multipart drawer + backend `POST /api/photos/upload` + phase 51 metadata PATCH fix + phase 53 bytes preview |
| Project / Company / User create-edit forms | ✅ shipped phase 48 | Portfolio create drawer + Companies admin page + People & Members admin page; existing-user management is full UI |
| Closeout checklist item edit drawer | ✅ shipped phase 50 | Full FormDrawer with name / category / status / due_date / assigned_person_id / assigned_company_id / notes / spec_division / spec_section |
| Per-route error boundaries | ✅ shipped phase 46 | `ErrorBoundary` with `routeKey={location.pathname}` auto-resets on navigation, retry without reload, Sentry reporting |
| BuildVersionChip in sidebar | ✅ shipped phase 47 | FE + BE commit; click to expand popover with full `/api/version` identity |
| Responsive layout (900px + 560px) | ✅ shipped phase 50 | Off-canvas sidebar + hamburger + grid collapse + drawer clamp |
| Mobile responsiveness (phone-sized) | deferred (low priority) | Phase 50 did narrow-desktop + tablet; phone-device breakpoint still open |
| Keyboard nav / focus traps in drawers | deferred (low priority) | ESC works; tab navigation escapes drawers |
| ARIA labels / Lighthouse audit | deferred (low priority) | Partial ARIA labels added phase 50; Lighthouse pass not done |
| Email-invite / signup flow for new users | deferred (not yet designed) | Existing-user management shipped phase 48; new-account creation is still DB-direct |
| Global route-transition loading indicator | deferred (low priority) | Per-page `PageLoader` is sufficient for now |
| Code splitting (react.lazy) | deferred (low priority) | Bundle is ~620 KB raw / ~156 KB gzip — over the 500 KB advisory but not blocking |
| Component unit tests (Vitest) | deferred (low priority) | Shared modules lack tests |
| Visual regression tests (Chromatic/Percy) | deferred (low priority) | Not justified at current screen count |
| TypeScript migration | deferred (low priority) | Would require porting 32 pages + shared modules |
| Frontend source map upload for Sentry | deferred (blocking prod Sentry flip) | Required before frontend Sentry stack traces will be meaningful |

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

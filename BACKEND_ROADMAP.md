# Rex OS Backend Roadmap

> Single source of truth for backend planning.
> Last reconciled: **2026-04-14** (phases 41–53: production promotion complete).
> Reflects actual implemented state on the `main` branch (deployed to production),
> not aspirational claims. The prior integration branch `master` is deprecated —
> see `DEPLOY.md §4c`.

---

## 1) Executive snapshot

| Metric | Count | Source |
|---|---|---|
| Domains | 7 | foundation / schedule / field_ops / financials / document_management / closeout / system |
| ORM model classes | ~64 | `backend/app/models/*.py` |
| Routers registered | 64 | `backend/app/routes/__init__.py` (`all_routers`) |
| HTTP routes (approx) | 250+ | sum of CRUD + summary + admin endpoints across routers |
| Background jobs | 5 | `backend/app/jobs/*.py` (warranty/insurance/snapshot/aging/session_purge) |
| Schema migrations applied | 8 | `migrations/*.sql` driven by `app/migrate.py::MIGRATION_ORDER` |
| Optional demo seed | 1 | `migrations/rex2_demo_seed.sql` (gated by `REX_DEMO_SEED`, not in `MIGRATION_ORDER`; phase 53 expanded it to also seed closeout checklists) |
| Rate limiting | slowapi | `app/rate_limit.py` — `POST /api/auth/login` at `REX_LOGIN_RATE_LIMIT` (default `10/minute`) |
| Error tracking | sentry-sdk | **implemented + tested**, gated by `REX_SENTRY_DSN` in `main.py`. **Not activated in prod** as of this reconciliation — code-ready only. |
| Ops endpoints | 3 | `GET /api/health`, `/api/ready`, `/api/version` (`ops.py`). All **deployed-verified** on prod 2026-04-14. |
| CI | GitHub Actions | `.github/workflows/ci.yml` (pytest + vite build), `deployed-smoke.yml` (browser + curl against deployed URL) |
| Backend test files | 53 | `backend/tests/test_*.py` (+ phase 41 `test_demo_seed_smoke.py`, phase 42 `test_proxy_headers_regression.py`, phase 44 `test_version_endpoint.py`, phase 51 `test_photo_metadata_patch.py`) |
| Tests passing | **589** | `pytest` — 583 through phase 44 + 6 phase-51 photos PATCH tests (filename/taken_at/lat/lng round-trip) |
| Full suite runtime | ~104–135s | Varies with local CPU state; bounded by the 5 real-backend e2e suites, not the unit layer |
| Deployment | **live on `main @ d119663`** | Railway (`rex-os-api-production.up.railway.app`) + Postgres + apscheduler. Phases 41–53 **deployed-verified** on 2026-04-14 at merge commit `3148f0c`; `d119663` is a post-reconciliation CI-only fix on top, no runtime change. |

**Stack:** FastAPI + SQLAlchemy 2.x async + asyncpg + apscheduler + bcrypt + python-multipart + httpx (test). Python 3.12. No queue/broker.

---

## 2) Domain coverage by table count

| Domain | Tables | CRUD baseline | Workflow layer |
|---|---|---|---|
| Foundation | 9 + insurance_certificates + job_runs | ✅ complete | auth/sessions, role templates with overrides, project members with primary-role integrity, insurance compliance with auto-status refresh |
| Schedule | 5 (+actuals/WBS/start-finish-variance/free-float audited fields) | ✅ complete | drift summary, project schedule health, schedule snapshots, advisory-lock-safe daily snapshot job |
| Field Ops | 12 | ✅ complete | punch days_open + critical_path + closed_by, daily-log + manpower summaries, inspection summary with linked punch, observation root-cause fields, OSHA-recordable safety incidents |
| Financials | 14 | ✅ complete | budget rollup math, billing/pay-app/commitment summaries, change-event detail with line items + linked PCO/CCO, retention tracking |
| Document Management | 9 | ✅ complete | RFI/submittal aging + manager fields, drawing revisions, submittal packages, polymorphic attachments via `source_type`/`source_id`, file download + preview boundary |
| Closeout & Warranty | 8 + om_manuals | ✅ heavily implemented | template-based checklists, evidence checklist, certification, gate evaluation, project + portfolio readiness, warranty auto-status refresh, warranty alerts/claims, completion milestones with forecast + percent_complete + evidence requirements, **O&M manual tracker** |
| System / Operational | notifications + job_runs | ✅ complete | dedupe-aware notifications with partial unique index, advisory-lock-protected job runner, admin operations API |

---

## 3) Auth, sessions, RBAC

- Bearer-token auth via `Authorization: Bearer <token>`; tokens stored in `rex.sessions` with bcrypt-hashed `token_hash` and expiry
- bcrypt for password hashes (people credentials) and token hashing
- Access-level hierarchy: `read_only` → `field_only` → `standard` → `admin` (numerically ordered in `ACCESS_LEVEL_RANK`)
- `is_admin == true` and `global_role == "vp"` bypass project-membership checks
- Helpers in `backend/app/dependencies.py`:
  - `get_current_user` — resolves bearer → UserAccount, 401 on failure
  - `require_authenticated_user` — pass-through
  - `require_admin_or_vp` — 403 unless admin/VP
  - `assert_project_access(min_access_level)` — imperative check
  - `assert_project_write` (= standard), `assert_field_write` (= field_only)
  - `enforce_project_read` — **404** instead of 403 to avoid leaking project existence
  - `get_readable_project_ids` — per-request cached allow-list for read scoping
- Role templates (`rex.role_templates`) define `visible_tools`, `visible_panels`, `quick_action_groups`, `can_write`, `can_approve`, `notification_defaults`, `home_screen` as JSONB
- Per-project overrides via `rex.role_template_overrides` with `replace`/`add`/`remove` modes
- **Status:** Production-grade. Tested end-to-end via `test_auth.py`, `test_permissions.py`, sprint E security tests, real-backend e2e tests in phases 25/30/35.

---

## 4) Storage / file handling

- `backend/app/services/storage.py` defines a pluggable storage adapter with `local`, `memory`, and `s3` backends (s3 implementation present but unused in current deploy)
- Local backend writes to `REX_STORAGE_PATH` (defaults to repo-relative dir); path-traversal hardened via `_resolve_safe`
- `POST /api/attachments/upload` accepts multipart `file` + `project_id` + `source_type` + `source_id`, validates non-empty, project-scoped via `assert_project_access(field_only)`
- `GET /api/attachments/{id}/download` enforces project-scoped `read_only` access and streams the raw file content with proper `Content-Disposition`
- File preview drawer in frontend (`frontend/src/preview.jsx`) consumes the auth-gated download endpoint, creates blob URLs for inline PDF/image preview, falls back to download for unsupported types
- Polymorphic attachments via `source_type`/`source_id` columns — used by warranties, correspondence, observations, inspections, RFIs, etc.
- **Phase 49**: added `POST /api/photos/upload` as a dedicated multipart route
  for the Photos page (image-only, `field_only` project access). Phase 51
  expanded `PhotoUpdate` to accept `filename`/`taken_at`/`latitude`/`longitude`
  on PATCH (previously silently dropped — regression-locked by 6 focused
  tests in `test_photo_metadata_patch.py`). Phase 53 added
  `GET /api/photos/{id}/bytes` for auth-gated raw byte streaming to power
  the Photos preview path.
- **Status:** Production-ready for local storage, **deployed-verified** on
  2026-04-14 at the promotion commit `3148f0c` (currently `d119663` after
  a CI-only fix, no runtime change). S3 backend exists, is demo-safe, and is
  ready to flip whenever the operational sequence in `DEPLOY.md §1f` runs
  (demo round-trip first, then prod). **Photo file upload UI shipped in
  phase 49** — metadata edit, upload, and preview are all
  browser-verified on demo and deployed-verified on prod.

---

## 5) Migrations

| Order | File | Purpose |
|---|---|---|
| 1 | `001_create_schema.sql` | rex schema + `set_updated_at()` trigger |
| 2 | `rex2_canonical_ddl.sql` | All 57 canonical tables |
| 3 | `rex2_foundation_bootstrap.sql` | Seed users/projects/role-templates + defensive constraint backfill for `connector_mappings` |
| 4 | `rex2_business_seed.sql` | Business seed data |
| 5 | `002_field_parity_batch.sql` | Phase 4-5: closed_by, is_critical_path×2, rfi_manager, submittal_manager_id, estimated_completion_date, change_event_line_items table |
| 6 | `003_phase21_p1_batch.sql` | Phase 21: schedule actuals + WBS, milestone forecast + %, warranty system/manufacturer, insurance_certificates table |
| 7 | `004_phase31_jobs_notifications.sql` | Phase 31: job_runs + notifications tables with partial unique dedupe index |
| 8 | `005_phase38_phase39_p2_batch.sql` | Phase 38/39: schedule start/finish variance + free float, projects lat/lng, companies mobile/website, observation contributing_*, closeout_checklist_items spec_*, om_manuals table |

- **Runner:** `backend/app/migrate.py` with hardcoded `MIGRATION_ORDER` list, idempotent applies, robust `_find_migrations_dir()` that tries 5 candidate locations for Railway compatibility
- **Auto-apply:** `REX_AUTO_MIGRATE=true` lifespan hook applies pending migrations on startup; used in production
- **Manual fallback:** `GET /api/admin/migrate?secret=...` for emergency apply
- **Pattern:** all phase migrations are additive (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, defensive `DROP INDEX IF EXISTS` where needed). No destructive operations are shipped.
- **Status:** Production-safe. The `rex2_foundation_bootstrap.sql` includes defensive backfill for the wrong-columned `uq_connector_mapping` index inherited from a prior Rex Procore deployment.

---

## 6) Background jobs

5 jobs registered in `backend/app/jobs/`:

| Job key | Schedule (UTC) | Purpose |
|---|---|---|
| `warranty_refresh` | daily 06:00 | Recompute statuses; emit per-tier (90/30/expired) notifications via `upsert_notification`; resolve stale via `resolve_notifications_by_dedupe_prefix` |
| `insurance_refresh` | daily 06:15 | Same pattern; admin/VP fanout only since insurance is global to companies; tiers 90/60/30/expired |
| `schedule_snapshot` | daily 06:30 | Idempotent per-day snapshot of active schedule activities; drift threshold notifications via `REX_DRIFT_CRITICAL_DAYS` / `REX_DRIFT_WARNING_DAYS` env vars |
| `aging_alerts` | daily 06:45 | **Emits 3 separate per-category notifications** (`aging_summary_rfi`, `aging_summary_submittal`, `aging_summary_punch`) with deep-link action paths to `/#/rfis?status=open`, etc. |
| `session_purge` | every 2h | Delete expired auth sessions |

- **Runner** (`backend/app/jobs/runner.py`):
  - `register_job` decorator + `JOB_REGISTRY` dict
  - `run_job_now()` uses **Postgres `pg_try_advisory_xact_lock`** per job_key (32-bit signed int hash) — multi-instance safe, transaction-scoped, no pool leaks
  - 3-phase commit pattern (running row → execute → final status) so failures persist via a fresh session
  - Skipped runs persist as `JobRun(status="skipped", summary="Skipped: another instance holds the advisory lock")`
- **Scheduler:** apscheduler `AsyncIOScheduler` with `coalesce=True, max_instances=1`; gated by `REX_ENABLE_SCHEDULER=true` env var; off in tests; idempotent boot via `_scheduler` global guard
- **Admin API** (`backend/app/routes/admin_jobs.py`, admin/VP only):
  - `GET /api/admin/jobs` — list with last_run, last_success, last_failure
  - `GET /api/admin/job-runs?job_key=&limit=` — history
  - `POST /api/admin/jobs/{job_key}/run` — manual trigger uses the same lock path
- **Status:** Production-grade and **multi-instance safe** as of phase 36. Tested via `test_phase31_jobs.py` (21 tests), `test_phase36_advisory_lock.py` (5 tests), `test_phase35_jobs_notifications.py` (10 real-backend e2e tests).

---

## 7) Notifications

- `rex.notifications` table with partial unique index `uq_notif_dedupe(user_account_id, dedupe_key) WHERE active`
- Service (`backend/app/services/notifications.py`):
  - `upsert_notification(...)` — dedupe-aware update-or-insert
  - `resolve_notifications_by_dedupe_prefix(prefix, keep_keys)` — clear stale alerts when conditions clear
  - `get_admin_and_vp_user_ids` / `get_project_user_ids` — fanout helpers
  - `list_for_user`, `unread_count_for_user`, `mark_read`, `dismiss`, `mark_all_read` — user-scoped query helpers
- Route (`backend/app/routes/notifications.py`, user-scoped via `require_authenticated_user`):
  - `GET /api/notifications/?unread=&domain=&project_id=&severity=&limit=&offset=`
  - `GET /api/notifications/unread-count`
  - `PATCH /api/notifications/{id}/read`
  - `PATCH /api/notifications/{id}/dismiss`
  - `PATCH /api/notifications/read-all`
- All user-scoped queries filter by `user_account_id == user.id`. **No cross-user leakage.** No admin-can-read-everyone backdoor.
- `action_path` hash routes are now domain-correct (phase 37): `/#/rfis?status=open`, `/#/submittals?status=submitted`, `/#/punch-list?status=open`, `/#/warranties?status=expired`, `/#/insurance?status=expired`, `/#/schedule?tab=critical`
- **Status:** Production-grade. Tested via phase 31, 35 test suites.

---

## 8) Email transport

- `backend/app/services/email.py` defines 3 transports:
  - `NoopTransport` (default) — silently swallows
  - `LogTransport` — writes to logger at INFO
  - `SmtpTransport` — uses `smtplib` via `REX_SMTP_HOST/PORT/USER/PASSWORD/FROM/TLS`
- Selected via `REX_EMAIL_TRANSPORT` env var
- **SMTP errors are caught** and logged; the app never crashes on email failure
- Currently configured to `noop` in production. SMTP credentials exist on the Railway service from a previous Rex Procore deployment but are unused.
- **Status:** Abstraction is in place; in-app inbox is the source of truth. SMTP wiring deferred until there's a clear product need.

---

## 9) Real-backend verification

Four test files exercise real-backend integration via httpx + the in-process FastAPI app + rollback isolation:

| File | Tests | Coverage |
|---|---|---|
| `test_phase25_real_e2e.py` | 8 | login/portfolio, RFI lifecycle, punch closure, daily log + manpower, change event + line item, insurance cert, schedule actuals + WBS, read-only denial |
| `test_phase30_schedule_files.py` | 10 | schedule workbench data, activity links, constraints, schedule health summary, critical-only filter, activity detail GET, attachment upload+download, polymorphic attachment listing, drawing image_url, read-only schedule write denial |
| `test_phase35_jobs_notifications.py` | 10 | admin list jobs, run all 5 jobs manually, schedule_snapshot idempotence, user notification scoping, mark read + dismiss, read-only admin denial, dedupe upsert behavior |
| `test_phase40_verification.py` | 8 | phase 38/39 fields roundtrip via `rollback_client` (lat/lng, mobile/website, contributing, spec_division/section, start/finish variance + free_float, om_manuals lifecycle); per-domain notification `action_path` literal audit (warranty / insurance / aging-rfi/submittal/punch / schedule drift); cross-domain routing consistency check; `upsert_notification` → API round-trip; advisory-lock stability on sequential `session_purge` runs; `NotificationResponse` schema drift guard; **dynamic aging_alerts end-to-end** (fresh project with overdue RFI + overdue submittal + aged punch triggering 3 correctly-routed notifications); O&M manual list + get + filter surface |

- All use the `rollback_client` fixture (savepoint-isolated) where possible
- Pollution-prone tests (`test_field_ops::test_daily_log_crud`, `test_phase21_parity::test_insurance_cert_*`, `test_schedule::test_list_schedules_filter_project`) use the fresh-throwaway-project pattern
- `conftest.py` includes a session-start cleanup of stale `pg_try_advisory_lock` backends from interrupted prior runs
- **Phase 40 verification strategy**: the real-backend job execution is already proven by the phase 35 suite. Phase 40 adds static source audits of the `action_path` string literals inside the job files (`warranty_refresh`, `insurance_refresh`, `schedule_snapshot`, `aging_alerts`) plus an API-level round-trip test for `NotificationResponse.action_path`. Re-running the full jobs inside phase 40 tests was intentionally avoided because the dev DB carries ~1700 legacy schedule activities that make `schedule_snapshot` extremely slow.
- **Status:** 36 real-backend tests passing (28 existing + 8 new phase 40). The mocked Playwright smoke (8 tests in `frontend/e2e/smoke.spec.js`) is the frontend-side complement.

---

## 10) Production deployment

- **Railway** (backend + Postgres):
  - Project: `Rex OS` under `exxir's Projects` workspace
  - **Environments**: `production` + `demo` (demo added 2026-04-14 as the
    phase 46–53 proving ground; see `DEPLOY.md §7`)
  - Production service: `rex-os-api`
  - Production public URL: `https://rex-os-api-production.up.railway.app`
  - Build: Nixpacks via `nixpacks.toml` at repo root → venv at `backend/.venv`, install via `python -m venv` (Nix-managed Python doesn't ship pip)
  - Start: `cd backend && export LD_LIBRARY_PATH=$(find /nix/store ... libstdc++.so*) && .venv/bin/uvicorn main:app`
  - Env vars set on prod: `DATABASE_URL`, `REX_AUTO_MIGRATE=true`, `REX_ENABLE_SCHEDULER=true`, `REX_CORS_ORIGINS`, `REX_EMAIL_TRANSPORT=noop`, `MIGRATE_SECRET`. `REX_DEMO_SEED` explicitly **unset** on prod. `REX_STORAGE_BACKEND` unset on prod (= `local`). `REX_SENTRY_DSN` unset on prod.
  - Healthcheck: `/api/health` (cheap, no DB) and `/api/ready` (DB + storage).
    `railway.json` sets `healthcheckTimeout: 300` (was 100 before phase 51)
    to accommodate first-boot migration runs on fresh databases.
- **Postgres**: Railway-managed; one per environment. Prod uses
  `${{Postgres.DATABASE_URL}}`; demo uses `${{Postgres-gpQz.DATABASE_URL}}`
  (random suffix assigned when the demo Postgres was provisioned).
- **Auto-deploy**: GitHub webhook on push to `main`. The in-flight branch
  occasionally needs an empty commit to force Vercel's git webhook to run
  a genuine build rather than a 0ms no-op redeploy of a stale artifact —
  observed during the 2026-04-14 promotion, documented in
  `DEPLOY.md §3 Known gotchas`.
- **Migration on deploy**: `REX_AUTO_MIGRATE=true` triggers `apply_migrations()` from the lifespan hook on startup; idempotent. First boot of the new prod build on 2026-04-14 applied phases 41–50 migrations cleanly (`db.ok=true` on first `/api/ready`).
- **CORS**: `REX_CORS_ORIGINS` is a comma-separated allowlist; production includes `https://rex-os.vercel.app`, demo includes the `rex-os-demo-git-master-*` preview alias.
- **Status:** **Live and stable on `main @ d119663` as of 2026-04-14**
  (phase 41–53 promotion landed at `3148f0c`; `d119663` is a CI workflow
  fix on top with no runtime change). Multi-instance scheduler safety from
  phase 36 still in effect.

---

## 11) Known backend risks / deferred items

### Operational
- **Email transport**: SMTP wired but disabled. Daily-digest job + per-user preference matrix not built.
- **Photo file upload**: ✅ **shipped phase 49** — `POST /api/photos/upload`
  multipart route + frontend drawer, deployed-verified 2026-04-14.
- **Custom monitoring**: Backend Sentry code-ready (phase 44), not activated
  in prod — `REX_SENTRY_DSN` unset. Activation is an ops step: set DSN on
  demo first, prove one event in Sentry dashboard, then set on prod.
- **Rate limiting**: ✅ **shipped phase 44** — slowapi on `POST /api/auth/login`
  at `REX_LOGIN_RATE_LIMIT` (default `10/minute`).
- **API versioning**: no `/api/v1` prefix; all routes are unversioned. Acceptable for current scale; not negligible for long-term.

### Data / parity
- **Bonus / performance system**: ~12 tables in the original Rex Procore schema (quarterly_scorecards, milestone_bonus_pools, buyout_savings, ebitda_growth, etc.) — **explicitly out of scope** until a product design pass.
- **Real S3 storage in prod**: implementation **code-ready and demo-safe**;
  not activated on prod. Activation sequence is in `DEPLOY.md §1f` — demo
  round-trip is the gate, not a deploy step.

### Test infra
- **Test pollution**: 3 test files historically polluted PROJECT_BISHOP / COMPANY_REX seed data and were patched to use fresh-throwaway-project per call. Some pollution from earlier sprints still exists in dev DB (~1700 leftover schedules) but doesn't affect tests.
- **CI**: ✅ **shipped phase 42** — `.github/workflows/ci.yml` runs backend
  pytest + frontend vite build on every push and PR.
  `.github/workflows/deployed-smoke.yml` runs curl + browser invariants
  against a deployed URL on manual dispatch and a 6-hour cron.

### Architecture
- **Multi-instance scheduler safety**: ✅ closed by phase 36 (Postgres advisory locks).
- **Notification delivery preferences**: deferred. No per-user opt-out matrix.
- **Webhook-out**: no outbound webhooks for external integrations.

---

## 12) Recommended next backend priorities

In rough priority order, **after** the phase 46–53 prod promotion:

1. **Demo-first S3 activation**: flip `REX_STORAGE_BACKEND=s3` on the demo
   environment, round-trip a photo upload, then flip prod. Sequence is in
   `DEPLOY.md §1f`. Prod will lose attachments on container recycle until
   this is done — not blocking today (low volume), will be blocking at any
   real user scale.
2. **Backend Sentry DSN activation**: set `REX_SENTRY_DSN` on demo, prove
   one safe event appears in the Sentry dashboard with `environment=demo`,
   then do the same on prod with a separate DSN and `environment=production`.
3. **Frontend Sentry activation**: set `VITE_SENTRY_DSN` + `VITE_SENTRY_ENV`
   on the Vercel demo project, redeploy (Vite env vars are build-time),
   confirm a deliberate browser event appears in Sentry, then repeat on prod.
4. **Real-browser sanity pass on prod** at the post-promotion build — walk
   the Phase 3 checklist from `DEPLOY.md §7d` against
   `https://rex-os.vercel.app` once, log the verdicts, close the loop.
5. **Email digest job**: daily summary of unread critical/warning notifications via the existing transport abstraction.
6. **Notification preference matrix**: per-user opt-out by domain/severity.
7. **API versioning prefix** (`/api/v1`) before any breaking response shape change.
8. **Bonus/performance system design pass** (if product wants it).

Items 1–4 are the remaining ops hardening gaps. None block the current
product but they close out the ops ladder the sprint brief called out.

---

## 13) What this roadmap is NOT

- **Not a changelog** — see `git log` and per-phase commit messages.
- **Not a release-notes doc** — see `PROGRAM_STATE.md` for the audited state of phase claims.
- **Not a frontend roadmap** — see `FRONTEND_ROADMAP.md`.
- **Not an AI roadmap** — see `AI_ROADMAP.md`.

---

## 14) Document hygiene

This file should be updated whenever:
- a new domain or major feature group ships
- the deployment topology changes
- a major operational risk closes or opens
- the test/route/migration count changes by >10%

Stale claims to watch out for in any PR review:
- "_RUNNING_JOBS in-process guard" — replaced by advisory locks in phase 36
- "Single-instance only" — no longer true
- "Generic alert infrastructure not yet built" — built in phase 32
- "Background jobs not yet implemented" — built in phase 31
- "All P1 parity items still open" — all closed by phase 25
- "No CI" — built in phase 42
- "No rate limiting" — built in phase 44
- "Photo upload UI deferred" — shipped in phase 49
- "Photos metadata PATCH silently drops filename/lat/lng/taken_at" — fixed in phase 51
- "Project / Company / User create-edit forms deferred" — shipped in phase 48
- "Closeout checklist item edit drawer deferred" — shipped in phase 50
- "Per-route error boundaries deferred" — shipped in phase 46
- "Deploys watch master" — **deploys watch `main`** since 2026-04-14
- Any test count claim below **589** (was 547 → 569 at phase 39 → 577 after phase 40 → 583 after phases 41–44 → **589** after phase 51 photos PATCH tests)
- Any page count below **32** (was 30 → **32** after phase 48 added Companies + People)
- Any bundle size below **~620 KB raw / ~156 KB gzip** (was ~508/122 → **~620/156** after phase 46–50 added BuildVersionChip, fetchState, sentry, Companies, People, FileInput, responsive CSS)

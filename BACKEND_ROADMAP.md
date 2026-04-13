# Rex OS Backend Roadmap

> Single source of truth for backend planning.
> Last reconciled: **2026-04-12** (post phase 39).
> Reflects actual implemented state on the master branch, not aspirational claims.

---

## 1) Executive snapshot

| Metric | Count | Source |
|---|---|---|
| Domains | 7 | foundation / schedule / field_ops / financials / document_management / closeout / system |
| ORM model classes | ~64 | `backend/app/models/*.py` |
| Routers registered | 64 | `backend/app/routes/__init__.py` (`all_routers`) |
| HTTP routes (approx) | 250+ | sum of CRUD + summary + admin endpoints across routers |
| Background jobs | 5 | `backend/app/jobs/*.py` (warranty/insurance/snapshot/aging/session_purge) |
| Migrations applied | 8 | `migrations/*.sql` (4 foundation + 4 phase-numbered) |
| Backend test files | 49 | `backend/tests/test_*.py` (phase 40 adds `test_phase40_verification.py`) |
| Tests collected | 577 | `pytest --collect-only` (569 pre-phase-40 + 8 phase 40 verification tests) |
| Full suite runtime | ~94s | Down from ~1079s at phase 39 — phase 40 eliminated legacy test pollution from the dev DB |
| Deployment | live | Railway (`rex-os-api-production.up.railway.app`) + Postgres + apscheduler |

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
- **Status:** Production-ready for local storage. S3 backend exists but unverified in production. **Photo file upload UI is intentionally deferred** — only metadata edit is exposed in the Photos page.

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
  - Service: `rex-os-api`
  - Public URL: `https://rex-os-api-production.up.railway.app`
  - Build: Nixpacks via `nixpacks.toml` at repo root → venv at `backend/.venv`, install via `python -m venv` (Nix-managed Python doesn't ship pip)
  - Start: `cd backend && export LD_LIBRARY_PATH=$(find /nix/store ... libstdc++.so*) && .venv/bin/uvicorn main:app`
  - Env vars set: `DATABASE_URL`, `REX_AUTO_MIGRATE=true`, `REX_ENABLE_SCHEDULER=true`, `REX_CORS_ORIGINS`, `REX_EMAIL_TRANSPORT=noop`, `MIGRATE_SECRET`
  - Healthcheck: `/api/health` (cheap, no DB) and `/api/ready` (DB + storage)
- **Postgres**: Railway-managed; lives in same project; `DATABASE_URL` references via `${{Postgres.DATABASE_URL}}`
- **Auto-deploy**: GitHub webhook on push to master; the in-flight branch needs an empty commit to wake the webhook if it's stuck (observed during initial bring-up)
- **Migration on deploy**: `REX_AUTO_MIGRATE=true` triggers `apply_migrations()` from the lifespan hook on startup; idempotent
- **CORS**: `REX_CORS_ORIGINS` is a comma-separated allowlist; production includes the Vercel domain explicitly
- **Status:** Live and stable as of 2026-04-12. Multi-instance scheduler safety added in phase 36.

---

## 11) Known backend risks / deferred items

### Operational
- **Email transport**: SMTP wired but disabled. Daily-digest job + per-user preference matrix not built.
- **Photo file upload**: needs multipart form UI on frontend + storage backend wiring in S3 mode for prod; deferred.
- **Custom monitoring**: no Sentry / Datadog / PromQL integration. Health/ready probes are the only liveness signal.
- **Rate limiting**: no per-IP or per-user rate limit middleware.
- **API versioning**: no `/api/v1` prefix; all routes are unversioned. Acceptable for current scale; not negligible for long-term.

### Data / parity
- **Bonus / performance system**: ~12 tables in the original Rex Procore schema (quarterly_scorecards, milestone_bonus_pools, buyout_savings, ebitda_growth, etc.) — **explicitly out of scope** until a product design pass.
- **Real S3 storage in prod**: implementation exists, not configured.

### Test infra
- **Test pollution**: 3 test files historically polluted PROJECT_BISHOP / COMPANY_REX seed data and were patched to use fresh-throwaway-project per call. Some pollution from earlier sprints still exists in dev DB (~1700 leftover schedules) but doesn't affect tests.
- **No CI**: tests run locally only; no GitHub Actions workflow.

### Architecture
- **Multi-instance scheduler safety**: ✅ closed by phase 36 (Postgres advisory locks).
- **Notification delivery preferences**: deferred. No per-user opt-out matrix.
- **Webhook-out**: no outbound webhooks for external integrations.

---

## 12) Recommended next backend priorities

In rough priority order, **after** the docs-reconciliation pass:

1. **CI / GitHub Actions**: minimum `pytest tests/ -q` + `cd frontend && npm run build` on PR. Currently zero automated test enforcement.
2. **API rate limiting**: `slowapi` or similar; protect `/api/auth/login` from credential stuffing first.
3. **Sentry or equivalent error tracking**: production has no error visibility beyond Railway log scraping.
4. **Photo upload UI** + S3 storage wiring (only if there's product demand).
5. **Email digest job**: daily summary of unread critical/warning notifications via the existing transport abstraction.
6. **Notification preference matrix**: per-user opt-out by domain/severity.
7. **API versioning prefix** (`/api/v1`) before any breaking response shape change.
8. **Bonus/performance system design pass** (if product wants it).

None of these are blocking the current product. They're the next operational hardening tier.

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
- Any test count claim from before phase 40 (was 547 → 569 at phase 39 → **577** after phase 40 verification additions)

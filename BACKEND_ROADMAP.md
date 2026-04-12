# Rex OS Backend Roadmap

Single source of truth for backend planning. Reflects actual implemented state.

---

## POST-SPRINT UPDATE — 2026-04-12 (Phases 31-35)

- **Background job runner foundation** — apscheduler-based runner with DB-backed `rex.job_runs` table, in-process `_RUNNING_JOBS` guard, advisory-lock-safe single-instance scheduling, `run_job_now()` helper callable from both scheduler and HTTP handlers
- **5 jobs registered**: `warranty_refresh` (daily 06:00 UTC), `insurance_refresh` (daily 06:15 UTC), `schedule_snapshot` (daily 06:30 UTC), `aging_alerts` (daily 06:45 UTC), `session_purge` (every 2 hours). All enabled by default; scheduler boot gated by `REX_ENABLE_SCHEDULER`.
- **Generic notification table + 5 user-facing endpoints** — `rex.notifications` with dedupe partial unique index; endpoints: `GET /api/notifications/`, `GET /api/notifications/unread-count`, `PATCH /api/notifications/{id}/read`, `PATCH /api/notifications/{id}/dismiss`, `PATCH /api/notifications/read-all`
- **Admin Operations page** — `GET /api/admin/jobs` (list with last-run), `POST /api/admin/jobs/{key}/run` (manual trigger), `GET /api/admin/job-runs` (history); admin/VP-only via `require_admin_or_vp`
- **Email transport abstraction** — 3 implementations (noop/log/smtp) selected via `REX_EMAIL_TRANSPORT`; SMTP errors caught and logged, never crash the app
- **Topbar notification bell** + full **Notifications page** — bell polls every 60 s, slide-in drawer with per-item mark-read/dismiss/deep-link, "View all" navigates to `/notifications` page
- **All 547 backend tests passing**, 78-module frontend bundle (494 KB)

---

---

## 1) Current backend status

| Domain | Tables | CRUD baseline | Workflow layer |
|--------|--------|---------------|----------------|
| Foundation | 9 | ✅ complete | partial — primary-role integrity, role resolution helper, auth/sessions live |
| Schedule | 5 | ✅ complete | partial — drift summary, project schedule health |
| Field Ops | 12 | ✅ complete | partial — punch days_open, daily log/manpower summaries, inspection summary, execution health |
| Financials | 14 | ✅ complete | partial — budget rollup math, billing/pay-app/commitment summaries |
| Document Management | 9 | ✅ complete | partial — RFI/submittal aging helpers + project summaries, attachment upload+storage boundary live |
| Closeout & Warranty | 8 | ✅ complete | ✅ heavily implemented (checklist, evidence, certification, gates, readiness, portfolio, warranty status auto-transitions) |

**Totals:** 57 tables, ~62 routers, ~247 endpoints, **488 tests passing**.

**Auth + permissions:** DB-backed sessions via `rex.user_accounts` + `rex.sessions`. Bcrypt password verification. **All mutating POST/PATCH routes require auth** (Sprint E). Admin/VP-only on 7 high-privilege workflow routes. **Project-scoped write authorization** (Sprint J + K): **every** project-bound POST/PATCH route across all six domains + their child collections now enforces `assert_project_write` / `assert_field_write` / parent-chain resolution. `read_only` members are denied writes; `field_only` is allowed only on field-ops routes. `reject_project_id_change` guardrail on representative PATCH routes prevents moving records between projects (422). Attachment metadata create/patch scoped consistently with upload/download. **Project-scoped read authorization** (Sprint G + H): all six domains' major + child list/detail surfaces use `get_readable_project_ids` / `enforce_project_read`. **Global resources** (people, companies) filtered via project_member joins; `role_templates` is intentionally auth-only. Read-side 404; write-side 403. Session lifecycle: cleanup, purge, logout-all. **Only remaining unscoped mutating routes**: `project_members` POST/PATCH (intentionally auth-only — membership management is a foundation action).

**Storage:** Pluggable `StorageAdapter` interface with a registry of `local` + `memory` + `s3` backends, selected via `REX_STORAGE_BACKEND` (default `local`). Local adapter is path-traversal hardened with a `healthcheck()` probe. **S3/R2 adapter** (Sprint I) is a production-ready skeleton using `boto3`; it fails fast with `StorageConfigError` if `REX_S3_BUCKET` is missing or `boto3` is not installed. Supports R2/MinIO via `REX_S3_ENDPOINT_URL`. Local storage dir is gitignored.

**Operability:** `GET /api/health` (liveness — process-up only) and `GET /api/ready` (readiness — DB + storage, 503 on degraded). Structured logging on critical workflows. Per-test DB rollback isolation via `rollback_client` fixture. **Migration runner** (Sprint I): `python -m app.migrate` applies the 4 canonical SQL files in hardcoded order, shared source of truth with the admin `/api/admin/migrate` endpoint, supports `--dry-run` / `--list`, stops on first failure. **Read-scope query reduction** (Sprint I): `get_readable_project_ids` now caches its result on the per-request `UserAccount` object (`_rex_readable_project_ids`), eliminating repeated membership queries within a single request.

**CORS:** Env-driven `REX_CORS_ORIGINS` (default `http://localhost:5173,http://localhost:3000`); no wildcard in default — fails closed in production.

**Persistence:** SQLAlchemy 2.0 async + asyncpg, single `rex.*` schema, partial unique indexes where needed.
**Errors:** Consistent shapes — `{"detail": "string"}` for 401/403/404, SQLSTATE-classified (409/422/500) with cleaned column hints, Pydantic 422 `{"detail": [...]}`.
**Validation:** Pydantic v2 with `Literal` types on enum-ish fields.

---

## 2) What is already working

**CRUD & filters across all 6 domains.** Every list endpoint accepts domain-appropriate query filters; standardized in cross-domain hardening pass.

**Cross-domain integration tests** prove FK references work across boundaries (inspection→activity, submittal→activity+cost_code, RFI→drawing+cost_code, warranty→commitment+cost_code, attachment→source).

### Closeout workflows (most mature)
- **Closeout checklist from template** — `POST /api/closeout-checklists/from-template`. Copies template items, computes due dates from `substantial_completion_date - days_before_substantial`.
- **Role-based assignee resolution** — Resolves `default_assignee_role` to project member at checklist creation, prefers `is_primary=true`, leaves null if ambiguous.
- **Project member primary integrity** — Partial unique index ensures at most one active primary per (project_id, role_template_id).
- **Checklist rollup** — `total_items`, `completed_items`, `percent_complete` recompute on item PATCH.

### Warranty workflows
- **Expiration date helper** — `compute_warranty_expiration(start, months)` with month-overflow handling. Auto-applied on warranty create when omitted.
- **Alert generation** — `POST /api/warranties/{id}/generate-alerts`. Idempotent. Creates 90_day, 30_day, expired alerts; skips dates before warranty start.

### Milestone workflows
- **Evidence helper** — `GET /{id}/evidence-checklist` (parsed JSONB), `POST /{id}/evaluate-evidence` (manual confirmation toggle).
- **Certification** — `POST /{id}/certify`. Validates `certified_by` person exists, sets status=achieved, computes variance_days, returns evidence_incomplete_warning flag.
- **Gate evaluation** — `POST /{id}/evaluate-gates`. Read-only. Checks: certified, evidence_complete, closeout_checklist (80%/100% thresholds), warranty_status (claimed=fail), punch_aging (10/10%/21-day thresholds), time_elapsed (45_days_post_final_co / 45_days_post_opening), gate_conditions metadata surfacing.

### Project & portfolio readiness
- **Per-project readiness summary** — `GET /api/projects/{id}/closeout-readiness`. Aggregates checklist + milestones + holdback gates + warranty + open issues into one response.
- **Portfolio rollup** — `GET /api/closeout-readiness/portfolio` with filters (project_status, project_type, city, state, limit/offset). Reuses per-project readiness.

---

## 3) Priority backlog

### Now (next 1–3 features)

**1. UI integration verification** *(Sprint L candidate)*
- Why: backend authorization is complete on read + write sides across all domains. The frontend needs to exercise the full flow.
- Acceptance: end-to-end smoke test with a frontend or API client covering login, project listing, CRUD on a project-bound resource, and permission denial paths.
- Depends on: frontend scaffolding or API test harness.

**2. Background jobs**
- Why: warranty status refresh, schedule snapshots, and session cleanup are all manual/opportunistic.
- Acceptance: APScheduler or minimal cron-like runner; nightly warranty refresh and session purge.
- Depends on: deployment story.

**3. Remaining foundation gaps**
- Why: `project_members` POST/PATCH is auth-only (no project-scope check) since membership management is a foundation action. Consider restricting to admin/VP or project admins in a future sprint.
- Acceptance: decision documented; possibly tightened.
- Depends on: product decision.

### Next (4–8)

**4. Schedule drift summary**
- Why: `schedule_snapshots` table exists and has `variance_days`, but no aggregation. Field Ops can't see "is this project drifting" without manual queries.
- Acceptance: `GET /api/projects/{id}/schedule-drift` returns activity-level variance summary, critical-path drift count, latest snapshot date.
- Depends on: nothing.

**5. Pay-app workflow guards**
- Why: `payment_applications` has `status` enum but no validation around transitions or lien-waiver requirements.
- Acceptance: `POST /api/payment-applications/{id}/submit` enforces required lien waivers; `POST /{id}/approve` enforces submitted; tests for invalid transitions.
- Depends on: nothing.

**6. Daily log → manpower aggregation**
- Why: Daily logs collect manpower but no per-project trade trend is computed.
- Acceptance: `GET /api/projects/{id}/manpower-summary?from=&to=` returns trade-grouped totals.
- Depends on: nothing.

**7. Inspection → punch auto-link**
- Why: `inspection_items` has `punch_item_id` but no helper creates a punch from a failed inspection item. The schema is ready; the workflow isn't.
- Acceptance: Failing an inspection item via PATCH (`result: "fail"`) optionally creates a punch item; `punch_item_id` populated on the inspection item.
- Depends on: nothing.

**8. Attachment storage integration**
- Why: `attachments` is metadata-only. Real file upload/download is missing.
- Acceptance: `POST /api/attachments/upload` accepts multipart, writes to R2/S3, returns attachment metadata.
- Depends on: storage credentials, R2/S3 client config.

### Later

**9. Auth + permissions**
- Why: Every endpoint is unauthenticated. No JWT, no role enforcement, no row-level security.
- Acceptance: JWT issuance via `/api/auth/login`, dependency injection for current user, role-based gate on certify/approve actions.
- Depends on: bcrypt password handling (model exists, not wired), session table usage.

**10. Background jobs**
- Why: Warranty alerts, schedule snapshots, daily-log digests all need scheduled execution.
- Acceptance: APScheduler or similar; nightly snapshot of schedule_activities → schedule_snapshots; daily warranty status refresh.
- Depends on: deployment story (Railway scheduler vs in-process).

**11. Notifications**
- Why: Generated warranty alerts have `is_sent=false` forever. No email/SMS pipeline.
- Acceptance: SMTP send for warranty alerts when within window; mark `is_sent=true`.
- Depends on: SMTP credentials (already in .env), background jobs.

**12. Production hardening**
- Why: Test DB accumulation, no migration runner, no health metrics.
- Acceptance: Per-test transaction rollback or test schema; alembic or simple migration tracker; structured health endpoint.

---

## 4) Recommended sequence (next 8–12)

1. RFI / submittal aging helpers
2. Warranty status auto-transition helper
3. Budget rollup math
4. Schedule drift summary
5. Pay-app workflow guards (depends on lien waivers being created via existing CRUD)
6. Daily log → manpower aggregation
7. Inspection → punch auto-link
8. Auth + permissions (do this BEFORE attachment uploads)
9. Attachment storage integration
10. Notifications (warranty alerts → email)
11. Background jobs (snapshots, warranty refresh)
12. Production hardening (test isolation, migration runner)

---

## 5) Risks / gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **No auth** | ~~High~~ | ~~Resolved in Sprint D.~~ Closed (DB-backed sessions live; 7 routes protected; pattern reusable). |
| **No file storage** | ~~High~~ | ~~Resolved in Sprint D.~~ Closed (local storage boundary live; cloud-swap clean). |
| **Permissions only on subset of routes** | ~~Medium~~ | ~~Resolved in Sprint E.~~ Closed (all mutating routes require auth; project-scoped auth on attachment download/upload). |
| **Unprotected attachment download** | ~~High~~ | ~~Resolved in Sprint E.~~ Closed (project-scoped check + admin bypass + missing-file safe 404). |
| **No RFI/submittal aging** | ~~Medium~~ | ~~Resolved in Sprint A.~~ Closed. |
| **No budget rollup** | ~~Medium~~ | ~~Resolved in Sprint B.~~ Closed (read + refresh helpers live). |
| **No schedule drift analytics** | ~~Medium~~ | ~~Resolved in Sprint C.~~ Closed (drift summary + project health live). |
| **No background jobs** | Medium | All workflow runs synchronously on request. Warranty alerts, snapshots, status refresh all manual. |
| **No cloud storage adapter** | ~~Medium~~ | ~~Resolved in Sprint I.~~ `S3StorageAdapter` registered under `s3` backend; requires `REX_S3_BUCKET` + `boto3`; fails fast otherwise. Production deploy requires creds and `boto3` install. |
| **Read-side listings unscoped** | ~~Medium~~ | ~~Resolved in Sprint G + H.~~ All major project-bound + child list/detail surfaces now filter by `get_readable_project_ids` and 404 on cross-tenant detail. Global `people`/`companies` are filtered via project_member joins; `role_templates` is intentionally world-readable to authenticated users. |
| **Tests mutate dev DB** | ~~Low~~ | ~~Partially resolved in Sprint F.~~ `rollback_client` fixture enables per-test isolation for new tests; existing test files still commit, but the pattern is available and proven. |
| **`days_open` on punch_items** | Low | Used by gate evaluation but is client-stored, not computed. Can drift. |
| **No portfolio sort order** | Low | Portfolio endpoint returns DB insertion order. |
| **N+1 in portfolio readiness** | Low | ~8 queries × N projects. Acceptable < 100 projects. |

---

## 6) Change log

### Latest completed
- **2026-04-10 UI/API verification prep** — `UI_VERIFICATION_PLAN.md` documenting 6 end-to-end flows (portfolio readiness, project readiness, checklist-from-template, item rollup, milestone lifecycle, attachment upload/download) with exact endpoints, seed data, auth instructions, and permission denial expectations. **Tightened**: portfolio readiness endpoint (`GET /api/closeout-readiness/portfolio`) now requires auth + project-scoped read filtering via `accessible_project_ids` — was previously unscoped. 9 focused integration tests exercise the full vertical slice end-to-end: portfolio summary shape, project readiness shape, checklist-from-template (34 items), item completion → rollup (percent_complete updates), milestone evidence → certify → gates lifecycle, attachment upload + download round-trip, non-member download denial, and unauthenticated portfolio denial. Suite: 479 → **488**.
- **2026-04-10 Sprint K: backend cleanup before UI verification** — **Child write-scoping**: all remaining project-bound POST/PATCH routes now enforce project-scoped write access — 26 route files updated via bulk script + 3 manual fixups for multi-line signatures (activity_links, schedule_constraints, schedule_snapshots). Field-ops children use `assert_field_write`; all others use `assert_project_write`. Parent chain resolution for indirect models (e.g. schedule_constraints → ScheduleActivity → Schedule, pco_cco_links → PCO → ChangeEvent). **PATCH guardrails**: `reject_project_id_change` helper in `app/dependencies.py` returns 422 when a PATCH body attempts to move a record to a different project; applied on 5 representative routes (daily_logs, schedules, rfis, commitments, attachments). **Attachment metadata**: `POST /api/attachments/` and `PATCH /api/attachments/{id}` now enforce `assert_project_write` and `reject_project_id_change`, matching upload/download strength. **OpenAPI**: verified 146 paths, 209 schemas, all auth-dependent endpoints have proper response documentation. 12 new tests. Suite: 467 → **479**.
- **2026-04-10 Sprint J: write-side project scoping and frontend integration prep** — **Write-scope helpers**: `assert_project_write` (min `standard`) and `assert_field_write` (min `field_only`) added to `app/dependencies.py`. Applied to major POST/PATCH routes across all six domains: field ops (daily_logs, punch_items, inspections, tasks, meetings — `field_only`), schedule (schedules, schedule_activities — `standard`), financials (cost_codes, budget_line_items, commitments, payment_applications — `standard`), doc mgmt (rfis, submittals, correspondence — `standard`), closeout (closeout_checklists, closeout_checklist_items, warranties, completion_milestones — `standard`). `read_only` members denied on all writes. Child routes resolve parent project_id before checking (payment_applications→Commitment, schedule_activities→Schedule, closeout_checklist_items→CloseoutChecklist). **CORS**: replaced wildcard `*` with env-driven `REX_CORS_ORIGINS` (default `http://localhost:5173,http://localhost:3000`); documented in code. **API ergonomics**: audited error shapes — confirmed consistent `{"detail": str}` on 401/403/404 across all paths. 17 new tests covering write-scope per domain, access-level enforcement (read_only denied, field_only scoped, admin bypass), CORS config + preflight, and error-shape consistency. Suite: 450 → **467**.
- **2026-04-10 Sprint I: storage, migration, and read-scope performance** — **Storage**: `S3StorageAdapter` added to the adapter registry (`scheme="s3"`) with full `save`/`read`/`delete`/`healthcheck` implementation using `boto3`; fails fast with `StorageConfigError` when `REX_S3_BUCKET` is missing or `boto3` is uninstalled; supports R2/MinIO via `REX_S3_ENDPOINT_URL`. **Migration runner**: new `app/migrate.py` module with `MIGRATION_ORDER` as the single source of truth (replaces the inline list that was in `main.py`); CLI entry point `python -m app.migrate` with `--dry-run`/`--list` mode; the admin `/api/admin/migrate` endpoint now delegates to the same `apply_migrations()` function; runner stops on first failure instead of silently continuing. **Read-scope performance**: `get_readable_project_ids` now caches its result on the per-request `UserAccount` instance (attribute `_rex_readable_project_ids`); `enforce_project_read` reuses the cached set instead of issuing its own membership query; sentinel `_SENTINEL` distinguishes "not cached" from a cached `None` (admin/VP). Fixed a pre-existing limit-window test flake in Sprint G's `test_admin_bypasses_all_scoping` (switched from list assertion to deterministic detail-fetch). 17 new tests. Suite: 433 → **450**.
- **2026-04-09 Sprint H: read scoping completeness and permission consistency** — Closed remaining read-side gaps after Sprint G. **Global resources**: `is_person_readable` / `is_company_readable` helpers on `app/services/foundation.py`; `list_people` / `list_companies` now JOIN through `project_members.is_active`; detail handlers return **404** for non-members; `role_templates` GETs explicitly require auth (intentionally global). **Child collections**: 25 child routes scoped across all six domains via parent JOIN — field ops (`inspection_items`→Inspection, `manpower_entries`→DailyLog, `meeting_action_items`→Meeting, `photo_albums`/`photos`/`observations`/`safety_incidents` direct), financials (`commitment_line_items`→Commitment, `commitment_change_orders`→Commitment, `potential_change_orders`→ChangeEvent, `pco_cco_links`→PCO→ChangeEvent, `lien_waivers`→PaymentApplication→Commitment, `billing_periods`/`direct_costs`/`budget_snapshots`/`prime_contracts`/`change_events` direct), doc mgmt (`drawing_revisions`→Drawing, `drawings`/`drawing_areas`/`specifications`/`submittal_packages`/`correspondence` direct), closeout (`closeout_checklist_items`→CloseoutChecklist, `warranty_claims`/`warranty_alerts`→Warranty), schedule (`activity_links`→Schedule, `schedule_constraints`/`schedule_snapshots`→ScheduleActivity→Schedule). **Read-denial consistency**: audit + fixes across `budget_line_items.py`, `cost_codes.py`, `payment_applications.py`, and 7 nested aggregate routes in `projects.py` (`closeout-readiness`, `rfi-aging`, `submittal-aging`, `billing-periods/summary`, `schedule-health`, `manpower-summary`, `execution-health`) — all now call `enforce_project_read`. Service-layer `_filtered_list_join_parent` / `_flist_via_commitment` / `_flist_via_change_event` helpers added to keep route code thin. 16 new isolation tests covering global resources, one representative child per domain, project aggregate denial, and admin-bypass. Suite: 417 → **433**.
- **2026-04-09 Sprint G: read authorization and tenant scoping** — Two new dependencies in `app/dependencies.py`: `get_readable_project_ids(db, user)` returns the set of project ids the caller can read (or `None` for admin/VP "see-all"); `enforce_project_read(db, user, project_id)` raises **404** (not 403, to avoid leaking existence) for non-member detail access. Service-layer `_filtered_list` / `_flist` helpers in `field_ops`, `foundation`, `schedule`, `financials`, `document_management`, and `closeout` accept `accessible_project_ids` and add a project-scoped `WHERE … IN` clause (or empty-list short-circuit). Routes updated for the major project-bound surfaces across all six domains: projects, project-members, daily-logs, punch-items, inspections, tasks, meetings, schedules, schedule-activities (joined via Schedule), cost-codes, budget-line-items, commitments, payment-applications (joined via Commitment), rfis, submittals, attachments, closeout-checklists, warranties, completion-milestones — list filtered + detail 404 on non-member access, admin/VP bypass throughout. UTC fix in `document_management._today_utc()` to eliminate a latent local-vs-UTC off-by-one in RFI/submittal aging math (2 pre-existing flaky tests aligned). 17 new isolation tests covering each domain plus admin-bypass + member-allowlist sanity checks. Suite: 400 → **417**.
- **2026-04-09 Sprint F: production hardening** — Pluggable `StorageAdapter` interface with `local` + `memory` backends and `REX_STORAGE_BACKEND`-driven registry; `StorageConfigError` for fail-fast misconfig; `healthcheck()` probe on `LocalStorageAdapter`. New `app/routes/ops.py` with `GET /api/health` (cheap liveness, no DB) and `GET /api/ready` (DB + storage checks, 503 on degraded, no secret leakage). Session operability: `purge_expired_sessions` deterministic helper, `POST /api/auth/logout-all` scoped to the caller's own sessions only. Per-test rollback isolation via opt-in `rollback_client` fixture (connection-scoped SAVEPOINT join). Permission coverage audit across all 51 non-op route files — every mutating endpoint confirmed protected. Structured logging (`rex.auth`, `rex.attachments`, `rex.closeout`, `rex.milestones`, `rex.warranty`) on login success/failure, logout, logout-all, attachment upload/download + denials, milestone certify, warranty alert generation/refresh, checklist-from-template — no secrets, no tokens. 17 new tests. Suite: 383 → **400**.
- **2026-04-09 Sprint E: security and operability hardening** — Project-scoped authorization helper (`assert_project_access` + `require_project_access` factory) using `project_members.access_level` hierarchy with admin/VP bypass; attachment download + upload now enforce project-scoped checks (401 unauthenticated, 403 non-member, 200 member, 404 safe missing-file); bulk auth dependency injection across 54 route files protecting all mutating POST/PATCH endpoints; opportunistic expired session cleanup (throttled per-process); `LocalStorageAdapter` path-traversal hardening (`_resolve_safe`) so DB-supplied storage keys cannot escape root; `backend_storage/` added to `.gitignore`. 12 new security tests + 2 existing auth tests updated for now-protected `POST /api/people/`. Suite: 371 → **383**.
- **2026-04-09 Sprint D: auth, permissions, and storage boundary** — DB-backed session auth (login/logout/me) with bcrypt, reusable `require_admin_or_vp` dependency applied to 7 protected routes, attachment upload + download with `LocalStorageAdapter` abstraction (configurable via `REX_STORAGE_PATH`), conftest stub-admin override + `real_auth_client` fixture for auth tests. 26 new tests. Suite: 345 → 371.
- **2026-04-09 Sprint C: schedule and execution health** — schedule drift summary, project schedule health rollup, daily log summary, project manpower aggregation with date filters + by-company breakdown, inspection summary with linked-punch visibility, cross-domain project execution health helper. 21 new tests. Suite: 324 → 345.
- **2026-04-09 Sprint B: financial intelligence** — budget rollup math (`compute_budget_line_item_rollup` + read endpoint + single/bulk refresh), billing period summary helpers (single + project), payment application summary (commitment+billing+lien waivers), commitment summary (PCO/CCO/links/pay app aggregation). 19 new tests. Suite: 305 → 324.
- **2026-04-09 Sprint A: operational intelligence** — warranty status auto-transitions (refresh single + bulk), RFI aging helper + project summary, submittal aging helper + project summary, punch days_open read-time computation in gate evaluator, punch aging refresh endpoints. 21 new tests + 2 existing punch gate tests rewritten to backdate `created_at` honestly. Portfolio readiness rollup confirmed already-implemented.
- **2026-04-09** Portfolio-level closeout readiness rollup (`GET /api/closeout-readiness/portfolio`) with filters and 9 tests
- **2026-04-09** Time-based gate conditions (`45_days_post_final_co`, `45_days_post_opening`) — 11 tests
- **2026-04-09** Punch aging gate in holdback evaluation — 8 tests
- **2026-04-09** Project closeout readiness summary (`GET /api/projects/{id}/closeout-readiness`) — 9 tests
- **2026-04-09** Milestone gate evaluation (certified, evidence, checklist, warranty, gate_conditions metadata) — 10 tests
- **2026-04-09** Milestone certification workflow with variance computation — 10 tests
- **2026-04-09** Milestone evidence helper (parsed JSONB checklist + evaluate) — 10 tests
- **2026-04-09** Project member primary-role partial unique index — 6 tests
- **2026-04-09** Warranty expiration helper + alert generation — 11 tests
- **2026-04-09** Role-based checklist assignee resolution — 6 tests
- **2026-04-09** Closeout checklist from template + rollup — 9 tests

### Currently running
- (none — between sprints)

### Latest frontend
- **2026-04-10 Frontend Sprint 1: closeout slice UI** — 7 files: `api.js` (token-managed fetch wrapper), `auth.jsx` (context + /me), `Login.jsx`, `Portfolio.jsx` (readiness table with status badges), `ProjectReadiness.jsx` (detail cards for checklist/milestones/holdback/warranty/issues), `Checklists.jsx` (create-from-template, item list with checkbox toggle + rollup progress bar), `Milestones.jsx` (evidence checklist, evaluate/certify/gates panel), `Attachments.jsx` (upload form + download table). Builds to 65 KB gzip. Uses HashRouter, Vite proxy to :8000, inline styles. All 6 verification flows exercisable end-to-end.

### Next up
- **Frontend polish + expanded coverage**: loading spinners, error boundaries, responsive layout, Mitch-vs-admin role UX, field-ops CRUD screens. Also: background jobs (warranty refresh, snapshots, session cleanup).

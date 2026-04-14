# Rex OS Deployment Runbook

> Last reconciled: **2026-04-14** (phases 41–53: full production promotion complete).
> Current production topology:
> - Backend: Railway (`rex-os-api-production.up.railway.app`) — Nixpacks build,
>   auto-migrate on startup, apscheduler enabled with 5 background jobs,
>   slowapi login rate limiting, optional Sentry via `REX_SENTRY_DSN`
>   (code-ready, not activated in prod as of this reconciliation).
> - Frontend: Vercel (`rex-os.vercel.app`) — Vite build, HashRouter, no SPA rewrites.
>   Git SHA injected at build time via `VERCEL_GIT_COMMIT_SHA`.
>   BuildVersionChip in the sidebar surfaces both `/api/version` (backend) and
>   the injected frontend commit so support can confirm the running build.
> - DB: Railway-managed Postgres in the same project; `rex` schema.
> - Schema migrations: **8 total** (4 `rex2_*` bootstrap files + 4 phase-numbered batches
>   — see `migrations/` and `backend/app/migrate.py::MIGRATION_ORDER`).
> - Optional demo seed: `migrations/rex2_demo_seed.sql`, gated by `REX_DEMO_SEED`,
>   NOT in `MIGRATION_ORDER` — applied only when the env var is set.
>   **Production has `REX_DEMO_SEED` unset**; demo data never touches prod.
> - File storage: `REX_STORAGE_BACKEND` — **production is currently `local`**
>   (ephemeral Railway disk). S3/R2 adapter is **code-ready and demo-safe
>   but not activated in production** as of this reconciliation. The cutover
>   is a later operational step; see §1f for the required sequence (demo
>   round-trip first, then prod).
> - CI: `.github/workflows/ci.yml` runs backend pytest + frontend `vite build` on
>   every push + PR. `.github/workflows/deployed-smoke.yml` runs browser + curl
>   proxy/redirect invariants against a deployed URL (manual dispatch + 6h cron).
> - Release visibility: `GET /api/version` on the backend returns `{commit, build_time, environment}`;
>   the frontend exposes `window.__REX_VERSION__` for the browser console and
>   renders the same identity in the sidebar BuildVersionChip popover.

## Post-promotion status (2026-04-14)

- Production promoted from `release/prod-closure @ 3c215f0` through a merge to
  `master` and fast-forward of `main` to `8f191f5`, plus one empty commit
  `3148f0c` to force Vercel's git webhook to run a genuine `vite build`
  (prior deploys had been serving a stale pre-phase-46 bundle via 0ms no-op
  rebuilds — see "Known production gotchas" below).
- Railway prod currently runs **`main @ d119663`** (post-reconciliation
  CI-only fix on top of `3148f0c`, no runtime change) with
  `REX_AUTO_MIGRATE=true` having successfully applied phases 41–50
  migrations on first boot at `3148f0c`. `/api/ready` reports `db.ok=true`
  and `storage.ok=true, backend=local`.
- Vercel prod currently serves `index-gT1ItBVr.js` (~620 KB raw / ~156 KB gzip,
  contains all phase 46–50 UI: BuildVersionChip, Companies admin, People &
  Members admin, Photos upload, Closeout item edit drawer, per-route
  ErrorBoundary, responsive 900/560px media queries).
- A separate demo environment was used as the proving ground for this
  promotion. See §7 "Demo environment" below.

Architecture:
- **Frontend** → Vercel (React + Vite, served from `frontend/`)
- **Backend** → Railway (FastAPI + uvicorn, served from `backend/`)
- **Database** → Railway-managed PostgreSQL (`rex` schema)

The frontend hits the backend cross-origin via `VITE_API_URL`. The backend
allows the Vercel domain via `REX_CORS_ORIGINS`.

---

## 1. Deploy the backend to Railway

### 1a. Create the Railway project

1. Go to https://railway.com/new
2. Click **Deploy from GitHub repo** → select `papadrew1182/rex-os`
3. Railway will auto-detect `nixpacks.toml` and `railway.json`. Don't change anything yet.

### 1b. Add Postgres

1. In the Railway project view, click **+ New** → **Database** → **Add PostgreSQL**
2. Wait ~30s for it to provision
3. Click the Postgres service → **Variables** tab → copy the value of `DATABASE_URL`
   (it looks like `postgresql://postgres:xxx@xxx.railway.internal:5432/railway`)

### 1c. Set backend env vars

Click your backend service (the one created from the GitHub repo) → **Variables** tab → add:

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference the Postgres service. Railway resolves it automatically. **If the project has more than one Postgres service** (e.g. `Postgres` and `Postgres-BzcC`), use the exact service name that holds the live rex schema — `${{Postgres-BzcC.DATABASE_URL}}`. A hardcoded URL string will silently break on the next private-DNS change. |
| `REX_AUTO_MIGRATE` | `true` | Apply all migrations on startup. |
| `REX_ENABLE_SCHEDULER` | `true` | Boot the apscheduler with all 5 jobs. |
| `REX_CORS_ORIGINS` | `https://rex-os.vercel.app,https://rex-os-papadrew1182.vercel.app` | Update after Vercel gives you the real URL in step 2. |
| `MIGRATE_SECRET` | (any random string) | Protects `/api/admin/migrate`. |
| `LOG_LEVEL` | `INFO` | Optional. |
| `REX_EMAIL_TRANSPORT` | `noop` | Or `smtp` if you set the SMTP_* vars. |

### 1d. Generate a public URL

1. Click your backend service → **Settings** tab → **Networking** → **Generate Domain**
2. Copy the URL — looks like `https://rex-os-production-xxxx.up.railway.app`
3. Verify it works: `https://<your-railway-url>/api/health` should return `{"status":"ok",...}`

### 1e. First deploy

Railway auto-deploys on push to the linked branch. The first deploy after setting
`REX_AUTO_MIGRATE=true` will apply all 8 migrations in order: the 4 `rex2_*` base
files (schema + canonical DDL + foundation bootstrap + business seed) followed by
the 4 phase-numbered migrations (`002_field_parity_batch.sql`,
`003_phase21_p1_batch.sql`, `004_phase31_jobs_notifications.sql`,
`005_phase38_phase39_p2_batch.sql`). The applied list is hardcoded in
`backend/app/migrate.py::MIGRATION_ORDER`.

Watch the logs in **Deployments** → **View Logs** for `auto_migrate complete applied=N failed=0`.
On a healthy boot you should also see `scheduler_started job_count=5`, confirming
the apscheduler started with all 5 background jobs registered.

### 1f. File storage (S3 cutover — currently deferred in prod)

Rex OS uses a pluggable storage adapter (`backend/app/services/storage.py`).
The `local`, `memory`, and `s3` backends are all implemented.

**Current production state (as of 2026-04-14):** `REX_STORAGE_BACKEND` is
**unset** on prod, which resolves to `local` — uploaded files are written to
the Railway container's ephemeral disk. This is **tolerated temporarily**
because the current user base is internal, photo/attachment volume is low,
and the prod promotion of phases 41–53 was explicitly scoped to hold storage
backend unchanged. `GET /api/ready` on prod confirms
`storage.ok=true, backend=local`.

**The S3 cutover is the next operational hardening step**, not code work.
Before flipping prod, the **demo proving-ground sequence is required**:

1. Create a demo-scoped S3 (or R2) bucket
2. Create a demo-scoped IAM user / API token limited to that bucket
3. Set `REX_STORAGE_BACKEND=s3` + bucket/region/creds on the **demo** Railway
   environment first (NOT prod)
4. Verify `GET /api/ready` on demo reports `backend=s3, ok=true`
5. Upload a photo via the Photos page on demo, reload, confirm it still
   previews (this is the proof local disk can't provide)
6. Only after demo round-trip succeeds, repeat the var set on **prod**
   with a **separate** prod bucket and prod-scoped IAM credentials

Supported backends via `REX_STORAGE_BACKEND=s3`:
- AWS S3
- Cloudflare R2 (recommended for egress cost — demo buckets are cheap)
- MinIO / any S3-compatible endpoint

Env vars to set when activating (per environment):

| Variable | Example | Notes |
|---|---|---|
| `REX_STORAGE_BACKEND` | `s3` | Currently unset on prod (= `local`). |
| `REX_S3_BUCKET` | `rex-os-prod-attachments` / `rex-os-demo-attachments` | Must exist; **must differ between prod and demo**. |
| `REX_S3_REGION` | `us-east-1` (AWS) / `auto` (R2) | Default `us-east-1`. |
| `REX_S3_ENDPOINT_URL` | `https://<acct>.r2.cloudflarestorage.com` | Set for R2 / MinIO. Omit for plain AWS S3. |
| `AWS_ACCESS_KEY_ID` | — | Standard boto3 env; R2 uses an R2 API token as key. |
| `AWS_SECRET_ACCESS_KEY` | — | Standard boto3 env. Scope demo and prod to separate keys. |

Verification after each environment flip:
1. `GET /api/ready` must report `storage.ok: true` with `backend: "s3"`.
2. Upload any attachment from the UI (e.g. a photo via `/#/photos` → Upload
   Photo, or any file into an RFI drawer).
3. Redeploy the backend and confirm the attachment still previews.

If `/api/ready` returns 503 with storage `error: S3 bucket '...' is not reachable`,
either the bucket name is wrong, the region/endpoint pair does not match, or the
credentials lack `s3:HeadBucket` permission. Fix the specific error — do not
fall back to `local` in production **if the S3 flip has already happened**;
if the flip hasn't happened yet, staying on `local` is the current baseline.

---

## 2. Deploy the frontend to Vercel

### 2a. Import the repo

1. Go to https://vercel.com/new
2. Click **Import Git Repository** → select `papadrew1182/rex-os`
3. Vercel will auto-detect the `vercel.json`. Don't change the build settings.

### 2b. Set frontend env vars

In the import flow → **Environment Variables**, add:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://<your-railway-backend-url>` (from step 1d, no trailing slash) |

### 2c. Deploy

Click **Deploy**. The first build takes ~60s.

When it completes, Vercel gives you a URL like `https://rex-os.vercel.app` and one
or two preview URLs. **Copy the production URL.**

### 2d. Update CORS on Railway

1. Go back to Railway → backend service → **Variables**
2. Edit `REX_CORS_ORIGINS` and set it to the actual Vercel URL(s):
   `https://rex-os.vercel.app,https://rex-os-git-master-papadrew1182.vercel.app`
3. Railway will redeploy automatically (~30s)

---

## 3. Verify

1. Open the Vercel URL in a browser
2. You should see the Rex OS login page
3. Sign in with `aroberts@exxircapital.com` / `rex2026!` (the seeded admin)
4. Portfolio should load with seeded projects

If anything is broken:
- Check Railway logs for the backend
- Check Vercel deployment logs for the frontend
- Hit `https://<railway-url>/api/health` and `/api/ready` to confirm the backend is up
- Check browser DevTools Network tab for CORS or 401 errors

### Known production gotchas (2026-04-13 / 2026-04-14)

- **`/api/health` ok but `/api/ready` hanging / 503 with asyncpg
  `InterfaceError: connection is closed`**
  Root cause: SQLAlchemy pool handed out a stale connection after Railway's
  idle killer closed it. Fix lives in `backend/app/database.py` —
  `pool_pre_ping=True` + `pool_recycle=1800`. If the error ever comes back,
  confirm those kwargs are still on `create_async_engine`.
- **New deploys fail startup with `asyncpg TimeoutError` at `db.get_pool()`**
  while the old deployment keeps serving `/api/health`.
  Root cause: `DATABASE_URL` points at a Postgres service that no longer
  resolves (e.g. you created a second Postgres service and the private
  hostname became ambiguous). Fix: set `DATABASE_URL` to an **explicit**
  service reference — e.g. `${{Postgres-BzcC.DATABASE_URL}}` — rather than a
  hardcoded internal hostname string. Verify with `railway variables` that
  the resolved value matches the Postgres service that actually holds the
  `rex` schema.
- **Vercel UI shows "Failed to fetch" on login.**
  Root cause: `REX_CORS_ORIGINS` on the Railway backend didn't include the
  Vercel origin (CORS defaults to `localhost:5173,localhost:3000`). Fix: set
  `REX_CORS_ORIGINS=https://rex-os.vercel.app` on `rex-os-api`. Confirm with
  a preflight curl:
  ```
  curl -i -X OPTIONS \
    -H "Origin: https://rex-os.vercel.app" \
    -H "Access-Control-Request-Method: POST" \
    https://<railway-url>/api/auth/login
  ```
  The response must include `access-control-allow-origin: https://rex-os.vercel.app`.
- **Railway nixpacks container crashes at import time with
  `sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from given
  URL string`** — healthcheck fails 6 times in a row with no app stdout.
  Root cause: `DATABASE_URL` env var is set to an empty string (usually
  because a `${{Postgres.DATABASE_URL}}` reference didn't resolve — e.g.
  the Postgres service in a new environment is named `Postgres-<hash>`,
  not `Postgres`). Pydantic `BaseSettings` returns `""` as an override
  (not the default), and SQLAlchemy's `create_async_engine("")` fails at
  module import before uvicorn can log anything. Fix: copy the
  `DATABASE_URL` value directly from the Postgres service's own Variables
  tab and paste it as a literal into the backend service — less elegant
  than a reference but unambiguous. Verify with
  `railway variables --service rex-os-api | grep DATABASE_URL` that the
  value is a real `postgresql://...` string, not blank.
- **First-time boot on a fresh Postgres times out the healthcheck** even
  though migrations are running cleanly in the background.
  Root cause: `REX_AUTO_MIGRATE=true` applies ~2,900 lines of DDL + seed SQL
  from foundation bootstrap on first boot; this can take 60–90s, leaving
  almost no margin inside the default 100s healthcheck window.
  Fix: `railway.json` now sets `healthcheckTimeout: 300` for the prod
  service — ample for cold starts, still tight enough to catch genuinely
  stuck containers. Steady-state redeploys remain sub-10s.
- **Vercel "Redeploy" produces a 0ms no-op build and serves a stale bundle.**
  Root cause: a dashboard **Redeploy** on an existing deployment record
  reuses the prior build artifact — if that prior artifact was from before
  a major frontend change, the "new" deploy silently serves the old UI
  (observed during the 2026-04-14 prod promotion: Vercel kept serving a
  391-byte stub referencing `index-DNZpiF_4.js` even after Railway was on
  the new commit). **Fix:** push an empty commit to the deploy branch —
  this gives Vercel a fresh git SHA and forces a real `npm install + vite
  build` via the webhook path:
  ```
  git checkout main
  git commit --allow-empty -m "deploy: force fresh Vercel build"
  git push origin main
  ```
  Verify the fix by fetching `https://rex-os.vercel.app/` and grepping for
  the script tag — the bundle hash should change, and grepping the new
  bundle should find user-visible strings like `Build Identity` or
  `Upload Photo` which are present in phase 46–50 source.

---

## 4. Future deploys — canonical branch is `main`

### 4a. Production deploy branch

**Both Railway prod (`rex-os-api-production.up.railway.app`) and Vercel
prod (`rex-os.vercel.app`) watch `main`.** Pushes to `main` auto-deploy
both backend and frontend in parallel:

```
git push origin main
```

Railway picks it up via GitHub webhook → Nixpacks build → migrations run
on boot → zero-downtime container swap. Vercel picks it up via its own
GitHub webhook → `npm install + vite build` → alias swap. Typical
end-to-end time is 60–180s for both.

### 4b. Release flow (recommended going forward)

Simple path:
1. Create a feature branch off `main`
2. Land changes via PR to `main`
3. Merge — both platforms auto-deploy

Multi-commit stabilization path (only when a set of changes needs to be
integrated and browser-verified against a separate environment before
prod):
1. Create a `release/<name>` branch off `main`
2. Land the feature commits on the release branch
3. Point the **demo** environment (see §7) at the release branch
4. Verify in demo — real backend, real browser, not mocks
5. Merge release branch → `main`, push `main`, let auto-deploy handle prod

This is the pattern phases 46–53 used (release branch was
`release/prod-closure`, demo proved it, then merged to main on
2026-04-14).

### 4c. Historical `master` branch — deprecated

Prior to 2026-04-14, this repo kept both `main` (deployed) and `master`
(integration). That split existed for ops history reasons but caused real
confusion during the phase 46–53 promotion — merges landed on `master`
but prod watched `main`, and the branches diverged when cherry-picks were
applied to both.

**Going forward, `master` is redundant.** New work should go through
`main` only. `master` can be deleted on origin once the next team member
confirms no local tooling references it — until then it's kept as a
historical mirror and may fall behind `main` as fast-forwards stop being
applied to it.

### 4d. Historical `release/prod-closure` branch — deprecated

This branch existed specifically to stage phases 46–52 for the 2026-04-14
promotion. Its work has been merged to `main` as of commit `8f191f5`
(release merge) → `3148f0c` (Vercel forced-rebuild empty commit). The
branch can be deleted on origin. Future release branches should use the
generic `release/<purpose>` pattern and be deleted after promotion.

---

## 5. Manual migration trigger (fallback)

If `REX_AUTO_MIGRATE` is off and you need to apply pending migrations:

```
curl -X GET "https://<railway-url>/api/admin/migrate?secret=$MIGRATE_SECRET"
```

This returns a JSON list of every migration file with its applied status.

---

## 6. Env var reference

### Backend (Railway)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | Postgres connection string (Railway provides) |
| `REX_AUTO_MIGRATE` | no | `false` | Auto-apply migrations on startup |
| `REX_ENABLE_SCHEDULER` | no | `false` | Boot apscheduler + 5 background jobs |
| `REX_CORS_ORIGINS` | yes (prod) | `localhost:5173,localhost:3000` | Comma-separated allowed origins |
| `MIGRATE_SECRET` | yes (prod) | `rex-migrate-2026` | Protects /api/admin/migrate |
| `REX_EMAIL_TRANSPORT` | no | `noop` | `noop` / `log` / `smtp` |
| `REX_SMTP_HOST` | if smtp | `localhost` | SMTP server |
| `REX_SMTP_PORT` | if smtp | `587` | SMTP port |
| `REX_SMTP_USER` | if smtp | — | SMTP username |
| `REX_SMTP_PASSWORD` | if smtp | — | SMTP password |
| `REX_SMTP_FROM` | if smtp | `rex@localhost` | From address |
| `REX_DRIFT_CRITICAL_DAYS` | no | `5` | Schedule drift critical threshold |
| `REX_DRIFT_WARNING_DAYS` | no | `2` | Schedule drift warning threshold |
| `REX_STORAGE_BACKEND` | no | `local` | `local` / `memory` / `s3`. Currently unset on prod (= `local`). S3 cutover is a later step — see §1f. |
| `REX_STORAGE_PATH` | no | `./backend_storage` | Local backend only. |
| `REX_S3_BUCKET` | if s3 | — | Bucket name for the s3 adapter. |
| `REX_S3_REGION` | if s3 | `us-east-1` | AWS region or R2 equivalent. |
| `REX_S3_ENDPOINT_URL` | if r2/minio | — | Custom S3 endpoint for R2 / MinIO. |
| `AWS_ACCESS_KEY_ID` | if s3 | — | boto3 credential (S3 / R2 token id). |
| `AWS_SECRET_ACCESS_KEY` | if s3 | — | boto3 credential. |
| `REX_DEMO_SEED` | no | `false` | Opt-in demo data for Bishop Modern. Never set in prod. |
| `REX_LOGIN_RATE_LIMIT` | no | `10/minute` | Rate limit on `/api/auth/login` (slowapi format). |
| `REX_SENTRY_DSN` | no | — | Enables backend Sentry when set. |
| `REX_RELEASE` | no | commit sha | Release identifier surfaced by `/api/version`. |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

### Frontend (Vercel)

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_URL` | yes (prod) | empty | Backend base URL, e.g. `https://rex-os-api-production.up.railway.app` |
| `VITE_SENTRY_DSN` | no | empty | Enables frontend Sentry when set. Baked at build time — changing requires a Vercel redeploy. Currently unset on prod (code-ready, not activated). |
| `VITE_SENTRY_ENV` | no | `production` (build `MODE`) | Environment tag for frontend Sentry events. Set to `demo` on the demo Vercel project so the BuildVersionChip shows the environment badge. |

---

## 7. Demo environment

A separate demo environment exists under the same Railway project (`Rex OS`
under `exxir's Projects`) as the prod backend. It was used as the proving
ground for the phase 46–53 prod promotion and continues to serve that role
for future release flights.

### 7a. Topology

- **Railway project**: same `Rex OS` project; **environment: `demo`** (not
  `production`). Railway's native per-project environment feature gives
  isolated env vars and its own Postgres service.
- **Railway services in demo**: `rex-os` (the backend), `Postgres-gpQz`
  (the Postgres — note the random suffix, see the DATABASE_URL gotcha in §3)
- **Vercel project**: separate project `rex-os-demo` (not `rex-os`). Preview
  deploys are served under the git-branch alias pattern
  `https://rex-os-demo-git-<branch>-<team>.vercel.app`.
- **Deploy branch**: typically `main` or a `release/<name>` branch being
  flight-tested. Demo watched `release/prod-closure` for the phase 46–53
  promotion flight.

### 7b. Demo-specific env var deltas from prod

| Variable | Demo value | Why different |
|---|---|---|
| `ENVIRONMENT` | `demo` | Surfaced in `/api/version` and BuildVersionChip badge |
| `REX_DEMO_SEED` | `true` | **Never set this on prod.** Populates Bishop Modern + full operational data set |
| `REX_ENABLE_SCHEDULER` | `false` | Demo does not need the 5 background jobs running |
| `REX_STORAGE_BACKEND` | `local` | Matches prod baseline; S3 can be flipped here first for activation testing |
| `REX_CORS_ORIGINS` | demo Vercel URL | Must include the `rex-os-demo-*` alias |
| `REX_JWT_SECRET` | **new value, NOT reused from prod** | Isolated session signing |
| `MIGRATE_SECRET` | **new value, NOT reused from prod** | Protects `/api/admin/migrate` separately |
| `DATABASE_URL` | `${{Postgres-gpQz.DATABASE_URL}}` OR the literal URL | Use the **exact** service name — the random `-gpQz` suffix matters |

### 7c. Demo seeded admin credentials

Login as `aroberts@exxircapital.com` / `rex2026!`. These credentials come
from `rex2_foundation_bootstrap.sql` and are the same on prod (foundation
bootstrap runs in both environments). Demo additionally has Bishop Modern
operational data loaded via `rex2_demo_seed.sql`.

### 7d. Verification sequence for a new demo deploy

```
DEMO=https://rex-os-demo.up.railway.app
curl -sS $DEMO/api/health
curl -sS $DEMO/api/ready              # backend=local OR backend=s3 if flipped
curl -sS $DEMO/api/version            # environment=demo, commit matches branch HEAD
curl -sS -X POST $DEMO/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"aroberts@exxircapital.com","password":"rex2026!"}'
# Expect 200 with token
```

Then open the demo Vercel URL in a browser, log in, and walk the core
flight (portfolio, schedule, RFIs, photos upload+metadata, people admin,
BuildVersionChip). **Demo passing all of this is the gate for a prod
promotion.** Never promote to prod without a clean demo flight first.

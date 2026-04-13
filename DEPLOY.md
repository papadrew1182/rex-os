# Rex OS Deployment Runbook

> Last reconciled: **2026-04-13** (phases 41–44: production credibility sprint).
> Current production topology:
> - Backend: Railway (`rex-os-api-production.up.railway.app`) — Nixpacks build,
>   auto-migrate on startup, apscheduler enabled with 5 background jobs,
>   slowapi login rate limiting, optional Sentry via `REX_SENTRY_DSN`.
> - Frontend: Vercel (`rex-os.vercel.app`) — Vite build, HashRouter, no SPA rewrites.
>   Git SHA injected at build time via `VERCEL_GIT_COMMIT_SHA`.
> - DB: Railway-managed Postgres in the same project; `rex` schema.
> - Schema migrations: **8 total** (4 `rex2_*` bootstrap files + 4 phase-numbered batches
>   — see `migrations/` and `backend/app/migrate.py::MIGRATION_ORDER`).
> - Optional demo seed: `migrations/rex2_demo_seed.sql`, gated by `REX_DEMO_SEED`,
>   NOT in `MIGRATION_ORDER` — applied only when the env var is set.
> - File storage: `REX_STORAGE_BACKEND` (`local` for dev, **must be `s3` in prod**
>   — see §1f).
> - CI: `.github/workflows/ci.yml` runs backend pytest + frontend `vite build` on
>   every push + PR. `.github/workflows/deployed-smoke.yml` runs browser + curl
>   proxy/redirect invariants against a deployed URL (manual dispatch + 6h cron).
> - Release visibility: `GET /api/version` on the backend returns `{commit, build_time, environment}`;
>   the frontend exposes `window.__REX_VERSION__` for the browser console.

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

### 1f. File storage (required for production)

Rex OS uses a pluggable storage adapter (`backend/app/services/storage.py`).
Locally the `local` backend is fine; **in production you must use S3-compatible
object storage** because Railway containers have ephemeral disks — uploaded
attachments, warranty letters, lien waivers, and spec PDFs would be lost on
every redeploy.

Supported via `REX_STORAGE_BACKEND=s3`:
- AWS S3
- Cloudflare R2 (recommended for egress cost)
- MinIO / any S3-compatible endpoint

Add these on the Railway backend service:

| Variable | Example | Notes |
|---|---|---|
| `REX_STORAGE_BACKEND` | `s3` | Default is `local` — **must** be set in prod. |
| `REX_S3_BUCKET` | `rex-os-prod-attachments` | Required when backend is `s3`. Must exist. |
| `REX_S3_REGION` | `us-east-1` (AWS) / `auto` (R2) | Default `us-east-1`. |
| `REX_S3_ENDPOINT_URL` | `https://<acct>.r2.cloudflarestorage.com` | Set for R2 / MinIO. Omit for plain AWS S3. |
| `AWS_ACCESS_KEY_ID` | — | Standard boto3 env; R2 uses an R2 API token as key. |
| `AWS_SECRET_ACCESS_KEY` | — | Standard boto3 env. |

Verification after deploy:
1. `GET /api/ready` must report `storage.ok: true` with `backend: "s3"`.
2. Upload any attachment from the UI (e.g. drop a file in the RFI drawer).
3. Redeploy the backend and confirm the attachment still previews — this is
   the exact invariant local disk cannot hold.

If `/api/ready` returns 503 with storage `error: S3 bucket '...' is not reachable`,
either the bucket name is wrong, the region/endpoint pair does not match, or the
credentials lack `s3:HeadBucket` permission. Fix the specific error — do not
fall back to `local` in production.

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

### Known production gotchas (encountered 2026-04-13)

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

---

## 4. Future deploys

Both platforms watch the `master` branch and auto-deploy on push:

```
git push origin master
```

Vercel deploys the frontend, Railway deploys the backend, in parallel.

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
| `REX_STORAGE_BACKEND` | yes (prod) | `local` | `local` / `memory` / `s3`. Prod must be `s3`. |
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
| `VITE_API_URL` | yes (prod) | empty | Backend base URL, e.g. `https://rex-os.up.railway.app` |

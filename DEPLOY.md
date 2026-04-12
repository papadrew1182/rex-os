# Rex OS Deployment Runbook

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
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference the Postgres service. Railway resolves it automatically. |
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
`REX_AUTO_MIGRATE=true` will apply all 7 migrations (`001` → `004` plus the rex2 base files).

Watch the logs in **Deployments** → **View Logs** for `auto_migrate complete applied=N failed=0`.

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
| `REX_STORAGE_PATH` | no | (default) | Local file storage dir |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

### Frontend (Vercel)

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_URL` | yes (prod) | empty | Backend base URL, e.g. `https://rex-os.up.railway.app` |

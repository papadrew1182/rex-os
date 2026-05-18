# Phase E Handoff Dry Run — Sentry Activation + Production Browser Sanity

Dry-run completion of `docs/handoffs/phase_e_sentry_browser_sanity_handoff_template.md` against current known blockers to validate template completeness before operator execution.

## 1) Run metadata
- Run timestamp (UTC): 2026-05-18T03:43:31Z
- Operator: autonomous cron (Hermes)
- Branch / commit used for prep: `fix/login-api-base-routing` @ `b74228c04926204abbb7f403cab07c72bdedf898`
- Target environment: planning dry-run (`demo` then `production` sequence)
- Scope executed in this handoff:
  - [x] Backend Sentry activation (planning checklist only; no env mutation performed)
  - [x] Frontend Sentry activation (planning checklist only; no env mutation performed)
  - [x] Real-browser sanity pass (planning checklist only; no browser execution performed)

## 2) Preconditions
- [x] `DEPLOY.md` reviewed (env + verification sections)
- [x] Rollback plan captured (`ROLLBACK_REGISTRY.md` reference)
- [x] No schema migration required for this run
- [ ] Credentials/access verified for Railway, Vercel, Sentry (operator step required)

## 3) Backend Sentry activation evidence
### Config changes
- `REX_SENTRY_DSN` set: no (dry-run only)
- `REX_RELEASE` / commit reference: planned source = deploy commit at execution time

### Verification commands + output
```bash
curl -fsS "$REX_API_BASE/api/health"
curl -fsS "$REX_API_BASE/api/version"
```
- Health result: N/A (dry-run planning)
- Version result: N/A (dry-run planning)

### Controlled error probe
- Probe method: intentionally trigger one controlled backend exception in non-destructive endpoint context after DSN set
- Expected behavior: event captured in Sentry with backend release metadata
- Sentry event ID: N/A (dry-run planning)
- Timestamp (UTC): N/A

### Rollback (if needed)
- [ ] DSN unset/reverted
- [ ] Service restarted/redeployed
- [ ] Health rechecked

## 4) Frontend Sentry activation evidence
### Config changes
- `VITE_SENTRY_DSN` set: no (dry-run only)
- Vercel deploy URL: N/A
- Deployed frontend commit SHA: N/A

### Verification
- [ ] `BuildVersionChip` matches intended backend/frontend commit
- [ ] Controlled frontend error emitted
- Sentry event ID: N/A
- Timestamp (UTC): N/A

### Rollback (if needed)
- [ ] DSN removed/reverted
- [ ] Frontend redeployed
- [ ] App smoke-loaded successfully

## 5) Real-browser production sanity pass
### Accounts/roles validated
- Admin account: N/A (requires operator-run browser session)
- Non-admin account: N/A (requires operator-run browser session)

### Required checks
- [ ] Login success (both roles)
- [ ] Portfolio loads
- [ ] At least one user-visible operational page loads (record page)
- [ ] One write-guard denial path validated for non-admin
- [ ] Notifications surface loads
- [ ] Screenshot set captured and attached

### Evidence links
- Screenshot bundle path: N/A
- Notes/log snippets: N/A

## 6) Outcome summary
- Overall result: `PARTIAL` (template validated; operational execution still pending)
- Open blockers:
  - Production/demo Sentry DSN provisioning not completed
  - Operator credentials/session access not verified in this automation host
  - Real-browser pass requires manual interactive execution window
- Follow-up owner: Platform/Ops + QA/Release operator
- Next executable step: operator executes demo-first Sentry activation using this filled checklist, captures event IDs and deploy URLs, then repeats for production and browser sanity pass.
- Rollback state at close: no changes performed; rollback not required.

## 7) Operator-ready execution packet (demo-first, then production)

### 7.1 Environment variables to set locally before execution
```bash
# Pick one target at a time: demo first, then production
export REX_API_BASE="https://<target-api-host>"
export REX_WEB_BASE="https://<target-web-host>"
export TARGET_ENV="demo"   # switch to production after demo pass
export RUN_TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
```

### 7.2 Backend Sentry activation + verification commands
```bash
# 1) Set DSN in backend runtime (Railway service/env-specific step)
# railway variables set REX_SENTRY_DSN="<dsn>" --service <backend-service> --environment $TARGET_ENV

# 2) Verify backend health + version after deploy/restart
curl -fsS "$REX_API_BASE/api/health"
curl -fsS "$REX_API_BASE/api/version"

# 3) Capture evidence payload for handoff
curl -fsS "$REX_API_BASE/api/version" | jq .
```

Evidence placeholders:
- Railway service/environment:
- Deploy/restart URL or log reference:
- `/api/health` response:
- `/api/version` response (include commit/environment):

### 7.3 Frontend Sentry activation + verification commands
```bash
# 1) Set frontend DSN in Vercel project/environment
# vercel env add VITE_SENTRY_DSN <environment>

# 2) Trigger/review deploy and capture URL
# vercel --prod   # for production pass; use non-prod flow for demo pass

# 3) Confirm app + version API reachability
curl -fsS "$REX_WEB_BASE" >/dev/null
curl -fsS "$REX_API_BASE/api/version"
```

Evidence placeholders:
- Vercel project/environment:
- Deploy URL:
- Frontend commit SHA shown by BuildVersionChip:
- Backend commit SHA shown by BuildVersionChip:

### 7.4 Controlled Sentry probe checklist (backend + frontend)
- Backend probe executed (method + endpoint):
- Backend Sentry event ID:
- Frontend probe executed (route + action):
- Frontend Sentry event ID:
- Timestamp window (UTC):

### 7.5 Real-browser sanity pass script (manual)
1. Open `$REX_WEB_BASE`.
2. Login as non-admin user; confirm portfolio load.
3. Visit one operational page (record exact route).
4. Attempt an admin-only write path as non-admin; capture denial evidence.
5. Logout/login as admin; confirm same path succeeds (or intended admin behavior).
6. Open notifications surface; capture screenshot.
7. Capture BuildVersionChip popover showing FE+BE SHAs.

Evidence placeholders:
- Non-admin account used:
- Admin account used:
- Operational route validated:
- Write-guard denial artifact (screenshot/log):
- Notifications artifact (screenshot/log):
- BuildVersionChip artifact (screenshot/log):

### 7.6 Rollback quick commands (if Sentry activation needs revert)
```bash
# Backend rollback (unset DSN + redeploy/restart)
# railway variables delete REX_SENTRY_DSN --service <backend-service> --environment $TARGET_ENV

# Frontend rollback (remove DSN + redeploy)
# vercel env rm VITE_SENTRY_DSN <environment>
```

# Phase E Handoff Template — Sentry Activation + Production Browser Sanity

Use this template for every Phase E production-readiness execution pass.

## 1) Run metadata
- Run timestamp (UTC):
- Operator:
- Branch / commit used for prep:
- Target environment: `demo` or `production`
- Scope executed in this handoff:
  - [ ] Backend Sentry activation
  - [ ] Frontend Sentry activation
  - [ ] Real-browser sanity pass

## 2) Preconditions
- [ ] `DEPLOY.md` reviewed (env + verification sections)
- [ ] Rollback plan captured (`ROLLBACK_REGISTRY.md` reference)
- [ ] No schema migration required for this run
- [ ] Credentials/access verified for Railway, Vercel, Sentry

## 3) Backend Sentry activation evidence
### Config changes
- `REX_SENTRY_DSN` set: yes/no
- `REX_RELEASE` / commit reference:

### Verification commands + output
```bash
curl -fsS "$REX_API_BASE/api/health"
curl -fsS "$REX_API_BASE/api/version"
```
- Health result:
- Version result:

### Controlled error probe
- Probe method:
- Expected behavior:
- Sentry event ID:
- Timestamp (UTC):

### Rollback (if needed)
- [ ] DSN unset/reverted
- [ ] Service restarted/redeployed
- [ ] Health rechecked

## 4) Frontend Sentry activation evidence
### Config changes
- `VITE_SENTRY_DSN` set: yes/no
- Vercel deploy URL:
- Deployed frontend commit SHA:

### Verification
- [ ] `BuildVersionChip` matches intended backend/frontend commit
- [ ] Controlled frontend error emitted
- Sentry event ID:
- Timestamp (UTC):

### Rollback (if needed)
- [ ] DSN removed/reverted
- [ ] Frontend redeployed
- [ ] App smoke-loaded successfully

## 5) Real-browser production sanity pass
### Accounts/roles validated
- Admin account:
- Non-admin account:

### Required checks
- [ ] Login success (both roles)
- [ ] Portfolio loads
- [ ] At least one user-visible operational page loads (record page)
- [ ] One write-guard denial path validated for non-admin
- [ ] Notifications surface loads
- [ ] Screenshot set captured and attached

### Evidence links
- Screenshot bundle path:
- Notes/log snippets:

## 6) Outcome summary
- Overall result: `PASS` / `PARTIAL` / `FAIL`
- Open blockers:
- Follow-up owner:
- Next executable step:
- Rollback state at close:

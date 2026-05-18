# RELEASE_TRAIN

Last Updated (UTC): 2026-05-18 19:03:34Z

## Current Train
- Train: Rex 2.0 autonomous execution continuation
- Stage: Phase D (hardening + continuity lane, with Phase E readiness staging)
- Branch: `fix/login-api-base-routing`
- Base Head: `origin/main @ b08f5ef`

## Mandatory Gates
1. Fresh-db replay validation before schema-risk merges.
2. Runtime survivability checks captured.
3. Frontend build/test parity after UI changes.
4. Production-protected ops stop at approval boundary.

## Current Gate Status
- Fresh-db replay: PASS (`2026-05-17T16-40-05Z_fresh_db_replay`)
- Action queue/compensator pytest subset: PASS (15 passed, 2 skipped)
- Frontend build: PASS
- Frontend SSE parser unit test path: PASS (`npm run test:unit:sse`)
- Frontend API-base host inference unit test path: PASS (`npm run test:unit:api-base`)
- Frontend lint parity: PASS (`npm run lint`)
- Migration-sanity reliability check: PASS (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_session2_migration_sanity.py` => 7 passed)
- Auth/session production-like verification: PASS (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_verification_flows.py` => 9 passed)
- Rollback/advisory-lock recovery verification: PASS (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_phase40_verification.py` => 8 passed; focused `...::test_ph40_advisory_lock_stable_across_repeat_runs` => 1 passed)
- Default local migration-sanity path (no DB override): FAIL (`pytest -q backend/tests/test_session2_migration_sanity.py` => 1 passed, 6 errors; `InvalidPasswordError` for `deploy@localhost/rex_os`)
- Production writes: none
- Latest unattended rerun (2026-05-18 16:17Z): architecture/static gates revalidated green (backend pytest subset + migration-sanity, frontend SSE + API-base unit tests, lint, build); user-visible Schedule Workbench UX hardening advanced with date-range quick presets (`Next 14 days`, `Next 30 days`, `This month`, `Clear dates`) in `frontend/src/pages/ScheduleHealth.jsx` for faster filtering workflows.

## Next Planned Stop
- Execute staffed Phase E operator handoff packet (`docs/handoffs/2026-05-18_041939Z_phase_e_operator_handoff.md`) and attach Sentry/browser evidence; then mirror evidence + rollback state into continuity docs in one commit.

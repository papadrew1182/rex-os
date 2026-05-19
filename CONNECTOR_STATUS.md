# CONNECTOR_STATUS

Last Updated (UTC): 19/05/2026 17:08:39 UTC

## Control-Plane Status
- Railway account auth: yes (`railway whoami`)
- Railway local repo link: no (`railway status` => unlinked)
- Connector runtime mutation: none performed in this phase

## Validation posture
- Fresh-db replay harness is now in place and passing for local validation:
  - `backend/scripts/fresh_db_replay.sh`
  - artifacts under `docs/ops/runtime/2026-05-16T15-23-04Z_fresh_db_replay`
- Connector-adjacent validation this run:
  - Auth/session control-path probe (no DB override) FAIL as expected on local credential drift (`InvalidPasswordError` for `deploy@localhost/rex_os`)
  - Auth/session canonical production-like path PASS (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_verification_flows.py` => 9 passed)
  - Rollback recovery suite PASS (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_phase40_verification.py` => 8 passed)
  - Rollback focused advisory-lock repeat PASS (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_phase40_verification.py::test_ph40_advisory_lock_stable_across_repeat_runs` => 1 passed)
  - Migration sanity control-path (no DB override) FAIL (`pytest -q backend/tests/test_session2_migration_sanity.py` => 1 passed, 6 errors; `InvalidPasswordError`)
  - Migration sanity canonical production-like path PASS (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_session2_migration_sanity.py` => 7 passed)
  - Action queue/compensator pytest subset PASS (15 passed, 2 skipped)
  - No connector runtime mutations executed

## Immediate recommendation
Before any deploy-adjacent connector runtime action:
1. Bind explicit Railway target context (project/service/environment), either by controlled `railway link` or explicit flags.
2. Run read-only connector health introspection.
3. Record result in deployment/handoff artifacts.

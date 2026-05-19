# MIGRATION_LEDGER

Last Updated (UTC): 19/05/2026 17:08:39 UTC

## Session 2 Replay Gate (local)
- No new migrations created.
- No schema files modified.
- Full migration chain replayed on fresh local DB.

## Evidence
- Harness: `backend/scripts/fresh_db_replay.sh`
- Artifacts: `/home/deploy/rex-os/docs/ops/runtime/2026-05-16T15-23-04Z_fresh_db_replay`
- Migration replay result: 36 applied, 0 missing, 0 errors.

## Fresh-DB Replay Rule
- Remains mandatory before destructive migration planning/execution.

## This Run
- No new migrations created.
- No migration files modified.
- Control-path migration sanity remains FAIL without DB override (`pytest -q backend/tests/test_session2_migration_sanity.py` => 1 passed, 6 errors; `InvalidPasswordError` for `deploy@localhost/rex_os`).
- Canonical production-like migration sanity remains PASS with explicit override (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_session2_migration_sanity.py` => 7 passed).
- Migration replay not rerun because this run touched no schema/migration artifacts.

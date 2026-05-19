# ROLLBACK_REGISTRY

Last Updated (UTC): 19/05/2026 17:08:39 UTC

## Current Session (Phase C Validation Sweep)
- Change class: blocker-first verification evidence refresh + documentation/state artifacts
- Runtime impact: local validation only
- Schema impact: none
- Rollback required: no
- Recovery proof this run:
  - `DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_phase40_verification.py` => PASS (8 passed)
  - `DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_phase40_verification.py::test_ph40_advisory_lock_stable_across_repeat_runs` => PASS (1 passed)
  - Confirms rollback-state checks and repeat-run recovery behavior remain stable.

## Last replay artifact
- `docs/ops/runtime/2026-05-16T15-23-04Z_fresh_db_replay/00_summary.txt`

## Rollback Standard (for future deploy-affecting PRs)
Record:
- target environment
- deployed SHA
- previous known-good SHA
- rollback trigger conditions
- rollback command sequence
- post-rollback verification evidence

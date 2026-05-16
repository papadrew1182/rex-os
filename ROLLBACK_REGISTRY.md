# ROLLBACK_REGISTRY

Last Updated (UTC): 2026-05-16 15:23:14Z

## Current Session (Fresh-DB Replay Gate)
- Change class: local replay harness + documentation/state artifacts
- Runtime impact: local validation only
- Schema impact: none in repo (replay applied existing migrations to local DB only)
- Rollback required: no

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

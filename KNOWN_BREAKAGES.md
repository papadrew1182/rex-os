# KNOWN_BREAKAGES

Last Updated (UTC): 2026-05-16 15:23:49Z

## Open Breakages / Environment Gaps
1. Railway project context is not linked in repo working copy.
   - Evidence: `railway status` => "No linked project found".
   - Impact: implicit-context Railway commands are unsafe/ambiguous.
   - Mitigation: explicit selectors or controlled `railway link` step.

## Resolved in this phase
- Local DB survivability gap for baseline validation is resolved via a deterministic local Postgres replay harness:
  - `backend/scripts/fresh_db_replay.sh`
  - Artifacts: `/home/deploy/rex-os/docs/ops/runtime/2026-05-16T15-23-04Z_fresh_db_replay`

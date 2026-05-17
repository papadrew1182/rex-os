# ACTIVE_PR_QUEUE

Last Updated (UTC): 2026-05-16 15:23:49Z

## In Flight
1. **Session 1B Baseline Reconciliation PR**
   - PR: #21
   - Branch: `chore/session-1b-baseline-reconciliation-2026-05-16`
   - Scope: docs/ops baseline alignment only

2. **Session 2 Fresh-DB Replay Gate PR**
   - Branch: `chore/session-1b-baseline-reconciliation-2026-05-16`
   - Type: local replay harness + verification artifacts
   - Scope: no production writes, no schema changes in this PR
   - Status: ready for commit/push/PR open

## Next (Queued)
1. Phase 2 schema-affecting execution lane
   - Prereq: Session 2 replay gate merged
   - Guard: preserve fresh-db replay as mandatory preflight

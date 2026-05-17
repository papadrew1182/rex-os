# ACTIVE_PR_QUEUE

Last Updated (UTC): 2026-05-17 19:59:15Z

## In Flight
1. **Phase C validation sweep (current)**
   - Branch: `main`
   - Base: `origin/main`
   - Scope:
     - Action queue service/repository validation
     - Undo compensator dispatch validation
     - SSE parser test-path audit for current frontend toolchain
     - Connector posture + CI parity recheck
    - Validation completed this run:
      - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` PASS (15 passed, 2 skipped)
      - `npm run build` PASS
      - `npm run test:unit:sse` PASS (10 passed, 0 failed)
      - `npm run lint` FAIL (no baseline config; generated Playwright artifacts and existing repo lint backlog surfaced)

## Next (Queued)
1. Phase D hardening pass (migration integrity + CI parity edge checks + stale-doc cleanup)
   - Immediate next executable: introduce scoped ESLint baseline + ignore generated outputs, then resolve first e2e lint blocker.
2. Phase E production-readiness progression review and continuity update

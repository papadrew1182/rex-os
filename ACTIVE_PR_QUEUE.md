# ACTIVE_PR_QUEUE

Last Updated (UTC): 2026-05-17 20:53:21Z

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
      - Added frontend lint baseline artifacts: `frontend/.eslintrc.cjs`, `frontend/.eslintignore` (scoped ignores for `dist/`, `playwright-report/`, `test-results/`, `node_modules/`)
      - Resolved first e2e lint blocker: removed unused `method` variable in `frontend/e2e/phase54_live_integration.spec.js`
      - `npx eslint e2e/phase54_live_integration.spec.js` PASS
      - `npm run lint` still FAIL on pre-existing repo lint backlog outside this targeted Phase D step (51 errors, 10 warnings)
      - Removed two `no-empty` violations in `frontend/src/AlertCallout.jsx` by adding explicit warn-path catches for dismiss + mark-read actions.
      - Re-ran validations after patch: `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` PASS; `npm run test:unit:sse` PASS; `npm run build` PASS; `npm run lint` now 47 errors / 10 warnings (down from 49 / 10).

## Next (Queued)
1. Phase D hardening pass (migration integrity + CI parity edge checks + stale-doc cleanup)
   - Immediate next executable: remove stale `eslint-disable` in `frontend/src/ErrorBoundary.jsx` and continue lint backlog burn-down to restore `npm run lint` pass.
2. Phase E production-readiness progression review and continuity update

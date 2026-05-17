# ACTIVE_PR_QUEUE

Last Updated (UTC): 2026-05-17 21:49:00Z

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
      - Removed stale `no-console` eslint-disable directives in `frontend/src/ErrorBoundary.jsx`, `frontend/src/assistant/ChatThread.jsx`, `frontend/src/lib/api.js`, `frontend/src/lib/sse.js`, and `frontend/src/sentry.js`.
      - `npx eslint src/ErrorBoundary.jsx src/assistant/ChatThread.jsx src/lib/api.js src/lib/sse.js src/sentry.js` PASS.
      - `npm run lint` now 41 errors / 10 warnings (down from 47 / 10); remaining failures are pre-existing lint backlog items.
      - Cleared stale `eslint-disable-line react-hooks/exhaustive-deps` from `frontend/src/pages/ScheduleHealth.jsx:1135` (no rule violation existed).
      - Re-ran architecture/static checks: backend pytest subset PASS (15 passed, 2 skipped), frontend SSE unit tests PASS (10 passed), frontend build PASS, frontend lint remains FAIL but improved to 42 findings (33 errors, 9 warnings) from 43 findings.

## Next (Queued)
1. Phase D hardening pass (migration integrity + CI parity edge checks + stale-doc cleanup)
   - Immediate next executable: remove `no-empty` lint violations in `frontend/src/notifications.jsx` and `frontend/src/pages/Notifications.jsx`, then rerun `npm run lint`.
2. Phase E production-readiness progression review and continuity update

# ACTIVE_PR_QUEUE

Last Updated (UTC): 2026-05-18 02:31:52Z

## In Flight
1. **Phase C validation sweep (current)**
   - Branch: `fix/login-api-base-routing`
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
      - Phase D lint-hardening slice complete for notification surfaces: replaced empty catch blocks with explicit warn-path catches in `frontend/src/notifications.jsx` and `frontend/src/pages/Notifications.jsx`.
      - Verification: `npx eslint src/notifications.jsx src/pages/Notifications.jsx` PASS.
      - Full lint regression after patch: `npm run lint` still FAIL on pre-existing backlog, but improved from 42 findings (33 errors, 9 warnings) to 35 findings (26 errors, 9 warnings).
      - Executed queued ScheduleHealth lint task from prior run: hoisted `weekKey` out of `renderPrintTable()` in `frontend/src/pages/ScheduleHealth.jsx` to clear `no-inner-declarations` at line 102.
      - Verification: `npx eslint src/pages/ScheduleHealth.jsx` no longer reports `no-inner-declarations`; file now reports remaining pre-existing lint backlog (`no-unused-vars` for `idSet`/`SORT_KEYS`, `no-empty` at line ~901, and one hooks warning).
      - Full lint regression after patch: `npm run lint` still FAIL due to repo backlog, improved to **34 findings** (25 errors, 9 warnings) from 35 findings (26 errors, 9 warnings).
      - Executed queued `ScheduleHealth` no-empty remediation: replaced empty `catch {}` in `LookaheadView` constraints fetch with explicit warn-path catch in `frontend/src/pages/ScheduleHealth.jsx`.
      - Verification: `npx eslint src/pages/ScheduleHealth.jsx` no longer reports `no-empty`; file now has only pre-existing `no-unused-vars` (`idSet`, `SORT_KEYS`) plus one hooks warning.
      - Full validation sweep: backend pytest subset PASS (15 passed, 2 skipped), frontend SSE unit tests PASS (10 passed), frontend build PASS, and full frontend lint still FAIL on backlog but improved to **33 findings** (24 errors, 9 warnings) from 34 findings.
      - Executed highest-priority lint burn-down slice this run (user-visible pages): removed unused `Badge` imports in `BudgetOverview.jsx`, `Drawings.jsx`, `Photos.jsx`, and `Specifications.jsx`; removed unused `TextArea` import in `SubmittalManagement.jsx`.
      - Verification: `npm run lint` remains FAIL on backlog but improved to **26 findings** (17 errors, 9 warnings) from 31 findings (22 errors, 9 warnings) at run start.
      - Re-ran Phase C/D architecture+static checks on branch `fix/login-api-base-routing`: backend AI/action queue pytest subset PASS (15 passed, 2 skipped), frontend SSE unit tests PASS (10 passed), and frontend production build PASS.
      - Executed full frontend lint gate: `npm run lint` now PASS clean (`eslint . --max-warnings 0`), indicating the prior lint backlog is fully cleared in current workspace state.
      - Ran migration-order integrity audit (`backend/app/migrate.py::MIGRATION_ORDER` vs `migrations/*.sql`): no missing ordered files; 3 intentional data-seed SQL files remain outside ordered schema migrations (`023_bishop_modern_dashboard_seed.sql`, `seed_dashboard_demo.sql`, `rex2_demo_seed.sql`).
      - Re-ran migration-order integrity audit this run: `MIGRATION_ORDER` now resolves 34 ordered SQL files with no missing entries; non-ordered SQLs are intentional bootstrap/seed artifacts (`rex2_business_seed.sql`, `rex2_canonical_ddl.sql`, `rex2_demo_seed.sql`, `rex2_foundation_bootstrap.sql`, `seed_dashboard_demo.sql`).
      - Re-ran Phase C/D architecture+static checks on `fix/login-api-base-routing`: backend AI/action queue pytest subset PASS (15 passed, 2 skipped), frontend SSE unit tests PASS (10 passed), frontend production build PASS, and frontend lint PASS (`eslint . --max-warnings 0`).
      - Executed queued Phase E progression task: refreshed `CURRENT_PHASE.md` and staged explicit Phase E readiness blocker list (Sentry DSNs, real-browser prod sanity pass, frontend chunk-size hardening).
      - Mirrored staged Phase E blockers into `PROGRAM_STATE.md` with explicit owner/status/verification entries for backend/frontend Sentry activation, real-browser prod sanity pass, and frontend code-splitting hardening.
      - Re-validated architecture/static gates in same run: backend AI/action queue pytest subset PASS (15 passed, 2 skipped), frontend SSE parser unit tests PASS (10 passed), frontend production build PASS (with chunk-size advisory), frontend lint PASS (`eslint . --max-warnings 0`).
      - Reconciled continuity metadata drift by correcting this queue's active validation branch from stale `main` to `fix/login-api-base-routing` (base remains `origin/main`), aligning Phase D docs with live git state.
      - Re-ran architecture/static checks in same run after doc reconciliation: backend AI/action queue pytest subset PASS (15 passed, 2 skipped), frontend SSE parser unit tests PASS (10 passed), frontend lint PASS (`eslint . --max-warnings 0`), frontend build PASS.

## Next (Queued)
1. Phase D hardening pass (stale-doc cleanup)
   - Immediate next executable: audit remaining continuity docs for stale active-branch references and normalize to `fix/login-api-base-routing` (or explicit historical `main` where intentional).
2. Phase E production-readiness progression review and continuity update
   - Immediate next executable: draft a single handoff template in `docs/handoffs/` for Sentry activation and real-browser sanity evidence capture to reduce operator variance.

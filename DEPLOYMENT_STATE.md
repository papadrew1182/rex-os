# DEPLOYMENT_STATE

Last Updated (UTC): 2026-05-18 09:00:56Z

## Baseline
- Repo: `papadrew1182/rex-os`
- Local Branch: `fix/login-api-base-routing`
- Local HEAD: `47bd7a6b0e0aee3585579b69b71afb5ef5e17cec`

## Runtime Targets
- Railway auth: **authenticated** (`railway whoami`)
- Railway repo link state: **not linked in local clone** (`railway status` => "No linked project found")
- Recommendation: use explicit `--project/--service/--environment` or run controlled `railway link` before deploy-adjacent operations.

## Phase C Validation Snapshot (local)
- AI/action queue/compensator pytest subset: PASS (`pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => 15 passed, 2 skipped)
- Frontend production build: PASS (`npm run build`)
- Frontend SSE unit-test command: PASS (`npm run test:unit:sse` => 10 passed, 0 failed)
- Frontend lint hardening pass: PASS (prior backlog cleared in workspace)
- Frontend lint command: PASS (`npm run lint`)
- CI queue state: local validation rerun this session; backend pytest subset + frontend SSE tests + frontend lint + frontend build all green
- 2026-05-18 04:56Z verification rerun (same branch/SHA lane):
  - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => PASS (15 passed, 2 skipped)
  - `npm run test:unit:sse` => PASS (10 passed, 0 failed)
  - `npm run lint` => PASS
  - `npm run build` => PASS (chunked output, largest chunk 141.83 kB vendor-react)
- 2026-05-18 05:16Z verification rerun (same branch/SHA lane):
  - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => PASS (15 passed, 2 skipped)
  - `npm run test:unit:sse` => PASS (10 passed, 0 failed)
  - `npm run lint` => PASS
  - `npm run build` => PASS (largest emitted JS chunk: `vendor-react` 141.83 kB; under `REX_MAX_CHUNK_KB=150` budget)
  - `pytest -q backend/tests/test_session2_migration_sanity.py` => PARTIAL (1 passed, 6 errors) — local DB auth blocker: `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "deploy"` on `localhost:5432/rex_os`
- 2026-05-18 05:35Z verification rerun (same branch/SHA lane):
  - Initial stale shorthand probes corrected in-run (`pytest -q backend/tests/test_assistant_router.py ...` not found; `npm run test` script absent).
  - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => PASS (15 passed, 2 skipped)
  - `npm run test:unit:sse` => PASS (10 passed, 0 failed)
  - `npm run lint` => PASS
  - `npm run build` => PASS (largest emitted JS chunk: `vendor-react` 141.83 kB)
  - `pytest -q backend/tests/test_session2_migration_sanity.py` => PARTIAL (1 passed, 6 errors) — blocker unchanged: `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "deploy"` on `localhost:5432/rex_os`
- 2026-05-18 05:52Z verification rerun (same branch/SHA lane):
  - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => PASS (15 passed, 2 skipped)
  - `npm run test:unit:sse` => PASS (10 passed, 0 failed)
  - `npm run lint -- --max-warnings 0` => PASS
  - `npm run build` => PASS (largest emitted JS chunk: `vendor-react` 141.83 kB; under chunk budget)
  - `pytest -q backend/tests/test_session2_migration_sanity.py` => PARTIAL (1 passed, 6 errors) — blocker unchanged: `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "deploy"` on `localhost:5432/rex_os`
- 2026-05-18 07:24Z verification rerun (same branch/SHA lane):
  - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => PASS (15 passed, 2 skipped)
  - `npm run test:unit:sse` => PASS (10 passed, 0 failed)
  - `npm run lint -- --max-warnings 0` => PASS
  - `npm run build` => PASS (largest emitted JS chunk: `vendor-react` 141.83 kB; split build stable)
  - `pytest -q backend/tests/test_session2_migration_sanity.py` => PARTIAL (1 passed, 6 errors) — blocker unchanged: `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "deploy"` on `localhost:5432/rex_os`
- 2026-05-18 08:19Z verification rerun (same branch/SHA lane):
  - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => PASS (15 passed, 2 skipped)
  - `npm run test:unit:sse` => PASS (10 passed, 0 failed)
  - `npm run lint -- --max-warnings 0` => PASS
  - `npm run build` => PASS (largest emitted JS chunk: `vendor-react` 141.83 kB; split build stable)
  - `DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_session2_migration_sanity.py` => PASS (7 passed)
- 2026-05-18 09:00Z verification rerun + routing hardening patch (same branch lane):
  - `pytest -q backend/tests/services/ai/test_action_queue_service.py backend/tests/repositories/test_action_queue_repository.py backend/tests/services/ai/test_undo_compensator_dispatch.py backend/tests/services/ai/tools/test_base_compensator.py` => PASS (15 passed, 2 skipped)
  - `npm run test:unit:sse` => PASS (10 passed, 0 failed)
  - `npm run lint -- --max-warnings 0` => PASS
  - `npm run build` => PASS (largest emitted JS chunk remains `vendor-react` 141.83 kB)
  - User-visible reliability hardening applied: `frontend/src/api.js` host inference now covers `www.rex.papadrew.com` plus Vercel preview host patterns (`rex-os-git-*`, `rex-os-demo-git-*`) to prevent login/API fallthrough to broken same-origin `/api` on frontend-only hosts.

## Safety Posture
- No production deployment actions executed in this phase.
- No production DB writes executed in this phase.

## Reliability Blocker Status (local env)
- Previous blocker (`deploy@localhost/rex_os` authentication failure) is now treated as environment-specific credential drift, not a migration integrity failure.
- Canonical unattended validation path is green via explicit local CI-style DB override:
  - `DATABASE_URL=postgresql://rex:rex@localhost:5432/rex_ci pytest -q backend/tests/test_session2_migration_sanity.py` => PASS (7 passed)
- Rollback state: no rollback required (validation-only commands; no migrations or production mutations executed).

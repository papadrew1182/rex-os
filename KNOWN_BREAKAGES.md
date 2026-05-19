# KNOWN_BREAKAGES

Last Updated (UTC): 19/05/2026 17:08:39 UTC

## Open Breakages / Environment Gaps
1. Railway project context is not linked in this working copy.
   - Evidence: `railway status` => "No linked project found".
   - Impact: implicit-context Railway deploy commands remain unsafe.
   - Mitigation: use explicit selectors or controlled `railway link`.

2. Vercel CLI unavailable in execution environment.
   - Evidence: `vercel: command not found`.
   - Impact: cannot directly verify Vercel runtime/parity from this host via CLI.
   - Mitigation: use GitHub/Vercel web integrations or install CLI in a controlled step.

3. Playwright phase6 action-card e2e is still environment-gated.
   - Evidence: local run requires live backend + assistant path and currently times out on assistant composer selection.
   - Current state: test remains `test.skip` to avoid false-negative CI breakage.
   - Mitigation: wire deterministic assistant test fixture/mocks before unskip.

4. Frontend lint parity is baseline-clean on this branch.
   - Evidence: `npm run lint` PASS (`eslint . --max-warnings 0`) on `fix/login-api-base-routing`.
   - Impact: lint can now be used as a strict gate for this branch's frontend surface.
   - Follow-up: preserve this as a no-regression invariant during Phase D/E progression.

5. Default local DB credential path remains invalid when `DATABASE_URL` is not overridden.
   - Evidence (19/05/2026 17:07:51 UTC): control-path auth/session probe failed (`pytest -q backend/tests/test_verification_flows.py` => 8 failed, 1 passed) with `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "deploy"` against localhost:5432/rex_os.
   - Evidence (19/05/2026 17:07:51 UTC): control-path migration sanity failed (`pytest -q backend/tests/test_session2_migration_sanity.py` => 1 passed, 6 errors) with same `InvalidPasswordError`.
   - Impact: default local env remains non-parity for blocker verification.
   - Mitigation: continue canonical production-like evidence path via explicit override (`DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci`), and separately remediate local `deploy@localhost/rex_os` credentials for true default-path parity.

## Resolved in this phase
- Fresh-db replay gate re-verified PASS with survivability subsets.
- Dashboard demo seed file created and idempotency validated locally.
- Action queue + compensator validation subset re-run PASS (15 passed, 2 skipped).
- Frontend SSE parser unit test is now script-wired and validated (`npm run test:unit:sse` PASS, 10 passed).
- Frontend lint gate now passes clean (`npm run lint` PASS), closing prior lint backlog blocker for this branch.

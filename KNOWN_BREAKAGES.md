# KNOWN_BREAKAGES

Last Updated (UTC): 2026-05-18 03:44:00Z

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

5. Local DB credentials for Phase C backend validation are currently invalid.
   - Evidence: targeted pytest subset failed with `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "deploy"` against localhost:5432.
   - Impact: cannot re-validate action queue/compensator/advisory-lock paths in this environment until DB auth is restored.
   - Mitigation: set correct `DATABASE_URL`/`REX_DB_*` secrets for local test runner or provision matching local Postgres user/password.

## Resolved in this phase
- Fresh-db replay gate re-verified PASS with survivability subsets.
- Dashboard demo seed file created and idempotency validated locally.
- Action queue + compensator validation subset re-run PASS (15 passed, 2 skipped).
- Frontend SSE parser unit test is now script-wired and validated (`npm run test:unit:sse` PASS, 10 passed).
- Frontend lint gate now passes clean (`npm run lint` PASS), closing prior lint backlog blocker for this branch.

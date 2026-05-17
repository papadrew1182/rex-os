# KNOWN_BREAKAGES

Last Updated (UTC): 2026-05-17 23:19:26Z

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

4. Frontend lint parity is not baseline-clean.
   - Evidence: `npm run lint` still fails on baseline backlog (currently 17 errors + 9 warnings).
   - Impact: lint cannot yet serve as a strict CI gate for this branch without scoping/normalization.
   - Mitigation: add explicit ESLint baseline config and ignore generated artifacts; then burn down violations incrementally by domain.
   - Progress this run: reduced findings from 31 (22 errors + 9 warnings) → 26 (17 errors + 9 warnings) by removing unused imports in user-visible pages.

5. Local DB credentials for Phase C backend validation are currently invalid.
   - Evidence: targeted pytest subset failed with `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "deploy"` against localhost:5432.
   - Impact: cannot re-validate action queue/compensator/advisory-lock paths in this environment until DB auth is restored.
   - Mitigation: set correct `DATABASE_URL`/`REX_DB_*` secrets for local test runner or provision matching local Postgres user/password.

## Resolved in this phase
- Fresh-db replay gate re-verified PASS with survivability subsets.
- Dashboard demo seed file created and idempotency validated locally.
- Action queue + compensator validation subset re-run PASS (15 passed, 2 skipped).
- Frontend SSE parser unit test is now script-wired and validated (`npm run test:unit:sse` PASS, 10 passed).

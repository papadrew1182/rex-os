# KNOWN_BREAKAGES

Last Updated (UTC): 2026-05-17 19:32:30Z

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

4. Frontend SSE parser unit test is present but not runnable via npm scripts.
   - Evidence: `npm test -- --run frontend/src/lib/__tests__/sseParser.test.js` returns "Missing script: test".
   - Impact: SSE parser regression checks are not wired into the frontend validation path.
   - Mitigation: add a supported frontend unit-test runner script (e.g., Vitest) and bind `frontend/src/lib/__tests__/sseParser.test.js`.

## Resolved in this phase
- Fresh-db replay gate re-verified PASS with survivability subsets.
- Dashboard demo seed file created and idempotency validated locally.
- Action queue + compensator validation subset re-run PASS (15 passed, 2 skipped).

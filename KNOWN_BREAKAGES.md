# KNOWN_BREAKAGES

Last Updated (UTC): 2026-05-16 15:12:35Z

## Open Breakages / Environment Gaps
1. Local backend integration tests requiring DB currently fail in this runner due to missing local PostgreSQL / DATABASE_URL wiring.
   - Evidence:
     - `pytest -q tests/test_sprint_i_infra.py` => 3 failed / 14 passed
     - Failures include missing `DATABASE_URL` and inability to connect `localhost:5432`.
   - Impact: blocks full local-runtime survivability proof in this environment.
   - Mitigation: provide local postgres (or containerized test DB) + set DATABASE_URL before full suite.

2. Railway project context is not linked in repo working copy.
   - Evidence: `railway status` => "No linked project found".
   - Impact: commands needing implicit project context are unsafe/ambiguous.
   - Mitigation: explicit link/selectors and capture in handoff before deploy-adjacent work.

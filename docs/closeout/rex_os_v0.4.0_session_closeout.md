# rex-os final closeout handoff

Date: 2026-04-15

## Executive summary

rex-os is back on a single mainline.

- Session 1 (AI Spine) is merged.
- Session 2 (Canonical Connectors / RBAC / identity-context) is merged.
- The post-merge cleanup PR is merged.
- Production migrations were reported as successfully auto-applied.
- Release tag `v0.4.0-session2` was created and pushed.
- Finished Session 2 cleanup branches were deleted.

At this point, rex-os should be treated as normal production code again, not as a parallel-session repo.

## Final known code state

Main/prod tip:
- `9d47fef3bcb780e5ae8af861c0b95b652397d03f`

Merged milestones:
- PR #2: Session 2 canonical connectors / RBAC / identity-context
- PR #3: post-merge cleanup / package consolidation / migration-comment cleanup

Package/layout state:
- active backend package layout is consolidated under `backend/app/`
- old parallel package roots under `backend/{routers,services,repositories,schemas,data}/` are gone
- dead `backend/models/` placeholder removed

Migration ladder on main:
- `001..005` historical
- Session 1: `006`, `007`, `008`
- Session 2: `009..022`

## What shipped

### Session 1
- assistant backbone
- `/api/assistant/*`
- chat / catalog / prompt repositories
- quick-action catalog
- Session 1 migrations `006/007/008`

### Session 2
- RBAC and identity foundation
- connector registry and account health model
- `connector_procore` and `connector_exxir` stage schemas
- `rex.source_links` as a view over `rex.connector_mappings`
- canonical additions and bridge views
- 7 top-level `rex.v_*` read-model views
- endpoints:
  - `/api/me`
  - `/api/me/permissions`
  - `/api/context/current`
  - `/api/connectors`
  - `/api/connectors/health`

### Post-merge cleanup
- Session 2 migration header comments aligned with `009..022`
- dead `backend/models/.gitkeep` removed
- Session 1 packages consolidated into `backend/app/`
- stale docs/path references updated

## Locked invariants to preserve

These should be treated as architectural guardrails now:

- Session 1 owns migration slots `006`, `007`, `008`
- Session 2 owns migration slots `009..022`
- `rex.source_links` is a **view** over `rex.connector_mappings`
- do not create a second physical `source_links` table
- do not replace the metadata-based uniqueness test with a row-insert collision test
- `v_project_sources` lives in `015_sync_runs_and_source_links.sql`
- `015_sync_runs_and_source_links.sql` must remain after `011_project_assignment_bridges.sql`
- canonical product data lives in `rex`
- connector-native staged/source data lives in `connector_procore` and `connector_exxir`
- downstream product surfaces should consume `rex.v_*`, not connector stage tables directly

## Production / deployment state

From the latest operator note:
- Railway auto-migrate reported success with all migrations applied and zero failures
- release tag `v0.4.0-session2` was pushed
- `feat/canonical-connectors` and `fix/rex-prod-cleanup` were deleted locally and remotely
- unauthenticated production smoke showed:
  - `/api/health` -> 200
  - `/api/ready` -> 200
  - Session 2 endpoints -> 401 (routes mounted, auth enforced)

## Remaining validation gap

The only meaningful gap left is authenticated production smoke with a real admin token.

Recommended authenticated checks:
- `GET /api/me`
- `GET /api/me/permissions`
- `GET /api/context/current`
- `GET /api/connectors`
- `GET /api/connectors/health`

What to verify:
- status 200
- response shapes match the intended contracts
- role / permission payloads are populated correctly
- context resolution is correct
- connector health/list payloads are sensible

## Lessons learned

1. Parallel migration-slot ownership must be explicit and enforced.
   - The Session 1 / Session 2 collision at slot `008` was the load-bearing integration bug.
   - Session 2 absorbed the safe fix by moving from `008..021` to `009..022`.

2. Fresh-schema validation catches issues long-lived dev DBs hide.
   - The `v_project_sources` forward-reference bug only surfaced on pristine apply.

3. Git mergeability is not enough.
   - Some conflicts were semantic (`MIGRATION_ORDER`) rather than textual.

4. Package-path consistency matters.
   - Consolidating Session 1 into `backend/app/` removed a lasting source of confusion.

5. A single canonical closeout doc is better than relying on session transcripts.
   - Several intermediate handoffs became partially outdated as PRs merged and production moved.

## Recommended operating mode from here

- Stop using “session” branches as the normal way of working in rex-os.
- Work from `main` or short-lived bugfix branches off `main`.
- One active branch, one concrete issue at a time.
- Treat the older session prompts as historical context, not active instructions.

## Suggested next actions

1. Run the authenticated production smoke with an admin bearer token.
2. Reattach detached/local worktrees to current `main` or delete stale ones.
3. Start all future rex-os work from fresh branches off current `main`.
4. Only reopen architectural questions if a real prod bug or new requirement forces them.

## Suggested permanent repo doc name

If you want this committed into the repo, a good permanent path is:

`docs/closeout/rex_os_v0.4.0_session_closeout.md`


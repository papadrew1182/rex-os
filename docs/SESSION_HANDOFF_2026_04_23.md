# Session Handoff — 2026-04-23

Pick this up immediately in the next session.

## Where we are

**Phase 6a (Commands, Actions & Approvals — core framework):** SHIPPED 2026-04-21 (PR #16, commit `0578a0d`).

**Phase 6b Wave 1 (internal auto-pass tools + real undo compensators):** SHIPPED 2026-04-22 (PR #17, merge commit `d487660`).

## What's live as of Phase 6b Wave 1

**8 auto-pass internal tools with real 60-second undo** (compensators actually reverse the DB mutation):

| slug | table | operation | compensator |
|---|---|---|---|
| `create_task` | `rex.tasks` | INSERT | DELETE by id |
| `update_task_status` | `rex.tasks` | UPDATE status | UPDATE back to prior status |
| `create_note` | `rex.notes` | INSERT | DELETE by id |
| `save_meeting_packet` | `rex.meetings` | UPDATE packet_url | UPDATE back to prior |
| `save_draft` | `rex.correspondence` | INSERT (type=email, status=draft) | DELETE by id |
| `create_alert` | `rex.notifications` | INSERT | DELETE by id |
| `delete_task` | `rex.tasks` | DELETE after full-row snapshot | re-INSERT from snapshot |
| `delete_note` | `rex.notes` | DELETE after full-row snapshot | re-INSERT from snapshot |

**1 approval-required external tool** (no compensator — "Send correction" is a future Wave 3 feature):

| slug | flow |
|---|---|
| `answer_rfi` | approval → Procore API call FIRST → rex.rfis UPDATE on success |

**Key infrastructure added this session:**
- `ActionSpec.compensator` optional field in `backend/app/services/ai/tools/base.py`
- `ActionContext.original_result` optional field (compensators read it for payload access)
- `ActionQueueRepository.insert()` takes `correction_of_id` + `committed_at_now` kwargs
- `ActionQueueService.undo()` now inserts a synthetic `<slug>__undo` correction row, invokes the compensator inline, and flips the original to `undone` only on compensator success
- `__undo` rows are filtered out of `/api/actions/pending` (not pending from a user's perspective)
- End-to-end regression test exercising the real `/api/actions/{id}/undo` HTTP endpoint

## Deploy state

- **Prod backend (`rex-os-api-production.up.railway.app`):** <FILL IN AT DEPLOY> Railway auto-deploys from `main`. `/api/ready` green.
- **Demo backend (`rex-os-demo.up.railway.app`):** <FILL IN AT DEPLOY> demo env requires manual `railway redeploy` if not auto-wired. `/api/ready` green.
- **Frontend (Vercel `rex-os.vercel.app`):** still SPA-only; no approval card UI yet.

## Known follow-ups (not blocking)

1. **Frontend approval card UI.** Backend emits `action_proposed`/`action_auto_committed`/`action_failed` SSE events; the mobile-first conversation-inline card is not built. The undo toast also needs UI wiring (HTTP `/api/actions/{id}/undo` response is the source of truth — there is no separate SSE event for undo).
2. **Live LLM tool_use smoke.** Backend dispatcher intercepts `tool_use` blocks; needs one real assistant conversation that triggers any of the 8 auto-pass tools or `answer_rfi` in prod/demo to exercise the full path end-to-end.
3. **Procore OAuth creds on demo Railway.** `answer_rfi` still needs `PROCORE_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/COMPANY_ID`. The other 8 tools work without Procore.
4. **Correspondence numbering.** `save_draft` uses `DRAFT-<uuid-hex-8>` instead of the per-project MAX+1 sequence Phase 6a's `create_task` uses. Fine for drafts (not sent externally) but unifies badly if the same code later handles sent emails. Revisit when `send_draft` ships.
5. **Global "all pending" VP view.** Spec §4 calls for it; `/api/actions/pending` is still user-scoped only.

## Phase 6b Wave 2 (next scope)

Per the 2026-04-22 brainstorm (§B split), Wave 2 holds:

- **Financial approval-required tools:** `pay_application`, `lien_waiver`, `create_change_event`, `create_pco`. All 4 tables exist; blast_radius classifier fires `financial_dollar_amount>0 → requires_approval`. Procore writeback ordering per parent spec §5 — **submittals first**, then financial. Don't ship financial writeback until submittal writeback has validated a month in the wild.
- **Punch transitions:** `punch_close`, `punch_reopen`. `rex.punch_items.status` UPDATE. Brainstorm pass needed on whether these should fire notifications to subs.
- **`create_decision`** — needs new `rex.decisions` migration (no existing table). Brainstorm needed on schema shape.

## Next natural work

Andrew's consistent preference: ship what's wired, investigate follow-ups in parallel.

**Top 3 candidates in priority order:**

1. **Frontend approval card UI + undo toast.** Unlocks real daily usage of the 9 tools already shipped. Separate frontend plan required. This is the highest-leverage next step.
2. **Phase 6b Wave 2 (financial + punch + create_decision).** ~7 more tools on the same scaffolding. Needs one brainstorm pass (punch notification semantics + create_decision schema).
3. **Phase 4 resource rollout Wave 2** (submittals, daily_logs, tasks, change_events connector syncs). Unblocks the 4 `adapter_pending` Wave 1 quick actions AND the Procore writeback sequence for Wave 2 financial tools.

Candidate 1 and 3 are mostly independent and can run in parallel. Candidate 2 is blocked on candidate 3 for financial writeback (but not for the local-only punch + create_decision parts).

## PRs merged this session

- **#17** — feat: Phase 6b Wave 1 — 5 new tools + real undo compensators (merge commit `d487660`)

## Plan + spec documents

- Spec: `docs/superpowers/specs/2026-04-22-phase6b-wave1-design.md`
- Plan: `docs/superpowers/plans/2026-04-22-phase6b-wave1.md`

## Test suite

Full backend: **957 passed, 1 skipped** (Phase 6a baseline was 934; Wave 1 added 23 new tests: 3 compensator roundtrips on Phase 6a tools, 3-4 per new tool × 5 tools, 4 on undo dispatch, 2 on the repo extension, 4 on registry, 1 end-to-end route test, 1 base spec test).

## Critical learnings banked this session

1. **asyncpg ISO-string → timestamptz binding.** Direct `$N::timestamptz` fails with "expected datetime instance, got str". The fix is `$N::text::timestamptz` — route through Postgres's text parser instead of asyncpg's type-binding checks. Used in `delete_task` and `delete_note` compensators when re-INSERTing snapshot timestamps.
2. **`rex.user_accounts.person_id` is NOT NULL.** Test fixtures that seed user_accounts MUST first insert a `rex.people` row and pass that id as `person_id`. The "copy an existing auth fixture pattern" approach caught this late in T5 and propagated the fix to T6-T9 upfront.
3. **`correspondence_number` uniqueness per project.** The plan's initial MAX+1 SUBSTRING regex was fragile. `save_draft` now uses `DRAFT-<uuid-hex-8>` which is race-free and doesn't require regex parsing of the numeric suffix.
4. **`__undo` correction rows must be filtered from pending views.** Spec §6 caught this; implementation uses `AND tool_slug NOT LIKE '%\_\_undo' ESCAPE '\'` with a raw Python string so backslashes reach Postgres literally.
5. **Pre-existing undo-related tests break when `undo()` signature changes.** T3's undo() rewrite required passing `conn=` AND configuring the test spec with a compensator (otherwise the new "not undoable" semantics kick in). The fix preserved the original test's intent — just passed the new required kwarg and added a noop compensator.

## Operator checklist (you, the next day)

- [ ] Verify prod + demo Railway logs show no errors on auto-deploy (`railway logs --deployment` in both envs, two passes ~1 minute apart).
- [ ] Smoke: `curl` `/api/actions/pending` authed on demo → 200 with empty or existing items.
- [ ] Smoke: a real chat message in demo that triggers `create_task` → verify auto-commit toast + undo within 60s actually removes the task.
- [ ] (Optional) Set `PROCORE_*` env vars on demo Railway if not already there, for `answer_rfi` live testing.

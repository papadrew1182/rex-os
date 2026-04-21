# Session Handoff — 2026-04-24

Pick this up immediately in the next session.

## Where we are

**Phase 6a (backend):** SHIPPED 2026-04-21 — framework + 4 core tools (PR #16 `0578a0d`).
**Phase 6b Wave 1 (backend):** SHIPPED 2026-04-22 — 5 more tools + real undo compensators for all 8 auto-pass tools (PR #17 `d487660`).
**Phase 6 Frontend Wave 1:** SHIPPED 2026-04-22 — inline approval/commit/failure cards + 60s undo + retry (PR #18, merge commit `4887990`).

## What's live as of Phase 6 Frontend Wave 1

The 9 shipped tools are now **fully usable by a human in a browser**. End-to-end flow:

1. Andrew types a message in the assistant sidebar (e.g., "create a task to check the duct conflict").
2. Backend classifies via blast-radius; either auto-commits or enqueues for approval.
3. Frontend renders an inline `ActionCard` with:
   - **Amber accent bar** if approval required (shows effects + quoted trigger; Discard / Approve buttons)
   - **Green accent bar** if auto-committed (60s countdown; Undo button)
   - **Red accent bar** if failed (shows the real error excerpt; Retry / Dismiss buttons)
   - **Grey accent bar with strikethrough** if undone (history only)
4. Click Undo within 60s → backend compensator reverses the DB mutation, card flips grey with strikethrough.
5. Click Approve on approval card → backend fires the handler; card flips green (or red on handler error).
6. Click Retry on failed card → re-runs the handler (same `/api/actions/{id}/approve` endpoint).

Mobile: same inline card, buttons reflow full-width below 560px breakpoint. No modal, no sheet, no separate inbox.

## Frontend changes this session

| File | Purpose |
|---|---|
| `frontend/src/assistant/actionSummary.js` | Per-tool copy (`create_task` → "Create task" + title) — covers all 9 tools |
| `frontend/src/assistant/ActionCard.jsx` | Unified accent-bar card component, countdown timer |
| `frontend/src/assistant/actionCardStyles.css` | State-modifier CSS classes |
| `frontend/src/lib/actionsApi.js` | fetch wrappers for `/api/actions/{id}/approve|discard|undo` |
| `frontend/src/assistant/useAssistantState.js` | +4 reducer action types, +4 cases |
| `frontend/src/assistant/useAssistantClient.js` | SSE switch extended with action_proposed / action_auto_committed / action_failed |
| `frontend/src/assistant/ChatThread.jsx` | Renders ActionCard; wires handlers for all 5 button actions |
| `frontend/tests/e2e/phase6-action-card.spec.js` | Playwright smoke (skipped — enable when running against real dev env) |

## Backend change this session

One line in `backend/app/services/ai/chat_service.py` — the `action_proposed` SSE frame now carries `tool_args` so the frontend can render the card's secondary line.

## Deploy state

- **Prod backend (`rex-os-api-production.up.railway.app`):** Railway auto-deployed from main, migrations applied=31 failed=0, `/api/ready` 200.
- **Demo backend (`rex-os-demo.up.railway.app`):** Same.
- **Vercel prod (`rex-os.vercel.app`):** Frontend deployed on merge.

Logs on both Railway envs clean; two passes ran ~1 minute apart showed no errors.

## Known follow-ups

1. **Enable Playwright e2e** (`frontend/e2e/phase6-action-card.spec.js`). Currently `test.skip`. Prerequisites: backend on localhost with `ANTHROPIC_API_KEY`, frontend dev server, seeded admin. Remove `.skip` and run `npx playwright test phase6-action-card.spec.js --headed`. Nice to have in CI once dev-env secrets are wired in.
2. **Mobile smoke on Andrew's phone** — render an approval card, verify buttons are tappable, text wraps sensibly, no horizontal overflow.
3. **Real-world LLM smoke in demo** — send a chat message that triggers `create_task`, verify auto-commit toast + actual Undo reverses the rex.tasks row.
4. **Procore OAuth creds on demo Railway** — `answer_rfi` still needs `PROCORE_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/COMPANY_ID` to land in Procore for real.

## Phase 6 Wave 2 queued

Per the 2026-04-22 brainstorm, Wave 2 holds:

- **Financial tools:** `pay_application`, `lien_waiver`, `create_change_event`, `create_pco`. All 4 tables exist; financial dollar amount triggers approval path. Procore writeback sequence per parent spec §5 — submittals first, then financial. Don't ship financial writeback until submittal writeback has validated a month in the wild.
- **Punch transitions:** `punch_close`, `punch_reopen`. `rex.punch_items.status` UPDATE. One brainstorm pass needed on notification semantics (sub receives an email? in-app alert only? silent?).
- **`create_decision`** — needs a new `rex.decisions` migration (no existing table). Brainstorm needed on schema shape.
- **Pending Approvals filter view** — if/when Andrew starts losing track of approval cards in long conversations.
- **Real-undo compensators for approval-required tools** — currently only auto-pass tools have compensators. "Send correction" on `answer_rfi` is a Wave 3 design (compensator that itself goes through approval).

## What's next

**Three candidates in priority order:**

1. **Let the real UI sit for a few days.** Andrew uses it. Real data emerges on (a) whether auto-commit undo is responsive enough, (b) whether inline card density is right, (c) whether the Pending Approvals filter view is actually needed. Wave 2 scope sharpens based on what he hits.
2. **Phase 6b Wave 2** — the remaining ~7 tools on the same scaffolding. Needs one brainstorm pass (punch notification semantics + create_decision schema).
3. **Phase 4 resource rollout Wave 2** — submittals + daily_logs + tasks + change_events connector syncs. Unblocks the 4 remaining `adapter_pending` Wave 1 quick actions AND the Procore writeback sequence for Wave 2 financial tools.

Candidate 1 (wait-and-learn) is probably the highest leverage. Candidates 2 and 3 are mostly independent; 3 blocks the financial parts of 2 but not the local-only parts.

## PRs merged this session

- **#18** — feat: Phase 6 Frontend Wave 1 — approval cards + undo + failure UI (merge commit `4887990`)

## Plan + spec documents

- Spec: `docs/superpowers/specs/2026-04-22-phase6-frontend-wave1-design.md`
- Plan: `docs/superpowers/plans/2026-04-22-phase6-frontend-wave1.md`

## Test suite

- **Backend:** 957 passed, 1 skipped (unchanged vs Phase 6b Wave 1 baseline — T1 extended an existing test, didn't add a new file).
- **Frontend:** 24 reducer tests + 7 action-reducer tests + 15 actionSummary tests = 46 pure-Node tests. All green.
- **Frontend build:** vite build succeeds.

## Critical learnings banked this session

1. **Visual companion skill works well for UI design brainstorming.** Three mockup rounds (card layout, toast placement, mobile variant) collapsed what would've been 20+ back-and-forth terminal messages into ~5 clicks. Worth using again for any UI-heavy brainstorm.
2. **Pure-Node reducer tests > adding a test framework.** The repo's pattern of `node <test-file>` with `node:assert/strict` kept the frontend test setup dead simple. No Vitest / RTL dependency added.
3. **ESLint config is broken on main** — `npm run lint` fails with "ESLint couldn't find a configuration file." Pre-existing. Not blocking anything but worth fixing eventually.
4. **SSE event names use underscores, not dots.** Backend emits `action_auto_committed` (not `action.auto_committed`). Frontend switch matches verbatim. Other events (`conversation.created`, `message.delta`) use dots. Inconsistent but documented by example.
5. **Client-side countdown is sufficient for undo UX.** No SSE needed — the backend's committed_at timestamp + client's system clock + 1s interval is enough. The 60s window is enforced server-side on the undo route; the UI just decides when to hide the button.

## Operator checklist (you, the next day)

- [ ] Railway logs first pass clean on both envs after the Phase 6 FE merge
- [ ] Railway logs second pass clean ~1 minute later
- [ ] Vercel deploy 200 on rex-os.vercel.app
- [ ] Send one real chat message in demo that triggers `create_task`; verify the green card appears with countdown
- [ ] Click Undo within 60s; verify the rex.tasks row is actually gone + card flips grey with strikethrough
- [ ] (Optional) Same loop on Andrew's phone to verify mobile reflow

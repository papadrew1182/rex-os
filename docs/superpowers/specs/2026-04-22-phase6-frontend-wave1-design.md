# Phase 6 Frontend Wave 1 — Approval Cards, Undo Toasts & Failed-Action UI

**Status:** approved 2026-04-22. Ready for implementation plan.
**Author:** Claude + Andrew Roberts.
**Parent spec:** `docs/superpowers/specs/2026-04-21-phase6-commands-approvals-design.md` (Phase 6 overall).

## Goal

Make the 9 Phase 6a+6b backend tools actually usable by rendering the `action_proposed`, `action_auto_committed`, and `action_failed` SSE events inline in the chat conversation, with a 60-second Undo flow that hits `/api/actions/{id}/undo`. One unified accent-bar card design carries all four possible states (approval / committed-undoable / failed / undone). No modal, no sheet, no separate inbox — cards live inline in the conversation stream per parent-spec §8.

**Exit criterion:** Andrew types "create a task to check the duct conflict at Bishop Modern" on his phone, sees a green inline card with a 60s Undo button, and either watches it fade to grey history or taps Undo and sees the card flip to strikethrough "UNDONE" — all without leaving the conversation.

## Pre-locked decisions (from 2026-04-22 brainstorm)

1. **Scope** = full set of Phase 6 events. All 3 backend SSE event types render in Wave 1, plus the HTTP-response-driven `undone` state from the `/api/actions/{id}/undo` endpoint. No deferral of `action_failed` to Wave 2.
2. **Card visual** = accent-bar design (left colored border, state label, summary + secondary + meta, right-aligned buttons). Unified shape across all 4 states, color signals state.
3. **Auto-commit toast** = inline card (same shape, green border), NOT a corner toast or a floating pill. Maximum consistency with approval card.
4. **Mobile** = the same inline card, reflowed. Buttons stack full-width on narrow screens. No full-screen sheet, no bottom sheet. "Pending Approvals" filter view catches missed cards in a future iteration if needed.
5. **Pending Approvals filter view** = DEFERRED to Wave 2. Parent spec §8 explicitly warns against preempting a separate inbox UI. Let Andrew hit the pain point first, then build.
6. **Failure render + retry** = red accent-bar card with real error excerpt. Retry button re-runs the same handler (re-POST to `/api/actions/{id}/approve` for approval-required, same semantics as first approval). Dismiss marks the action resolved in local UI state (backend keeps the row — audit log).

## Frontend stack (confirmed by discovery)

- React 18 + Vite, JSX only (no TypeScript in this repo)
- Custom CSS design system at `frontend/src/rex-theme.css` — `.rex-card`, `.rex-btn-*`, `.rex-badge-*`, `.rex-drawer`, typography primitives
- State: React Context + reducer in `frontend/src/assistant/AppContext.jsx`
- SSE plumbing: `frontend/src/lib/sse.js::openAssistantStream(payload, handlers)`
- SSE event routing: switch statement in `frontend/src/assistant/useAssistantClient.js` lines 148-201 — currently handles `conversation.created`, `message.started`, `message.delta`, `message.completed`, `followups.generated`, `action.suggestions`, `error`. Zero action handling. Ready to extend.
- Message rendering: `frontend/src/assistant/ChatThread.jsx` iterates `activeConversation.messages` and renders per `message.type`.

No existing toast system — we don't need one; inline cards replace it.

## Architecture

### New files

- `frontend/src/assistant/ActionCard.jsx` — unified accent-bar card component. Props: `{ action, onApprove, onDiscard, onUndo, onRetry, onDismiss }`. Internal state: `countdown` (for the 60s timer on auto-committed actions).
- `frontend/src/assistant/actionCardStyles.css` — state-modifier classes (`.rex-action-card--approval|committed|failed|undone|undoable`) layered on top of existing theme.
- `frontend/src/lib/actionsApi.js` — thin fetch wrapper for `POST /api/actions/{id}/approve|discard|undo`. Retry uses the same `/approve` endpoint.

### Modified files

- `frontend/src/assistant/useAssistantClient.js` — extend SSE switch with 3 new cases (`action_proposed`, `action_auto_committed`, `action_failed`). Each dispatches a reducer action appending an entry of `type === 'action'` to the message timeline.
- `frontend/src/assistant/ChatThread.jsx` — in the message-list map, render `<ActionCard>` for entries with `type === 'action'`.
- `frontend/src/assistant/AppContext.jsx` (or wherever the message reducer lives) — new reducer action types:
  - `ACTION_PROPOSED` — append an `action` entry with `state='approval'`
  - `ACTION_AUTO_COMMITTED` — append with `state='committed'`, record `committed_at`
  - `ACTION_FAILED` — append (or mutate) with `state='failed'`, record `error_excerpt`
  - `ACTION_STATE_UPDATED` — mutate an existing entry (for approve/undo/retry local flips after HTTP responses)

### Message timeline entry shape

```js
{
  type: 'action',
  action_id: string,             // uuid
  slug: string,                   // 'create_task' | 'answer_rfi' | ...
  state: 'approval' | 'committed' | 'failed' | 'undone',
  summary: string,                // plain-English 1-liner from backend
  secondary: string | null,       // e.g. the answer text for answer_rfi
  effects: string[],              // blast_radius.reasons()
  trigger: string,                // the user message that caused this
  committed_at: string | null,    // ISO, for countdown calc
  undone_at: string | null,       // ISO
  error_excerpt: string | null,   // for failed state
  // local UI state (not from SSE)
  busy: boolean,                   // request in-flight
  buttons_disabled: boolean,       // for retry lockout
}
```

Backend-provided fields (`summary`, `secondary`, `effects`, `trigger`) arrive in the SSE event payload — Wave 1 backend change requirement: `chat_service.py` already emits `action_proposed` / `action_auto_committed` / `action_failed` events, but the payload shape needs verification. If the payloads don't include these fields today, Wave 1 adds them (minimal backend change — straight dict packing from the `ActionSpec` + `tool_args`).

**Action: plan must verify what the current SSE payloads contain and fill gaps as its first task.**

## Card visual spec

All four states share the same box shape. Color + label + buttons change per state.

### Layout (fixed across states)

```
┌─4px accent bar───────────────────────────────┐
│ STATE LABEL (uppercase, state color)         │
│ Primary line — summary                       │
│ Secondary — args preview (if present)        │
│                                              │
│ ⓘ meta — effects + quoted trigger (muted)    │
│                                              │
│                       [button] [button]      │
└──────────────────────────────────────────────┘
```

Typography:
- STATE LABEL: 10px uppercase, 0.04em letter-spacing, state-color
- Primary: 13px, normal weight, `#111`
- Secondary: 12px, `#555`, max 2 lines with ellipsis
- Meta: 11px, `#4b5563`, 2px left border in `#e5e7eb` with 10px padding-left
- Buttons: 12px, right-aligned, 6px gap, 6-12px padding, 5px radius

### Per-state details

| State | Border color | Label | Buttons |
|---|---|---|---|
| `approval` | `#f59e0b` (amber) | `⚠ APPROVAL` | `Discard` (outline) · `Approve` (primary blue) |
| `committed` + within 60s | `#059669` (green) | `✓ COMMITTED · {Ns}` | `Undo` (right-aligned, outline) |
| `committed` + ≥60s | `#d1d5db` (grey) | `✓ COMMITTED · {time}` | — |
| `failed` | `#dc2626` (red) | `✗ FAILED` (error excerpt replaces meta) | `Retry` (primary) · `Dismiss` (outline) |
| `undone` | `#d1d5db` (grey) + strikethrough primary | `↩ UNDONE` | — |

### Mobile

Below 560px breakpoint (existing in `rex-theme.css`):
- Card padding drops to 10px 12px
- Button row becomes `flex: 1` each, stacking full-width side-by-side
- Meta line font-size drops to 10px
- No modal, no sheet, no drag handle

## Undo flow

Countdown is client-side only (no SSE):

1. `action_auto_committed` event arrives → reducer adds entry, `committed_at` set to now, state `committed`.
2. `ActionCard` mounts a `setInterval(1000)` computing `Math.max(0, 60 - elapsedSeconds)`.
3. Label renders `✓ COMMITTED · {countdown}s` while > 0.
4. At 0, interval cleared, label becomes `✓ COMMITTED · {localized time}`, Undo button removed.

Click Undo:
1. `busy=true`, button shows spinner.
2. `POST /api/actions/{id}/undo`.
3. Response cases:
   - `200 {status: 'undone', undo_action_id}` → reducer: state='undone', `undone_at=now`. Card flips to grey with strikethrough.
   - `400` (window expired, or race condition) → reducer: treat as if countdown hit 0. Show toast (use existing `Flash` component) saying "Undo window expired."
   - `500` (compensator failed) → reducer: state='failed', record `error_excerpt` from response body. User can Retry to attempt undo again.

No SSE event needed for undone state — the HTTP response is the signal.

## Retry flow

When `action_failed` arrives (or undo itself fails):
1. Card renders in red with `Retry` + `Dismiss` buttons.
2. Click Retry → `busy=true`.
3. Same semantics as initial approval: `POST /api/actions/{id}/approve`.
4. Response:
   - `200 {status: 'committed'}` → reducer: state='committed', committed_at=now. Card flips green with 60s undo (same as fresh auto-commit).
   - `500` → reducer: state stays 'failed', `error_excerpt` updated with new error. Card stays red.

**Note:** Retry on `answer_rfi` specifically re-hits the Procore API. Because the backend handler writes to Procore FIRST and only updates `rex.rfis` on 2xx, the retry is either cleanly successful or cleanly failed — no half-state. Documented for implementer awareness; no special UI handling needed.

Click Dismiss → reducer: card is removed from the timeline (or marked hidden — implementer's choice; the backend row persists for audit).

## State management

Extend the existing `ChatThread` reducer (`frontend/src/assistant/AppContext.jsx` or equivalent). New reducer cases handle the 4 new action types. The message list map in `ChatThread.jsx` gets a new branch:

```jsx
{msg.type === 'action' ? <ActionCard action={msg} {...handlers} /> : /* existing types */}
```

Handlers (onApprove, onDiscard, onUndo, onRetry, onDismiss) live at the `ChatThread` level, import `actionsApi`, and dispatch `ACTION_STATE_UPDATED` on success/failure.

Hot-reload safety: the countdown interval must clean up in `useEffect` teardown. Component unmount during navigation must not leak timers.

## API surface (client side)

`frontend/src/lib/actionsApi.js`:

```js
export async function approveAction(action_id) { /* POST /api/actions/{id}/approve */ }
export async function discardAction(action_id) { /* POST /api/actions/{id}/discard */ }
export async function undoAction(action_id) { /* POST /api/actions/{id}/undo */ }
// Retry is just approveAction called again.
```

All four helpers use the existing auth-header injection pattern (check how `/api/assistant/chat` auth is currently wired and follow the same approach).

## Testing strategy

Frontend test coverage (Vitest + React Testing Library — confirm these are already set up, if not, Wave 1 adds minimal setup):

1. **ActionCard render tests** — one per state (approval, committed-undoable, committed-history, failed, undone). Snapshot + visual state class assertions.
2. **Countdown test** — fake timers, advance 30s, assert label contains `30s`. Advance another 31s, assert button removed.
3. **Undo happy path** — click Undo, mock 200 response, assert state='undone' + strikethrough class applied.
4. **Undo expired path** — click Undo, mock 400, assert Flash toast fires + card stays committed-history.
5. **Undo compensator failure** — click Undo, mock 500, assert card goes red with error excerpt.
6. **Retry flow** — failed card, click Retry, mock 200, assert card flips green with fresh 60s countdown.
7. **SSE routing test** — mock `openAssistantStream`, dispatch `action_proposed` event, assert reducer appends an `action` entry with state='approval'. Same for `action_auto_committed` and `action_failed`.
8. **Mobile reflow test** — render at 375px viewport, assert buttons have `flex: 1`.

Backend has end-to-end coverage of the server-side already (Phase 6a + 6b regression suite). Frontend tests focus on component logic and reducer behavior, not duplicate end-to-end.

## Out of scope for Wave 1

- **Pending Approvals filter view** — per Q5 brainstorm answer, defer to Wave 2 once Andrew has real data on whether he loses track of cards.
- **Diff view for edit actions** — parent spec §2 mentions collapsed diff for edits; no Wave 1 tool is an edit except `update_task_status` (where the diff is trivial — old status → new status, already captured in secondary line). Formal diff component is Wave 2 when richer edits land.
- **"Send correction" flow** — when a committed approval-required external action needs reversal (e.g., oops-approved RFI answer). This is Phase 6c per parent spec §6.
- **Full-screen / bottom-sheet mobile modal** — per Q4, same inline card reflows.
- **Globally-persistent toast system** — not needed; inline cards replace it.
- **Desktop browser notifications / system tray** — not in Phase 6.
- **Bulk approve / reject** — no batch actions in Phase 6.
- **Keyboard shortcuts** (e.g. `⌘+enter` to approve) — Wave 2 polish.

## Success criteria

- Andrew sends a message that triggers `create_task` (auto-pass) in prod; sees a green inline card with a live 60s countdown; click Undo within 60s; card flips to grey strikethrough and the `rex.tasks` row is actually gone.
- Andrew sends a message that triggers `answer_rfi` (approval-required) in demo; sees an amber inline card with effects "Writes to Procore. Notifies GC."; clicks Approve; card flips green with 60s undo; inspects Procore to verify the RFI answer landed.
- If Procore happens to be down during the approval-required test, the card flips red with the real httpx error message; clicking Retry re-hits Procore and the card flips green once Procore is back.
- Full frontend test suite green; zero backend regressions.
- Mobile smoke on Andrew's phone: inline card renders correctly, buttons are tappable, no horizontal overflow.

## Spec self-review

**Placeholder scan:** none. Every state has a concrete visual spec, concrete event routing, concrete reducer action.

**Internal consistency:** card shape is identical across all 4 states; only border color + label + buttons vary. Event-to-state mapping is 1:1 (no ambiguous routing). Timer cleanup specified in both §Undo flow and §State management.

**Scope check:** one new component family (ActionCard + styles + API wrapper), 4 new reducer actions, 3 extended files. Comparable size to Phase 6a/6b backend PRs. Shippable in a single PR.

**Ambiguity:** one — the SSE payload field names from the current `chat_service.py` need verification (it's possible the server already emits exactly these fields, or it emits a subset). Plan must read the actual emit sites as its first discovery step and adjust field names to match reality or add the missing fields to the backend. Flagged in §Architecture.

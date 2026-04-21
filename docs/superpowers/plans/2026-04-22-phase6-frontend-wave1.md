# Phase 6 Frontend Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render Phase 6 action SSE events (`action_proposed`, `action_auto_committed`, `action_failed`) as inline cards in the assistant chat thread, with client-side 60-second undo countdown hitting `/api/actions/{id}/undo`, retry hitting `/api/actions/{id}/approve`, and failure display using the real underlying error excerpt. One unified accent-bar card shape covers all four states (approval / committed-undoable / failed / undone).

**Architecture:** React + Vite + custom CSS (no TypeScript, no Vitest, no RTL in this repo). Extend the existing `ASSISTANT_ACTIONS` enum, reducer, and SSE switch. New `ActionCard.jsx` component. New `actionsApi.js` fetch wrapper. Playwright e2e smoke covers the happy path end-to-end against the real backend.

**Tech Stack:** React 18, Vite, plain JSX, custom CSS design system (`rex-theme.css`), Node-assert for reducer tests (matches existing `useAssistantState.test.js`), Playwright for e2e.

---

## File structure

**New files:**
- `frontend/src/assistant/ActionCard.jsx` — unified accent-bar card for all 4 states
- `frontend/src/assistant/actionCardStyles.css` — state-modifier classes
- `frontend/src/assistant/actionSummary.js` — pure util: `(slug, tool_args, result) → {primary, secondary}`
- `frontend/src/lib/actionsApi.js` — approve/discard/undo HTTP wrappers
- `frontend/src/assistant/__tests__/useAssistantState.actions.test.js` — reducer tests for the 4 new action types
- `frontend/src/assistant/__tests__/actionSummary.test.js` — summary-formatter tests
- `frontend/tests/e2e/phase6-action-card.spec.js` — Playwright smoke (create_task → undo)

**Modified files:**
- `backend/app/services/ai/chat_service.py` — add `tool_args` to the `action_proposed` SSE event payload
- `backend/tests/services/ai/test_chat_service_tool_use.py` — assert `tool_args` is present in the `action_proposed` frame
- `frontend/src/assistant/useAssistantState.js` — add `ASSISTANT_ACTIONS.ACTION_PROPOSED|ACTION_AUTO_COMMITTED|ACTION_FAILED|ACTION_STATE_UPDATED`; extend reducer with 4 new cases; extend message merge logic
- `frontend/src/assistant/useAssistantClient.js` — extend SSE `onEvent` switch (lines 148-201) with 3 new cases; wire handlers to the reducer
- `frontend/src/assistant/ChatThread.jsx` — render `ActionCard` for timeline entries where `type === 'action'`
- `frontend/src/assistant/AssistantSidebar.jsx` (maybe) — only if the action handlers need to be hoisted above `ChatThread` for context-passing; decide during implementation
- `frontend/src/rex-theme.css` — minor additions only if new tokens are needed (expect none — existing `.rex-btn`, `.rex-muted`, breakpoints cover us)

---

## Task 1: Backend SSE payload — add tool_args to action_proposed

**Files:**
- Modify: `backend/app/services/ai/chat_service.py` (the `action_proposed` emit site, around lines 375-385)
- Modify: `backend/tests/services/ai/test_chat_service_tool_use.py` (add assertion for `tool_args`)

**Why:** Currently the `action_proposed` SSE frame has `{type, action_id, tool_slug, status, reasons, blast_radius}`. The frontend needs `tool_args` to render the card's secondary line (e.g., "Answer RFI-42" requires knowing which RFI). `action_auto_committed` already carries `result` which is derivable. `action_failed` carries `error` which is enough. Only `action_proposed` has the gap.

- [ ] **Step 1: Write failing test**

Find the test(s) that assert the `action_proposed` frame shape in `backend/tests/services/ai/test_chat_service_tool_use.py`. Add an assertion:

```python
# In whichever existing test asserts action_proposed frames:
proposed_frames = [e for e in events_out if e.get("type") == "action_proposed"]
assert len(proposed_frames) >= 1
frame = proposed_frames[0]
assert "tool_args" in frame
assert isinstance(frame["tool_args"], dict)
```

If there's no existing test that yields approval-flavored results (i.e., the test uses a tool that always auto-pass), add a new test that exercises the approval path — use a mock `action_queue_service` that returns `DispatchResult(status='pending_approval', ...)` so the `action_proposed` branch fires.

- [ ] **Step 2: Run test to verify failure**

```
cd backend && py -m pytest tests/services/ai/test_chat_service_tool_use.py -v -k "action_proposed or proposed_frame"
```
Expected: FAIL — `tool_args` missing from the frame.

- [ ] **Step 3: Update chat_service.py**

In `backend/app/services/ai/chat_service.py`, find the block that yields `action_proposed` (around lines 375-385):

```python
if result.status == "pending_approval":
    yield sse_event(
        {
            "type": "action_proposed",
            "action_id": str(result.action_id),
            "tool_slug": tool_slug,
            "status": "pending_approval",
            "reasons": list(result.reasons or []),
            "blast_radius": dict(result.blast_radius or {}),
            "tool_args": dict(tool_args or {}),  # NEW
        }
    )
```

- [ ] **Step 4: Run test to verify pass**

```
cd backend && py -m pytest tests/services/ai/test_chat_service_tool_use.py -v
```
Expected: PASS. All pre-existing chat_service tool_use tests still green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/chat_service.py backend/tests/services/ai/test_chat_service_tool_use.py
git commit -m "feat(phase6-fe): include tool_args in action_proposed SSE frame"
```

---

## Task 2: actionSummary util (pure function)

**Files:**
- Create: `frontend/src/assistant/actionSummary.js`
- Create: `frontend/src/assistant/__tests__/actionSummary.test.js`

**Why:** Centralize "how does slug X render?" so the ActionCard and reducer can both call it and tests can cover all 9 slugs without UI mocking.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/assistant/__tests__/actionSummary.test.js`:

```javascript
// Pure-Node tests for actionSummary. Follows the pattern in
// useAssistantState.test.js — Node's built-in `assert`, run via
// `node frontend/src/assistant/__tests__/actionSummary.test.js`.
import assert from "node:assert/strict";
import { formatActionSummary } from "../actionSummary.js";

// create_task — uses args.title
{
  const s = formatActionSummary("create_task",
    { title: "Check the duct conflict", project_id: "abc-..." },
    null);
  assert.equal(s.primary, "Create task");
  assert.equal(s.secondary, "Check the duct conflict");
}

// create_task — from result_payload (auto-committed path)
{
  const s = formatActionSummary("create_task",
    {},
    { task_id: "x", task_number: 14, title: "Inspect grid B/4" });
  assert.equal(s.primary, "Create task");
  assert.ok(s.secondary.includes("Inspect grid B/4"));
}

// update_task_status — shows task_id + new status
{
  const s = formatActionSummary("update_task_status",
    { task_id: "11111111-2222-3333-4444-555555555555", status: "complete" },
    null);
  assert.equal(s.primary, "Update task status");
  assert.ok(/complete/.test(s.secondary));
}

// create_note
{
  const s = formatActionSummary("create_note",
    { content: "Remember to chase the insulation sub on Thursday" },
    null);
  assert.equal(s.primary, "Create note");
  assert.ok(s.secondary.startsWith("Remember to chase"));
}

// answer_rfi
{
  const s = formatActionSummary("answer_rfi",
    { rfi_id: "rfi-abc", answer: "Confirmed — use revised detail A-501" },
    null);
  assert.equal(s.primary, "Answer RFI");
  assert.ok(s.secondary.includes("Confirmed"));
}

// save_meeting_packet
{
  const s = formatActionSummary("save_meeting_packet",
    { meeting_id: "m-1", packet_url: "https://ex.com/packet.pdf" },
    null);
  assert.equal(s.primary, "Save meeting packet");
  assert.ok(s.secondary.includes("packet.pdf"));
}

// save_draft
{
  const s = formatActionSummary("save_draft",
    { subject: "Duct conflict follow-up", body: "..." },
    null);
  assert.equal(s.primary, "Save draft email");
  assert.ok(s.secondary.includes("Duct conflict follow-up"));
}

// create_alert
{
  const s = formatActionSummary("create_alert",
    { severity: "warning", title: "Daily log missing for Bishop Modern" },
    null);
  assert.equal(s.primary, "Create alert");
  assert.ok(s.secondary.includes("Daily log missing"));
}

// delete_task — uses snapshot from result_payload
{
  const s = formatActionSummary("delete_task",
    { task_id: "t-1" },
    { snapshot: { title: "Old obsolete task", task_number: 9 } });
  assert.equal(s.primary, "Delete task");
  assert.ok(s.secondary.includes("Old obsolete task"));
}

// delete_note — snapshot
{
  const s = formatActionSummary("delete_note",
    { note_id: "n-1" },
    { snapshot: { content: "Scratch note to discard" } });
  assert.equal(s.primary, "Delete note");
  assert.ok(s.secondary.includes("Scratch note"));
}

// Unknown slug — degrades gracefully
{
  const s = formatActionSummary("mystery_tool", { foo: "bar" }, null);
  assert.equal(s.primary, "mystery_tool");
  assert.ok(typeof s.secondary === "string");
}

console.log("actionSummary: all tests passed");
```

- [ ] **Step 2: Run test to verify failure**

```
cd frontend && node src/assistant/__tests__/actionSummary.test.js
```
Expected: FAIL — `actionSummary.js` doesn't exist yet.

- [ ] **Step 3: Implement `actionSummary.js`**

Create `frontend/src/assistant/actionSummary.js`:

```javascript
// frontend/src/assistant/actionSummary.js
// Pure utility: translate an action's (slug, tool_args, result) into
// (primary, secondary) strings for the ActionCard. All logic is
// tool-specific; adding a new tool requires one case here.

function truncate(s, n = 120) {
  if (!s) return "";
  const str = String(s);
  return str.length > n ? str.slice(0, n - 1) + "…" : str;
}

const HANDLERS = {
  create_task: (args, result) => ({
    primary: "Create task",
    secondary: truncate(
      args?.title ?? result?.title ?? "(no title)",
    ),
  }),
  update_task_status: (args, result) => ({
    primary: "Update task status",
    secondary: result?.previous_status
      ? `${result.previous_status} → ${args?.status ?? result?.new_status ?? "?"}`
      : `status → ${args?.status ?? "?"}`,
  }),
  create_note: (args, result) => ({
    primary: "Create note",
    secondary: truncate(args?.content ?? result?.content ?? ""),
  }),
  answer_rfi: (args) => ({
    primary: "Answer RFI",
    secondary: truncate(args?.answer ?? "(no answer)", 140),
  }),
  save_meeting_packet: (args) => ({
    primary: "Save meeting packet",
    secondary: truncate(args?.packet_url ?? "(no url)"),
  }),
  save_draft: (args) => ({
    primary: "Save draft email",
    secondary: truncate(args?.subject ?? "(no subject)"),
  }),
  create_alert: (args) => ({
    primary: "Create alert",
    secondary: truncate(args?.title ?? "(no title)"),
  }),
  delete_task: (args, result) => ({
    primary: "Delete task",
    secondary: truncate(result?.snapshot?.title ?? `task ${args?.task_id ?? "?"}`),
  }),
  delete_note: (args, result) => ({
    primary: "Delete note",
    secondary: truncate(result?.snapshot?.content ?? `note ${args?.note_id ?? "?"}`),
  }),
};

export function formatActionSummary(slug, toolArgs, resultPayload) {
  const handler = HANDLERS[slug];
  if (!handler) {
    return { primary: slug, secondary: "" };
  }
  try {
    return handler(toolArgs || {}, resultPayload || null);
  } catch (_e) {
    return { primary: slug, secondary: "" };
  }
}
```

- [ ] **Step 4: Run test to verify pass**

```
cd frontend && node src/assistant/__tests__/actionSummary.test.js
```
Expected: `actionSummary: all tests passed`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/assistant/actionSummary.js frontend/src/assistant/__tests__/actionSummary.test.js
git commit -m "feat(phase6-fe): actionSummary util for per-tool card copy"
```

---

## Task 3: actionsApi.js (fetch wrapper)

**Files:**
- Create: `frontend/src/lib/actionsApi.js`

**Why:** Central place for the 3 HTTP calls the card makes, matching the existing `frontend/src/lib/` pattern. Reuses the auth-header injection helper used by other API calls.

- [ ] **Step 1: Discovery**

Read `frontend/src/lib/` — find the existing auth-header helper (probably in `sse.js` or a sibling file). Confirm the Authorization header pattern (usually `Authorization: Bearer <token>` from localStorage or cookie). Also find one existing API helper (e.g. `frontend/src/lib/assistantApi.js` or similar) to mirror its shape.

- [ ] **Step 2: Implement**

Create `frontend/src/lib/actionsApi.js`:

```javascript
// frontend/src/lib/actionsApi.js
// Thin fetch wrappers for the Phase 6 action queue endpoints.
//
// Retry (after a failure) = call approveAction again — same semantics
// as initial approval (re-runs the handler).

import { apiFetch } from "./apiFetch.js"; // Adjust import to match the real helper name/path found in Step 1.

export async function approveAction(action_id) {
  const res = await apiFetch(`/api/actions/${action_id}/approve`, { method: "POST" });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`approve failed: ${res.status} ${body}`);
  }
  return res.json();
}

export async function discardAction(action_id) {
  const res = await apiFetch(`/api/actions/${action_id}/discard`, { method: "POST" });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`discard failed: ${res.status} ${body}`);
  }
  return res.json();
}

export async function undoAction(action_id) {
  const res = await apiFetch(`/api/actions/${action_id}/undo`, { method: "POST" });
  const body = await res.json().catch(() => ({}));
  // Return the body along with the status so the caller can distinguish
  // 400 (window expired) from 500 (compensator failed) without throwing.
  return { status: res.status, body };
}
```

**Note to implementer:** if the existing helper is not named `apiFetch`, adjust the import. If auth-header injection is done via a wrapper around `fetch`, use that. If auth is via same-origin cookies + there is no wrapper, call `fetch` directly but add `credentials: "same-origin"`. Match whatever the existing `/api/assistant/chat` call does in `postAssistantChat`.

- [ ] **Step 3: No standalone tests.**

This module is pure I/O and gets exercised by the Playwright e2e in Task 9.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/actionsApi.js
git commit -m "feat(phase6-fe): actionsApi wrapper for approve/discard/undo"
```

---

## Task 4: Reducer — 4 new action types + message-timeline integration

**Files:**
- Modify: `frontend/src/assistant/useAssistantState.js`
- Append to: `frontend/src/assistant/__tests__/useAssistantState.test.js` OR create `useAssistantState.actions.test.js` sibling

**Why:** The reducer is the source of truth for the message timeline. Action cards are entries with `type === 'action'`. The reducer handles inserting them and mutating their local UI state.

- [ ] **Step 1: Discovery**

Read `frontend/src/assistant/useAssistantState.js` end-to-end. Understand:
- The `initialAssistantState.activeConversation.messages` shape
- How `STREAM_STARTED` / `STREAM_DELTA` append/mutate messages
- The locally-generated-id pattern (`nextLocalId`)

- [ ] **Step 2: Write the failing test**

Create `frontend/src/assistant/__tests__/useAssistantState.actions.test.js`:

```javascript
// Pure-Node reducer tests for the Phase 6 action entries. Mirrors
// the pattern in useAssistantState.test.js.
import assert from "node:assert/strict";
import { reducer, initialAssistantState, ASSISTANT_ACTIONS } from "../useAssistantState.js";

function withConversation(messages = []) {
  return {
    ...initialAssistantState,
    activeConversation: {
      ...initialAssistantState.activeConversation,
      id: "conv-1",
      messages,
    },
  };
}

// ACTION_PROPOSED appends an approval entry.
{
  const s = reducer(withConversation(), {
    type: ASSISTANT_ACTIONS.ACTION_PROPOSED,
    payload: {
      action_id: "a-1",
      tool_slug: "answer_rfi",
      tool_args: { rfi_id: "rfi-42", answer: "Confirmed" },
      reasons: ["writes to external system (Procore)"],
      blast_radius: { fires_external_effect: true },
    },
  });
  const msgs = s.activeConversation.messages;
  assert.equal(msgs.length, 1);
  assert.equal(msgs[0].type, "action");
  assert.equal(msgs[0].action_id, "a-1");
  assert.equal(msgs[0].slug, "answer_rfi");
  assert.equal(msgs[0].state, "approval");
  assert.deepEqual(msgs[0].effects, ["writes to external system (Procore)"]);
}

// ACTION_AUTO_COMMITTED appends a committed entry with committed_at set.
{
  const before = Date.now();
  const s = reducer(withConversation(), {
    type: ASSISTANT_ACTIONS.ACTION_AUTO_COMMITTED,
    payload: {
      action_id: "a-2",
      tool_slug: "create_task",
      result: { task_id: "t-1", task_number: 14, title: "Inspect" },
    },
  });
  const m = s.activeConversation.messages[0];
  assert.equal(m.type, "action");
  assert.equal(m.state, "committed");
  assert.ok(m.committed_at);
  assert.ok(new Date(m.committed_at).getTime() >= before);
}

// ACTION_FAILED appends a failed entry.
{
  const s = reducer(withConversation(), {
    type: ASSISTANT_ACTIONS.ACTION_FAILED,
    payload: {
      action_id: "a-3",
      tool_slug: "answer_rfi",
      error: "Procore API returned 500: Internal Server Error",
    },
  });
  const m = s.activeConversation.messages[0];
  assert.equal(m.state, "failed");
  assert.ok(m.error_excerpt.includes("Procore"));
}

// ACTION_STATE_UPDATED mutates an existing entry in place.
{
  const initial = withConversation([
    { type: "action", action_id: "a-4", slug: "create_task", state: "committed",
      committed_at: new Date().toISOString() },
  ]);
  const s = reducer(initial, {
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id: "a-4", state: "undone", undone_at: new Date().toISOString() },
  });
  const m = s.activeConversation.messages[0];
  assert.equal(m.state, "undone");
  assert.ok(m.undone_at);
}

// ACTION_STATE_UPDATED on a missing action_id is a no-op (doesn't crash).
{
  const s = reducer(withConversation(), {
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id: "nope", state: "undone" },
  });
  assert.equal(s.activeConversation.messages.length, 0);
}

console.log("useAssistantState actions: all tests passed");
```

- [ ] **Step 3: Run test to verify failure**

```
cd frontend && node src/assistant/__tests__/useAssistantState.actions.test.js
```
Expected: FAIL — the ACTION_* constants don't exist.

- [ ] **Step 4: Extend the reducer**

In `frontend/src/assistant/useAssistantState.js`:

Add to the `ASSISTANT_ACTIONS` object (next to the SSE section):

```javascript
// Phase 6 action cards
ACTION_PROPOSED: "action/proposed",
ACTION_AUTO_COMMITTED: "action/autoCommitted",
ACTION_FAILED: "action/failed",
ACTION_STATE_UPDATED: "action/stateUpdated",
```

Add an import at the top:
```javascript
import { formatActionSummary } from "./actionSummary.js";
```

Then add the 4 reducer cases. Example sketch:

```javascript
case ASSISTANT_ACTIONS.ACTION_PROPOSED: {
  const { action_id, tool_slug, tool_args, reasons, blast_radius } = action.payload;
  const { primary, secondary } = formatActionSummary(tool_slug, tool_args || {}, null);
  const entry = {
    type: "action",
    action_id,
    slug: tool_slug,
    state: "approval",
    primary, secondary,
    effects: Array.isArray(reasons) ? reasons : [],
    tool_args: tool_args || {},
    blast_radius: blast_radius || {},
    committed_at: null,
    undone_at: null,
    error_excerpt: null,
    busy: false,
  };
  return {
    ...state,
    activeConversation: {
      ...state.activeConversation,
      messages: [...state.activeConversation.messages, entry],
    },
  };
}

case ASSISTANT_ACTIONS.ACTION_AUTO_COMMITTED: {
  const { action_id, tool_slug, result } = action.payload;
  const { primary, secondary } = formatActionSummary(tool_slug, {}, result || null);
  const entry = {
    type: "action",
    action_id,
    slug: tool_slug,
    state: "committed",
    primary, secondary,
    effects: [],
    tool_args: {},
    blast_radius: {},
    committed_at: new Date().toISOString(),
    undone_at: null,
    error_excerpt: null,
    result_payload: result || null,
    busy: false,
  };
  return {
    ...state,
    activeConversation: {
      ...state.activeConversation,
      messages: [...state.activeConversation.messages, entry],
    },
  };
}

case ASSISTANT_ACTIONS.ACTION_FAILED: {
  const { action_id, tool_slug, error } = action.payload;
  const { primary, secondary } = formatActionSummary(tool_slug, {}, null);
  const entry = {
    type: "action",
    action_id,
    slug: tool_slug,
    state: "failed",
    primary, secondary,
    effects: [],
    tool_args: {},
    blast_radius: {},
    committed_at: null,
    undone_at: null,
    error_excerpt: error || "unknown error",
    busy: false,
  };
  return {
    ...state,
    activeConversation: {
      ...state.activeConversation,
      messages: [...state.activeConversation.messages, entry],
    },
  };
}

case ASSISTANT_ACTIONS.ACTION_STATE_UPDATED: {
  const { action_id, ...patch } = action.payload;
  const messages = state.activeConversation.messages.map((m) =>
    m.type === "action" && m.action_id === action_id ? { ...m, ...patch } : m,
  );
  return {
    ...state,
    activeConversation: { ...state.activeConversation, messages },
  };
}
```

- [ ] **Step 5: Run test to verify pass**

```
cd frontend && node src/assistant/__tests__/useAssistantState.actions.test.js
cd frontend && node src/assistant/__tests__/useAssistantState.test.js   # regression
```
Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/assistant/useAssistantState.js frontend/src/assistant/__tests__/useAssistantState.actions.test.js
git commit -m "feat(phase6-fe): reducer appends action entries to message timeline"
```

---

## Task 5: ActionCard.jsx + styles

**Files:**
- Create: `frontend/src/assistant/ActionCard.jsx`
- Create: `frontend/src/assistant/actionCardStyles.css`

- [ ] **Step 1: Implement the CSS**

Create `frontend/src/assistant/actionCardStyles.css`:

```css
/* Phase 6 action card — unified accent-bar design for all 4 states. */

.rex-action-card {
  background: #fff;
  border: 1px solid var(--rex-border, #e5e7eb);
  border-left-width: 4px;
  border-radius: 6px;
  padding: 10px 14px;
  margin: 6px 0;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
}

.rex-action-card__label {
  font-size: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 600;
  margin-bottom: 2px;
}

.rex-action-card__primary {
  color: #111;
  font-weight: 500;
}

.rex-action-card__secondary {
  color: #555;
  margin-top: 2px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.rex-action-card__meta {
  color: #4b5563;
  font-size: 11px;
  margin: 8px 0;
  padding-left: 10px;
  border-left: 2px solid #e5e7eb;
}

.rex-action-card__error {
  color: #b91c1c;
  font-size: 11px;
  margin: 8px 0;
  padding: 6px 8px;
  background: #fef2f2;
  border-radius: 4px;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.rex-action-card__actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  margin-top: 8px;
}

.rex-action-card__actions .rex-btn {
  padding: 5px 12px;
  font-size: 12px;
}

/* state modifiers */
.rex-action-card--approval { border-left-color: #f59e0b; }
.rex-action-card--approval .rex-action-card__label { color: #b45309; }

.rex-action-card--committed { border-left-color: #059669; }
.rex-action-card--committed .rex-action-card__label { color: #047857; }

.rex-action-card--history { border-left-color: #d1d5db; }
.rex-action-card--history .rex-action-card__label { color: #6b7280; }

.rex-action-card--failed { border-left-color: #dc2626; }
.rex-action-card--failed .rex-action-card__label { color: #b91c1c; }

.rex-action-card--undone { border-left-color: #d1d5db; }
.rex-action-card--undone .rex-action-card__label { color: #6b7280; }
.rex-action-card--undone .rex-action-card__primary,
.rex-action-card--undone .rex-action-card__secondary {
  text-decoration: line-through;
  color: #9ca3af;
}

/* mobile — reflow buttons full-width */
@media (max-width: 560px) {
  .rex-action-card { padding: 10px 12px; font-size: 12.5px; }
  .rex-action-card__meta { font-size: 10px; }
  .rex-action-card__actions .rex-btn { flex: 1; }
}
```

- [ ] **Step 2: Implement the component**

Create `frontend/src/assistant/ActionCard.jsx`:

```jsx
// frontend/src/assistant/ActionCard.jsx
// Unified Phase 6 action card. Renders all 4 states (approval,
// committed, failed, undone). Counts down 60s on committed state
// client-side and removes the Undo button when time runs out.

import { useEffect, useMemo, useState } from "react";
import "./actionCardStyles.css";

const UNDO_WINDOW_SECONDS = 60;

function formatTimestamp(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function secondsRemaining(committedAt) {
  if (!committedAt) return 0;
  const start = new Date(committedAt).getTime();
  const elapsed = (Date.now() - start) / 1000;
  return Math.max(0, Math.floor(UNDO_WINDOW_SECONDS - elapsed));
}

export default function ActionCard({ action, onApprove, onDiscard, onUndo, onRetry, onDismiss }) {
  // Live countdown for committed-undoable state.
  const [countdown, setCountdown] = useState(() =>
    action.state === "committed" ? secondsRemaining(action.committed_at) : 0,
  );

  useEffect(() => {
    if (action.state !== "committed" || !action.committed_at) return undefined;
    const tick = () => setCountdown(secondsRemaining(action.committed_at));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [action.state, action.committed_at]);

  const undoable = action.state === "committed" && countdown > 0;
  const variant = useMemo(() => {
    if (action.state === "approval") return "approval";
    if (action.state === "failed") return "failed";
    if (action.state === "undone") return "undone";
    if (action.state === "committed") return undoable ? "committed" : "history";
    return "history";
  }, [action.state, undoable]);

  const label = (() => {
    if (variant === "approval") return "⚠ Approval";
    if (variant === "committed") return `✓ Committed · ${countdown}s`;
    if (variant === "history") return `✓ Committed · ${formatTimestamp(action.committed_at)}`;
    if (variant === "failed") return "✗ Failed";
    if (variant === "undone") return "↩ Undone";
    return "";
  })();

  const busy = !!action.busy;

  return (
    <div className={`rex-action-card rex-action-card--${variant}`}>
      <div className="rex-action-card__label">{label}</div>
      <div className="rex-action-card__primary">{action.primary}</div>
      {action.secondary ? (
        <div className="rex-action-card__secondary">{action.secondary}</div>
      ) : null}

      {variant === "approval" && (action.effects || []).length > 0 ? (
        <div className="rex-action-card__meta">
          {action.effects.map((r, i) => (
            <span key={i}>{i > 0 ? " · " : "ⓘ "}{r}</span>
          ))}
        </div>
      ) : null}

      {variant === "failed" ? (
        <div className="rex-action-card__error">{action.error_excerpt}</div>
      ) : null}

      <div className="rex-action-card__actions">
        {variant === "approval" ? (
          <>
            <button className="rex-btn rex-btn-outline" disabled={busy} onClick={() => onDiscard?.(action)}>
              Discard
            </button>
            <button className="rex-btn rex-btn-primary" disabled={busy} onClick={() => onApprove?.(action)}>
              {busy ? "Approving…" : "Approve"}
            </button>
          </>
        ) : null}
        {variant === "committed" ? (
          <button className="rex-btn rex-btn-outline" disabled={busy} onClick={() => onUndo?.(action)}>
            {busy ? "Undoing…" : "Undo"}
          </button>
        ) : null}
        {variant === "failed" ? (
          <>
            <button className="rex-btn rex-btn-outline" disabled={busy} onClick={() => onDismiss?.(action)}>
              Dismiss
            </button>
            <button className="rex-btn rex-btn-primary" disabled={busy} onClick={() => onRetry?.(action)}>
              {busy ? "Retrying…" : "Retry"}
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify lint passes**

```
cd frontend && npm run lint
```
Expected: no new warnings on ActionCard.jsx.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/assistant/ActionCard.jsx frontend/src/assistant/actionCardStyles.css
git commit -m "feat(phase6-fe): ActionCard — unified accent-bar card + countdown"
```

---

## Task 6: SSE routing — extend useAssistantClient

**Files:**
- Modify: `frontend/src/assistant/useAssistantClient.js`

- [ ] **Step 1: Add 3 new cases to the SSE switch**

Add these cases inside the switch at lines 148-201 (just before `default:`):

```javascript
case "action_proposed":
  ctx.assistantDispatch({
    type: ASSISTANT_ACTIONS.ACTION_PROPOSED,
    payload: data,
  });
  break;
case "action_auto_committed":
  ctx.assistantDispatch({
    type: ASSISTANT_ACTIONS.ACTION_AUTO_COMMITTED,
    payload: data,
  });
  break;
case "action_failed":
  ctx.assistantDispatch({
    type: ASSISTANT_ACTIONS.ACTION_FAILED,
    payload: data,
  });
  break;
```

- [ ] **Step 2: No test required here.**

The reducer tests from Task 4 already verify the side effect. The SSE route is a 3-line pass-through.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/assistant/useAssistantClient.js
git commit -m "feat(phase6-fe): route action_* SSE events to reducer"
```

---

## Task 7: ChatThread renders ActionCard

**Files:**
- Modify: `frontend/src/assistant/ChatThread.jsx`

- [ ] **Step 1: Discovery**

Read `frontend/src/assistant/ChatThread.jsx` end-to-end. Find the message-list map — it's a loop over `activeConversation.messages` rendering per-type.

- [ ] **Step 2: Wire the action entry + handlers**

At the top of the component, add imports:

```jsx
import ActionCard from "./ActionCard.jsx";
import { ASSISTANT_ACTIONS } from "./useAssistantState.js";
import { approveAction, discardAction, undoAction } from "../lib/actionsApi.js";
```

Inside `ChatThread`, define handlers (or hoist to a custom hook if the component is already large — use judgment):

```jsx
const markBusy = (action_id, busy) =>
  ctx.assistantDispatch({
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id, busy },
  });

const handleApprove = async (action) => {
  markBusy(action.action_id, true);
  try {
    await approveAction(action.action_id);
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: {
        action_id: action.action_id,
        state: "committed",
        committed_at: new Date().toISOString(),
        busy: false,
      },
    });
  } catch (e) {
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: {
        action_id: action.action_id,
        state: "failed",
        error_excerpt: e.message || String(e),
        busy: false,
      },
    });
  }
};

const handleDiscard = async (action) => {
  markBusy(action.action_id, true);
  try {
    await discardAction(action.action_id);
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: { action_id: action.action_id, state: "undone", busy: false },
    });
  } catch (e) {
    markBusy(action.action_id, false);
    console.error("discard failed", e);
  }
};

const handleUndo = async (action) => {
  markBusy(action.action_id, true);
  const { status, body } = await undoAction(action.action_id);
  if (status === 200) {
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: {
        action_id: action.action_id,
        state: "undone",
        undone_at: new Date().toISOString(),
        busy: false,
      },
    });
  } else if (status === 400) {
    // window expired — just treat as history
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: { action_id: action.action_id, busy: false },
    });
  } else {
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: {
        action_id: action.action_id,
        state: "failed",
        error_excerpt: body?.detail || body?.error || `undo failed (${status})`,
        busy: false,
      },
    });
  }
};

const handleRetry = (action) => handleApprove(action);

const handleDismiss = (action) => {
  // Local hide — backend row stays for audit.
  ctx.assistantDispatch({
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id: action.action_id, state: "undone", busy: false },
  });
};
```

In the message list map, add a branch BEFORE the existing user/assistant branches:

```jsx
{msg.type === "action" ? (
  <ActionCard
    key={msg.action_id}
    action={msg}
    onApprove={handleApprove}
    onDiscard={handleDiscard}
    onUndo={handleUndo}
    onRetry={handleRetry}
    onDismiss={handleDismiss}
  />
) : /* existing user/assistant branches */}
```

- [ ] **Step 2: Verify lint + dev build**

```
cd frontend && npm run lint
cd frontend && npm run build
```
Expected: green on both.

- [ ] **Step 3: Visual smoke in dev server**

```
cd frontend && npm run dev
```

Open localhost URL, send a chat message that triggers `create_task` (e.g., "create a task to check the duct conflict"), observe:
- Green ActionCard appears in the thread
- Countdown ticks down from ~59s
- Clicking Undo within window flips card to grey strikethrough
- Clicking Undo after 60s (wait it out) button is gone, label shows timestamp

If auto-commit doesn't trigger in dev (maybe LLM routing not wired to hit `create_task`), verify end-to-end in Playwright (Task 9).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/assistant/ChatThread.jsx
git commit -m "feat(phase6-fe): ChatThread renders ActionCard + wires action handlers"
```

---

## Task 8: Playwright e2e smoke — create_task → undo

**Files:**
- Create: `frontend/tests/e2e/phase6-action-card.spec.js`

**Why:** The component/reducer unit tests cover logic; this verifies the full SSE → card → HTTP loop works against the real backend on a dev server.

- [ ] **Step 1: Discovery**

Read `frontend/playwright.config.js` (or `.ts`) to confirm test dir + baseURL. Look at any existing e2e under `frontend/tests/e2e/` for the auth-login pattern (how does the test log in?).

- [ ] **Step 2: Write the spec**

Create `frontend/tests/e2e/phase6-action-card.spec.js`:

```javascript
// Phase 6 action card end-to-end smoke.
// Requires: backend running on 8000 with a test admin seeded,
// frontend dev server on its configured port.

import { test, expect } from "@playwright/test";

test("create_task auto-commits inline and can be undone within 60s", async ({ page }) => {
  // 1. Log in (mirror whatever existing specs do for auth).
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("aroberts@exxircapital.com");
  await page.getByLabel(/password/i).fill("rex2026!");
  await page.getByRole("button", { name: /sign in|log in/i }).click();

  // 2. Open the assistant sidebar + go to thread tab.
  await page.goto("/");
  // (adjust selectors to match the actual UI once you inspect it)

  // 3. Send a message that should trigger create_task auto-pass.
  const composer = page.getByRole("textbox", { name: /ask|message/i });
  await composer.fill("create a task to check the duct conflict at grid B/4");
  await composer.press("Enter");

  // 4. Expect a committed action card to appear.
  const card = page.locator(".rex-action-card--committed").first();
  await expect(card).toBeVisible({ timeout: 15000 });
  await expect(card).toContainText(/Create task/i);
  await expect(card).toContainText(/Undo/i);

  // 5. Click Undo; expect card to flip to undone state.
  await card.getByRole("button", { name: /undo/i }).click();
  await expect(page.locator(".rex-action-card--undone").first()).toBeVisible();
});
```

**Implementer note:** Selectors will almost certainly need tweaking based on the real UI. Don't be a literalist — find the actual login form / composer textbox / etc. and adjust. The goal is the happy path works end-to-end.

- [ ] **Step 3: Run locally**

Start the backend + frontend dev servers, then:

```
cd frontend && npx playwright test phase6-action-card.spec.js --headed
```

Iterate on selectors until the test passes. If `create_task` isn't the path the LLM actually picks for that message (the model is stochastic), adjust the prompt or mock the backend's model_client.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/e2e/phase6-action-card.spec.js
git commit -m "test(phase6-fe): playwright smoke — create_task auto-commit + undo"
```

---

## Task 9: Full regression + PR + deploy + smoke

**Files:** none (operational)

- [ ] **Step 1: Backend regression**

```
cd backend && py -m pytest --tb=line -q
```
Expected: 957+ tests passing. Task 1's backend change added 1+ test.

- [ ] **Step 2: Frontend regression**

```
cd frontend && node src/assistant/__tests__/useAssistantState.test.js
cd frontend && node src/assistant/__tests__/useAssistantState.actions.test.js
cd frontend && node src/assistant/__tests__/actionSummary.test.js
cd frontend && npm run lint
cd frontend && npm run build
```
Expected: all green.

- [ ] **Step 3: Playwright smoke** (already verified in Task 8).

- [ ] **Step 4: Open PR**

```bash
git push -u origin feat/phase6-frontend-wave1
gh pr create --title "feat: Phase 6 Frontend Wave 1 — approval cards + undo + failure UI" --body "$(cat <<'EOF'
## Summary
- Unified accent-bar ActionCard renders all 4 Phase 6 states (approval / committed-undoable / failed / undone)
- 60s client-side undo countdown hits POST /api/actions/{id}/undo
- Approve hits /approve; Retry on failed re-runs the same /approve endpoint; Discard hits /discard
- Reducer gains 4 new action types for the message-timeline integration
- Backend: action_proposed SSE payload now includes tool_args so the card can render secondary line

## Test plan
- [x] Backend regression (957+ passing)
- [x] Frontend reducer unit tests (pure Node)
- [x] actionSummary unit tests (9 slugs covered)
- [x] Playwright e2e smoke: create_task auto-commit + undo
- [ ] Deploy: Railway prod + demo, Vercel prod
- [ ] Mobile smoke on Andrew's phone after deploy

## Out of scope (Wave 2)
- Pending Approvals filter view
- Diff view for edit actions
- "Send correction" flow
- Bottom-sheet mobile modal

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Monitor deploys (two passes)**

```
# Prod backend
railway link --workspace "exxir's Projects" --project "Rex OS" --environment production --service rex-os-api
railway logs --deployment | tail -20

# Demo backend
railway link --workspace "exxir's Projects" --project "Rex OS" --environment demo --service rex-os
railway logs --deployment | tail -20
```

Also monitor Vercel for the frontend deploy (check `gh pr view` for the Vercel bot's preview URL).

Run each log check twice, ~1 minute apart, confirming no errors.

- [ ] **Step 6: HTTP surface smoke**

```
curl -sS -o /dev/null -w "prod_ready: %{http_code}\n" https://rex-os-api-production.up.railway.app/api/ready
curl -sS -o /dev/null -w "demo_ready: %{http_code}\n" https://rex-os-demo.up.railway.app/api/ready
curl -sS -o /dev/null -w "vercel_prod_root: %{http_code}\n" https://rex-os.vercel.app/
```
Expected: 200 / 200 / 200.

- [ ] **Step 7: Update handoff doc**

Create `docs/SESSION_HANDOFF_2026_04_24.md` noting: Phase 6 Frontend Wave 1 shipped, tools now fully usable by a human in a browser, next is either Phase 6b Wave 2 (financial/punch/create_decision) or Phase 4 resource rollout Wave 2.

- [ ] **Step 8: Mark umbrella execution task complete.**

---

## Spec coverage self-review

| Spec section | Task(s) |
|---|---|
| §1 Scope (4 SSE event types) | Tasks 4 (reducer), 6 (SSE routing) |
| §2 Component tree (ActionCard, actionsApi, reducer extensions) | Tasks 3, 4, 5, 7 |
| §3 Card visual spec (5 states, same shape) | Tasks 5 (component + CSS) |
| §4 Undo flow (countdown, 200/400/500 handling) | Task 5 (countdown), Task 7 (handler) |
| §5 Retry flow (re-POST /approve) | Task 7 (handleRetry = handleApprove) |
| §6 State management (reducer shape) | Task 4 |
| §7 Out of scope | Respected |
| Backend SSE payload gap (tool_args) | Task 1 |

## Placeholder scan

One intentional soft-spot: Task 3 says "Adjust import to match the real helper name/path found in Step 1" for the auth-injection helper. That's a discovery step, not a placeholder — the implementer reads existing code to find the right name rather than guessing. If no helper exists, they use `fetch` directly with `credentials: "same-origin"`.

Task 8 Playwright selectors are intentionally imprecise because the implementer needs to look at the actual rendered UI to pick stable selectors.

Everything else is concrete: file paths, exact code, exact expected outcomes.

## Type consistency

- `action_id` is a string (stringified UUID) everywhere — backend emits `str(result.action_id)`, frontend stores as-is.
- `state` values: `"approval" | "committed" | "failed" | "undone"` in reducer; `variant` (CSS modifier) has one extra: `"history"` for post-60s committed rows. `variant` derives from `state` + countdown, never stored.
- `busy` is local UI state only; never persisted, never serialized.
- Payload shape matches between `useAssistantClient.js` (where SSE data is routed) and `useAssistantState.js` (where the reducer consumes it) — both use the backend-emitted field names verbatim.

## Follow-ups (not in scope)

- **Pending Approvals filter view** (per §5 brainstorm). Build if Andrew hits pain after a week.
- **Diff component** for edit actions (Phase 6b Wave 2's punch close / status transitions might benefit; revisit at that time).
- **"Send correction" flow** (Phase 6c).
- **Keyboard shortcuts** (`⌘+enter` to approve).
- **Bulk approve / reject** (Phase 7 if batch actions ever ship).

// Pure-Node unit tests for the assistant reducer.
//
// Run with: node src/assistant/__tests__/useAssistantState.test.js
//
// No test framework dependency — just Node's built-in `assert`. The
// reducer is pure and imports only loadUiPrefs() from uiPrefs.js,
// which no-ops when `window` is undefined (Node environment). That
// means this test file is a bare-script Node import away from
// exercising every reducer path.
//
// Covered:
//   - initial state shape
//   - catalog load lifecycle
//   - conversations load lifecycle
//   - active conversation load
//   - optimistic user message append + remove
//   - SSE STREAM_STARTED + STREAM_DELTA + STREAM_COMPLETED chain
//   - STREAM_DELTA arriving before STREAM_STARTED (placeholder inline)
//   - STREAM_ACTION_SUGGESTIONS defensive shape handling
//   - STREAM_ABORT leaves partial content + tags aborted
//   - STREAM_ERROR tags message + sets error banner
//   - UI tab rotation ("next" / "prev")
//   - UI workspace mode toggle auto-uncollapses
//   - ACTIVE_CONVERSATION_CLEAR resets activeActionSlug

import assert from "node:assert";
import {
  assistantReducer,
  initialAssistantState,
  ASSISTANT_ACTIONS,
  ASSISTANT_TABS,
  __resetIdCounterForTests,
} from "../useAssistantState.js";

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    __resetIdCounterForTests();
    fn();
    console.log(`  ok  ${name}`);
    passed += 1;
  } catch (err) {
    console.error(`  FAIL  ${name}`);
    console.error(`         ${err.message}`);
    if (err.actual !== undefined) {
      console.error(`         actual:   ${JSON.stringify(err.actual)}`);
      console.error(`         expected: ${JSON.stringify(err.expected)}`);
    }
    failed += 1;
  }
}

// ── Initial state ──────────────────────────────────────────────────

test("initial state has five top-level buckets", () => {
  const s = initialAssistantState;
  assert.ok(s.catalog);
  assert.ok(s.conversations);
  assert.ok(s.activeConversation);
  assert.ok(s.ui);
  assert.strictEqual(s.ui.activeTab, ASSISTANT_TABS.QUICK_ACTIONS);
  assert.strictEqual(s.ui.collapsed, false);
  assert.strictEqual(s.ui.workspaceMode, false);
  assert.strictEqual(s.ui.pending, false);
});

// ── Catalog lifecycle ──────────────────────────────────────────────

test("CATALOG_LOADING → CATALOG_LOADED", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.CATALOG_LOADING });
  assert.strictEqual(s.catalog.loading, true);
  assert.strictEqual(s.catalog.error, null);
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.CATALOG_LOADED,
    payload: { version: "v1", categories: [], actions: [{ slug: "x" }] },
  });
  assert.strictEqual(s.catalog.loading, false);
  assert.strictEqual(s.catalog.data.actions.length, 1);
  assert.strictEqual(s.catalog.data.actions[0].slug, "x");
});

test("CATALOG_ERROR sets error and clears loading", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.CATALOG_LOADING });
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.CATALOG_ERROR, payload: "boom" });
  assert.strictEqual(s.catalog.loading, false);
  assert.strictEqual(s.catalog.error, "boom");
});

// ── Conversations ──────────────────────────────────────────────────

test("CONVERSATIONS_LOADED populates items", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.CONVERSATIONS_LOADED,
    payload: [{ id: "c1", title: "Test" }],
  });
  assert.strictEqual(s.conversations.items.length, 1);
  assert.strictEqual(s.conversations.items[0].id, "c1");
});

// ── Active conversation ────────────────────────────────────────────

test("ACTIVE_CONVERSATION_LOADED sets conversation + messages", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_LOADED,
    payload: {
      conversation: { id: "c1", title: "T" },
      messages: [
        { id: "m1", sender_type: "user", content: "hi" },
        {
          id: "m2",
          sender_type: "assistant",
          content: "hello",
          structured_payload: { followups: ["more"] },
        },
      ],
    },
  });
  assert.strictEqual(s.activeConversation.id, "c1");
  assert.strictEqual(s.activeConversation.messages.length, 2);
  assert.deepStrictEqual(s.activeConversation.followups, ["more"]);
});

test("ACTIVE_CONVERSATION_CLEAR resets activeActionSlug", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_SET_ACTIVE_ACTION, payload: "budget_variance" });
  assert.strictEqual(s.ui.activeActionSlug, "budget_variance");
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_CLEAR });
  assert.strictEqual(s.ui.activeActionSlug, null);
  assert.strictEqual(s.activeConversation.messages.length, 0);
});

// ── Optimistic user message append + remove ────────────────────────

test("APPEND_LOCAL_USER_MESSAGE adds a user bubble with caller localId", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.APPEND_LOCAL_USER_MESSAGE,
    payload: { content: "hello", localId: "local-abc" },
  });
  assert.strictEqual(s.activeConversation.messages.length, 1);
  assert.strictEqual(s.activeConversation.messages[0].id, "local-abc");
  assert.strictEqual(s.activeConversation.messages[0].sender_type, "user");
  assert.strictEqual(s.activeConversation.messages[0].local, true);
});

test("REMOVE_LOCAL_USER_MESSAGE deletes by localId", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.APPEND_LOCAL_USER_MESSAGE,
    payload: { content: "a", localId: "A" },
  });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.APPEND_LOCAL_USER_MESSAGE,
    payload: { content: "b", localId: "B" },
  });
  assert.strictEqual(s.activeConversation.messages.length, 2);
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.REMOVE_LOCAL_USER_MESSAGE,
    payload: { localId: "A" },
  });
  assert.strictEqual(s.activeConversation.messages.length, 1);
  assert.strictEqual(s.activeConversation.messages[0].id, "B");
});

// ── SSE stream delta merging ───────────────────────────────────────

test("STREAM_STARTED appends a placeholder assistant bubble", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: {} });
  assert.strictEqual(s.activeConversation.streaming, true);
  assert.strictEqual(s.activeConversation.messages.length, 1);
  assert.strictEqual(s.activeConversation.messages[0].sender_type, "assistant");
  assert.strictEqual(s.activeConversation.messages[0].streaming, true);
});

test("STREAM_STARTED is idempotent when a streaming bubble already exists", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: {} });
  const firstIdx = s.activeConversation.messages.length;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: {} });
  assert.strictEqual(s.activeConversation.messages.length, firstIdx);
});

test("STREAM_DELTA appends accumulated content to streaming bubble", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: {} });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_DELTA,
    payload: { delta: "Hello", accumulated: "Hello" },
  });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_DELTA,
    payload: { delta: " world", accumulated: "Hello world" },
  });
  const last = s.activeConversation.messages[s.activeConversation.messages.length - 1];
  assert.strictEqual(last.content, "Hello world");
  assert.strictEqual(last.streaming, true);
});

test("STREAM_DELTA before STREAM_STARTED creates placeholder inline", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_DELTA,
    payload: { delta: "foo", accumulated: "foo" },
  });
  assert.strictEqual(s.activeConversation.messages.length, 1);
  assert.strictEqual(s.activeConversation.messages[0].content, "foo");
  assert.strictEqual(s.activeConversation.messages[0].streaming, true);
});

test("STREAM_COMPLETED finalizes content and clears streaming flag", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: {} });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_DELTA,
    payload: { accumulated: "partial" },
  });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_COMPLETED,
    payload: { content: "final full answer" },
  });
  assert.strictEqual(s.activeConversation.streaming, false);
  const last = s.activeConversation.messages[s.activeConversation.messages.length - 1];
  assert.strictEqual(last.content, "final full answer");
  assert.strictEqual(last.streaming, false);
});

test("STREAM_FOLLOWUPS sets followups", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_FOLLOWUPS,
    payload: { followups: ["a", "b", "c"] },
  });
  assert.deepStrictEqual(s.activeConversation.followups, ["a", "b", "c"]);
});

test("STREAM_ACTION_SUGGESTIONS accepts { suggestions: [...] }", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_ACTION_SUGGESTIONS,
    payload: { suggestions: [{ slug: "x", reason: "y" }] },
  });
  assert.strictEqual(s.activeConversation.actionSuggestions.length, 1);
  assert.strictEqual(s.activeConversation.actionSuggestions[0].slug, "x");
});

test("STREAM_ACTION_SUGGESTIONS accepts bare array", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_ACTION_SUGGESTIONS,
    payload: ["rfi_aging", "submittal_sla"],
  });
  assert.deepStrictEqual(s.activeConversation.actionSuggestions, ["rfi_aging", "submittal_sla"]);
});

test("STREAM_ACTION_SUGGESTIONS ignores unknown shapes", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_ACTION_SUGGESTIONS,
    payload: { unexpected: "garbage" },
  });
  assert.deepStrictEqual(s.activeConversation.actionSuggestions, []);
});

test("STREAM_ERROR tags streaming bubble as errored + sets banner", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: {} });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_DELTA,
    payload: { accumulated: "partial" },
  });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_ERROR,
    payload: "network dead",
  });
  const last = s.activeConversation.messages[s.activeConversation.messages.length - 1];
  assert.strictEqual(last.error, true);
  assert.strictEqual(last.streaming, false);
  assert.strictEqual(last.content, "partial"); // partial preserved
  assert.strictEqual(s.activeConversation.error, "network dead");
});

test("STREAM_ABORT tags streaming bubble aborted without error", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: {} });
  s = assistantReducer(s, {
    type: ASSISTANT_ACTIONS.STREAM_DELTA,
    payload: { accumulated: "partial" },
  });
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.STREAM_ABORT });
  const last = s.activeConversation.messages[s.activeConversation.messages.length - 1];
  assert.strictEqual(last.aborted, true);
  assert.strictEqual(last.streaming, false);
  assert.strictEqual(last.content, "partial");
});

// ── UI state ───────────────────────────────────────────────────────

test("UI_TOGGLE_COLLAPSED flips", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_TOGGLE_COLLAPSED });
  assert.strictEqual(s.ui.collapsed, true);
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_TOGGLE_COLLAPSED });
  assert.strictEqual(s.ui.collapsed, false);
});

test("UI_SET_TAB 'next' rotates forward with wrap-around", () => {
  let s = initialAssistantState; // starts at QUICK_ACTIONS
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: "next" });
  assert.strictEqual(s.ui.activeTab, ASSISTANT_TABS.THREAD);
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: "next" });
  assert.strictEqual(s.ui.activeTab, ASSISTANT_TABS.CONVERSATIONS);
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: "next" });
  assert.strictEqual(s.ui.activeTab, ASSISTANT_TABS.COMMAND);
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: "next" });
  assert.strictEqual(s.ui.activeTab, ASSISTANT_TABS.QUICK_ACTIONS);
});

test("UI_SET_TAB 'prev' rotates backward with wrap-around", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: "prev" });
  assert.strictEqual(s.ui.activeTab, ASSISTANT_TABS.COMMAND);
});

test("UI_TOGGLE_WORKSPACE_MODE entering auto-uncollapses", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_SET_COLLAPSED, payload: true });
  assert.strictEqual(s.ui.collapsed, true);
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.UI_TOGGLE_WORKSPACE_MODE });
  assert.strictEqual(s.ui.workspaceMode, true);
  assert.strictEqual(s.ui.collapsed, false);
});

test("SEND_PENDING / SEND_SETTLED toggle pending flag", () => {
  let s = initialAssistantState;
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.SEND_PENDING });
  assert.strictEqual(s.ui.pending, true);
  s = assistantReducer(s, { type: ASSISTANT_ACTIONS.SEND_SETTLED });
  assert.strictEqual(s.ui.pending, false);
});

// ── Results ────────────────────────────────────────────────────────

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);

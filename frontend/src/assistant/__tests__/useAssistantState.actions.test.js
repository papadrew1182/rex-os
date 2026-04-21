// Pure-Node reducer tests for the Phase 6 action entries. Mirrors
// the pattern in useAssistantState.test.js.
import assert from "node:assert/strict";
import {
  assistantReducer as reducer,
  initialAssistantState,
  ASSISTANT_ACTIONS,
} from "../useAssistantState.js";

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

// ACTION_PROPOSED appends an approval entry with effects + tool_args
{
  const s = reducer(withConversation(), {
    type: ASSISTANT_ACTIONS.ACTION_PROPOSED,
    payload: {
      action_id: "a-1",
      tool_slug: "answer_rfi",
      tool_args: { rfi_id: "rfi-42", answer: "Confirmed — use revised detail A-501" },
      reasons: ["writes to external system (Procore)"],
      blast_radius: { fires_external_effect: true },
    },
  });
  const msgs = s.activeConversation.messages;
  assert.equal(msgs.length, 1);
  const m = msgs[0];
  assert.equal(m.type, "action");
  assert.equal(m.action_id, "a-1");
  assert.equal(m.slug, "answer_rfi");
  assert.equal(m.state, "approval");
  assert.equal(m.primary, "Answer RFI");
  assert.ok(m.secondary.includes("Confirmed"));
  assert.deepEqual(m.effects, ["writes to external system (Procore)"]);
  assert.equal(m.committed_at, null);
  assert.equal(m.busy, false);
}

// ACTION_AUTO_COMMITTED appends a committed entry with committed_at set
{
  const before = Date.now();
  const s = reducer(withConversation(), {
    type: ASSISTANT_ACTIONS.ACTION_AUTO_COMMITTED,
    payload: {
      action_id: "a-2",
      tool_slug: "create_task",
      result: { task_id: "t-1", task_number: 14, title: "Inspect grid B/4" },
    },
  });
  const m = s.activeConversation.messages[0];
  assert.equal(m.type, "action");
  assert.equal(m.state, "committed");
  assert.equal(m.slug, "create_task");
  assert.equal(m.primary, "Create task");
  assert.ok(m.secondary.includes("Inspect grid B/4"));
  assert.ok(m.committed_at);
  assert.ok(new Date(m.committed_at).getTime() >= before);
  assert.equal(m.error_excerpt, null);
}

// ACTION_FAILED appends a failed entry with error_excerpt
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
  assert.equal(m.slug, "answer_rfi");
  assert.ok(m.error_excerpt.includes("Procore"));
}

// ACTION_STATE_UPDATED patches an existing entry in place
{
  const initial = withConversation([
    { type: "action", action_id: "a-4", slug: "create_task", state: "committed",
      committed_at: new Date().toISOString(), busy: false },
  ]);
  const s = reducer(initial, {
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id: "a-4", state: "undone", undone_at: new Date().toISOString() },
  });
  const m = s.activeConversation.messages[0];
  assert.equal(m.state, "undone");
  assert.ok(m.undone_at);
}

// ACTION_STATE_UPDATED is no-op when action_id not found
{
  const s = reducer(withConversation(), {
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id: "nope", state: "undone" },
  });
  assert.equal(s.activeConversation.messages.length, 0);
}

// ACTION_STATE_UPDATED can mark an entry busy (for approve-in-flight UI)
{
  const initial = withConversation([
    { type: "action", action_id: "a-5", slug: "answer_rfi", state: "approval", busy: false },
  ]);
  const s = reducer(initial, {
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id: "a-5", busy: true },
  });
  const m = s.activeConversation.messages[0];
  assert.equal(m.busy, true);
  assert.equal(m.state, "approval");   // unchanged
}

// Non-action entries are not touched by ACTION_STATE_UPDATED
{
  const initial = withConversation([
    { type: "user", id: "u-1", content: "hi" },
    { type: "action", action_id: "a-6", slug: "create_task", state: "committed", busy: false },
  ]);
  const s = reducer(initial, {
    type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
    payload: { action_id: "a-6", state: "undone" },
  });
  assert.equal(s.activeConversation.messages[0].type, "user");
  assert.equal(s.activeConversation.messages[1].state, "undone");
}

console.log("useAssistantState actions: all tests passed");

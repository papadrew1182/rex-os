// Pure-Node unit tests for lib/contractProbes.js.
//
// Run: node src/lib/__tests__/contractProbes.test.js
//
// Each probe takes a raw response body and returns { ok, issues }.
// Probes never throw and never mutate. Tests cover:
//   - a valid shape matching the Session 3 charter
//   - the minimum-drift cases the adapter is likely to hit
//   - the canonical-role / readiness-vocabulary guardrails

import assert from "node:assert";
import {
  probeMeShape,
  probePermissionsShape,
  probeCurrentContextShape,
  probeCatalogShape,
  probeConversationsListShape,
  probeConversationDetailShape,
  probeChatAckShape,
  probeConnectorsShape,
  probeAutomationsShape,
  isKnownSseEvent,
} from "../contractProbes.js";

let passed = 0, failed = 0;
function test(name, fn) {
  try { fn(); console.log(`  ok  ${name}`); passed += 1; }
  catch (e) { console.error(`  FAIL  ${name}\n        ${e.message}`); failed += 1; }
}

// ── /api/me ────────────────────────────────────────────────────────

test("probeMeShape accepts wrapped { user } envelope", () => {
  const res = probeMeShape({
    user: {
      id: "u1", email: "a@b.c", full_name: "A B",
      primary_role_key: "VP", role_keys: ["VP"],
      legacy_role_aliases: ["VP_PM"], project_ids: [],
      feature_flags: { assistant_sidebar: true },
    },
  });
  assert.strictEqual(res.ok, true);
  assert.deepStrictEqual(res.issues, []);
});

test("probeMeShape accepts bare user (tolerates unwrapping)", () => {
  const res = probeMeShape({
    id: "u1", email: "a@b.c", full_name: "A B",
    primary_role_key: "PM", role_keys: ["PM"],
    project_ids: [], feature_flags: {},
  });
  assert.strictEqual(res.ok, true);
});

test("probeMeShape flags missing fields with human-readable issues", () => {
  const res = probeMeShape({ user: { id: "u1", email: "a@b.c" } });
  assert.strictEqual(res.ok, false);
  assert.ok(res.issues.some((i) => i.includes("full_name")));
  assert.ok(res.issues.some((i) => i.includes("primary_role_key")));
  assert.ok(res.issues.some((i) => i.includes("role_keys")));
});

test("probeMeShape rejects non-canonical role keys", () => {
  const res = probeMeShape({
    user: {
      id: "u1", email: "a@b.c", full_name: "X",
      primary_role_key: "SUPER_ADMIN", role_keys: ["SUPER_ADMIN", "VP"],
      project_ids: [], feature_flags: {},
    },
  });
  assert.strictEqual(res.ok, false);
  assert.ok(res.issues.some((i) => i.includes("SUPER_ADMIN") && i.includes("not canonical")));
});

test("probeMeShape flags role_keys type drift", () => {
  const res = probeMeShape({
    user: {
      id: "u1", email: "a@b.c", full_name: "X",
      primary_role_key: "VP", role_keys: "VP",
      project_ids: [], feature_flags: {},
    },
  });
  assert.strictEqual(res.ok, false);
  assert.ok(res.issues.some((i) => i.includes("role_keys should be an array")));
});

// ── /api/me/permissions ────────────────────────────────────────────

test("probePermissionsShape accepts valid array", () => {
  assert.strictEqual(probePermissionsShape({ permissions: ["assistant.chat"] }).ok, true);
});

test("probePermissionsShape flags missing array", () => {
  assert.strictEqual(probePermissionsShape({}).ok, false);
});

test("probePermissionsShape flags non-string entries", () => {
  const res = probePermissionsShape({ permissions: ["assistant.chat", 42] });
  assert.strictEqual(res.ok, false);
});

// ── /api/context/current ───────────────────────────────────────────

test("probeCurrentContextShape accepts canonical shape", () => {
  const res = probeCurrentContextShape({
    project: { id: "p1", name: "Tower 3" },
    route: { name: "project_dashboard", path: "/projects/tower-3" },
    page_context: { surface: "dashboard" },
    assistant_defaults: { suggested_action_slugs: ["budget_variance"] },
  });
  assert.strictEqual(res.ok, true);
});

test("probeCurrentContextShape flags missing route.name", () => {
  const res = probeCurrentContextShape({
    project: null,
    route: { path: "/" },
    page_context: {},
    assistant_defaults: { suggested_action_slugs: [] },
  });
  assert.strictEqual(res.ok, false);
  assert.ok(res.issues.some((i) => i.includes("route.name")));
});

// ── /api/assistant/catalog ─────────────────────────────────────────

test("probeCatalogShape accepts minimal valid catalog", () => {
  const res = probeCatalogShape({
    version: "v1",
    categories: [{ key: "FIN", label: "Financials" }],
    actions: [
      {
        slug: "budget_variance", label: "Budget Variance",
        category: "FIN", readiness_state: "live",
        role_visibility: ["VP", "PM"],
      },
    ],
  });
  assert.strictEqual(res.ok, true);
});

test("probeCatalogShape flags readiness vocabulary drift", () => {
  const res = probeCatalogShape({
    version: "v1",
    categories: [],
    actions: [{ slug: "x", label: "X", category: "FIN", readiness_state: "sort-of-live" }],
  });
  assert.strictEqual(res.ok, false);
  assert.ok(res.issues.some((i) => i.includes("sort-of-live") && i.includes("vocabulary")));
});

test("probeCatalogShape flags non-canonical role in role_visibility", () => {
  const res = probeCatalogShape({
    version: "v1",
    categories: [],
    actions: [{
      slug: "x", label: "X", category: "FIN", readiness_state: "live",
      role_visibility: ["VP", "SITE_ADMIN"],
    }],
  });
  assert.strictEqual(res.ok, false);
  assert.ok(res.issues.some((i) => i.includes("SITE_ADMIN")));
});

test("probeCatalogShape fails fast when actions is not an array", () => {
  const res = probeCatalogShape({ version: "v1", categories: [], actions: "nope" });
  assert.strictEqual(res.ok, false);
});

// ── /api/assistant/conversations ───────────────────────────────────

test("probeConversationsListShape accepts empty items", () => {
  assert.strictEqual(probeConversationsListShape({ items: [] }).ok, true);
});

test("probeConversationsListShape accepts items with null title", () => {
  assert.strictEqual(
    probeConversationsListShape({ items: [{ id: "c1", title: null }] }).ok,
    true,
  );
});

test("probeConversationsListShape flags missing items", () => {
  assert.strictEqual(probeConversationsListShape({}).ok, false);
});

// ── /api/assistant/conversations/{id} ──────────────────────────────

test("probeConversationDetailShape accepts canonical shape", () => {
  const res = probeConversationDetailShape({
    conversation: { id: "c1", title: "T" },
    messages: [
      { id: "m1", sender_type: "user", content: "hi" },
      { id: "m2", sender_type: "assistant", content: "hello" },
    ],
  });
  assert.strictEqual(res.ok, true);
});

test("probeConversationDetailShape flags unknown sender_type", () => {
  const res = probeConversationDetailShape({
    conversation: { id: "c1" },
    messages: [{ id: "m1", sender_type: "bot", content: "x" }],
  });
  assert.strictEqual(res.ok, false);
  assert.ok(res.issues.some((i) => i.includes("sender_type")));
});

// ── POST /api/assistant/chat ack ───────────────────────────────────

test("probeChatAckShape accepts accepted:true", () => {
  assert.strictEqual(probeChatAckShape({ accepted: true, conversation_id: "c1" }).ok, true);
});

test("probeChatAckShape rejects accepted:false", () => {
  assert.strictEqual(probeChatAckShape({ accepted: false }).ok, false);
});

// ── control plane ──────────────────────────────────────────────────

test("probeConnectorsShape accepts { items: [{key}] }", () => {
  assert.strictEqual(
    probeConnectorsShape({ items: [{ key: "procore", label: "Procore" }] }).ok,
    true,
  );
});

test("probeAutomationsShape flags unknown readiness value", () => {
  const res = probeAutomationsShape({
    items: [{ slug: "x", readiness_state: "kinda_on" }],
  });
  assert.strictEqual(res.ok, false);
});

// ── SSE event vocabulary guard ─────────────────────────────────────

test("isKnownSseEvent accepts all seven documented events", () => {
  const events = [
    "conversation.created", "message.started", "message.delta",
    "message.completed", "followups.generated", "action.suggestions", "error",
  ];
  for (const e of events) assert.strictEqual(isKnownSseEvent(e), true);
});

test("isKnownSseEvent rejects made-up events", () => {
  assert.strictEqual(isKnownSseEvent("message.finished"), false);
  assert.strictEqual(isKnownSseEvent("action.launched"), false);
});

// ── Results ────────────────────────────────────────────────────────

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);

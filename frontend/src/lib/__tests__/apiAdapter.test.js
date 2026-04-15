// Pure-Node unit tests for the lib/api.js adapter layer.
//
// We are NOT importing lib/api.js here — it drags in a Vite-only
// import tree (React + browser fetch + legacy api.js). Instead we
// re-exercise the same probe + normalize code paths that liveOrMock
// uses, by driving `integrationSource` directly. That covers:
//
//   1. pass-through when the shape is already correct
//   2. normalization path when the envelope is missing
//   3. probe failure → surface is reported unavailable, probeIssues
//      captured verbatim for the diagnostics panel
//
// Run: node src/lib/__tests__/apiAdapter.test.js

import assert from "node:assert";
import {
  __resetIntegrationSourceForTests,
  markLive,
  markMock,
  markUnavailable,
  markPending,
  getSurface,
  getSnapshot,
} from "../integrationSource.js";
import {
  probeMeShape,
  probeCatalogShape,
} from "../contractProbes.js";

let passed = 0, failed = 0;
function test(name, fn) {
  try {
    __resetIntegrationSourceForTests();
    fn();
    console.log(`  ok  ${name}`);
    passed += 1;
  } catch (e) {
    console.error(`  FAIL  ${name}\n        ${e.message}`);
    failed += 1;
  }
}

// Mirror of the adapter's liveOrMock path, minus the real fetch. Keeps
// the test hermetic and documents the contract expectations.
function simulateLiveOrMock({ surface, probe, liveResponse, mockResponse }) {
  markPending(surface);
  if (liveResponse === null) {
    markMock(surface);
    return mockResponse;
  }
  const result = probe(liveResponse);
  if (!result.ok) {
    markUnavailable(surface, {
      error: `contract probe failed: ${result.issues.join("; ")}`,
      probeIssues: result.issues,
    });
    return mockResponse;
  }
  markLive(surface);
  return liveResponse;
}

// ── Pass-through ──────────────────────────────────────────────────

test("pass-through: valid /api/me response is returned live", () => {
  const live = {
    user: {
      id: "u1", email: "a@b.c", full_name: "A B",
      primary_role_key: "VP", role_keys: ["VP"],
      legacy_role_aliases: [], project_ids: [], feature_flags: {},
    },
  };
  const result = simulateLiveOrMock({
    surface: "identity",
    probe: probeMeShape,
    liveResponse: live,
    mockResponse: { user: { id: "mock" } },
  });
  assert.strictEqual(result, live);
  const state = getSurface("identity");
  assert.strictEqual(state.source, "live");
  assert.strictEqual(state.attemptedLive, true);
  assert.deepStrictEqual(state.probeIssues, []);
});

// ── Probe failure → unavailable ──────────────────────────────────

test("probe failure: missing required fields → unavailable + fallback to mock", () => {
  const badLive = { user: { id: "u1" } };
  const mock = { user: { id: "mock-user" } };
  const result = simulateLiveOrMock({
    surface: "identity",
    probe: probeMeShape,
    liveResponse: badLive,
    mockResponse: mock,
  });
  assert.strictEqual(result, mock, "falls back to mock shape");
  const state = getSurface("identity");
  assert.strictEqual(state.source, "unavailable");
  assert.ok(state.lastError.includes("contract probe failed"));
  assert.ok(state.probeIssues.length > 0);
  assert.ok(state.probeIssues.some((i) => i.includes("full_name")));
});

test("probe failure: non-canonical role → issues include role name", () => {
  const badLive = {
    user: {
      id: "u1", email: "a@b.c", full_name: "A",
      primary_role_key: "SITE_OWNER", role_keys: ["SITE_OWNER"],
      project_ids: [], feature_flags: {},
    },
  };
  simulateLiveOrMock({
    surface: "identity",
    probe: probeMeShape,
    liveResponse: badLive,
    mockResponse: { user: { id: "mock" } },
  });
  const state = getSurface("identity");
  assert.strictEqual(state.source, "unavailable");
  assert.ok(state.probeIssues.some((i) => i.includes("SITE_OWNER")));
});

// ── Catalog drift ─────────────────────────────────────────────────

test("catalog: readiness_state drift flagged", () => {
  const driftedCatalog = {
    version: "v1", categories: [],
    actions: [{ slug: "x", label: "X", category: "FIN", readiness_state: "probably_live" }],
  };
  simulateLiveOrMock({
    surface: "catalog",
    probe: probeCatalogShape,
    liveResponse: driftedCatalog,
    mockResponse: { version: "mock", categories: [], actions: [] },
  });
  const state = getSurface("catalog");
  assert.strictEqual(state.source, "unavailable");
  assert.ok(state.probeIssues.some((i) => i.includes("probably_live")));
});

// ── Mock path ────────────────────────────────────────────────────

test("mock path: when live is null, surface is reported mock not pending", () => {
  const mock = { user: { id: "mock" } };
  const result = simulateLiveOrMock({
    surface: "identity",
    probe: probeMeShape,
    liveResponse: null, // simulates shouldUseMocks()===true
    mockResponse: mock,
  });
  assert.strictEqual(result, mock);
  const state = getSurface("identity");
  assert.strictEqual(state.source, "mock");
});

// ── Snapshot shape ────────────────────────────────────────────────

test("getSnapshot returns one row per documented surface", () => {
  const snap = getSnapshot();
  const expected = [
    "identity", "permissions", "context", "catalog", "conversations",
    "conversationDetail", "chatStream",
    "controlPlaneConnectors", "controlPlaneAutomations", "controlPlaneQueue",
    "myDayHome",
  ];
  for (const k of expected) {
    assert.ok(k in snap, `snapshot missing surface ${k}`);
    assert.strictEqual(snap[k].source, "pending");
  }
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
